"""Dump raw token sequence from a generation run for gap/duplicate diagnosis.

6차 리포트 변경 3 진단 유틸 — "무음 중간 구간"이 (a) 모델이 Bar 토큰을
건너뛰어 발생하는지 (b) 디코더가 노트를 누락하는지 (c) Pos 이후 pitch
그룹 없이 다음 Pos 로 넘어가는지 구분하기 위한 정보를 제공한다.

사용법:
    python tools/dump_generated_tokens.py \
        --input "./TEST MIDI/어떤파일.mid" \
        --output ./output/generated.mid \
        --tokens_out ./output/generated_tokens.txt

동작:
    1) 입력 MIDI 로 generate 를 돌려 토큰 시퀀스를 얻는다.
    2) 토큰을 Bar 마커 기준으로 그룹핑하여 읽기 쉬운 txt 로 저장한다.
    3) 각 Bar 그룹 내에서 (Pos, Track, Pitch, Vel, Dur) 구조를 그대로 출력.
    4) 생성된 MIDI 도 함께 저장 (표준 경로는 engine 의 decode_to_midi 이용).

출력 예시:
    === Bar 0 ===
      Pos 0 | Track accomp | Pitch 60 Vel 8 Dur 4
      Pos 0 | Track accomp | Pitch 64 Vel 8 Dur 4  ← 같은 Pos 동일 pitch 중복이면 여기 보임
      Pos 4 | Track accomp | Pitch 67 Vel 8 Dur 4
    === Bar 1 ===   ← 갭이 있으면 Bar 0 다음이 Bar 5 처럼 건너뛰어 보임
      ...
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    # rules/03-windows-compat.md §3.2 — 한글 파일명/출력 보장
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from midigpt.inference.engine import InferenceConfig, MidiGPTInference
from midigpt.tokenizer.encoder import SongMeta
from midigpt.tokenizer.vocab import VOCAB


def dump_tokens(token_ids: list[int], out_path: Path) -> dict:
    """Write a Bar-grouped dump of tokens. Returns a stats dict."""
    tokens = VOCAB.decode_ids(token_ids)

    stats = {
        "total_tokens": len(tokens),
        "bar_markers": 0,
        "pos_markers": 0,
        "pitch_tokens": 0,
        "unknown_tokens": 0,
        "bar_sequence": [],       # e.g. [0, 1, 2, 5, 6] — gap between 2 and 5
        "max_bar_jump": 0,
        "dupes_same_bar_pos_pitch": 0,
    }

    seen_bp_pitch: set[tuple[int, int, int]] = set()
    current_bar = 0
    current_pos = 0

    lines: list[str] = []
    lines.append(f"# Raw tokens dump — {len(tokens)} tokens")
    lines.append("")

    last_bar = None
    for tok in tokens:
        if tok.startswith("<"):
            lines.append(f"<SPECIAL> {tok}")
            continue
        if tok.startswith("Bar_"):
            try:
                current_bar = int(tok.split("_")[1])
            except ValueError:
                stats["unknown_tokens"] += 1
                continue
            stats["bar_markers"] += 1
            if last_bar is not None:
                stats["max_bar_jump"] = max(
                    stats["max_bar_jump"], current_bar - last_bar
                )
            stats["bar_sequence"].append(current_bar)
            last_bar = current_bar
            lines.append(f"")
            lines.append(f"=== Bar {current_bar} ===")
            continue
        if tok.startswith("Pos_"):
            try:
                current_pos = int(tok.split("_")[1])
            except ValueError:
                stats["unknown_tokens"] += 1
                continue
            stats["pos_markers"] += 1
            lines.append(f"  Pos {current_pos}")
            continue
        if tok.startswith("Pitch_"):
            try:
                pitch = int(tok.split("_")[1])
            except ValueError:
                stats["unknown_tokens"] += 1
                continue
            stats["pitch_tokens"] += 1
            key = (current_bar, current_pos, pitch)
            dup_marker = ""
            if key in seen_bp_pitch:
                stats["dupes_same_bar_pos_pitch"] += 1
                dup_marker = "   ← DUP"
            seen_bp_pitch.add(key)
            lines.append(f"    Pitch {pitch}{dup_marker}")
            continue
        # Everything else — include raw token for context but don't parse
        lines.append(f"    {tok}")

    lines.append("")
    lines.append("# --- stats ---")
    for k, v in stats.items():
        if k == "bar_sequence":
            # Only show first 40 bars to keep file readable
            preview = v[:40]
            suffix = " ..." if len(v) > 40 else ""
            lines.append(f"#   {k}: {preview}{suffix}")
        else:
            lines.append(f"#   {k}: {v}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate and dump raw token sequence for gap/duplicate diagnosis."
    )
    parser.add_argument("--input", required=True, help="Input MIDI file")
    parser.add_argument("--output", default="./output/debug_generated.mid",
                        help="Output MIDI path")
    parser.add_argument("--tokens_out", default="./output/debug_tokens.txt",
                        help="Where to write the token dump")
    parser.add_argument("--model", default="./checkpoints/midigpt_latest.pt")
    parser.add_argument("--max_tokens", type=int, default=1024)
    parser.add_argument("--temperature", type=float, default=0.85)
    parser.add_argument("--tempo", type=float, default=120.0)
    parser.add_argument("--key", default="C")
    parser.add_argument("--style", default="pop")
    parser.add_argument("--section", default="verse")
    args = parser.parse_args()

    config = InferenceConfig(model_path=args.model, device="cuda")
    engine = MidiGPTInference(config)
    print(engine.get_status())

    meta = SongMeta(
        tempo=args.tempo, key=args.key, style=args.style, section=args.section,
    )

    # The engine exposes generate_to_midi; we need the raw tokens too.
    # Use the lower-level API if available, otherwise re-generate.
    if hasattr(engine, "generate_tokens"):
        tokens = engine.generate_tokens(
            midi_path=args.input, meta=meta,
            max_tokens=args.max_tokens, temperature=args.temperature,
        )
        # Also save the MIDI
        from midigpt.tokenizer.decoder import MidiDecoder
        MidiDecoder().decode_to_midi(tokens, args.output, tempo=args.tempo)
    else:
        # Fallback: only MIDI output is accessible, so we just log a note.
        engine.generate_to_midi(
            midi_path=args.input, output_path=args.output, meta=meta,
            max_tokens=args.max_tokens, temperature=args.temperature,
        )
        print(
            "[WARN] engine.generate_tokens not exposed — tokens dump requires\n"
            "       MidiGPTInference.generate_tokens(...). Add that method\n"
            "       (it should return the raw token id list before decode)."
        )
        return

    tokens_out = Path(args.tokens_out)
    stats = dump_tokens(tokens, tokens_out)
    print(f"\nGenerated MIDI:  {args.output}")
    print(f"Token dump:      {tokens_out}")
    print(f"Stats:")
    for k, v in stats.items():
        if k != "bar_sequence":
            print(f"  {k}: {v}")
    if stats["max_bar_jump"] > 1:
        print(
            f"\n[DIAGNOSIS] Bar 점프 최대 {stats['max_bar_jump']} 마디 발견 — "
            f"이것이 DAW 상 무음 갭의 직접 원인."
        )
    if stats["dupes_same_bar_pos_pitch"] > 0:
        print(
            f"[DIAGNOSIS] 같은 Bar/Pos/Pitch 중복 {stats['dupes_same_bar_pos_pitch']}건 — "
            f"디코더 dedup 으로 흡수됨 (decoder.py 변경 2)."
        )


if __name__ == "__main__":
    main()
