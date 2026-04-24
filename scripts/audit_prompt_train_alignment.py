"""Prompt/Train format 정합성 자동 진단 (Sprint ZZZ — S11).

테스터 검토의견(2026-04-23) §[14-2] 권고:

    지금 학습에서 본 입력 형식과 실제 DAW/engine 이 추론 때 넣는 입력
    형식이 조금이라도 다르면 task generalization 이 약해질 수 있다.
    아래를 정확히 맞춰야 한다.
      - task token
      - start_bar / end_bar
      - target_track
      - context track ordering
      - separator placement
      - output start convention

이 스크립트는 단일 MIDI 파일에 대해 **학습 경로** 와 **추론 경로** 가
각각 만들어내는 input 시퀀스를 산출하고, 항목별로 자동 diff 한다.
모델 로드는 필요 없음 — encoder 와 vocab 만 사용.

학습 경로 (build_task_pairs → dataset._get_sft):
    combined = pair["input"] + [SEP] + pair["output"]
  - pair["input"]  : context 트랙만 남긴 pm encode (BOS 포함)
  - pair["output"] : target 트랙만 encode (BOS 제거)

추론 경로 (inference_server → engine.generate_to_midi):
    input_ids = encoder.encode_file(full MIDI, meta)
    if input_ids[-1] == EOS: drop
    input_ids.append(SEP)
    if target_track: input_ids.append(Track_<target>)
  - 전체 MIDI (context + target) 를 전부 encode
  - target_track 이 입력에 이미 포함됨

이 두 경로가 얼마나 다른지 진단한다.

사용:
    python scripts/audit_prompt_train_alignment.py
    python scripts/audit_prompt_train_alignment.py \\
        --midi_path "midi_data_combined/HIPHOP 63 4-4 ALL.mid" \\
        --task strings_from_context
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from midigpt.tokenizer.encoder import MidiEncoder, SongMeta
from midigpt.tokenizer.vocab import VOCAB
from midigpt.build_task_pairs import build_pairs_for_task, TASKS


def _tokens(ids: list[int]) -> list[str]:
    return [VOCAB.decode_id(t) for t in ids]


def _summarize(ids: list[int], label: str) -> dict:
    """Extract a structured snapshot of a token sequence."""
    toks = _tokens(ids)
    prefix_counter: Counter[str] = Counter()
    bar_vals: list[int] = []
    tracks: list[str] = []
    pitches: list[int] = []
    special_positions: dict[str, list[int]] = {
        "<BOS>": [], "<EOS>": [], "<SEP>": [], "<PAD>": [],
    }
    for i, tok in enumerate(toks):
        if tok in special_positions:
            special_positions[tok].append(i)
        prefix = tok.split("_", 1)[0]
        prefix_counter[prefix] += 1
        if tok.startswith("Bar_"):
            try:
                bar_vals.append(int(tok.split("_")[1]))
            except ValueError:
                pass
        elif tok.startswith("Track_"):
            tracks.append(tok)
        elif tok.startswith("Pitch_"):
            try:
                pitches.append(int(tok.split("_")[1]))
            except ValueError:
                pass
    return {
        "label":            label,
        "length":           len(ids),
        "prefix_counts":    dict(prefix_counter),
        "special_pos":      special_positions,
        "bar_range":        (min(bar_vals), max(bar_vals)) if bar_vals else None,
        "bar_count":        len(bar_vals),
        "track_tokens":     tracks,
        "pitch_count":      len(pitches),
        "pitch_range":      (min(pitches), max(pitches)) if pitches else None,
    }


def _print_snapshot(snap: dict) -> None:
    print(f"\n── {snap['label']} ──")
    print(f"   length           = {snap['length']}")
    print(f"   bar_count        = {snap['bar_count']}  "
          f"range={snap['bar_range']}")
    print(f"   pitch_count      = {snap['pitch_count']}  "
          f"range={snap['pitch_range']}")
    print(f"   track_tokens     = {snap['track_tokens']}")
    sp = snap["special_pos"]
    print(f"   <BOS> positions  = {sp['<BOS>']}")
    print(f"   <SEP> positions  = {sp['<SEP>']}")
    print(f"   <EOS> positions  = {sp['<EOS>']}")
    print(f"   <PAD> positions  = {sp['<PAD>']}")
    print(f"   prefix counts    = {snap['prefix_counts']}")


def _split_on_sep(ids: list[int]) -> tuple[list[int], list[int]]:
    sep_id = VOCAB.sep_id
    try:
        idx = ids.index(sep_id)
    except ValueError:
        return ids, []
    return ids[:idx], ids[idx + 1:]


def _diff(train_snap: dict, infer_snap: dict,
          train_ids: list[int], infer_ids: list[int],
          target_track: str) -> int:
    print("\n" + "=" * 60)
    print("  [DIFF] train vs inference")
    print("=" * 60)
    mismatches = 0

    # Length
    if train_snap["length"] != infer_snap["length"]:
        print(f"  [~] length differs: train={train_snap['length']} "
              f"vs infer={infer_snap['length']}")

    # BOS / SEP / EOS presence
    if train_snap["special_pos"]["<SEP>"] != infer_snap["special_pos"]["<SEP>"]:
        print(f"  [!] <SEP> position differs: "
              f"train={train_snap['special_pos']['<SEP>']} "
              f"vs infer={infer_snap['special_pos']['<SEP>']}")
        mismatches += 1

    # Target track presence in INPUT (pre-SEP) portion — the critical axis.
    train_input, train_output = _split_on_sep(train_ids)
    infer_input, infer_output = _split_on_sep(infer_ids)

    def _has_track_in(ids: list[int], track_name: str) -> bool:
        needle = f"Track_{track_name}"
        return any(VOCAB.decode_id(t) == needle for t in ids)

    train_input_has_target = _has_track_in(train_input, target_track)
    infer_input_has_target = _has_track_in(infer_input, target_track)

    print(f"\n  [CRITICAL] target_track='{target_track}' in INPUT region:")
    print(f"    train input : {train_input_has_target}")
    print(f"    infer input : {infer_input_has_target}")
    if train_input_has_target != infer_input_has_target:
        print(f"  [!] 대단히 큰 분포 불일치 — 학습은 target 이 없는 문맥을 "
              f"보고 target 을 생성하도록 배웠는데 추론은 target 이 이미 "
              f"있는 문맥을 넣는다. 또는 그 반대. task generalization 약화 "
              f"원인 1순위.")
        mismatches += 1

    # Post-SEP token
    def _first_non_empty(ids: list[int]) -> str | None:
        return VOCAB.decode_id(ids[0]) if ids else None

    train_first_out = _first_non_empty(train_output)
    infer_first_out = _first_non_empty(infer_output)
    print(f"\n  Post-<SEP> first token:")
    print(f"    train : {train_first_out}")
    print(f"    infer : {infer_first_out}")
    if train_first_out != infer_first_out:
        # not always a bug — infer intentionally inserts Track_<target>.
        print(f"  [i] 구조적 차이 — 추론은 Track_<target> 힌트를 SEP 뒤에 "
              f"명시적으로 삽입. 학습 pair 의 output 첫 토큰이 Track_ 이 "
              f"아니면 모델이 Track_ 뒤에 무엇이 와야 할지 약하게 학습됐을 "
              f"수 있음.")

    # Bar range
    if (train_snap["bar_range"] and infer_snap["bar_range"]
            and train_snap["bar_range"] != infer_snap["bar_range"]):
        print(f"\n  [~] bar_range differs: train={train_snap['bar_range']} "
              f"vs infer={infer_snap['bar_range']}")

    # Track token set in whole sequence
    train_tracks = set(train_snap["track_tokens"])
    infer_tracks = set(infer_snap["track_tokens"])
    if train_tracks != infer_tracks:
        only_train = train_tracks - infer_tracks
        only_infer = infer_tracks - train_tracks
        print(f"\n  [~] Track_* 토큰 집합 다름:")
        if only_train:
            print(f"    train 만: {sorted(only_train)}")
        if only_infer:
            print(f"    infer 만: {sorted(only_infer)}")

    return mismatches


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--midi_path", type=Path,
                    default=Path("midi_data_combined/CITY POP 105 4-4 ALL.mid"),
                    help="Input MIDI file (default: CITY POP 105 샘플)")
    ap.add_argument("--task", default="drums_from_context",
                    choices=list(TASKS.keys()))
    ap.add_argument("--max_pair_tokens", type=int, default=2040)
    args = ap.parse_args()

    if not args.midi_path.is_absolute():
        args.midi_path = REPO_ROOT / args.midi_path
    if not args.midi_path.exists():
        print(f"[FATAL] MIDI not found: {args.midi_path}")
        sys.exit(2)

    target_track = TASKS[args.task]["target"]

    encoder = MidiEncoder()

    # ----- Training path -----
    print("=" * 60)
    print(f"  Prompt/Train Format Alignment Audit — S11")
    print(f"  MIDI: {args.midi_path.name}")
    print(f"  Task: {args.task}  (target={target_track})")
    print("=" * 60)

    pairs, drop = build_pairs_for_task(
        args.midi_path, args.task, encoder,
        max_pair_tokens=args.max_pair_tokens)
    if not pairs:
        print(f"[FATAL] build_pairs_for_task dropped with reason={drop}")
        print("       Pick another MIDI or task whose pair survives.")
        sys.exit(3)
    pair = pairs[0]
    # Dataset _get_sft mirror: input + SEP + output (no BOS/EOS wrap here;
    # pair["input"] already contains BOS, pair["output"] already stripped BOS)
    train_combined = pair["input"] + [VOCAB.sep_id] + pair["output"]

    # ----- Inference path -----
    # generate_to_midi encodes the WHOLE MIDI, drops trailing EOS, then
    # appends SEP + Track_<target>.
    meta = SongMeta(key="C", style="pop", section="chorus", tempo=120.0)
    infer_input_ids = encoder.encode_file(str(args.midi_path), meta=meta)
    if infer_input_ids and infer_input_ids[-1] == VOCAB.eos_id:
        infer_input_ids = infer_input_ids[:-1]
    # Assume LoRA active (testers' path)
    infer_input_ids.append(VOCAB.sep_id)
    track_tok = f"Track_{target_track}"
    tid = VOCAB.encode_token(track_tok)
    if tid != VOCAB.unk_id:
        infer_input_ids.append(tid)

    # Snapshots + diff
    train_snap = _summarize(train_combined, "TRAIN (build_task_pairs + SEP + output)")
    infer_snap = _summarize(infer_input_ids, "INFER (encode_file + SEP + Track_hint)")
    _print_snapshot(train_snap)
    _print_snapshot(infer_snap)

    critical_mismatches = _diff(
        train_snap, infer_snap,
        train_combined, infer_input_ids,
        target_track=target_track)

    print()
    print("=" * 60)
    if critical_mismatches == 0:
        print("  정합성 OK (구조적 차이는 있을 수 있음 — [i] 참고)")
        sys.exit(0)
    print(f"  CRITICAL mismatches: {critical_mismatches}")
    print("  모델의 task generalization 약화 원인 후보 — 분포 정렬 검토 필요")
    sys.exit(1)


if __name__ == "__main__":
    main()
