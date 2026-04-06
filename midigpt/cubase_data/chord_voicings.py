"""
Cubase 15 기반 코드 보이싱 & 그루브 시스템
==========================================
Cubase 15 Chorder 프리셋 (Single Chords, Guitar Chords, Jazz, Octave)과
코드패드 시스템에서 추출한 보이싱 데이터를 엔진에 통합.

기능:
- 24종 코드 품질별 다중 보이싱 (클로즈, 오픈, 드롭2, 드롭3, 기타 등)
- 장르별 그루브 템플릿 (보사노바, 삼바, 레게, 펑크 등)
- Cubase 스타일 코드패드 시스템 (64 패드)
- 자동 보이스 리딩 (최소 이동 원칙)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import random


# ─── 코드 인터벌 정의 (Cubase 15 Chorder 기반) ───

# 반음 단위 인터벌 — 24종 코드 품질 (vocab.py CHORD_QUALITIES와 동기화)
CHORD_INTERVALS: dict[str, list[int]] = {
    "maj":    [0, 4, 7],
    "min":    [0, 3, 7],
    "dim":    [0, 3, 6],
    "aug":    [0, 4, 8],
    "sus2":   [0, 2, 7],
    "sus4":   [0, 5, 7],
    "7":      [0, 4, 7, 10],
    "maj7":   [0, 4, 7, 11],
    "m7":     [0, 3, 7, 10],
    "m7b5":   [0, 3, 6, 10],
    "dim7":   [0, 3, 6, 9],
    "7sus4":  [0, 5, 7, 10],
    "add9":   [0, 4, 7, 14],
    "madd9":  [0, 3, 7, 14],
    "6":      [0, 4, 7, 9],
    "m6":     [0, 3, 7, 9],
    "9":      [0, 4, 7, 10, 14],
    "m9":     [0, 3, 7, 10, 14],
    "maj9":   [0, 4, 7, 11, 14],
    "7b9":    [0, 4, 7, 10, 13],
    "7#9":    [0, 4, 7, 10, 15],
    "11":     [0, 4, 7, 10, 14, 17],
    "13":     [0, 4, 7, 10, 14, 21],
    "5":      [0, 7],
}


# ─── 보이싱 타입 (Cubase 15 Chorder Single Chords 기반) ───

@dataclass
class Voicing:
    """코드 보이싱 정의."""
    name: str
    intervals: list[int]          # 루트 기준 반음 인터벌
    velocity_curve: list[float]   # 각 음의 상대 벨로시티 (1.0 = 기준)
    spread_ms: float = 0.0       # 아르페지오 스프레드 (ms)
    description: str = ""


# Cubase 15 Chorder "Single Chords" 프리셋 기반 보이싱 라이브러리
VOICING_LIBRARY: dict[str, dict[str, list[Voicing]]] = {
    # ─── Close Position (밀집 배치) ───
    "close": {
        "maj":  [
            Voicing("Root", [0, 4, 7], [1.0, 0.85, 0.85]),
            Voicing("1st_inv", [4, 7, 12], [0.85, 0.85, 1.0]),
            Voicing("2nd_inv", [7, 12, 16], [0.85, 1.0, 0.85]),
        ],
        "min":  [
            Voicing("Root", [0, 3, 7], [1.0, 0.85, 0.85]),
            Voicing("1st_inv", [3, 7, 12], [0.85, 0.85, 1.0]),
            Voicing("2nd_inv", [7, 12, 15], [0.85, 1.0, 0.85]),
        ],
        "7":    [
            Voicing("Root", [0, 4, 7, 10], [1.0, 0.8, 0.8, 0.75]),
            Voicing("1st_inv", [4, 7, 10, 12], [0.8, 0.8, 0.75, 1.0]),
            Voicing("2nd_inv", [7, 10, 12, 16], [0.8, 0.75, 1.0, 0.8]),
            Voicing("3rd_inv", [10, 12, 16, 19], [0.75, 1.0, 0.8, 0.8]),
        ],
        "maj7": [
            Voicing("Root", [0, 4, 7, 11], [1.0, 0.8, 0.8, 0.75]),
            Voicing("1st_inv", [4, 7, 11, 12], [0.8, 0.8, 0.75, 1.0]),
        ],
        "m7":   [
            Voicing("Root", [0, 3, 7, 10], [1.0, 0.8, 0.8, 0.75]),
            Voicing("1st_inv", [3, 7, 10, 12], [0.8, 0.8, 0.75, 1.0]),
        ],
        "dim":   [Voicing("Root", [0, 3, 6], [1.0, 0.85, 0.85])],
        "aug":   [Voicing("Root", [0, 4, 8], [1.0, 0.85, 0.85])],
        "sus2":  [Voicing("Root", [0, 2, 7], [1.0, 0.85, 0.85])],
        "sus4":  [Voicing("Root", [0, 5, 7], [1.0, 0.85, 0.85])],
        "m7b5":  [Voicing("Root", [0, 3, 6, 10], [1.0, 0.8, 0.8, 0.75])],
        "dim7":  [Voicing("Root", [0, 3, 6, 9], [1.0, 0.8, 0.8, 0.75])],
        "9":     [Voicing("Root", [0, 4, 7, 10, 14], [1.0, 0.8, 0.75, 0.7, 0.8])],
        "m9":    [Voicing("Root", [0, 3, 7, 10, 14], [1.0, 0.8, 0.75, 0.7, 0.8])],
        "add9":  [Voicing("Root", [0, 4, 7, 14], [1.0, 0.85, 0.8, 0.85])],
        "6":     [Voicing("Root", [0, 4, 7, 9], [1.0, 0.8, 0.8, 0.75])],
    },

    # ─── Open Position (개방 배치 — Cubase "Major Straight/Velo" 스타일) ───
    "open": {
        "maj":  [
            Voicing("Wide", [0, 7, 12, 16], [1.0, 0.75, 0.9, 0.8]),
            Voicing("Spread", [0, 12, 16, 19], [1.0, 0.9, 0.8, 0.75]),
        ],
        "min":  [
            Voicing("Wide", [0, 7, 12, 15], [1.0, 0.75, 0.9, 0.8]),
            Voicing("Spread", [0, 12, 15, 19], [1.0, 0.9, 0.8, 0.75]),
        ],
        "7":    [
            Voicing("Wide", [0, 10, 16, 19], [1.0, 0.7, 0.8, 0.75]),
        ],
        "maj7": [
            Voicing("Wide", [0, 11, 16, 19], [1.0, 0.7, 0.85, 0.75]),
        ],
        "m7":   [
            Voicing("Wide", [0, 10, 15, 19], [1.0, 0.7, 0.8, 0.75]),
        ],
    },

    # ─── Drop 2 (재즈 표준 — Cubase "Jazz" 프리셋 기반) ───
    "drop2": {
        "maj7": [
            Voicing("Drop2_Root", [0, 11, 16, 19], [1.0, 0.75, 0.85, 0.8]),
            Voicing("Drop2_1st", [4, 12, 16, 23], [0.85, 0.9, 0.8, 0.75]),
            Voicing("Drop2_2nd", [7, 12, 16, 23], [0.8, 0.9, 0.85, 0.75]),
        ],
        "m7":   [
            Voicing("Drop2_Root", [0, 10, 15, 19], [1.0, 0.75, 0.85, 0.8]),
            Voicing("Drop2_1st", [3, 12, 15, 22], [0.85, 0.9, 0.8, 0.75]),
        ],
        "7":    [
            Voicing("Drop2_Root", [0, 10, 16, 19], [1.0, 0.75, 0.85, 0.8]),
            Voicing("Drop2_1st", [4, 12, 16, 22], [0.85, 0.9, 0.8, 0.75]),
        ],
        "m7b5": [
            Voicing("Drop2_Root", [0, 10, 15, 18], [1.0, 0.75, 0.85, 0.8]),
        ],
        "dim7": [
            Voicing("Drop2_Root", [0, 9, 15, 18], [1.0, 0.75, 0.85, 0.8]),
        ],
    },

    # ─── Drop 3 ───
    "drop3": {
        "maj7": [
            Voicing("Drop3_Root", [0, 7, 16, 23], [1.0, 0.7, 0.85, 0.75]),
        ],
        "m7":   [
            Voicing("Drop3_Root", [0, 7, 15, 22], [1.0, 0.7, 0.85, 0.75]),
        ],
        "7":    [
            Voicing("Drop3_Root", [0, 7, 16, 22], [1.0, 0.7, 0.85, 0.75]),
        ],
    },

    # ─── Guitar Voicings (Cubase "Guitar Chords" 프리셋 기반) ───
    "guitar": {
        "maj":  [
            Voicing("Open_E", [0, 7, 12, 16, 19, 24], [1.0, 0.8, 0.9, 0.85, 0.8, 0.75], spread_ms=15),
            Voicing("Barre", [0, 7, 12, 16, 19], [1.0, 0.85, 0.9, 0.85, 0.8], spread_ms=12),
        ],
        "min":  [
            Voicing("Open_Em", [0, 7, 12, 15, 19, 24], [1.0, 0.8, 0.9, 0.85, 0.8, 0.75], spread_ms=15),
            Voicing("Barre_m", [0, 7, 12, 15, 19], [1.0, 0.85, 0.9, 0.85, 0.8], spread_ms=12),
        ],
        "7":    [
            Voicing("Dom7", [0, 4, 7, 10, 12, 16], [1.0, 0.85, 0.8, 0.75, 0.9, 0.8], spread_ms=15),
        ],
        "maj7": [
            Voicing("Maj7_Gtr", [0, 4, 7, 11, 16], [1.0, 0.85, 0.8, 0.75, 0.85], spread_ms=12),
        ],
        "m7":   [
            Voicing("m7_Gtr", [0, 3, 7, 10, 15], [1.0, 0.85, 0.8, 0.75, 0.8], spread_ms=12),
        ],
        "sus2":  [
            Voicing("Sus2_Gtr", [0, 2, 7, 12, 14, 19], [1.0, 0.8, 0.85, 0.9, 0.8, 0.75], spread_ms=15),
        ],
        "sus4":  [
            Voicing("Sus4_Gtr", [0, 5, 7, 12, 17, 19], [1.0, 0.8, 0.85, 0.9, 0.8, 0.75], spread_ms=15),
        ],
        "5":     [
            Voicing("Power", [0, 7, 12], [1.0, 0.95, 0.9]),
            Voicing("Power_Oct", [0, 7, 12, 19], [1.0, 0.95, 0.9, 0.85]),
        ],
    },

    # ─── Stacked 4ths (모던 재즈/컨템포러리 — Cubase "Stacked 4th" 프리셋) ───
    "quartal": {
        "maj":  [Voicing("4ths", [0, 5, 10, 14], [1.0, 0.85, 0.8, 0.85])],
        "min":  [Voicing("4ths_m", [0, 5, 10, 15], [1.0, 0.85, 0.8, 0.85])],
        "7":    [Voicing("4ths_7", [0, 5, 10, 16], [1.0, 0.85, 0.8, 0.8])],
    },
}


# ─── 그루브 템플릿 (Cubase 15 프로젝트 템플릿 + 프리셋 기반) ───

@dataclass
class GrooveTemplate:
    """장르별 그루브 템플릿 — 타이밍/벨로시티 미세 조정."""
    name: str
    style: str
    swing_amount: float          # 0.0 (straight) ~ 1.0 (full triplet swing)
    timing_offsets: list[float]  # 16단계 그리드별 타이밍 오프셋 (틱 단위)
    velocity_pattern: list[float]  # 16단계 그리드별 상대 벨로시티
    ghost_note_probability: float  # 고스트 노트 발생 확률
    description: str = ""


GROOVE_TEMPLATES: dict[str, GrooveTemplate] = {
    # ─── Bossa Nova (Cubase Bossa 프리셋 기반) ───
    "bossa_nova": GrooveTemplate(
        name="Bossa Nova",
        style="latin",
        swing_amount=0.0,  # 보사노바는 straight 8th
        # 16th note grid (4/4, 16 positions per bar)
        # 보사노바 특유의 앞당김 (anticipation) 패턴
        timing_offsets=[
            0, 0, 0, 0,    # Beat 1
            0, -5, 0, 0,   # Beat 2 (약간 앞당김)
            0, 0, 0, 0,    # Beat 3
            0, -5, 0, -3,  # Beat 4 (앞당김 + 넘김)
        ],
        velocity_pattern=[
            1.0, 0.5, 0.7, 0.4,   # Beat 1
            0.8, 0.6, 0.7, 0.4,   # Beat 2
            0.9, 0.5, 0.7, 0.4,   # Beat 3
            0.8, 0.6, 0.7, 0.5,   # Beat 4
        ],
        ghost_note_probability=0.1,
        description="클래식 보사노바 그루브 — straight 8th, 부드러운 앞당김",
    ),

    # ─── Samba (Cubase Samba 프리셋 기반) ───
    "samba": GrooveTemplate(
        name="Samba",
        style="latin",
        swing_amount=0.0,
        timing_offsets=[
            0, 0, -3, 0,   0, 0, -3, 0,
            0, 0, -3, 0,   0, 0, -3, 0,
        ],
        velocity_pattern=[
            1.0, 0.4, 0.8, 0.5,   0.9, 0.4, 0.8, 0.5,
            1.0, 0.4, 0.8, 0.5,   0.9, 0.4, 0.8, 0.5,
        ],
        ghost_note_probability=0.15,
        description="삼바 그루브 — 16th note 기반, 강한 다운비트",
    ),

    # ─── Reggae (Cubase Reggae 프리셋 기반) ───
    "reggae": GrooveTemplate(
        name="Reggae",
        style="reggae",
        swing_amount=0.0,
        timing_offsets=[
            0, 0, 0, 5,    0, 0, 0, 5,
            0, 0, 0, 5,    0, 0, 0, 5,
        ],
        velocity_pattern=[
            0.3, 0.2, 0.9, 0.4,   0.3, 0.2, 0.9, 0.4,
            0.3, 0.2, 0.9, 0.4,   0.3, 0.2, 0.9, 0.4,
        ],
        ghost_note_probability=0.05,
        description="레게 오프비트 스캥크 — 2, 4박 강조",
    ),

    # ─── Funk 16th (Cubase Funky Disco 프리셋 기반) ───
    "funk_16th": GrooveTemplate(
        name="Funk 16th",
        style="funk",
        swing_amount=0.05,  # 아주 약간의 셔플
        timing_offsets=[
            0, -2, 0, -2,  0, -2, 0, -2,
            0, -2, 0, -2,  0, -2, 0, -2,
        ],
        velocity_pattern=[
            1.0, 0.5, 0.7, 0.4,   0.8, 0.5, 0.7, 0.4,
            0.9, 0.5, 0.7, 0.4,   0.8, 0.5, 0.7, 0.4,
        ],
        ghost_note_probability=0.25,
        description="16th note 펑크 그루브 — 고스트 노트 많음",
    ),

    # ─── Jazz Swing ───
    "jazz_swing": GrooveTemplate(
        name="Jazz Swing",
        style="jazz",
        swing_amount=0.67,  # 트리플렛 스윙
        timing_offsets=[
            0, 0, 8, 0,    0, 0, 8, 0,
            0, 0, 8, 0,    0, 0, 8, 0,
        ],
        velocity_pattern=[
            0.9, 0.3, 0.7, 0.4,   0.8, 0.3, 0.7, 0.4,
            0.9, 0.3, 0.7, 0.4,   0.8, 0.3, 0.7, 0.4,
        ],
        ghost_note_probability=0.2,
        description="재즈 스윙 — 셔플 8th, 트리플렛 필",
    ),

    # ─── Hip Hop ───
    "hiphop": GrooveTemplate(
        name="Hip Hop",
        style="hiphop",
        swing_amount=0.15,
        timing_offsets=[
            0, 3, -2, 3,   0, 3, -2, 3,
            0, 3, -2, 3,   0, 3, -2, 3,
        ],
        velocity_pattern=[
            1.0, 0.3, 0.6, 0.4,   0.7, 0.3, 0.5, 0.4,
            0.9, 0.3, 0.6, 0.4,   0.7, 0.3, 0.5, 0.4,
        ],
        ghost_note_probability=0.15,
        description="힙합 바운스 — 레이드백 느낌, 불균일 벨로시티",
    ),

    # ─── EDM Straight ───
    "edm_straight": GrooveTemplate(
        name="EDM Straight",
        style="edm",
        swing_amount=0.0,
        timing_offsets=[0] * 16,
        velocity_pattern=[
            1.0, 0.6, 0.8, 0.6,   1.0, 0.6, 0.8, 0.6,
            1.0, 0.6, 0.8, 0.6,   1.0, 0.6, 0.8, 0.6,
        ],
        ghost_note_probability=0.0,
        description="EDM — 완전 straight, 강한 4-on-the-floor",
    ),

    # ─── R&B / Neo Soul ───
    "rnb_neosoul": GrooveTemplate(
        name="R&B / Neo Soul",
        style="rnb",
        swing_amount=0.3,
        timing_offsets=[
            0, 2, -3, 2,   0, 3, -2, 2,
            0, 2, -3, 2,   0, 3, -2, 2,
        ],
        velocity_pattern=[
            0.85, 0.4, 0.7, 0.5,   0.8, 0.4, 0.65, 0.5,
            0.85, 0.4, 0.7, 0.5,   0.8, 0.4, 0.65, 0.5,
        ],
        ghost_note_probability=0.2,
        description="네오소울 그루브 — 부드러운 스윙, 레이드백",
    ),

    # ─── Pop Ballad ───
    "pop_ballad": GrooveTemplate(
        name="Pop Ballad",
        style="pop",
        swing_amount=0.0,
        timing_offsets=[0] * 16,
        velocity_pattern=[
            0.9, 0.3, 0.5, 0.35,   0.7, 0.3, 0.5, 0.35,
            0.85, 0.3, 0.5, 0.35,  0.7, 0.3, 0.5, 0.35,
        ],
        ghost_note_probability=0.05,
        description="팝 발라드 — 부드럽고 일정한 8th note",
    ),

    # ─── Classical (Cubase Classical 템플릿 기반) ───
    "classical_rubato": GrooveTemplate(
        name="Classical Rubato",
        style="classical",
        swing_amount=0.0,
        timing_offsets=[
            0, 0, 0, 0,    -2, 0, 0, 2,
            0, 0, 0, 0,    -3, 0, 0, 3,
        ],
        velocity_pattern=[
            0.85, 0.6, 0.7, 0.5,   0.9, 0.6, 0.75, 0.5,
            0.8, 0.55, 0.65, 0.5,  0.9, 0.6, 0.7, 0.5,
        ],
        ghost_note_probability=0.0,
        description="클래식 루바토 — 미세한 타이밍 변화, 프레이즈 호흡",
    ),

    # ─── Lo-Fi ───
    "lofi": GrooveTemplate(
        name="Lo-Fi",
        style="lo-fi",
        swing_amount=0.25,
        timing_offsets=[
            0, 5, -3, 4,   0, 6, -2, 5,
            0, 4, -3, 5,   0, 5, -2, 4,
        ],
        velocity_pattern=[
            0.7, 0.35, 0.5, 0.3,   0.6, 0.35, 0.45, 0.3,
            0.65, 0.3, 0.5, 0.3,   0.6, 0.35, 0.45, 0.3,
        ],
        ghost_note_probability=0.1,
        description="로파이 — 불규칙한 타이밍, 낮은 벨로시티, 드렁큰 필",
    ),

    # ─── Metal / Rock ───
    "metal": GrooveTemplate(
        name="Metal",
        style="metal",
        swing_amount=0.0,
        timing_offsets=[0] * 16,
        velocity_pattern=[
            1.0, 0.8, 0.9, 0.8,   1.0, 0.8, 0.9, 0.8,
            1.0, 0.8, 0.9, 0.8,   1.0, 0.8, 0.9, 0.8,
        ],
        ghost_note_probability=0.0,
        description="메탈 — 강하고 일정한 16th, 하이 벨로시티",
    ),

    # ─── Country ───
    "country": GrooveTemplate(
        name="Country",
        style="folk",
        swing_amount=0.1,
        timing_offsets=[
            0, 0, 0, 0,    0, -3, 0, 0,
            0, 0, 0, 0,    0, -3, 0, 0,
        ],
        velocity_pattern=[
            1.0, 0.4, 0.7, 0.4,   0.8, 0.5, 0.7, 0.4,
            0.9, 0.4, 0.7, 0.4,   0.8, 0.5, 0.7, 0.4,
        ],
        ghost_note_probability=0.05,
        description="컨트리 — 약간의 셔플, 붐-칙 패턴",
    ),
}


# ─── 코드패드 시스템 (Cubase 15 ChordPad 기반, 64 패드) ───

@dataclass
class ChordPadEntry:
    """코드패드 항목."""
    root: int          # MIDI 노트 번호 (루트)
    quality: str       # 코드 품질 (CHORD_QUALITIES 중)
    bass_note: Optional[int] = None  # 슬래시 코드 베이스 (None = 루트)
    voicing_type: str = "close"      # 보이싱 타입
    label: str = ""


def build_chord_pad_set(key_root: int, scale: str = "major") -> list[ChordPadEntry]:
    """키 기반 코드패드 세트 생성 (Cubase 스타일 8패드 + 확장).

    Args:
        key_root: 키 루트 (0=C, 1=C#, ..., 11=B)
        scale: 'major' 또는 'minor'

    Returns:
        8개 기본 코드 + 8개 확장 코드 = 16개 ChordPadEntry
    """
    if scale == "major":
        # I, ii, iii, IV, V, vi, vii°, I(8va)
        degrees = [
            (0, "maj"), (2, "min"), (4, "min"), (5, "maj"),
            (7, "maj"), (9, "min"), (11, "dim"), (12, "maj"),
        ]
        # 확장: 7th 코드 변형
        extended = [
            (0, "maj7"), (2, "m7"), (4, "m7"), (5, "maj7"),
            (7, "7"), (9, "m7"), (11, "m7b5"), (0, "add9"),
        ]
    else:
        # i, ii°, III, iv, v, VI, VII, i(8va)
        degrees = [
            (0, "min"), (2, "dim"), (3, "maj"), (5, "min"),
            (7, "min"), (8, "maj"), (10, "maj"), (12, "min"),
        ]
        extended = [
            (0, "m7"), (2, "m7b5"), (3, "maj7"), (5, "m7"),
            (7, "m7"), (8, "maj7"), (10, "7"), (0, "m9"),
        ]

    pads = []
    for interval, quality in degrees:
        root_note = (key_root + interval) % 12
        pads.append(ChordPadEntry(
            root=root_note, quality=quality,
            voicing_type="close",
            label=f"{'CDEFGAB'[root_note % 7] if root_note < 7 else ''}{quality}",
        ))
    for interval, quality in extended:
        root_note = (key_root + interval) % 12
        pads.append(ChordPadEntry(
            root=root_note, quality=quality,
            voicing_type="drop2",
            label=f"{'CDEFGAB'[root_note % 7] if root_note < 7 else ''}{quality}",
        ))
    return pads


# ─── 보이스 리딩 엔진 ───

def voice_lead(
    prev_voicing: list[int],
    next_root: int,
    next_quality: str,
    voicing_type: str = "close",
    octave: int = 4,
) -> list[int]:
    """최소 이동 원칙 기반 자동 보이스 리딩.

    이전 보이싱에서 다음 코드로 이동할 때
    각 성부의 이동 거리를 최소화합니다.

    Args:
        prev_voicing: 이전 코드의 MIDI 노트 리스트
        next_root: 다음 코드 루트 (0-11)
        next_quality: 다음 코드 품질
        voicing_type: 보이싱 타입 (close, open, drop2, guitar 등)
        octave: 기준 옥타브

    Returns:
        최적 보이스 리딩이 적용된 MIDI 노트 리스트
    """
    # 보이싱 라이브러리에서 후보 가져오기
    voicings = VOICING_LIBRARY.get(voicing_type, VOICING_LIBRARY["close"])
    candidates = voicings.get(next_quality, voicings.get("maj", []))
    if not candidates:
        # 폴백: 기본 인터벌 사용
        intervals = CHORD_INTERVALS.get(next_quality, [0, 4, 7])
        base = next_root + (octave + 1) * 12
        return [base + i for i in intervals]

    if not prev_voicing:
        # 이전 보이싱 없으면 첫 번째 후보 사용
        v = candidates[0]
        base = next_root + (octave + 1) * 12
        return [base + i for i in v.intervals]

    # 각 후보 보이싱의 총 이동 거리 계산
    best_voicing = None
    best_distance = float("inf")

    for v in candidates:
        for oct_shift in [-12, 0, 12]:  # 옥타브 시프트 후보
            base = next_root + (octave + 1) * 12 + oct_shift
            notes = [base + i for i in v.intervals]

            # 음역 체크 (21-108)
            if any(n < 21 or n > 108 for n in notes):
                continue

            # 총 이동 거리 (매칭 가능한 성부끼리)
            distance = 0
            for i, note in enumerate(notes):
                if i < len(prev_voicing):
                    distance += abs(note - prev_voicing[i])
                else:
                    distance += 6  # 새 성부 패널티

            if distance < best_distance:
                best_distance = distance
                best_voicing = notes

    return best_voicing or [next_root + (octave + 1) * 12 + i
                            for i in CHORD_INTERVALS.get(next_quality, [0, 4, 7])]


def apply_groove(
    notes: list[dict],
    groove_name: str,
    ticks_per_beat: int = 480,
    intensity: float = 1.0,
) -> list[dict]:
    """그루브 템플릿을 노트 리스트에 적용.

    Args:
        notes: [{'pitch': int, 'start_tick': int, 'duration': int, 'velocity': int}, ...]
        groove_name: 그루브 템플릿 이름
        ticks_per_beat: MIDI 해상도
        intensity: 그루브 강도 (0.0 ~ 1.0)

    Returns:
        그루브가 적용된 노트 리스트
    """
    groove = GROOVE_TEMPLATES.get(groove_name)
    if not groove:
        return notes

    ticks_per_bar = ticks_per_beat * 4
    ticks_per_16th = ticks_per_beat // 4
    result = []

    for note in notes:
        n = dict(note)  # 복사
        # 바 내 위치 → 16th note 인덱스
        pos_in_bar = n["start_tick"] % ticks_per_bar
        grid_idx = min(15, pos_in_bar // ticks_per_16th)

        # 타이밍 오프셋 적용
        offset = groove.timing_offsets[grid_idx] * intensity
        n["start_tick"] = max(0, int(n["start_tick"] + offset))

        # 벨로시티 패턴 적용
        vel_mult = groove.velocity_pattern[grid_idx]
        vel_mult = 1.0 + (vel_mult - 1.0) * intensity  # intensity로 보간
        n["velocity"] = max(1, min(127, int(n["velocity"] * vel_mult)))

        # 스윙 적용 (홀수 8th note 위치에)
        if groove.swing_amount > 0 and grid_idx % 2 == 1:
            swing_offset = int(groove.swing_amount * ticks_per_16th * intensity)
            n["start_tick"] += swing_offset

        # 고스트 노트 확률
        if (random.random() < groove.ghost_note_probability * intensity
                and n["velocity"] < 80):
            n["velocity"] = max(1, int(n["velocity"] * 0.4))

        result.append(n)

    return result


def get_voicing(
    root: int,
    quality: str,
    voicing_type: str = "close",
    octave: int = 4,
    velocity_base: int = 80,
) -> list[dict]:
    """코드 보이싱을 MIDI 노트 이벤트로 변환.

    Args:
        root: 루트 노트 (0-11)
        quality: 코드 품질
        voicing_type: 보이싱 타입
        octave: 기준 옥타브
        velocity_base: 기준 벨로시티

    Returns:
        [{'pitch': int, 'velocity': int, 'spread_ms': float}, ...]
    """
    voicings = VOICING_LIBRARY.get(voicing_type, VOICING_LIBRARY["close"])
    candidates = voicings.get(quality)

    if not candidates:
        # 폴백: 기본 인터벌
        intervals = CHORD_INTERVALS.get(quality, [0, 4, 7])
        base = root + (octave + 1) * 12
        return [{"pitch": base + i, "velocity": velocity_base, "spread_ms": 0.0}
                for i in intervals]

    v = random.choice(candidates)
    base = root + (octave + 1) * 12

    return [
        {
            "pitch": max(21, min(108, base + interval)),
            "velocity": max(1, min(127, int(velocity_base * vel_curve))),
            "spread_ms": v.spread_ms * (i / max(1, len(v.intervals) - 1)) if v.spread_ms > 0 else 0.0,
        }
        for i, (interval, vel_curve) in enumerate(zip(v.intervals, v.velocity_curve))
    ]


def get_groove_for_style(style: str) -> Optional[GrooveTemplate]:
    """스타일에 맞는 그루브 템플릿 자동 선택."""
    style_map = {
        "ambient": "pop_ballad",
        "classical": "classical_rubato",
        "pop": "pop_ballad",
        "cinematic": "classical_rubato",
        "edm": "edm_straight",
        "jazz": "jazz_swing",
        "lo-fi": "lofi",
        "experimental": "lofi",
        "hiphop": "hiphop",
        "rnb": "rnb_neosoul",
        "latin": "bossa_nova",
        "reggae": "reggae",
        "funk": "funk_16th",
        "metal": "metal",
        "folk": "country",
        "orchestral": "classical_rubato",
        "ballad": "pop_ballad",
    }
    groove_name = style_map.get(style, "pop_ballad")
    return GROOVE_TEMPLATES.get(groove_name)
