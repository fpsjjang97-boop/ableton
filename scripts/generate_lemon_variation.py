"""Lemon 변주 생성 — MidiGPT inference engine 직접 호출 (서버 거치지 않음).

전사된 Lemon MIDI 를 입력으로 2가지 변주를 생성:
    v1: conservative  (temp=0.7, seed=42)  — 원곡과 가까운 변주
    v2: creative      (temp=1.05, seed=1337) — 멜로디 크게 변형

각 변주는 B minor key 유지 (원곡 기준), 86 BPM, section=chorus.

의존: 서버 불필요 — InferenceEngine 직접 호출.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main():
    from midigpt.inference.engine import InferenceConfig, MidiGPTInference
    from midigpt.tokenizer.encoder import SongMeta

    input_midi = REPO_ROOT / "audio_to_midi_output" / "Lemon" / "Lemon_refined.mid"
    if not input_midi.exists():
        print(f"[ERROR] 입력 없음: {input_midi}")
        sys.exit(1)

    output_dir = REPO_ROOT / "output" / "Lemon"
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = InferenceConfig(
        model_path=str(REPO_ROOT / "checkpoints" / "midigpt_best.pt"),
        device="auto",
    )
    print("[1/4] 모델 로드...")
    t0 = time.time()
    engine = MidiGPTInference(cfg)
    print(f"    로드 완료 ({time.time()-t0:.1f}s)")
    print(f"    status: {engine.get_status()}")

    variations = [
        # (name, temperature, top_k, top_p, seed_suffix)
        ("conservative",  0.7,  40, 0.9,   "t07"),
        ("creative",      1.05, 60, 0.95,  "t105"),
    ]

    for name, temp, topk, topp, suffix in variations:
        out = output_dir / f"Lemon_variation_{name}.mid"
        print(f"\n[{len(variations)+1-variations.index((name, temp, topk, topp, suffix))}/"
              f"{len(variations)+1}] {name} (T={temp}, top_k={topk}, top_p={topp})...")
        t1 = time.time()
        meta = SongMeta(tempo=86.1, key="B", style="base", section="chorus")
        try:
            result = engine.generate_to_midi(
                midi_path=str(input_midi),
                output_path=str(out),
                meta=meta,
                max_tokens=2048,
                min_new_tokens=512,
                temperature=temp,
                top_k=topk,
                top_p=topp,
                repetition_penalty=1.1,
                no_repeat_ngram_size=4,
                use_grammar=True,
                grammar_dedup_pitches=True,
            )
            print(f"    → {out.name}  ({time.time()-t1:.1f}s)")
        except Exception as e:
            print(f"    [FAIL] {type(e).__name__}: {e}")

    print(f"\n전체 소요: {time.time()-t0:.1f}s")
    print(f"출력 폴더: {output_dir}")


if __name__ == "__main__":
    main()
