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
from core.models import Note, Track, ProjectState, TICKS_PER_BEAT
from core.harmony_engine import HarmonyEngine

ANALYZED_DIR = REPO_ROOT / "analyzed_chords"
PATTERN_DIR = REPO_ROOT / "pattern_library"
EMBED_DIR = REPO_ROOT / "embeddings" / "individual"
INGEST_LOG_PATH = PATTERN_DIR / "ingest_log.json"


# ── MIDI parsing (reused from tools/analyze_maestro.py) ─────────────────

def parse_midi_to_tracks(midi_path: str) -> tuple[list[Track], float, int]:
    """Parse a MIDI file into Track objects using mido.

    Returns (tracks, bpm, ticks_per_beat).
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat or 480
    bpm = 120.0

    track_notes: dict[int, list[Note]] = {}

    for i, midi_track in enumerate(mid.tracks):
        abs_tick = 0
        active: dict[tuple[int, int], Note] = {}

        for msg in midi_track:
            abs_tick += msg.time

            if msg.type == "set_tempo":
                bpm = round(mido.tempo2bpm(msg.tempo), 2)

            elif msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
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

    tracks = []
    for idx in sorted(track_notes.keys()):
        notes = track_notes[idx]
        if notes:
            notes.sort(key=lambda n: n.start_tick)
            ch = notes[0].channel
            tracks.append(
                Track(name=f"Track_{idx}_ch{ch}", channel=ch, notes=notes)
            )

    return tracks, bpm, tpb


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
