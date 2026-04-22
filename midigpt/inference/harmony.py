"""Strict chord / beat-aware harmonic constraint helpers (Sprint YYY — S4).

Background
----------
2026-04-21 종합리뷰 §5-1 ("코드 진행이 안정적으로 들리지 않음") 과 커서형정리
§7-1 ("강박에서는 chord tone 만 허용") 이 지적한 문제:

    현재 ``_apply_harmonic_mask`` 는 Pos_M 에 상관없이 **모든 박자에 동일한**
    scale mask + chord-tone boost 를 적용한다. 즉 Pos_0 (downbeat) 과 Pos_4
    (16분 오프셋) 에 같은 제약이 걸린다. 결과적으로 강박에서 D/F/A/B 같은
    scale 내 non-chord-tone 이 chord-tone 과 비슷한 확률로 샘플링되어
    "해당 코드가 귀에 들리는 반주" 가 되지 못한다.

이 모듈은 beat strength 판정과 strict mode 의 allowed pitch-class 결정을
제공한다. 마스킹 자체는 engine.py 의 ``_apply_harmonic_mask`` 가 여전히
담당(rule 05 패턴 C — 정책은 한 곳) 하고, 이 모듈은 **순수 함수** 로 scope
를 좁힌다.

Pos 해상도
----------
Vocab 은 ``Pos_{0..31}`` — 32분음표 해상도, 4/4 기준 한 마디 = 32 position.

    Pos  0 = beat 1 (downbeat)        → STRONG
    Pos  4 = beat 1 + 16th offset     → WEAK
    Pos  8 = beat 2                   → UPBEAT
    Pos 12 = beat 2 + 16th offset     → WEAK
    Pos 16 = beat 3 (downbeat)        → STRONG
    Pos 20 = beat 3 + 16th offset     → WEAK
    Pos 24 = beat 4                   → UPBEAT
    Pos 28 = beat 4 + 16th offset     → WEAK
    그 외  = 8분·16분·32분 사이 오프셋 → VERY_WEAK

정책 (strict mode)
------------------
- STRONG (downbeat) → chord tone (root/3/5/7) 만 허용. 이게 "코드가 들리게"
  만드는 핵심 축.
- UPBEAT (beat 2/4) → chord tone ∪ {2nd, 4th, 6th} 의 일부 경과음 허용.
  구체적으로 scale 전체를 허용하되 off-scale 만 계속 차단(= 기존 동작).
- WEAK / VERY_WEAK → 기존 scale mask 유지 (passing tone 자유).

이 판단 근거는 커서형정리 §7-1 의 "강박 chord tone / 약박 scale passing"
가이드라인. 향후 장르/스타일별 튜닝이 필요하면 strict_allowed_pcs 에
style 인자를 추가하는 쪽으로 확장.
"""
from __future__ import annotations

from enum import Enum


class BeatStrength(str, Enum):
    """Beat position classification within a 4/4 bar at 32nd-note resolution."""
    STRONG = "strong"       # Pos_0, Pos_16 (beats 1, 3)
    UPBEAT = "upbeat"       # Pos_8, Pos_24 (beats 2, 4)
    WEAK = "weak"           # 16th offsets (Pos_4, _12, _20, _28)
    VERY_WEAK = "very_weak"  # 32nd offsets, anything else


# Strong beats (downbeats) — chord-tone only under strict mode.
_STRONG_POSITIONS = frozenset({0, 16})
# Upbeats (beats 2, 4) — still scale-constrained but allow passing tones.
_UPBEAT_POSITIONS = frozenset({8, 24})
# 16th-note offsets — weak beat.
_WEAK_POSITIONS = frozenset({4, 12, 20, 28})


def beat_strength(pos: int) -> BeatStrength:
    """Return the beat strength for a ``Pos_M`` index (0..31).

    Out-of-range values (including the FSM sentinel ``-1`` meaning "no Pos
    emitted yet") collapse to VERY_WEAK so the caller can apply the most
    permissive constraint — safer than STRONG when context is unknown.
    """
    if pos < 0 or pos >= 32:
        return BeatStrength.VERY_WEAK
    if pos in _STRONG_POSITIONS:
        return BeatStrength.STRONG
    if pos in _UPBEAT_POSITIONS:
        return BeatStrength.UPBEAT
    if pos in _WEAK_POSITIONS:
        return BeatStrength.WEAK
    return BeatStrength.VERY_WEAK


def strict_allowed_pcs(
    scale_pcs: set[int],
    chord_tone_pcs: set[int],
    beat: BeatStrength,
) -> set[int]:
    """Narrow the allowed pitch-class set based on beat strength.

    Args:
        scale_pcs:       scale-wide allowed PCs (from _allowed_pitch_classes).
        chord_tone_pcs:  chord tones only (from _chord_tone_pitch_classes).
        beat:            from :func:`beat_strength`.

    Returns:
        The tighter of the two sets when the beat is STRONG, else the full
        scale. Callers pass this to the mask routine which drops everything
        not in the returned set.

    Rationale
    ---------
    STRONG → chord_tone_pcs. This is the single biggest lever for "coder
    진행이 귀에 들리게" per 커서형정리 §7-1.

    UPBEAT/WEAK/VERY_WEAK → scale_pcs. Matches the old behaviour so that
    passing tones, neighbour tones, and 8th-note approach tones are still
    available. The model's repetition/motif patterns mostly land here.
    """
    if beat == BeatStrength.STRONG:
        # Guard: if chord_tone_pcs is empty (unknown quality with empty
        # fallback) fall back to scale_pcs so we never fully starve the
        # sampler. _chord_tone_pitch_classes in engine.py already falls
        # back to [0,4,7] so this branch is defensive.
        return chord_tone_pcs if chord_tone_pcs else scale_pcs
    return scale_pcs
