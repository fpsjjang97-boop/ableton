"""
Auto-Ingest CLI — analyse new MIDI files and add them to the pattern DB.

Usage:
    python tools/auto_ingest.py path/to/song.mid
    python tools/auto_ingest.py path/to/midi_folder/
    python tools/auto_ingest.py --rebuild-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────
# Support both normal Python and PyInstaller frozen exe
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    _BUNDLE_DIR = Path(sys._MEIPASS)
    # Repo root: look for analyzed_chords/ relative to the exe location
    _EXE_DIR = Path(sys.executable).resolve().parent
    # Walk up to find repo root (contains analyzed_chords/ or app/)
    REPO_ROOT = _EXE_DIR
    for _candidate in [_EXE_DIR, _EXE_DIR.parent, _EXE_DIR.parent.parent]:
        if (_candidate / "analyzed_chords").is_dir() or (_candidate / "app").is_dir():
            REPO_ROOT = _candidate
            break
    APP_DIR = REPO_ROOT / "app"
    # Add bundled path for imports
    sys.path.insert(0, str(_BUNDLE_DIR))
    sys.path.insert(0, str(APP_DIR))
else:
    REPO_ROOT = Path(__file__).resolve().parent.parent
    APP_DIR = REPO_ROOT / "app"
    sys.path.insert(0, str(APP_DIR))

import mido
from core.models import Note, Track, CCEvent, ProjectState, TICKS_PER_BEAT
from core.harmony_engine import HarmonyEngine

ANALYZED_DIR = REPO_ROOT / "analyzed_chords"
PATTERN_DIR = REPO_ROOT / "pattern_library"
EMBED_DIR = REPO_ROOT / "embeddings" / "individual"
INGEST_LOG_PATH = PATTERN_DIR / "ingest_log.json"


# ── MIDI parsing (reused from tools/analyze_maestro.py) ─────────────────

def parse_midi_to_tracks(midi_path: str) -> tuple[list[Track], float, int]:
    """Parse a MIDI file into Track objects using mido.

    Reads notes, CC events (sustain pedal etc.), program changes,
    track names, and preserves empty tracks.

    Returns (tracks, bpm, ticks_per_beat).
    The returned tracks carry a `_meta` dict on the list object with extra info:
      tracks._meta = {"song_name": str, "time_sig": (num, den)}
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat or 480
    bpm = 120.0
    song_name = ""
    time_sig_num, time_sig_den = 4, 4

    track_notes: dict[int, list[Note]] = {}
    track_ccs: dict[int, list[CCEvent]] = {}
    track_names: dict[int, str] = {}
    track_instruments: dict[int, int] = {}
    track_channels: dict[int, int] = {}

    for i, midi_track in enumerate(mid.tracks):
        abs_tick = 0
        active: dict[tuple[int, int], Note] = {}

        for msg in midi_track:
            abs_tick += msg.time

            if msg.type == "set_tempo":
                bpm = round(mido.tempo2bpm(msg.tempo), 2)

            elif msg.type == "time_signature":
                time_sig_num = msg.numerator
                time_sig_den = msg.denominator

            elif msg.type == "track_name":
                track_names[i] = msg.name
                if i == 0 and not song_name:
                    song_name = msg.name

            elif msg.type == "program_change":
                track_instruments[i] = msg.program
                track_channels.setdefault(i, msg.channel)

            elif msg.type == "control_change":
                ch = msg.channel
                track_channels.setdefault(i, ch)
                track_ccs.setdefault(i, []).append(
                    CCEvent(tick=abs_tick, control=msg.control,
                            value=msg.value, channel=ch)
                )

            elif msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                track_channels.setdefault(i, ch)
                key = (ch, msg.note)
                if key in active:
                    prev = active.pop(key)
                    prev.duration_ticks = max(1, abs_tick - prev.start_tick)
                note = Note(
                    pitch=msg.note,
                    velocity=msg.velocity,
                    start_tick=abs_tick,
                    duration_ticks=0,
                    channel=ch,
                )
                active[key] = note
                track_notes.setdefault(i, []).append(note)

            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                ch = msg.channel
                key = (ch, msg.note)
                if key in active:
                    n = active.pop(key)
                    n.duration_ticks = max(1, abs_tick - n.start_tick)

        for _key, n in active.items():
            if n.duration_ticks == 0:
                n.duration_ticks = max(1, tpb)

    # Build tracks — preserve ALL tracks including empty ones (except pure-meta track 0)
    tracks = []
    all_indices = sorted(
        set(track_notes.keys()) | set(track_ccs.keys()) |
        {k for k in track_names if k > 0}
    )

    for idx in all_indices:
        notes = track_notes.get(idx, [])
        notes.sort(key=lambda n: n.start_tick)
        ccs = track_ccs.get(idx, [])
        ccs.sort(key=lambda cc: cc.tick)
        ch = track_channels.get(idx, notes[0].channel if notes else 0)
        name = track_names.get(idx, f"Track_{idx}_ch{ch}")
        inst = track_instruments.get(idx, 0)
        tracks.append(
            Track(name=name, channel=ch, notes=notes,
                  cc_events=ccs, instrument=inst)
        )

    # Attach metadata for lossless round-trip
    class _TrackList(list):
        _meta: dict = {}
    result = _TrackList(tracks)
    result._meta = {
        "song_name": song_name,
        "time_sig": (time_sig_num, time_sig_den),
    }
    return result, bpm, tpb


def apply_sustain_pedal(tracks: list[Track]) -> list[Track]:
    """Extend note durations to account for sustain pedal (CC64).

    When pedal is ON (CC64 >= 64), notes ending before pedal OFF
    should have their effective duration extended to the pedal OFF tick.
    Returns new Track list with adjusted note durations (originals untouched).
    """
    result = []
    for trk in tracks:
        pedal_events = [(cc.tick, cc.value) for cc in trk.cc_events if cc.control == 64]
        if not pedal_events or not trk.notes:
            result.append(trk)
            continue

        pedal_events.sort(key=lambda x: x[0])

        # Build pedal-on regions: [(on_tick, off_tick), ...]
        regions: list[tuple[int, int]] = []
        on_tick = None
        for tick, val in pedal_events:
            if val >= 64 and on_tick is None:
                on_tick = tick
            elif val < 64 and on_tick is not None:
                regions.append((on_tick, tick))
                on_tick = None
        # Unclosed pedal: extend to end of track
        if on_tick is not None:
            last_tick = max(n.end_tick for n in trk.notes) if trk.notes else on_tick
            regions.append((on_tick, last_tick))

        if not regions:
            result.append(trk)
            continue

        # Extend notes: if note ends inside a pedal region, stretch to region end
        new_notes = []
        for n in trk.notes:
            extended = False
            for ped_on, ped_off in regions:
                # Note started before or during pedal, ends during pedal
                if n.start_tick <= ped_off and n.end_tick > ped_on and n.end_tick < ped_off:
                    new_dur = ped_off - n.start_tick
                    new_notes.append(Note(
                        pitch=n.pitch, velocity=n.velocity,
                        start_tick=n.start_tick, duration_ticks=new_dur,
                        channel=n.channel, articulation=n.articulation,
                        role=n.role, transition=n.transition,
                    ))
                    extended = True
                    break
            if not extended:
                new_notes.append(n.copy())

        new_trk = trk.copy()
        new_trk.notes = new_notes
        result.append(new_trk)

    return result


def classify_tracks(
    tracks: list[Track],
) -> tuple[list[Track], list[Track]]:
    """Classify tracks into melody vs accompaniment for chord analysis.

    Returns (melody_tracks, accompaniment_tracks).

    Detection priority:
    1. Track name keywords (MELODY, PIANO, Vocals, Chords, Bass, etc.)
    2. Pitch-range heuristic (narrow+high = melody, wide+low = accompaniment)
    3. Single track → treat as accompaniment
    """
    note_tracks = [t for t in tracks if t.notes]
    if not note_tracks:
        return [], []
    if len(note_tracks) == 1:
        return [], note_tracks  # single track = accompaniment

    _MEL_KEYWORDS = {"melody", "vocal", "vocals", "voice", "lead", "sing"}
    _ACC_KEYWORDS = {"piano", "chord", "chords", "accomp", "bass", "harmony",
                     "block", "pad", "string", "guitar", "organ", "midi"}

    melody: list[Track] = []
    accompaniment: list[Track] = []
    unclassified: list[Track] = []

    for t in note_tracks:
        name_lower = t.name.lower().strip()
        if any(kw in name_lower for kw in _MEL_KEYWORDS):
            melody.append(t)
        elif any(kw in name_lower for kw in _ACC_KEYWORDS):
            accompaniment.append(t)
        else:
            unclassified.append(t)

    # If nothing classified by name, use heuristic
    if not melody and not accompaniment and len(unclassified) >= 2:
        # Sort by note count ascending (melody usually has fewer notes)
        unclassified.sort(key=lambda t: len(t.notes))
        for t in unclassified:
            pitches = [n.pitch for n in t.notes]
            min_p, max_p = min(pitches), max(pitches)
            has_cc = len(t.cc_events) > 0
            pitch_range = max_p - min_p
            # Melody: fewer notes, narrow range, higher register, no CC
            # Accompaniment: more notes, wide range, low bass, has CC
            if pitch_range <= 18 and min_p >= 52 and not has_cc and len(t.notes) < 80:
                melody.append(t)
            else:
                accompaniment.append(t)
    elif unclassified:
        # Some already classified by name — still check unclassified by heuristic
        for t in unclassified:
            pitches = [n.pitch for n in t.notes]
            min_p, max_p = min(pitches), max(pitches)
            has_cc = len(t.cc_events) > 0
            pitch_range = max_p - min_p
            if pitch_range <= 18 and min_p >= 52 and not has_cc and len(t.notes) < 80:
                melody.append(t)
            else:
                accompaniment.append(t)

    # Fallback: if still no accompaniment, treat all as accompaniment
    if not accompaniment:
        accompaniment = melody + accompaniment
        melody = []

    return melody, accompaniment


def save_tracks_to_midi(
    path: str,
    tracks: list[Track],
    bpm: float = 120.0,
    tpb: int = 480,
) -> None:
    """Write Track objects back to a Standard MIDI File (lossless round-trip).

    Preserves notes, CC events, program changes, track names, and meta info.
    """
    meta = getattr(tracks, "_meta", {})
    song_name = meta.get("song_name", "")
    tsig = meta.get("time_sig", (4, 4))

    mid = mido.MidiFile(ticks_per_beat=tpb)

    # Meta track
    meta_track = mido.MidiTrack()
    mid.tracks.append(meta_track)
    if song_name:
        meta_track.append(mido.MetaMessage("track_name", name=song_name, time=0))
    meta_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    meta_track.append(mido.MetaMessage(
        "time_signature", numerator=tsig[0], denominator=tsig[1], time=0))
    meta_track.append(mido.MetaMessage("end_of_track", time=0))

    # Data tracks
    for trk in tracks:
        mt = mido.MidiTrack()
        mid.tracks.append(mt)
        mt.append(mido.MetaMessage("track_name", name=trk.name, time=0))
        if trk.instrument > 0:
            mt.append(mido.Message(
                "program_change", program=trk.instrument,
                channel=trk.channel, time=0))

        events: list[tuple[int, mido.Message]] = []
        for n in trk.notes:
            events.append((n.start_tick, mido.Message(
                "note_on", note=n.pitch, velocity=n.velocity, channel=n.channel)))
            events.append((n.end_tick, mido.Message(
                "note_off", note=n.pitch, velocity=0, channel=n.channel)))
        for cc in trk.cc_events:
            events.append((cc.tick, mido.Message(
                "control_change", control=cc.control,
                value=cc.value, channel=cc.channel)))

        events.sort(key=lambda e: e[0])
        last_tick = 0
        for abs_tick, msg in events:
            msg.time = max(0, abs_tick - last_tick)
            mt.append(msg)
            last_tick = abs_tick
        mt.append(mido.MetaMessage("end_of_track", time=0))

    mid.save(path)


# ── Difficulty heuristic ─────────────────────────────────────────────────

def _estimate_difficulty(total_notes: int, playability_score: int) -> str:
    """Rough difficulty estimate from note count and playability score."""
    if total_notes > 3000 or playability_score < 40:
        return "virtuoso"
    if total_notes > 1500 or playability_score < 60:
        return "advanced"
    if total_notes > 500:
        return "intermediate"
    return "beginner"


def _estimate_genre(harmony: dict, bpm: float) -> str:
    """Very rough genre guess from harmony data and tempo."""
    segments = harmony.get("segments", [])
    qualities = [s.get("quality", "") for s in segments]
    has_7ths = any(q in ("7", "m7", "maj7", "m7b5", "dim7") for q in qualities)
    chord_count = harmony.get("chord_count", 0)

    if has_7ths and chord_count > 30:
        return "jazz"
    if bpm and bpm >= 140:
        return "energetic"
    if chord_count < 10:
        return "ambient"
    return "classical"


# ── Single-file ingestion ────────────────────────────────────────────────

def ingest_file(
    engine: HarmonyEngine,
    midi_path: Path,
) -> dict:
    """Analyse a single MIDI file, save results, return log entry."""
    entry: dict = {
        "filename": midi_path.name,
        "source_path": str(midi_path),
        "ingested_at": datetime.now().isoformat(timespec="seconds"),
        "status": "pending_review",
        "reviewed_by": None,
        "approved": None,
    }

    try:
        # 1. Parse MIDI
        tracks, bpm, tpb = parse_midi_to_tracks(str(midi_path))
        if not tracks:
            entry["status"] = "error"
            entry["error"] = "No note data found"
            return entry

        all_notes: list[Note] = []
        for t in tracks:
            all_notes.extend(t.notes)
        all_notes.sort(key=lambda n: n.start_tick)
        combined = Track(name="Combined", channel=0, notes=all_notes)
        total_notes = len(all_notes)

        # 2. Harmony analysis
        harmony = engine.analyze_harmony(combined, key="C", scale="minor")

        # 3. Song form analysis
        project = ProjectState(
            name=midi_path.stem,
            tracks=tracks,
            bpm=bpm,
            key="C",
            scale="minor",
            ticks_per_beat=tpb,
        )
        song_form = engine.analyze_song_form(project)

        # 4. Playability validation
        playability = engine.validate_playability(all_notes)

        # 5. Save analysis JSON
        ANALYZED_DIR.mkdir(exist_ok=True)
        analysis_result = {
            "file": midi_path.name,
            "filename": midi_path.name,
            "bpm": bpm,
            "ticks_per_beat": tpb,
            "num_tracks": len(tracks),
            "total_notes": total_notes,
            "harmony": {
                "overall_score": harmony.get("overall_score", 0),
                "chord_count": harmony.get("chord_count", 0),
                "key_estimate": harmony.get("key_estimate", "C"),
                "issues": harmony.get("issues", []),
                "num_segments": len(harmony.get("segments", [])),
                "segments": harmony.get("segments", []),
            },
            "song_form": {
                "form_type": song_form.get("form_type", "unknown"),
                "confidence": song_form.get("confidence", 0.0),
                "total_bars": song_form.get("total_bars", 0),
                "sections": song_form.get("sections", []),
            },
            "playability": {
                "score": playability.get("score", 0),
                "pass": playability.get("pass", False),
                "num_issues": len(playability.get("issues", [])),
                "issues_sample": playability.get("issues", [])[:10],
            },
            "success": True,
        }
        safe_name = midi_path.stem.replace(" ", "_")
        out_path = ANALYZED_DIR / f"{safe_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(analysis_result, f, indent=2, ensure_ascii=False, default=str)

        # 6. Try to compute embedding (optional)
        _try_compute_embedding(midi_path)

        # Populate log entry
        harmony_score = harmony.get("overall_score", 0)
        chord_count = harmony.get("chord_count", 0)
        play_score = playability.get("score", 0)
        entry.update({
            "auto_genre": _estimate_genre(harmony, bpm),
            "auto_difficulty": _estimate_difficulty(total_notes, play_score),
            "harmony_score": harmony_score,
            "chord_count": chord_count,
            "total_notes": total_notes,
        })

    except Exception as exc:
        entry["status"] = "error"
        entry["error"] = f"{type(exc).__name__}: {exc}"
        print(f"    ERROR: {entry['error']}")
        traceback.print_exc()

    return entry


def _try_compute_embedding(midi_path: Path) -> None:
    """Attempt to generate an embedding for the file (best-effort)."""
    try:
        # The midi_embedding module requires pretty_midi which may not be
        # installed.  Import lazily so the rest of ingestion still works.
        tools_dir = REPO_ROOT / "tools"
        if str(tools_dir) not in sys.path:
            sys.path.insert(0, str(tools_dir))
        from midi_embedding import analyze_midi, NumpyEncoder

        EMBED_DIR.mkdir(parents=True, exist_ok=True)
        result = analyze_midi(str(midi_path))
        out_name = midi_path.stem.replace(" ", "_") + ".json"
        out_path = EMBED_DIR / out_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)
    except Exception:
        # Embedding is optional — silently skip on failure
        pass


# ── Ingest log helpers ───────────────────────────────────────────────────

def _load_ingest_log() -> dict:
    if INGEST_LOG_PATH.is_file():
        with open(INGEST_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": []}


def _save_ingest_log(log: dict) -> None:
    PATTERN_DIR.mkdir(exist_ok=True)
    with open(INGEST_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False, default=str)


# ── Pattern library rebuild (delegates to build_pattern_library logic) ───

def rebuild_patterns() -> None:
    """Rebuild the pattern library from analyzed_chords/."""
    # Import the builder functions directly
    tools_dir = REPO_ROOT / "tools"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))
    from build_pattern_library import (
        load_analyses,
        extract_chord_progressions,
        extract_voicing_examples,
        extract_form_templates,
        build_genre_statistics,
    )

    print("\nRebuilding pattern library...")
    analyses = load_analyses()
    print(f"  Loaded {len(analyses)} analyzed files")

    if not analyses:
        print("  [WARN] No analyses found — skipping rebuild.")
        return

    os.makedirs(str(PATTERN_DIR), exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d")
    corpus_label = f"auto-ingest ({len(analyses)} files)"

    progs = extract_chord_progressions(analyses)
    with open(PATTERN_DIR / "chord_progressions.json", "w", encoding="utf-8") as f:
        json.dump({"version": "0.1.0", "generated_date": now,
                    "source_corpus": corpus_label, "status": "auto-generated",
                    "patterns": progs}, f, indent=2, ensure_ascii=False)
    print(f"  Chord progressions: 2g={len(progs['2_gram'])}, "
          f"4g={len(progs['4_gram'])}, 8g={len(progs['8_gram'])}")

    voicings = extract_voicing_examples(analyses)
    with open(PATTERN_DIR / "voicing_examples.json", "w", encoding="utf-8") as f:
        json.dump({"version": "0.1.0", "generated_date": now,
                    "source_corpus": corpus_label, "status": "auto-generated",
                    "examples": voicings}, f, indent=2, ensure_ascii=False)
    print(f"  Voicing examples: {len(voicings)} qualities")

    forms = extract_form_templates(analyses)
    with open(PATTERN_DIR / "form_templates.json", "w", encoding="utf-8") as f:
        json.dump({"version": "0.1.0", "generated_date": now,
                    "source_corpus": corpus_label, "status": "auto-generated",
                    "statistics": forms}, f, indent=2, ensure_ascii=False)
    print(f"  Form templates: {forms.get('form_type_distribution', {})}")

    stats = build_genre_statistics(analyses)
    with open(PATTERN_DIR / "genre_statistics.json", "w", encoding="utf-8") as f:
        json.dump({"version": "0.1.0", "generated_date": now,
                    "source_corpus": corpus_label, "status": "auto-generated",
                    "statistics": stats}, f, indent=2, ensure_ascii=False)
    print(f"  Genre stats: {stats.get('corpus_size', 0)} files, "
          f"{stats.get('total_notes', 0)} notes")

    print("  Pattern library rebuild complete.")


# ── CLI entry point ──────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-ingest MIDI files into the pattern DB.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a .mid/.midi file or a directory of them.",
    )
    parser.add_argument(
        "--rebuild-only",
        action="store_true",
        help="Just rebuild the pattern library without ingesting new files.",
    )

    args = parser.parse_args()

    if args.rebuild_only:
        rebuild_patterns()
        return

    if not args.path:
        # No path given — open a file dialog (GUI mode for double-click users)
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            paths = filedialog.askopenfilenames(
                title="Select MIDI files to ingest",
                filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")],
            )
            root.destroy()
            if paths:
                args.path = paths[0] if len(paths) == 1 else os.path.dirname(paths[0])
                # If multiple files selected, copy them to a temp dir concept
                # For simplicity, process the parent directory
                if len(paths) > 1:
                    args.path = os.path.dirname(paths[0])
            else:
                print("No files selected. Exiting.")
                input("Press Enter to close...")
                sys.exit(0)
        except Exception:
            parser.error("Please provide a file or directory path, or use --rebuild-only.")

    target = Path(args.path).resolve()

    # Collect MIDI files
    midi_files: list[Path] = []
    if target.is_file():
        if target.suffix.lower() in (".mid", ".midi"):
            midi_files.append(target)
        else:
            print(f"[ERROR] Not a MIDI file: {target}")
            sys.exit(1)
    elif target.is_dir():
        for ext in ("*.mid", "*.midi"):
            midi_files.extend(sorted(target.glob(ext)))
        if not midi_files:
            print(f"[ERROR] No .mid/.midi files found in {target}")
            sys.exit(1)
    else:
        print(f"[ERROR] Path not found: {target}")
        sys.exit(1)

    print("=" * 60)
    print("Auto-Ingest MIDI Pipeline")
    print("=" * 60)
    print(f"Files to process: {len(midi_files)}")

    # Initialise engine
    print("Loading HarmonyEngine...")
    engine = HarmonyEngine()
    print(f"  Rule DB schema version: {engine.schema_version}")

    # Process each file
    log = _load_ingest_log()
    successes = 0
    failures = 0
    t_start = time.time()

    for i, midi_path in enumerate(midi_files, 1):
        print(f"\n  [{i}/{len(midi_files)}] {midi_path.name}")
        entry = ingest_file(engine, midi_path)

        if entry.get("status") == "error":
            failures += 1
        else:
            successes += 1

        log["entries"].append(entry)
        print(f"    status={entry['status']}  "
              f"notes={entry.get('total_notes', '?')}  "
              f"chords={entry.get('chord_count', '?')}  "
              f"genre={entry.get('auto_genre', '?')}  "
              f"difficulty={entry.get('auto_difficulty', '?')}")

    _save_ingest_log(log)
    elapsed = time.time() - t_start

    # Rebuild pattern library
    rebuild_patterns()

    # Summary
    print("\n" + "=" * 60)
    print("Ingestion Summary")
    print("=" * 60)
    print(f"  Files processed: {len(midi_files)}")
    print(f"  Successes:       {successes}")
    print(f"  Failures:        {failures}")
    print(f"  Time:            {elapsed:.1f}s")
    print(f"  Ingest log:      {INGEST_LOG_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
    # Keep console open when run as exe
    if getattr(sys, 'frozen', False):
        input("\nPress Enter to close...")
