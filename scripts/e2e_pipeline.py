"""오프라인 E2E 파이프라인 — audio → transcribe → refine → report (Sprint 44 HHH5).

서버 불필요. 단일 오디오 입력부터 정제된 MIDI + 품질 리포트까지 한 번에.
데모 환경/CI 에서 "파이프라인 안 깨졌는지" 보는 최종 게이트.

흐름:
    1. convert.convert_single(audio, --refine)     → *_refined.mid
    2. measure_generation_quality 로 노트 밀도/FSM 위반 리포트
    3. tone_classify (선택) 로 악기 family 추정
    4. JSON 리포트 저장

사용:
    python scripts/e2e_pipeline.py --audio input.wav --out report.json
    python scripts/e2e_pipeline.py --audio input.wav --out report.json --no-refine

종료 코드:
    0 = 파이프라인 전부 성공
    1 = 도중 실패 (리포트는 부분적으로 저장됨)
    2 = 입력 없음
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _measure(midi_path: Path) -> dict:
    """measure_generation_quality 의 핵심 로직만 추출 (subprocess 없이 직접)."""
    import pretty_midi
    from midigpt.tokenizer.encoder import MidiEncoder
    from midigpt.tokenizer.vocab import VOCAB
    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as e:
        return {"error": f"parse: {type(e).__name__}: {e}"}
    n = sum(len(i.notes) for i in pm.instruments)
    dur = pm.get_end_time()
    tempo = 120.0
    try:
        _, bpm = pm.get_tempo_changes()
        if len(bpm) > 0:
            tempo = float(bpm[0])
    except Exception:
        pass
    bars = max(1e-6, dur * tempo / 60.0 / 4.0)
    density = n / bars

    # FSM violations
    enc = MidiEncoder()
    try:
        ids = enc.encode_file(str(midi_path))
        tokens = VOCAB.decode_ids(ids)
    except Exception:
        return {
            "notes": n, "duration_sec": dur, "bars": bars, "density": density,
            "bar_reversals": None, "duplicate_notes": None,
        }
    bar_rev = 0
    last_bar = -1
    dup = 0
    prev = None
    cb = cp = None
    for t in tokens:
        if t.startswith("Bar_"):
            try:
                b = int(t.split("_")[1])
                if b < last_bar:
                    bar_rev += 1
                last_bar = b
                cb = t
            except ValueError:
                pass
        elif t.startswith("Pos_"):
            cp = t
        elif t.startswith("Pitch_"):
            sig = (cb, cp, t)
            if sig == prev and cb:
                dup += 1
            prev = sig
    return {
        "notes": n, "duration_sec": dur, "bars": bars, "density": density,
        "bar_reversals": bar_rev, "duplicate_notes": dup,
    }


def run_pipeline(audio: Path, out: Path, do_refine: bool, do_tone: bool,
                 output_dir: Path) -> int:
    report: dict = {
        "input_audio": str(audio),
        "output_dir": str(output_dir),
        "steps": {},
    }
    t0 = time.time()

    # 1. convert_single
    print(f"[1/3] transcribe (refine={do_refine})...")
    try:
        from convert import convert_single
        result_path = convert_single(
            audio_path=audio, output_dir=output_dir,
            keep_vocals=False, no_merge=False, refine=do_refine,
        )
    except Exception as e:
        report["steps"]["transcribe"] = {
            "ok": False, "error": f"{type(e).__name__}: {e}",
        }
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        return 1

    if result_path is None or not Path(result_path).exists():
        report["steps"]["transcribe"] = {"ok": False, "error": "no output"}
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        return 1

    report["steps"]["transcribe"] = {
        "ok": True, "midi_path": str(result_path),
        "elapsed_sec": time.time() - t0,
    }
    print(f"      -> {result_path}")

    # 2. quality measurement
    print("[2/3] measure quality...")
    quality = _measure(Path(result_path))
    report["steps"]["quality"] = quality
    print(f"      notes={quality.get('notes')}  density={quality.get('density'):.2f}  "
          f"dup={quality.get('duplicate_notes')}")

    # 3. tone classify (optional)
    if do_tone:
        print("[3/3] tone classify...")
        try:
            from tone_classify import classify_other
            family, conf, info = classify_other(audio)
            report["steps"]["tone"] = {
                "family": family, "confidence": conf,
                "scores": info.get("scores"),
            }
            print(f"      family={family}  confidence={conf:.2f}")
        except Exception as e:
            report["steps"]["tone"] = {
                "ok": False, "error": f"{type(e).__name__}: {e}",
            }

    report["total_elapsed_sec"] = time.time() - t0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n[OK] 리포트: {out}  ({report['total_elapsed_sec']:.1f}s)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--audio", required=True, help="입력 오디오 (wav/mp3)")
    ap.add_argument("--out", default="./output/e2e_pipeline_report.json")
    ap.add_argument("--output_dir", default="./audio_to_midi_output")
    ap.add_argument("--no-refine", action="store_true",
                    help="Sprint 43 source-filter refine 비활성화")
    ap.add_argument("--tone", action="store_true",
                    help="tone_classify 추가 실행 (Sprint 44 HHH3)")
    args = ap.parse_args()

    audio = Path(args.audio)
    if not audio.exists():
        print(f"[ERROR] 입력 없음: {audio}")
        sys.exit(2)

    sys.exit(run_pipeline(
        audio=audio, out=Path(args.out),
        do_refine=not args.no_refine, do_tone=args.tone,
        output_dir=Path(args.output_dir),
    ))


if __name__ == "__main__":
    main()
