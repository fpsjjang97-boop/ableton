"""생성 MIDI 품질 오프라인 측정 — 데모 게이트용.

데모 체크리스트 (docs/business/12_release_checklist.md 라인 26-28) 의
품질 기준을 **모델 호출 없이** 이미 생성된 MIDI 파일들만으로 검증:

    (1) 노트 밀도 0.5~1.5x 범위
    (2) FSM 문법 위반 (bar 역전, 동일 bar+pos+pitch 중복 노트)
    (3) 배치 리포트 (평균/표준편차/극값)

사용:
    # 생성 결과가 있는 폴더 1개 + 기준 입력 MIDI
    python scripts/measure_generation_quality.py \\
        --gen_dir ./output \\
        --input_midi "./TEST MIDI/CITY POP 105 4-4 DRUM E.PIANO.mid"

    # 여러 생성 단일 비교
    python scripts/measure_generation_quality.py \\
        --gen_dir ./output --input_midi input.mid --out ./output/quality.json

밀도 비율 = (gen notes / gen duration_bars) / (input notes / input duration_bars).
0.5~1.5 정상, 이탈 시 경고.

의존: pretty_midi (이미 설치됨), midigpt.tokenizer (encode → token check).

실패 모드:
    - gen_dir 없음 / 파일 0개 → exit 2
    - 개별 파일 parse 실패 → skip + warn, 집계에서 제외
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median, pstdev

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

try:
    import pretty_midi
except ImportError:
    print("[ERROR] pretty_midi 미설치. pip install pretty_midi")
    sys.exit(2)

from midigpt.tokenizer.vocab import VOCAB


def _notes_and_bars(midi: pretty_midi.PrettyMIDI) -> tuple[int, float, float]:
    """Returns (total_notes, total_duration_sec, estimated_bars).

    bars = duration_sec * (bpm/60) / 4  (4/4 가정)
    """
    notes = sum(len(inst.notes) for inst in midi.instruments)
    duration = midi.get_end_time()
    tempo = 120.0
    try:
        tempo_changes = midi.get_tempo_changes()
        if len(tempo_changes[1]) > 0:
            tempo = float(tempo_changes[1][0])
    except Exception:
        pass
    bars = duration * tempo / 60.0 / 4.0
    return notes, duration, max(bars, 1e-6)


def _check_grammar(midi_path: Path) -> dict:
    """MIDI → 토큰화 → 문법 위반 카운트.

    중복 노트: 같은 bar+pos+pitch+track 이 연속 등장
    Bar 역전: Bar_n 이후에 Bar_m (m < n) 이 등장
    """
    from midigpt.tokenizer.encoder import MidiEncoder
    enc = MidiEncoder()
    try:
        ids = enc.encode_file(str(midi_path))
    except Exception as e:
        return {"error": f"encode 실패: {type(e).__name__}: {e}"}

    tokens = VOCAB.decode_ids(ids)

    bar_reversals = 0
    last_bar = -1
    for t in tokens:
        if t.startswith("Bar_"):
            try:
                b = int(t.split("_")[1])
                if b < last_bar:
                    bar_reversals += 1
                last_bar = b
            except ValueError:
                pass

    # 중복 노트: Bar+Pos+Pitch 조합 해시가 연속 등장
    dup_notes = 0
    prev_sig: tuple | None = None
    cur_bar = None
    cur_pos = None
    for t in tokens:
        if t.startswith("Bar_"):
            cur_bar = t
        elif t.startswith("Pos_"):
            cur_pos = t
        elif t.startswith("Pitch_"):
            sig = (cur_bar, cur_pos, t)
            if sig == prev_sig and cur_bar is not None:
                dup_notes += 1
            prev_sig = sig

    return {
        "bar_reversals": bar_reversals,
        "duplicate_notes": dup_notes,
        "n_tokens": len(ids),
    }


def measure(gen_dir: Path, input_midi: Path | None, out: Path | None) -> int:
    files = sorted(gen_dir.glob("*.mid")) + sorted(gen_dir.glob("*.midi"))
    if not files:
        print(f"[ERROR] 생성 MIDI 없음: {gen_dir}")
        return 2

    # 기준 밀도 (입력)
    input_density = None
    if input_midi and input_midi.exists():
        try:
            in_pm = pretty_midi.PrettyMIDI(str(input_midi))
            n, _, b = _notes_and_bars(in_pm)
            input_density = n / b
            print(f"입력 기준: {input_midi.name}  notes={n}  bars={b:.1f}  "
                  f"density={input_density:.2f} notes/bar")
        except Exception as e:
            print(f"[WARN] 입력 parse 실패 ({input_midi}): {e}")

    print("=" * 72)
    per_file = []
    densities = []
    violations_total = 0
    dup_total = 0

    for f in files:
        try:
            pm = pretty_midi.PrettyMIDI(str(f))
            n, d, b = _notes_and_bars(pm)
            dens = n / b
        except Exception as e:
            print(f"  [SKIP] {f.name}: parse 실패 — {e}")
            continue

        grammar = _check_grammar(f)
        br = grammar.get("bar_reversals", 0)
        du = grammar.get("duplicate_notes", 0)
        err = grammar.get("error", "")
        violations_total += br
        dup_total += du

        ratio_str = ""
        if input_density:
            r = dens / input_density
            mark = "OK" if 0.5 <= r <= 1.5 else "WARN"
            ratio_str = f"  ratio={r:.2f} [{mark}]"

        print(f"  {f.name:>40}  notes={n:>4}  bars={b:>5.1f}  "
              f"density={dens:>5.2f}{ratio_str}  "
              f"barRev={br}  dupNotes={du}"
              + (f"  err={err}" if err else ""))

        per_file.append({
            "file": f.name,
            "notes": n,
            "duration_sec": d,
            "bars": b,
            "density": dens,
            "bar_reversals": br,
            "duplicate_notes": du,
        })
        densities.append(dens)

    if not densities:
        print("[ERROR] 유효 파일 0건")
        return 2

    print("=" * 72)
    print(f"Aggregate ({len(densities)} files):")
    print(f"  density — mean={mean(densities):.2f}  "
          f"median={median(densities):.2f}  "
          f"stdev={pstdev(densities):.2f}  "
          f"min={min(densities):.2f}  max={max(densities):.2f}")
    print(f"  FSM violations — bar_reversals={violations_total}  "
          f"duplicate_notes={dup_total}")

    # Pass/fail
    failures = []
    if input_density:
        ratios = [d / input_density for d in densities]
        out_of_range = sum(1 for r in ratios if not (0.5 <= r <= 1.5))
        if out_of_range:
            failures.append(f"{out_of_range}/{len(ratios)} 파일 density 0.5-1.5 범위 이탈")
    if violations_total > 0:
        failures.append(f"bar_reversals={violations_total}")
    if dup_total > 0:
        failures.append(f"duplicate_notes={dup_total}")

    if failures:
        print(f"[FAIL] {'; '.join(failures)}")
    else:
        print("[PASS] 전 항목 정상")

    if out:
        report = {
            "input_density": input_density,
            "per_file": per_file,
            "aggregate": {
                "count": len(densities),
                "density_mean": mean(densities),
                "density_median": median(densities),
                "density_stdev": pstdev(densities),
                "density_min": min(densities),
                "density_max": max(densities),
                "bar_reversals_total": violations_total,
                "duplicate_notes_total": dup_total,
            },
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)
        print(f"Report: {out}")

    return 1 if failures else 0


def _classify_audio_if_available(audio: Path) -> dict | None:
    """Sprint 45 III5 — tone_classify 연동 (optional)."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))
        from tone_classify import classify_other
        family, conf, info = classify_other(audio)
        return {"family": family, "confidence": conf,
                "scores": info.get("scores")}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gen_dir", default="./output", help="생성 MIDI 폴더")
    ap.add_argument("--input_midi", default=None,
                    help="기준 입력 MIDI (density 비율 계산용, 선택)")
    ap.add_argument("--audio", default=None,
                    help="원본 오디오 (tone_classify 결과 리포트에 포함, Sprint 45 III5)")
    ap.add_argument("--out", default=None, help="JSON 리포트 경로 (선택)")
    args = ap.parse_args()

    rc = measure(
        Path(args.gen_dir),
        Path(args.input_midi) if args.input_midi else None,
        Path(args.out) if args.out else None,
    )

    # Sprint 45 III5 — tone 정보를 기존 리포트에 덧붙이기 (비침습적)
    if args.audio and args.out and Path(args.out).exists():
        tone = _classify_audio_if_available(Path(args.audio))
        if tone:
            import json as _json
            try:
                with open(args.out, "r", encoding="utf-8") as fp:
                    rep = _json.load(fp)
                rep["tone_classify"] = tone
                with open(args.out, "w", encoding="utf-8") as fp:
                    _json.dump(rep, fp, ensure_ascii=False, indent=2)
                print(f"[tone] family={tone.get('family')} "
                      f"conf={tone.get('confidence', 0):.2f}")
            except Exception as e:
                print(f"[tone] 리포트 패치 실패: {e}")

    sys.exit(rc)


if __name__ == "__main__":
    main()
