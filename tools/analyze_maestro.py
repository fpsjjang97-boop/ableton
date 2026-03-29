"""
MAESTRO 93-file automatic harmony analysis.

Parses all MIDI files from Ableton/midi_raw/ (chamber/, recital/, schubert/),
runs HarmonyEngine analysis, and saves results as JSON.
"""
import json
import os
import sys
import time
import traceback
from pathlib import Path

# Setup paths
REPO_ROOT = Path(__file__).resolve().parent.parent
APP_DIR = REPO_ROOT / "app"
sys.path.insert(0, str(APP_DIR))

import mido
from core.models import Note, Track, ProjectState, TimeSignature, TICKS_PER_BEAT
from core.harmony_engine import HarmonyEngine

MIDI_RAW_DIR = REPO_ROOT / "Ableton" / "midi_raw"
OUTPUT_DIR = REPO_ROOT / "analyzed_chords"
OUTPUT_DIR.mkdir(exist_ok=True)


def parse_midi_to_tracks(midi_path: str) -> tuple[list[Track], float, int]:
    """Parse a MIDI file into Track objects using mido.

    Returns (tracks, bpm, ticks_per_beat).
    """
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat or 480
    bpm = 120.0

    # Collect notes per channel/track
    track_notes: dict[int, list[Note]] = {}

    for i, midi_track in enumerate(mid.tracks):
        abs_tick = 0
        active: dict[tuple[int, int], Note] = {}  # (channel, pitch) -> Note

        for msg in midi_track:
            abs_tick += msg.time

            # Extract tempo
            if msg.type == "set_tempo":
                bpm = round(mido.tempo2bpm(msg.tempo), 2)

            elif msg.type == "note_on" and msg.velocity > 0:
                ch = msg.channel
                key = (ch, msg.note)
                # Close any prior note on same key
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

            elif msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
                ch = msg.channel
                key = (ch, msg.note)
                if key in active:
                    n = active.pop(key)
                    n.duration_ticks = max(1, abs_tick - n.start_tick)

        # Close any still-active notes
        for key, n in active.items():
            if n.duration_ticks == 0:
                n.duration_ticks = max(1, tpb)

    tracks = []
    for idx in sorted(track_notes.keys()):
        notes = track_notes[idx]
        if notes:
            notes.sort(key=lambda n: n.start_tick)
            ch = notes[0].channel
            tracks.append(Track(
                name=f"Track_{idx}_ch{ch}",
                channel=ch,
                notes=notes,
            ))

    return tracks, bpm, tpb


def analyze_file(engine: HarmonyEngine, midi_path: Path) -> dict:
    """Run full analysis on a single MIDI file."""
    rel_path = str(midi_path.relative_to(MIDI_RAW_DIR))
    result = {
        "file": rel_path,
        "filename": midi_path.name,
        "category": midi_path.parent.name,
    }

    try:
        tracks, bpm, tpb = parse_midi_to_tracks(str(midi_path))
        result["bpm"] = bpm
        result["ticks_per_beat"] = tpb
        result["num_tracks"] = len(tracks)
        total_notes = sum(len(t.notes) for t in tracks)
        result["total_notes"] = total_notes

        if not tracks:
            result["error"] = "No note data found"
            return result

        # Merge all notes into one combined track for harmony analysis
        all_notes = []
        for t in tracks:
            all_notes.extend(t.notes)
        all_notes.sort(key=lambda n: n.start_tick)
        combined_track = Track(name="Combined", channel=0, notes=all_notes)

        # 1. analyze_harmony
        harmony = engine.analyze_harmony(combined_track, key="C", scale="minor")
        result["harmony"] = {
            "overall_score": harmony.get("overall_score", 0),
            "chord_count": harmony.get("chord_count", 0),
            "key_estimate": harmony.get("key_estimate", "C"),
            "issues": harmony.get("issues", []),
            "num_segments": len(harmony.get("segments", [])),
            "segments": harmony.get("segments", []),
        }

        # 2. analyze_song_form (create minimal ProjectState)
        project = ProjectState(
            name=midi_path.stem,
            tracks=tracks,
            bpm=bpm,
            key="C",
            scale="minor",
            ticks_per_beat=tpb,
        )
        song_form = engine.analyze_song_form(project)
        # Strip bar_features to keep JSON manageable
        song_form_slim = {
            "form_type": song_form.get("form_type", "unknown"),
            "confidence": song_form.get("confidence", 0.0),
            "total_bars": song_form.get("total_bars", 0),
            "sections": song_form.get("sections", []),
        }
        result["song_form"] = song_form_slim

        # 3. validate_playability
        playability = engine.validate_playability(all_notes)
        result["playability"] = {
            "score": playability.get("score", 0),
            "pass": playability.get("pass", False),
            "num_issues": len(playability.get("issues", [])),
            "issues_sample": playability.get("issues", [])[:10],
        }

        result["success"] = True

    except Exception as e:
        result["success"] = False
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()

    return result


def main():
    print("=" * 70)
    print("MAESTRO 93-File Automatic Harmony Analysis")
    print("=" * 70)

    # Collect all MIDI files
    midi_files = sorted(MIDI_RAW_DIR.rglob("*.midi")) + sorted(MIDI_RAW_DIR.rglob("*.mid"))
    print(f"Found {len(midi_files)} MIDI files")

    if not midi_files:
        print("ERROR: No MIDI files found!")
        return

    # Initialize HarmonyEngine
    print("Loading HarmonyEngine...")
    engine = HarmonyEngine()
    print(f"  Rule DB schema version: {engine.schema_version}")

    # Process each file
    results = []
    successes = 0
    failures = 0
    start_time = time.time()

    for i, midi_path in enumerate(midi_files, 1):
        category = midi_path.parent.name
        print(f"  [{i:3d}/{len(midi_files)}] {category}/{midi_path.name} ... ", end="", flush=True)

        t0 = time.time()
        result = analyze_file(engine, midi_path)
        elapsed = time.time() - t0

        if result.get("success"):
            successes += 1
            h = result.get("harmony", {})
            sf = result.get("song_form", {})
            p = result.get("playability", {})
            print(f"OK ({elapsed:.1f}s) "
                  f"notes={result.get('total_notes',0)} "
                  f"chords={h.get('chord_count',0)} "
                  f"form={sf.get('form_type','?')} "
                  f"play={p.get('score',0)}")
        else:
            failures += 1
            print(f"FAIL ({elapsed:.1f}s) {result.get('error', '?')}")

        # Save individual JSON
        safe_name = midi_path.stem.replace(" ", "_")
        out_path = OUTPUT_DIR / f"{safe_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)

        results.append(result)

    total_time = time.time() - start_time

    # Generate SUMMARY.json
    print("\n" + "=" * 70)
    print("Generating SUMMARY.json...")

    # Compute statistics
    successful = [r for r in results if r.get("success")]
    harmony_scores = [r["harmony"]["overall_score"] for r in successful if "harmony" in r]
    playability_scores = [r["playability"]["score"] for r in successful if "playability" in r]
    chord_counts = [r["harmony"]["chord_count"] for r in successful if "harmony" in r]
    note_counts = [r.get("total_notes", 0) for r in successful]
    form_types = [r["song_form"]["form_type"] for r in successful if "song_form" in r]
    bar_counts = [r["song_form"]["total_bars"] for r in successful if "song_form" in r]

    # Category breakdown
    categories = {}
    for r in results:
        cat = r.get("category", "unknown")
        if cat not in categories:
            categories[cat] = {"total": 0, "success": 0, "failed": 0, "files": []}
        categories[cat]["total"] += 1
        if r.get("success"):
            categories[cat]["success"] += 1
        else:
            categories[cat]["failed"] += 1
        categories[cat]["files"].append(r.get("filename", "?"))

    # Form type distribution
    form_dist = {}
    for ft in form_types:
        form_dist[ft] = form_dist.get(ft, 0) + 1

    summary = {
        "analysis_timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_files": len(midi_files),
        "successes": successes,
        "failures": failures,
        "total_time_seconds": round(total_time, 2),
        "avg_time_per_file": round(total_time / len(midi_files), 2) if midi_files else 0,
        "statistics": {
            "harmony_scores": {
                "mean": round(sum(harmony_scores) / len(harmony_scores), 1) if harmony_scores else 0,
                "min": min(harmony_scores) if harmony_scores else 0,
                "max": max(harmony_scores) if harmony_scores else 0,
            },
            "playability_scores": {
                "mean": round(sum(playability_scores) / len(playability_scores), 1) if playability_scores else 0,
                "min": min(playability_scores) if playability_scores else 0,
                "max": max(playability_scores) if playability_scores else 0,
            },
            "chord_counts": {
                "mean": round(sum(chord_counts) / len(chord_counts), 1) if chord_counts else 0,
                "min": min(chord_counts) if chord_counts else 0,
                "max": max(chord_counts) if chord_counts else 0,
            },
            "note_counts": {
                "mean": round(sum(note_counts) / len(note_counts), 1) if note_counts else 0,
                "min": min(note_counts) if note_counts else 0,
                "max": max(note_counts) if note_counts else 0,
                "total": sum(note_counts),
            },
            "bar_counts": {
                "mean": round(sum(bar_counts) / len(bar_counts), 1) if bar_counts else 0,
                "min": min(bar_counts) if bar_counts else 0,
                "max": max(bar_counts) if bar_counts else 0,
            },
        },
        "form_type_distribution": form_dist,
        "category_breakdown": categories,
        "failed_files": [
            {"file": r.get("file", "?"), "error": r.get("error", "?")}
            for r in results if not r.get("success")
        ],
    }

    summary_path = OUTPUT_DIR / "SUMMARY.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nResults saved to: {OUTPUT_DIR}/")
    print(f"  Individual JSONs: {successes + failures} files")
    print(f"  Summary: SUMMARY.json")
    print(f"\n{'=' * 70}")
    print(f"  Total files:   {len(midi_files)}")
    print(f"  Successes:     {successes}")
    print(f"  Failures:      {failures}")
    print(f"  Total time:    {total_time:.1f}s")
    if harmony_scores:
        print(f"  Avg harmony:   {sum(harmony_scores)/len(harmony_scores):.1f}")
    if playability_scores:
        print(f"  Avg playability: {sum(playability_scores)/len(playability_scores):.1f}")
    print(f"  Form types:    {form_dist}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
