"""MIDI 파일 통계 — 단일 파일 또는 폴더 (Sprint 46 JJJ4).

노트/트랙/BPM/key/duration/pitch range 통계. 배치 모드 시 CSV 출력.
데이터 augmentation / dedup / 증강 전 데이터 인벤토리에 활용.

사용:
    python scripts/midi_stats.py --input song.mid
    python scripts/midi_stats.py --input ./midi_data/ --csv stats.csv
    python scripts/midi_stats.py --input ./midi_data/ --summary   # aggregate 만

의존: pretty_midi.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from statistics import mean, median, pstdev

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


MIDI_EXTS = {".mid", ".midi"}
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def _estimate_key(pm) -> str:
    """거친 key 추정 — pitch class 히스토그램에서 Krumhansl 프로파일과 상관."""
    import numpy as np
    pc = [0] * 12
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for n in inst.notes:
            pc[n.pitch % 12] += 1
    if sum(pc) == 0:
        return "unknown"
    # Krumhansl major/minor key profile (summary)
    major = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
    minor = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
    pc_arr = np.array(pc) / sum(pc)
    best = ("C", 0.0)
    for tonic in range(12):
        m = np.roll(np.array(major), tonic)
        mi = np.roll(np.array(minor), tonic)
        sm = float(np.corrcoef(pc_arr, m)[0, 1])
        smi = float(np.corrcoef(pc_arr, mi)[0, 1])
        if sm > best[1]:
            best = (f"{NOTE_NAMES[tonic]}", sm)
        if smi > best[1]:
            best = (f"{NOTE_NAMES[tonic]}m", smi)
    return best[0]


def file_stats(path: Path) -> dict | None:
    import pretty_midi
    try:
        pm = pretty_midi.PrettyMIDI(str(path))
    except Exception as e:
        return {"file": str(path), "error": f"{type(e).__name__}: {e}"}

    total_notes = sum(len(i.notes) for i in pm.instruments)
    non_drum = [i for i in pm.instruments if not i.is_drum]
    duration = pm.get_end_time()

    # Tempo
    tempo = 120.0
    try:
        _, bpms = pm.get_tempo_changes()
        if len(bpms) > 0:
            tempo = float(bpms[0])
    except Exception:
        pass

    # Pitch range
    pitches = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        pitches.extend(n.pitch for n in inst.notes)
    pmin = min(pitches) if pitches else 0
    pmax = max(pitches) if pitches else 0

    return {
        "file": str(path),
        "notes": total_notes,
        "tracks": len(pm.instruments),
        "drum_tracks": sum(1 for i in pm.instruments if i.is_drum),
        "melodic_tracks": len(non_drum),
        "duration_sec": round(duration, 2),
        "tempo": round(tempo, 1),
        "key": _estimate_key(pm),
        "pitch_min": pmin,
        "pitch_max": pmax,
        "bars_4_4": round(duration * tempo / 60.0 / 4.0, 1),
    }


def collect(input_path: Path) -> list[dict]:
    if input_path.is_file():
        s = file_stats(input_path)
        return [s] if s else []
    files = sorted(f for f in input_path.rglob("*") if f.suffix.lower() in MIDI_EXTS)
    out = []
    for f in files:
        s = file_stats(f)
        if s:
            out.append(s)
    return out


def _summarize(rows: list[dict]) -> dict:
    good = [r for r in rows if "error" not in r]
    if not good:
        return {"count": 0, "errors": len(rows) - len(good)}
    notes = [r["notes"] for r in good]
    dur = [r["duration_sec"] for r in good]
    tempos = [r["tempo"] for r in good]
    return {
        "count": len(good),
        "errors": len(rows) - len(good),
        "notes_total": sum(notes),
        "notes_mean": round(mean(notes), 1),
        "notes_median": median(notes),
        "notes_max": max(notes),
        "duration_mean_sec": round(mean(dur), 1),
        "duration_median_sec": round(median(dur), 1),
        "tempo_mean": round(mean(tempos), 1),
        "tempo_stdev": round(pstdev(tempos), 1),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--input", required=True, help="MIDI 파일 또는 폴더")
    ap.add_argument("--csv", default=None, help="CSV 출력 경로 (폴더 모드)")
    ap.add_argument("--summary", action="store_true",
                    help="aggregate summary 만 출력")
    args = ap.parse_args()

    rows = collect(Path(args.input))
    if not rows:
        print(f"[ERROR] MIDI 없음: {args.input}")
        sys.exit(1)

    # Per-file
    if not args.summary:
        for r in rows:
            if "error" in r:
                print(f"  [ERR] {r['file']}: {r['error']}")
            else:
                print(f"  {Path(r['file']).name:>40}  "
                      f"notes={r['notes']:>4}  tempo={r['tempo']:>6.1f}  "
                      f"key={r['key']:>4}  dur={r['duration_sec']:>6.1f}s  "
                      f"range=[{r['pitch_min']},{r['pitch_max']}]")

    # Summary
    s = _summarize(rows)
    print("=" * 60)
    for k, v in s.items():
        print(f"  {k:>22}: {v}")

    if args.csv and rows:
        keys = list(rows[0].keys())
        # error 케이스가 섞여 있을 수 있음 — keys 확장
        all_keys = set()
        for r in rows:
            all_keys.update(r.keys())
        keys = sorted(all_keys)
        with open(args.csv, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=keys)
            w.writeheader()
            for r in rows:
                w.writerow(r)
        print(f"CSV: {args.csv}")


if __name__ == "__main__":
    main()
