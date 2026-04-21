"""
Sprint XXX — task-specific SFT pair builder
===========================================

Partner review §20-6 ("task-specific SFT pair 구조를 별도로 설계") 의 scaffold.
기존 ``build_sft_pairs.py`` 는 generic continuation / variation / track-
completion 을 다루고, 이 스크립트는 **edit-task 별로 input→output 을 분리**해
저장한다.

지원 태스크
-----------
drums_from_context
    멜로디 + 피아노/코드 문맥 → 드럼 트랙 생성 (§10-2 첫 검증 태스크).
bass_from_chords
    코드 + 멜로디 → 베이스 라인 생성.
piano_from_chords
    코드 + 멜로디 → 피아노 반주 (comp) 생성.
strings_from_context
    멜로디 + 코드 + 피아노 → 스트링 지원 라인.
guitar_from_context
    멜로디 + 코드 → 기타 pluck / strum.

공통 원칙
---------
- **Input tracks** 는 선택된 카테고리 집합을 pm 에서 남기고 나머지 제거 후
  tokenizer 로 인코딩. 학습 시 모델은 "이 문맥이 주어졌을 때" 를 본다.
- **Output tracks** 는 target 카테고리만 남긴 pm. 모델이 뽑아야 할
  정답.
- 저장 파일명: ``task_{drums_from_context|bass_from_chords|…}_{idx:04d}.json``
  → 기존 ``sft_*.json`` glob 와 **충돌하지 않도록** 접두사를 분리 (rule
  05-A 회귀 방지). dataset.py 는 pair_glob 인자로 원하는 접두사만 로딩.

스키마
------
각 pair 는 다음 JSON 을 저장:

.. code-block:: json

    {
        "input":  [int, ...],
        "output": [int, ...],
        "metadata": {
            "task":         "drums_from_context",
            "source":       "<원본 파일명>",
            "context_tracks": ["melody", "accomp"],
            "target_track":   "drums",
            "input_tokens":   123,
            "output_tokens":  456
        }
    }

사용
----
.. code-block:: bash

    python -m midigpt.build_task_pairs \\
        --midi_dir ./midi_data_combined \\
        --output_dir ./midigpt_pipeline/task_pairs \\
        --tasks drums_from_context,bass_from_chords

단일 태스크 먼저 실험하려면 ``--tasks drums_from_context`` 로 좁힌다.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import pretty_midi  # noqa: F401
except ImportError:
    print("[FATAL] pretty_midi 필요: pip install pretty_midi")
    sys.exit(1)

from midigpt.tokenizer.encoder import MidiEncoder  # noqa: E402
from midigpt.tokenizer.vocab import VOCAB          # noqa: E402


# ---------------------------------------------------------------------------
# Task registry — context set / target / description
# ---------------------------------------------------------------------------
TASKS = {
    "drums_from_context": {
        "context": {"melody", "accomp", "bass"},
        "target":  "drums",
        "min_context_tracks": 1,  # 적어도 1 개 문맥 트랙이 있어야 pair 성립
    },
    "bass_from_chords": {
        "context": {"melody", "accomp"},
        "target":  "bass",
        "min_context_tracks": 1,
    },
    "piano_from_chords": {
        "context": {"melody", "bass"},
        "target":  "accomp",  # 피아노 comp 는 accomp 카테고리로 학습
        "min_context_tracks": 1,
    },
    "strings_from_context": {
        "context": {"melody", "accomp", "bass"},
        "target":  "strings",
        "min_context_tracks": 2,
    },
    "guitar_from_context": {
        "context": {"melody", "accomp", "bass"},
        "target":  "guitar",
        "min_context_tracks": 1,
    },
}


# ---------------------------------------------------------------------------
# Track classification — mirrors encoder._classify_track semantics.
# We import that function if it's public; otherwise fall back to a minimal
# name/program based classifier. This keeps the task-pair builder robust to
# refactors in encoder.py.
# ---------------------------------------------------------------------------
def _classify_track(inst) -> str:
    """Best-effort category for a pretty_midi Instrument.

    Falls back to encoder's implementation when available.
    """
    try:
        from midigpt.tokenizer.encoder import MidiEncoder as _ME
        e = _ME()
        if hasattr(e, "_classify_track"):
            return e._classify_track(inst)  # type: ignore[attr-defined]
    except Exception:
        pass

    # Fallback: drums handled by is_drum channel, else name/program crude
    # match. Good enough for this scaffold; real builds rely on encoder.
    if getattr(inst, "is_drum", False):
        return "drums"
    name = (getattr(inst, "name", "") or "").lower()
    for kw, cat in (
        ("drum", "drums"), ("kick", "drums"), ("snare", "drums"),
        ("bass", "bass"),
        ("violin", "strings"), ("viola", "strings"), ("cello", "strings"),
        ("string", "strings"),
        ("guitar", "guitar"),
        ("vocal", "vocal"), ("vox", "vocal"),
        ("brass", "brass"), ("trumpet", "brass"), ("trombone", "brass"),
    ):
        if kw in name:
            return cat
    return "accomp"


def _split_pm_by_category(pm, context_cats: set, target_cat: str):
    """Return (pm_context, pm_target) where pm_context keeps only
    instruments in ``context_cats`` and pm_target keeps only instruments
    classified as ``target_cat``. Both copies share no mutable state with
    the original.
    """
    pm_ctx = copy.deepcopy(pm)
    pm_tgt = copy.deepcopy(pm)
    pm_ctx.instruments = [
        inst for inst in pm_ctx.instruments
        if _classify_track(inst) in context_cats
    ]
    pm_tgt.instruments = [
        inst for inst in pm_tgt.instruments
        if _classify_track(inst) == target_cat
    ]
    return pm_ctx, pm_tgt


def build_pairs_for_task(
    midi_path: Path,
    task_name: str,
    encoder: MidiEncoder,
    max_pair_tokens: int = 2040,
) -> list[dict]:
    """Produce zero or one pair for ``midi_path`` under ``task_name``.

    Returns a list (possibly empty) to match the existing builder pattern.
    """
    if task_name not in TASKS:
        raise ValueError(f"Unknown task: {task_name}")

    spec = TASKS[task_name]

    try:
        import pretty_midi as _pm
        pm = _pm.PrettyMIDI(str(midi_path))
    except (OSError, ValueError, IndexError):
        return []

    if not pm.instruments:
        return []

    pm_ctx, pm_tgt = _split_pm_by_category(pm, spec["context"], spec["target"])

    # Guard: both sides need content.
    if len(pm_ctx.instruments) < spec["min_context_tracks"]:
        return []
    if not pm_tgt.instruments:
        return []
    if not any(inst.notes for inst in pm_ctx.instruments):
        return []
    if not any(inst.notes for inst in pm_tgt.instruments):
        return []

    try:
        ctx_ids = encoder.encode_pretty_midi(pm_ctx)
        tgt_ids = encoder.encode_pretty_midi(pm_tgt)
    except (IndexError, ValueError, KeyError):
        return []

    # Strip BOS from output, EOS from input (same convention as
    # build_sft_pairs).
    if tgt_ids and tgt_ids[0] == VOCAB.bos_id:
        tgt_ids = tgt_ids[1:]
    if ctx_ids and ctx_ids[-1] == VOCAB.eos_id:
        ctx_ids = ctx_ids[:-1]

    if len(ctx_ids) < 10 or len(tgt_ids) < 10:
        return []
    if len(ctx_ids) + len(tgt_ids) > max_pair_tokens:
        return []

    return [{
        "input":  ctx_ids,
        "output": tgt_ids,
        "metadata": {
            "task":           task_name,
            "source":         midi_path.name,
            "context_tracks": sorted(spec["context"]),
            "target_track":   spec["target"],
            "input_tokens":   len(ctx_ids),
            "output_tokens":  len(tgt_ids),
        },
    }]


def main():
    ap = argparse.ArgumentParser(
        description="Build task-specific SFT pairs (Sprint XXX)")
    ap.add_argument("--midi_dir", required=True, type=Path)
    ap.add_argument("--output_dir", required=True, type=Path)
    ap.add_argument(
        "--tasks",
        default="drums_from_context",
        help="콤마로 구분한 태스크 이름 (기본: drums_from_context)",
    )
    ap.add_argument(
        "--max_pair_tokens",
        type=int,
        default=2040,
        help="모델 max_seq_len (2048) 대비 약간의 여유 둔 상한",
    )
    args = ap.parse_args()

    tasks: list[str] = [t.strip() for t in args.tasks.split(",") if t.strip()]
    unknown = [t for t in tasks if t not in TASKS]
    if unknown:
        print(f"[FATAL] unknown tasks: {unknown}")
        sys.exit(2)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    encoder = MidiEncoder()

    midi_files = sorted(args.midi_dir.rglob("*.mid")) \
                 + sorted(args.midi_dir.rglob("*.midi"))
    if not midi_files:
        print(f"[FATAL] no MIDI files under {args.midi_dir}")
        sys.exit(3)

    counts = {t: 0 for t in tasks}
    skipped = {t: 0 for t in tasks}
    per_task_idx = {t: 0 for t in tasks}

    for mf in midi_files:
        for task in tasks:
            pairs = build_pairs_for_task(
                mf, task, encoder, max_pair_tokens=args.max_pair_tokens)
            if not pairs:
                skipped[task] += 1
                continue
            for p in pairs:
                fn = args.output_dir / f"task_{task}_{per_task_idx[task]:05d}.json"
                with open(fn, "w", encoding="utf-8") as f:
                    json.dump(p, f, ensure_ascii=False)
                per_task_idx[task] += 1
                counts[task] += 1

    print("=" * 60)
    print(f"Output: {args.output_dir}")
    for t in tasks:
        print(f"  {t:<28} pairs={counts[t]:5d}  skipped={skipped[t]:5d}")
    print("=" * 60)


if __name__ == "__main__":
    main()
