"""
Pattern Library Builder — extracts patterns from analyzed_chords/ and
generates pattern_library/ files.

Usage:
    python tools/build_pattern_library.py

Requires: analyzed_chords/ directory with >=10 JSON files.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYZED_DIR = os.path.join(REPO_ROOT, "analyzed_chords")
PATTERN_DIR = os.path.join(REPO_ROOT, "pattern_library")


def load_analyses() -> list[dict]:
    """Load all analyzed chord JSON files."""
    results = []
    if not os.path.isdir(ANALYZED_DIR):
        print(f"[ERROR] {ANALYZED_DIR} not found")
        return results
    for fname in sorted(os.listdir(ANALYZED_DIR)):
        if not fname.endswith(".json") or fname == "SUMMARY.json":
            continue
        path = os.path.join(ANALYZED_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_filename"] = fname
            results.append(data)
        except Exception as e:
            print(f"  [WARN] Failed to load {fname}: {e}")
    return results


def extract_chord_progressions(analyses: list[dict]) -> dict:
    """Extract chord progression n-grams from analyzed files."""
    all_2grams: Counter = Counter()
    all_4grams: Counter = Counter()
    all_8grams: Counter = Counter()

    for analysis in analyses:
        segments = analysis.get("harmony", {}).get("segments", [])
        chords = [s.get("chord", "N.C.") for s in segments if s.get("chord", "N.C.") != "N.C."]

        # 2-grams
        for i in range(len(chords) - 1):
            gram = f"{chords[i]} → {chords[i+1]}"
            all_2grams[gram] += 1

        # 4-grams
        for i in range(len(chords) - 3):
            gram = " → ".join(chords[i:i+4])
            all_4grams[gram] += 1

        # 8-grams
        for i in range(len(chords) - 7):
            gram = " → ".join(chords[i:i+8])
            all_8grams[gram] += 1

    return {
        "2_gram": [{"pattern": k, "count": v} for k, v in all_2grams.most_common(50)],
        "4_gram": [{"pattern": k, "count": v} for k, v in all_4grams.most_common(30)],
        "8_gram": [{"pattern": k, "count": v} for k, v in all_8grams.most_common(20)],
    }


def extract_voicing_examples(analyses: list[dict]) -> dict:
    """Collect voicing examples grouped by chord quality."""
    by_quality: dict[str, list] = defaultdict(list)

    for analysis in analyses:
        segments = analysis.get("harmony", {}).get("segments", [])
        for seg in segments:
            quality = seg.get("quality", "")
            if not quality:
                continue
            entry = {
                "chord": seg.get("chord", ""),
                "root": seg.get("root", ""),
                "confidence": seg.get("confidence", 0),
                "source": analysis.get("_filename", ""),
                "bar": seg.get("bar", 0),
            }
            by_quality[quality].append(entry)

    # Keep top examples per quality
    result = {}
    for quality, examples in by_quality.items():
        examples.sort(key=lambda x: x["confidence"], reverse=True)
        result[quality] = examples[:20]

    return result


def extract_form_templates(analyses: list[dict]) -> dict:
    """Collect song form statistics."""
    form_counts: Counter = Counter()
    section_sequences: list[list[str]] = []

    for analysis in analyses:
        form = analysis.get("song_form", {})
        form_type = form.get("form_type", "unknown")
        form_counts[form_type] += 1

        sections = form.get("sections", [])
        seq = [s.get("label", "unknown") for s in sections]
        if seq:
            section_sequences.append(seq)

    return {
        "form_type_distribution": dict(form_counts.most_common()),
        "total_analyzed": len(analyses),
        "common_section_sequences": section_sequences[:20],
    }


def build_genre_statistics(analyses: list[dict]) -> dict:
    """Compute cross-corpus statistics."""
    total_notes = 0
    total_bars = 0
    total_chords = 0
    chord_counter: Counter = Counter()
    key_counter: Counter = Counter()

    for analysis in analyses:
        stats = analysis.get("statistics", {})
        total_notes += stats.get("total_notes", 0)
        total_bars += stats.get("total_bars", 0)
        total_chords += stats.get("unique_chords", 0)

        key_counter[analysis.get("key_estimate", "C")] += 1

        segments = analysis.get("harmony", {}).get("segments", [])
        for seg in segments:
            chord = seg.get("chord", "")
            if chord and chord != "N.C.":
                chord_counter[chord] += 1

    return {
        "corpus_size": len(analyses),
        "total_notes": total_notes,
        "total_bars": total_bars,
        "avg_notes_per_file": round(total_notes / max(len(analyses), 1), 1),
        "avg_bars_per_file": round(total_bars / max(len(analyses), 1), 1),
        "key_distribution": dict(key_counter.most_common()),
        "top_chords": [{"chord": k, "count": v} for k, v in chord_counter.most_common(30)],
    }


def main():
    print("=" * 60)
    print("Pattern Library Builder")
    print("=" * 60)

    analyses = load_analyses()
    print(f"Loaded {len(analyses)} analyzed files")

    if len(analyses) < 5:
        print("[WARN] Less than 5 files analyzed. Patterns may not be meaningful.")

    os.makedirs(PATTERN_DIR, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%d")

    # 1. Chord progressions
    print("\nExtracting chord progressions...")
    progs = extract_chord_progressions(analyses)
    prog_data = {
        "version": "0.1.0",
        "generated_date": now,
        "source_corpus": f"MAESTRO 2018 ({len(analyses)} files)",
        "status": "auto-generated",
        "patterns": progs,
    }
    with open(os.path.join(PATTERN_DIR, "chord_progressions.json"), "w", encoding="utf-8") as f:
        json.dump(prog_data, f, indent=2, ensure_ascii=False)
    print(f"  2-grams: {len(progs['2_gram'])}, 4-grams: {len(progs['4_gram'])}, 8-grams: {len(progs['8_gram'])}")

    # 2. Voicing examples
    print("Extracting voicing examples...")
    voicings = extract_voicing_examples(analyses)
    voicing_data = {
        "version": "0.1.0",
        "generated_date": now,
        "source_corpus": f"MAESTRO 2018 ({len(analyses)} files)",
        "status": "auto-generated",
        "examples": voicings,
    }
    with open(os.path.join(PATTERN_DIR, "voicing_examples.json"), "w", encoding="utf-8") as f:
        json.dump(voicing_data, f, indent=2, ensure_ascii=False)
    print(f"  {len(voicings)} chord qualities with examples")

    # 3. Form templates
    print("Extracting form templates...")
    forms = extract_form_templates(analyses)
    form_data = {
        "version": "0.1.0",
        "generated_date": now,
        "source_corpus": f"MAESTRO 2018 ({len(analyses)} files)",
        "status": "auto-generated",
        "statistics": forms,
    }
    with open(os.path.join(PATTERN_DIR, "form_templates.json"), "w", encoding="utf-8") as f:
        json.dump(form_data, f, indent=2, ensure_ascii=False)
    print(f"  Form types: {forms['form_type_distribution']}")

    # 4. Genre statistics
    print("Computing genre statistics...")
    genre_stats = build_genre_statistics(analyses)
    genre_data = {
        "version": "0.1.0",
        "generated_date": now,
        "source_corpus": f"MAESTRO 2018 ({len(analyses)} files)",
        "status": "auto-generated",
        "statistics": genre_stats,
    }
    with open(os.path.join(PATTERN_DIR, "genre_statistics.json"), "w", encoding="utf-8") as f:
        json.dump(genre_data, f, indent=2, ensure_ascii=False)
    print(f"  Corpus: {genre_stats['corpus_size']} files, {genre_stats['total_notes']} notes")

    print("\n" + "=" * 60)
    print(f"Pattern library generated in {PATTERN_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
