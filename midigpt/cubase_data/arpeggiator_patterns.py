"""
Cubase 15 스타일 아르페지에이터 패턴 라이브러리.

Cubase 15의 120+ 아르페지에이터 프리셋에서 영감을 받은 장르별 아르페지오 패턴을 제공합니다.
카테고리: Classic Arp, Guitar, Piano, Sequence, Bass, Pad.

각 패턴은 NoteEvent 기반으로 position(바 내 위치), voice_index(코드 톤 인덱스),
velocity, duration, offset_ms(휴머나이즈), is_chord 등을 포함합니다.
PPQ 기준: 480 ticks per quarter note.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple


# ---------------------------------------------------------------------------
# 데이터 구조 정의
# ---------------------------------------------------------------------------

@dataclass
class ArpEvent:
    """아르페지에이터 이벤트 하나를 나타내는 데이터 클래스.

    Attributes:
        position: 바 내 위치 (0.0 = beat 1, 0.25 = beat 2, 0.5 = beat 3, 0.75 = beat 4).
        voice_index: 코드 톤 인덱스 (0=root, 1=3rd, 2=5th, 3=7th, 4=9th).
        velocity: MIDI 벨로시티 (0-127).
        duration: 바 전체 대비 비율 (0.25 = 한 박).
        offset_ms: 타이밍 오프셋(ms), 휴머나이즈 용도.
        is_chord: True면 블록 코드로 연주.
    """
    position: float
    voice_index: int
    velocity: int
    duration: float
    offset_ms: float = 0.0
    is_chord: bool = False


@dataclass
class ArpPattern:
    """아르페지에이터 패턴 전체를 나타내는 데이터 클래스.

    Attributes:
        name: 패턴 표시 이름.
        category: 카테고리 (classic_arp, guitar, piano, sequence, bass, pad).
        time_signature: 박자표 (numerator, denominator).
        length_bars: 패턴 길이(마디 수).
        swing: 스윙 양 (0.0 = 없음, 1.0 = 최대).
        events: ArpEvent 리스트.
    """
    name: str
    category: str
    time_signature: Tuple[int, int] = (4, 4)
    length_bars: int = 1
    swing: float = 0.0
    events: List[ArpEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 패턴 정의 - Classic Arp
# ---------------------------------------------------------------------------

_CLASSIC_ARP_PATTERNS: Dict[str, ArpPattern] = {
    "classic_arp": ArpPattern(
        name="Classic Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.125, 1, 90, 0.125, 0),
            ArpEvent(0.25, 2, 85, 0.125, 0), ArpEvent(0.375, 3, 80, 0.125, 0),
            ArpEvent(0.5, 0, 95, 0.125, 0), ArpEvent(0.625, 1, 85, 0.125, 0),
            ArpEvent(0.75, 2, 80, 0.125, 0), ArpEvent(0.875, 3, 75, 0.125, 0),
        ],
    ),
    "fat_arp": ArpPattern(
        name="Fat Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 110, 0.25, 0, True), ArpEvent(0.25, 1, 100, 0.25, 0, True),
            ArpEvent(0.5, 2, 105, 0.25, 0, True), ArpEvent(0.75, 3, 95, 0.25, 0, True),
        ],
    ),
    "4th_arp": ArpPattern(
        name="4th Note Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 100, 0.25, 0), ArpEvent(0.25, 1, 90, 0.25, 0),
            ArpEvent(0.5, 2, 85, 0.25, 0), ArpEvent(0.75, 0, 90, 0.25, 0),
        ],
    ),
    "8th_arp": ArpPattern(
        name="8th Note Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.125, 1, 90, 0.125, 0),
            ArpEvent(0.25, 2, 85, 0.125, 0), ArpEvent(0.375, 0, 80, 0.125, 0),
            ArpEvent(0.5, 1, 95, 0.125, 0), ArpEvent(0.625, 2, 85, 0.125, 0),
            ArpEvent(0.75, 0, 80, 0.125, 0), ArpEvent(0.875, 1, 75, 0.125, 0),
        ],
    ),
    "step_by_step": ArpPattern(
        name="Step by Step", category="classic_arp", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0), ArpEvent(0.0625, 0, 70, 0.0625, 0),
            ArpEvent(0.125, 1, 95, 0.0625, 0), ArpEvent(0.1875, 1, 65, 0.0625, 0),
            ArpEvent(0.25, 2, 90, 0.0625, 0), ArpEvent(0.3125, 2, 60, 0.0625, 0),
            ArpEvent(0.375, 3, 85, 0.0625, 0), ArpEvent(0.4375, 3, 55, 0.0625, 0),
            ArpEvent(0.5, 2, 90, 0.0625, 0), ArpEvent(0.5625, 2, 60, 0.0625, 0),
            ArpEvent(0.625, 1, 85, 0.0625, 0), ArpEvent(0.6875, 1, 55, 0.0625, 0),
            ArpEvent(0.75, 0, 95, 0.0625, 0), ArpEvent(0.8125, 0, 65, 0.0625, 0),
            ArpEvent(0.875, 0, 80, 0.125, 0),
        ],
    ),
    "trance_line": ArpPattern(
        name="Trance Line", category="classic_arp", swing=0.0, events=[
            ArpEvent(0.0, 0, 110, 0.0625, 0), ArpEvent(0.0625, 2, 80, 0.0625, 0),
            ArpEvent(0.125, 0, 100, 0.0625, 0), ArpEvent(0.1875, 2, 75, 0.0625, 0),
            ArpEvent(0.25, 1, 105, 0.0625, 0), ArpEvent(0.3125, 2, 78, 0.0625, 0),
            ArpEvent(0.375, 0, 95, 0.0625, 0), ArpEvent(0.4375, 2, 72, 0.0625, 0),
            ArpEvent(0.5, 0, 108, 0.0625, 0), ArpEvent(0.5625, 2, 80, 0.0625, 0),
            ArpEvent(0.625, 1, 100, 0.0625, 0), ArpEvent(0.6875, 2, 75, 0.0625, 0),
            ArpEvent(0.75, 0, 95, 0.0625, 0), ArpEvent(0.8125, 3, 85, 0.0625, 0),
            ArpEvent(0.875, 2, 90, 0.0625, 0), ArpEvent(0.9375, 1, 80, 0.0625, 0),
        ],
    ),
    "arhythmic_phrase": ArpPattern(
        name="Arhythmic Phrase", category="classic_arp", events=[
            ArpEvent(0.0, 0, 95, 0.1, 3), ArpEvent(0.15, 2, 75, 0.08, -5),
            ArpEvent(0.28, 1, 80, 0.12, 7), ArpEvent(0.42, 3, 70, 0.06, -3),
            ArpEvent(0.55, 0, 90, 0.09, 4), ArpEvent(0.7, 2, 72, 0.1, -6),
            ArpEvent(0.85, 1, 78, 0.12, 2),
        ],
    ),
    "fast_arp": ArpPattern(
        name="Fast Arp", category="classic_arp", events=[
            ArpEvent(i * 0.0625, i % 4, 100 - (i % 4) * 8, 0.05, 0)
            for i in range(16)
        ],
    ),
    "hypnotic_arp": ArpPattern(
        name="Hypnotic Arp", category="classic_arp", length_bars=2, events=[
            # 바 1: 반복적 최면 패턴
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.125, 2, 75, 0.125, 0),
            ArpEvent(0.25, 1, 85, 0.125, 0), ArpEvent(0.375, 2, 70, 0.125, 0),
            ArpEvent(0.5, 0, 95, 0.125, 0), ArpEvent(0.625, 2, 75, 0.125, 0),
            ArpEvent(0.75, 1, 80, 0.125, 0), ArpEvent(0.875, 2, 70, 0.125, 0),
            # 바 2: 약간의 변형
            ArpEvent(1.0, 0, 100, 0.125, 0), ArpEvent(1.125, 2, 78, 0.125, 0),
            ArpEvent(1.25, 1, 88, 0.125, 0), ArpEvent(1.375, 3, 72, 0.125, 0),
            ArpEvent(1.5, 0, 95, 0.125, 0), ArpEvent(1.625, 2, 75, 0.125, 0),
            ArpEvent(1.75, 1, 82, 0.125, 0), ArpEvent(1.875, 0, 90, 0.125, 0),
        ],
    ),
    "jarre_arp": ArpPattern(
        name="Jarre Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 105, 0.0625, 0), ArpEvent(0.0625, 1, 70, 0.0625, 0),
            ArpEvent(0.125, 2, 90, 0.0625, 0), ArpEvent(0.1875, 1, 65, 0.0625, 0),
            ArpEvent(0.25, 0, 100, 0.0625, 0), ArpEvent(0.3125, 1, 68, 0.0625, 0),
            ArpEvent(0.375, 2, 88, 0.0625, 0), ArpEvent(0.4375, 3, 72, 0.0625, 0),
            ArpEvent(0.5, 0, 102, 0.0625, 0), ArpEvent(0.5625, 1, 70, 0.0625, 0),
            ArpEvent(0.625, 2, 85, 0.0625, 0), ArpEvent(0.6875, 1, 65, 0.0625, 0),
            ArpEvent(0.75, 0, 98, 0.0625, 0), ArpEvent(0.8125, 2, 75, 0.0625, 0),
            ArpEvent(0.875, 1, 80, 0.0625, 0), ArpEvent(0.9375, 0, 90, 0.0625, 0),
        ],
    ),
    "mellow_arp": ArpPattern(
        name="Mellow Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 75, 0.25, 0), ArpEvent(0.25, 1, 65, 0.25, 3),
            ArpEvent(0.5, 2, 60, 0.25, -2), ArpEvent(0.75, 1, 58, 0.25, 4),
        ],
    ),
    "sparkling_arp": ArpPattern(
        name="Sparkling Arp", category="classic_arp", events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0), ArpEvent(0.0625, 2, 95, 0.0625, 0),
            ArpEvent(0.125, 4, 100, 0.0625, 0), ArpEvent(0.1875, 2, 90, 0.0625, 0),
            ArpEvent(0.25, 1, 88, 0.0625, 0), ArpEvent(0.3125, 3, 93, 0.0625, 0),
            ArpEvent(0.375, 4, 98, 0.0625, 0), ArpEvent(0.4375, 3, 88, 0.0625, 0),
            ArpEvent(0.5, 0, 85, 0.0625, 0), ArpEvent(0.5625, 2, 92, 0.0625, 0),
            ArpEvent(0.625, 4, 97, 0.0625, 0), ArpEvent(0.6875, 2, 87, 0.0625, 0),
            ArpEvent(0.75, 1, 83, 0.0625, 0), ArpEvent(0.8125, 3, 90, 0.0625, 0),
            ArpEvent(0.875, 4, 95, 0.0625, 0), ArpEvent(0.9375, 3, 85, 0.0625, 0),
        ],
    ),
    "pulsating": ArpPattern(
        name="Pulsating", category="classic_arp", events=[
            ArpEvent(0.0, 0, 110, 0.0625, 0, True),
            ArpEvent(0.125, 0, 60, 0.0625, 0, True),
            ArpEvent(0.25, 0, 105, 0.0625, 0, True),
            ArpEvent(0.375, 0, 55, 0.0625, 0, True),
            ArpEvent(0.5, 0, 108, 0.0625, 0, True),
            ArpEvent(0.625, 0, 58, 0.0625, 0, True),
            ArpEvent(0.75, 0, 100, 0.0625, 0, True),
            ArpEvent(0.875, 0, 50, 0.0625, 0, True),
        ],
    ),
    "yello_sequence": ArpPattern(
        name="Yello Sequence", category="classic_arp", events=[
            ArpEvent(0.0, 0, 105, 0.0625, 0), ArpEvent(0.0625, 0, 60, 0.0625, 0),
            ArpEvent(0.125, 2, 95, 0.0625, 0), ArpEvent(0.25, 0, 100, 0.0625, 0),
            ArpEvent(0.3125, 1, 65, 0.0625, 0), ArpEvent(0.375, 2, 90, 0.0625, 0),
            ArpEvent(0.5, 0, 102, 0.0625, 0), ArpEvent(0.5625, 0, 58, 0.0625, 0),
            ArpEvent(0.625, 3, 88, 0.0625, 0), ArpEvent(0.75, 0, 98, 0.0625, 0),
            ArpEvent(0.8125, 2, 70, 0.0625, 0), ArpEvent(0.875, 1, 85, 0.0625, 0),
        ],
    ),
}

# ---------------------------------------------------------------------------
# 패턴 정의 - Guitar
# ---------------------------------------------------------------------------

_GUITAR_PATTERNS: Dict[str, ArpPattern] = {
    "bossa_nova_1": ArpPattern(
        name="Bossa Nova 1", category="guitar", length_bars=2, events=[
            # 바 1: 클래식 보사노바 - 베이스 + 코드 스탭
            ArpEvent(0.0, 0, 90, 0.125, 0, False),
            ArpEvent(0.125, 1, 70, 0.0625, 5, True),
            ArpEvent(0.1875, 2, 65, 0.0625, 0, True),
            ArpEvent(0.375, 0, 80, 0.0625, 0, False),
            ArpEvent(0.5, 0, 85, 0.125, 0, False),
            ArpEvent(0.625, 1, 70, 0.0625, 5, True),
            ArpEvent(0.6875, 2, 65, 0.0625, 0, True),
            ArpEvent(0.875, 0, 75, 0.0625, 0, False),
            # 바 2: 변형
            ArpEvent(1.0, 0, 88, 0.125, 0, False),
            ArpEvent(1.125, 1, 72, 0.0625, 4, True),
            ArpEvent(1.1875, 2, 68, 0.0625, 0, True),
            ArpEvent(1.375, 0, 78, 0.0625, 0, False),
            ArpEvent(1.5, 0, 82, 0.125, 0, False),
            ArpEvent(1.625, 1, 68, 0.0625, 6, True),
            ArpEvent(1.6875, 2, 63, 0.0625, 0, True),
            ArpEvent(1.875, 3, 70, 0.0625, 0, False),
        ],
    ),
    "bossa_nova_2": ArpPattern(
        name="Bossa Nova 2", category="guitar", length_bars=2, events=[
            ArpEvent(0.0, 0, 85, 0.125, 0, False),
            ArpEvent(0.125, 1, 68, 0.0625, 3, True),
            ArpEvent(0.25, 2, 65, 0.0625, 0, True),
            ArpEvent(0.375, 1, 60, 0.0625, -3, True),
            ArpEvent(0.5, 0, 82, 0.125, 0, False),
            ArpEvent(0.625, 2, 66, 0.0625, 4, True),
            ArpEvent(0.75, 1, 62, 0.0625, 0, True),
            ArpEvent(0.875, 0, 72, 0.0625, 0, False),
            ArpEvent(1.0, 0, 83, 0.125, 0, False),
            ArpEvent(1.125, 1, 67, 0.0625, 3, True),
            ArpEvent(1.25, 2, 64, 0.0625, 0, True),
            ArpEvent(1.5, 0, 80, 0.125, 0, False),
            ArpEvent(1.625, 1, 65, 0.0625, 5, True),
            ArpEvent(1.75, 2, 62, 0.0625, 0, True),
            ArpEvent(1.875, 0, 70, 0.125, 0, False),
        ],
    ),
    "samba_1": ArpPattern(
        name="Samba 1", category="guitar", events=[
            ArpEvent(0.0, 0, 95, 0.0625, 0, True),
            ArpEvent(0.0625, 1, 60, 0.0625, 0, True),
            ArpEvent(0.125, 0, 85, 0.0625, 0, True),
            ArpEvent(0.25, 1, 90, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 55, 0.0625, 0, True),
            ArpEvent(0.375, 1, 80, 0.0625, 0, True),
            ArpEvent(0.5, 0, 92, 0.0625, 0, True),
            ArpEvent(0.5625, 1, 58, 0.0625, 0, True),
            ArpEvent(0.625, 0, 82, 0.0625, 0, True),
            ArpEvent(0.75, 1, 88, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 55, 0.0625, 0, True),
            ArpEvent(0.875, 1, 78, 0.0625, 0, True),
        ],
    ),
    "samba_2": ArpPattern(
        name="Samba 2", category="guitar", swing=0.15, events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0, False),
            ArpEvent(0.0625, 1, 72, 0.0625, 0, True),
            ArpEvent(0.1875, 2, 68, 0.0625, 0, True),
            ArpEvent(0.25, 0, 85, 0.0625, 0, False),
            ArpEvent(0.375, 1, 75, 0.0625, 0, True),
            ArpEvent(0.4375, 2, 70, 0.0625, 0, True),
            ArpEvent(0.5, 0, 88, 0.0625, 0, False),
            ArpEvent(0.5625, 1, 70, 0.0625, 0, True),
            ArpEvent(0.6875, 2, 66, 0.0625, 0, True),
            ArpEvent(0.75, 0, 82, 0.0625, 0, False),
            ArpEvent(0.875, 1, 73, 0.0625, 0, True),
            ArpEvent(0.9375, 2, 68, 0.0625, 0, True),
        ],
    ),
    "reggae_1": ArpPattern(
        name="Reggae 1", category="guitar", events=[
            # 오프비트 스캥크 패턴
            ArpEvent(0.125, 0, 85, 0.1, 0, True),
            ArpEvent(0.375, 0, 80, 0.1, 0, True),
            ArpEvent(0.625, 0, 82, 0.1, 0, True),
            ArpEvent(0.875, 0, 78, 0.1, 0, True),
        ],
    ),
    "reggae_2": ArpPattern(
        name="Reggae 2", category="guitar", events=[
            ArpEvent(0.125, 0, 88, 0.08, 0, True),
            ArpEvent(0.25, 0, 50, 0.05, 0, True),
            ArpEvent(0.375, 0, 85, 0.08, 0, True),
            ArpEvent(0.625, 0, 86, 0.08, 0, True),
            ArpEvent(0.75, 0, 48, 0.05, 0, True),
            ArpEvent(0.875, 0, 82, 0.08, 0, True),
        ],
    ),
    "reggae_3": ArpPattern(
        name="Reggae 3", category="guitar", swing=0.1, events=[
            ArpEvent(0.125, 0, 82, 0.0625, 8, True),
            ArpEvent(0.375, 0, 78, 0.0625, 5, True),
            ArpEvent(0.5, 0, 45, 0.0625, 0, True),
            ArpEvent(0.625, 0, 80, 0.0625, 7, True),
            ArpEvent(0.875, 0, 76, 0.0625, 6, True),
        ],
    ),
    "funk_1": ArpPattern(
        name="Funk 1", category="guitar", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0, True),
            ArpEvent(0.0625, 0, 40, 0.0625, 0, True),  # 뮤트
            ArpEvent(0.125, 0, 90, 0.0625, 0, True),
            ArpEvent(0.1875, 0, 38, 0.0625, 0, True),
            ArpEvent(0.25, 0, 95, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.375, 0, 88, 0.0625, 0, True),
            ArpEvent(0.4375, 0, 40, 0.0625, 0, True),
            ArpEvent(0.5, 0, 98, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 38, 0.0625, 0, True),
            ArpEvent(0.625, 0, 85, 0.0625, 0, True),
            ArpEvent(0.6875, 0, 40, 0.0625, 0, True),
            ArpEvent(0.75, 0, 92, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.875, 0, 80, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 38, 0.0625, 0, True),
        ],
    ),
    "funk_2": ArpPattern(
        name="Funk 2", category="guitar", events=[
            ArpEvent(0.0, 0, 95, 0.0625, 0, True),
            ArpEvent(0.125, 0, 40, 0.0625, 0, True),
            ArpEvent(0.1875, 0, 88, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.375, 0, 90, 0.0625, 0, True),
            ArpEvent(0.5, 0, 92, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 38, 0.0625, 0, True),
            ArpEvent(0.6875, 0, 85, 0.0625, 0, True),
            ArpEvent(0.75, 0, 40, 0.0625, 0, True),
            ArpEvent(0.875, 0, 87, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 40, 0.0625, 0, True),
        ],
    ),
    "funky_disco": ArpPattern(
        name="Funky Disco", category="guitar", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0, True),
            ArpEvent(0.0625, 0, 50, 0.0625, 0, True),
            ArpEvent(0.125, 0, 92, 0.0625, 0, True),
            ArpEvent(0.25, 0, 98, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 48, 0.0625, 0, True),
            ArpEvent(0.375, 0, 90, 0.0625, 0, True),
            ArpEvent(0.4375, 0, 46, 0.0625, 0, True),
            ArpEvent(0.5, 0, 96, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 48, 0.0625, 0, True),
            ArpEvent(0.625, 0, 88, 0.0625, 0, True),
            ArpEvent(0.75, 0, 95, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 50, 0.0625, 0, True),
            ArpEvent(0.875, 0, 86, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 46, 0.0625, 0, True),
        ],
    ),
    "latin_pop_1": ArpPattern(
        name="Latin Pop 1", category="guitar", events=[
            ArpEvent(0.0, 0, 90, 0.125, 0, False),
            ArpEvent(0.125, 1, 72, 0.0625, 0, True),
            ArpEvent(0.25, 0, 85, 0.125, 0, False),
            ArpEvent(0.375, 1, 70, 0.0625, 0, True),
            ArpEvent(0.5, 0, 88, 0.125, 0, False),
            ArpEvent(0.625, 1, 74, 0.0625, 3, True),
            ArpEvent(0.75, 2, 68, 0.0625, 0, True),
            ArpEvent(0.875, 0, 78, 0.0625, 0, False),
        ],
    ),
    "latin_pop_2": ArpPattern(
        name="Latin Pop 2", category="guitar", events=[
            ArpEvent(0.0, 0, 92, 0.0625, 0, True),
            ArpEvent(0.125, 0, 45, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 80, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.375, 1, 85, 0.0625, 0, True),
            ArpEvent(0.5, 0, 90, 0.0625, 0, True),
            ArpEvent(0.625, 0, 44, 0.0625, 0, True),
            ArpEvent(0.6875, 1, 78, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 43, 0.0625, 0, True),
            ArpEvent(0.875, 1, 82, 0.0625, 0, True),
        ],
    ),
    "brit_pop_1": ArpPattern(
        name="Brit Pop 1", category="guitar", events=[
            ArpEvent(0.0, 0, 95, 0.125, 0, True),
            ArpEvent(0.25, 0, 88, 0.125, 0, True),
            ArpEvent(0.5, 0, 92, 0.125, 0, True),
            ArpEvent(0.75, 0, 85, 0.125, 0, True),
        ],
    ),
    "brit_pop_2": ArpPattern(
        name="Brit Pop 2", category="guitar", events=[
            ArpEvent(0.0, 0, 90, 0.125, 0), ArpEvent(0.125, 2, 75, 0.125, 0),
            ArpEvent(0.25, 1, 85, 0.125, 0), ArpEvent(0.375, 2, 70, 0.125, 0),
            ArpEvent(0.5, 0, 88, 0.125, 0), ArpEvent(0.625, 2, 72, 0.125, 0),
            ArpEvent(0.75, 1, 82, 0.125, 0), ArpEvent(0.875, 0, 78, 0.125, 0),
        ],
    ),
    "country_1": ArpPattern(
        name="Country 1", category="guitar", events=[
            # 알터네이팅 베이스 + 브러시 스트럼
            ArpEvent(0.0, 0, 95, 0.125, 0, False),
            ArpEvent(0.125, 1, 70, 0.0625, 0, True),
            ArpEvent(0.1875, 2, 65, 0.0625, 0, True),
            ArpEvent(0.25, 2, 90, 0.125, 0, False),
            ArpEvent(0.375, 1, 68, 0.0625, 0, True),
            ArpEvent(0.4375, 2, 63, 0.0625, 0, True),
            ArpEvent(0.5, 0, 92, 0.125, 0, False),
            ArpEvent(0.625, 1, 72, 0.0625, 0, True),
            ArpEvent(0.6875, 2, 67, 0.0625, 0, True),
            ArpEvent(0.75, 2, 88, 0.125, 0, False),
            ArpEvent(0.875, 1, 70, 0.0625, 0, True),
            ArpEvent(0.9375, 2, 65, 0.0625, 0, True),
        ],
    ),
    "country_2": ArpPattern(
        name="Country 2", category="guitar", events=[
            ArpEvent(0.0, 0, 92, 0.125, 0, False),
            ArpEvent(0.125, 1, 75, 0.125, 0, True),
            ArpEvent(0.25, 2, 88, 0.125, 0, False),
            ArpEvent(0.375, 1, 72, 0.125, 0, True),
            ArpEvent(0.5, 0, 90, 0.125, 0, False),
            ArpEvent(0.625, 1, 73, 0.125, 0, True),
            ArpEvent(0.75, 2, 85, 0.125, 0, False),
            ArpEvent(0.875, 1, 70, 0.125, 0, True),
        ],
    ),
    "clean_rock_1": ArpPattern(
        name="Clean Rock 1", category="guitar", events=[
            ArpEvent(0.0, 0, 95, 0.25, 0, True),
            ArpEvent(0.25, 0, 45, 0.0625, 0, True),
            ArpEvent(0.5, 0, 92, 0.25, 0, True),
            ArpEvent(0.75, 0, 42, 0.0625, 0, True),
            ArpEvent(0.875, 0, 85, 0.125, 0, True),
        ],
    ),
    "clean_rock_2": ArpPattern(
        name="Clean Rock 2", category="guitar", events=[
            ArpEvent(0.0, 0, 90, 0.125, 0), ArpEvent(0.125, 1, 80, 0.125, 0),
            ArpEvent(0.25, 2, 85, 0.125, 0), ArpEvent(0.375, 1, 75, 0.125, 0),
            ArpEvent(0.5, 0, 88, 0.125, 0), ArpEvent(0.625, 1, 78, 0.125, 0),
            ArpEvent(0.75, 2, 82, 0.125, 0), ArpEvent(0.875, 1, 72, 0.125, 0),
        ],
    ),
    "spanish": ArpPattern(
        name="Spanish", category="guitar", events=[
            # 라스게아도 스타일 빠른 스트럼
            ArpEvent(0.0, 0, 100, 0.02, 0), ArpEvent(0.02, 1, 95, 0.02, 2),
            ArpEvent(0.04, 2, 90, 0.02, 4), ArpEvent(0.06, 3, 85, 0.02, 6),
            ArpEvent(0.08, 2, 80, 0.18, 8),
            ArpEvent(0.25, 0, 70, 0.0625, 0, True),
            ArpEvent(0.5, 0, 95, 0.02, 0), ArpEvent(0.52, 1, 90, 0.02, 2),
            ArpEvent(0.54, 2, 85, 0.02, 4), ArpEvent(0.56, 3, 80, 0.02, 6),
            ArpEvent(0.58, 2, 75, 0.18, 8),
            ArpEvent(0.75, 0, 68, 0.0625, 0, True),
        ],
    ),
    "salsa": ArpPattern(
        name="Salsa Guitar", category="guitar", events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0, True),
            ArpEvent(0.125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 82, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 40, 0.0625, 0, True),
            ArpEvent(0.375, 1, 85, 0.0625, 0, True),
            ArpEvent(0.5, 0, 88, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 42, 0.0625, 0, True),
            ArpEvent(0.6875, 1, 80, 0.0625, 0, True),
            ArpEvent(0.75, 0, 40, 0.0625, 0, True),
            ArpEvent(0.875, 1, 83, 0.0625, 0, True),
        ],
    ),
    "electric_picking": ArpPattern(
        name="Electric Picking", category="guitar", events=[
            ArpEvent(0.0, 0, 90, 0.125, 0), ArpEvent(0.125, 2, 78, 0.125, 0),
            ArpEvent(0.25, 1, 82, 0.125, 0), ArpEvent(0.375, 2, 75, 0.125, 0),
            ArpEvent(0.5, 0, 88, 0.125, 0), ArpEvent(0.625, 2, 76, 0.125, 0),
            ArpEvent(0.75, 1, 80, 0.125, 0), ArpEvent(0.875, 2, 73, 0.125, 0),
        ],
    ),
    "steel_strummer": ArpPattern(
        name="Steel Strummer", category="guitar", events=[
            ArpEvent(0.0, 0, 95, 0.2, 0, True),
            ArpEvent(0.25, 0, 50, 0.05, 0, True),
            ArpEvent(0.375, 0, 88, 0.15, 0, True),
            ArpEvent(0.5, 0, 92, 0.2, 0, True),
            ArpEvent(0.75, 0, 48, 0.05, 0, True),
            ArpEvent(0.875, 0, 85, 0.15, 0, True),
        ],
    ),
}

# ---------------------------------------------------------------------------
# 패턴 정의 - Piano
# ---------------------------------------------------------------------------

_PIANO_PATTERNS: Dict[str, ArpPattern] = {
    "bossa_piano": ArpPattern(
        name="Bossa Piano", category="piano", length_bars=2, events=[
            # 바 1: 싱코페이션 보사 컴핑
            ArpEvent(0.0, 0, 80, 0.125, 0, False),
            ArpEvent(0.125, 1, 65, 0.0625, 3, True),
            ArpEvent(0.25, 2, 60, 0.0625, 0, True),
            ArpEvent(0.375, 1, 62, 0.0625, -2, True),
            ArpEvent(0.5, 0, 78, 0.125, 0, False),
            ArpEvent(0.625, 2, 63, 0.0625, 4, True),
            ArpEvent(0.75, 1, 58, 0.0625, 0, True),
            ArpEvent(0.875, 0, 68, 0.125, 0, False),
            # 바 2
            ArpEvent(1.0, 0, 78, 0.125, 0, False),
            ArpEvent(1.125, 1, 63, 0.0625, 3, True),
            ArpEvent(1.25, 2, 58, 0.0625, 0, True),
            ArpEvent(1.5, 0, 75, 0.125, 0, False),
            ArpEvent(1.625, 1, 60, 0.0625, 5, True),
            ArpEvent(1.75, 3, 55, 0.0625, 0, True),
            ArpEvent(1.875, 0, 65, 0.125, 0, False),
        ],
    ),
    "ballade_1": ArpPattern(
        name="Ballade 1", category="piano", events=[
            ArpEvent(0.0, 0, 75, 0.25, 0), ArpEvent(0.125, 1, 60, 0.125, 0),
            ArpEvent(0.25, 2, 55, 0.125, 0), ArpEvent(0.375, 3, 50, 0.125, 0),
            ArpEvent(0.5, 2, 55, 0.125, 0), ArpEvent(0.625, 1, 52, 0.125, 0),
            ArpEvent(0.75, 0, 70, 0.25, 0),
        ],
    ),
    "ballade_2": ArpPattern(
        name="Ballade 2", category="piano", events=[
            ArpEvent(0.0, 0, 72, 0.25, 0), ArpEvent(0.0625, 1, 55, 0.1875, 5),
            ArpEvent(0.125, 2, 50, 0.125, 10), ArpEvent(0.25, 3, 48, 0.125, 0),
            ArpEvent(0.375, 4, 45, 0.125, 0), ArpEvent(0.5, 3, 50, 0.125, 0),
            ArpEvent(0.625, 2, 48, 0.125, 0), ArpEvent(0.75, 1, 52, 0.25, 0),
        ],
    ),
    "ballade_3": ArpPattern(
        name="Ballade 3", category="piano", length_bars=2, events=[
            ArpEvent(0.0, 0, 70, 0.5, 0), ArpEvent(0.125, 1, 55, 0.375, 8),
            ArpEvent(0.25, 2, 50, 0.25, 15),
            ArpEvent(0.5, 0, 68, 0.5, 0), ArpEvent(0.625, 2, 52, 0.375, 6),
            ArpEvent(0.75, 1, 48, 0.25, 12),
            ArpEvent(1.0, 0, 72, 0.5, 0), ArpEvent(1.125, 1, 55, 0.375, 10),
            ArpEvent(1.25, 3, 48, 0.25, 15),
            ArpEvent(1.5, 2, 50, 0.5, 0), ArpEvent(1.75, 1, 52, 0.25, 8),
        ],
    ),
    "funky_piano_1": ArpPattern(
        name="Funky Piano 1", category="piano", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 85, 0.0625, 0, True),
            ArpEvent(0.25, 0, 45, 0.0625, 0, True),
            ArpEvent(0.375, 1, 90, 0.0625, 0, True),
            ArpEvent(0.5, 0, 95, 0.0625, 0, True),
            ArpEvent(0.6875, 1, 82, 0.0625, 0, True),
            ArpEvent(0.75, 0, 42, 0.0625, 0, True),
            ArpEvent(0.875, 1, 88, 0.0625, 0, True),
        ],
    ),
    "funky_piano_2": ArpPattern(
        name="Funky Piano 2", category="piano", events=[
            ArpEvent(0.0, 0, 98, 0.0625, 0, True),
            ArpEvent(0.0625, 0, 40, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 88, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 42, 0.0625, 0, True),
            ArpEvent(0.375, 1, 92, 0.0625, 0, True),
            ArpEvent(0.5, 0, 96, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 38, 0.0625, 0, True),
            ArpEvent(0.6875, 1, 86, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 40, 0.0625, 0, True),
            ArpEvent(0.875, 1, 90, 0.0625, 0, True),
        ],
    ),
    "funky_piano_3": ArpPattern(
        name="Funky Piano 3", category="piano", events=[
            ArpEvent(0.0, 0, 95, 0.05, 0, True),
            ArpEvent(0.125, 0, 42, 0.05, 0, True),
            ArpEvent(0.25, 1, 90, 0.05, 0, True),
            ArpEvent(0.375, 0, 40, 0.05, 0, True),
            ArpEvent(0.4375, 1, 85, 0.05, 0, True),
            ArpEvent(0.5, 0, 92, 0.05, 0, True),
            ArpEvent(0.625, 0, 44, 0.05, 0, True),
            ArpEvent(0.75, 1, 88, 0.05, 0, True),
            ArpEvent(0.875, 0, 38, 0.05, 0, True),
            ArpEvent(0.9375, 1, 82, 0.05, 0, True),
        ],
    ),
    "funky_piano_4": ArpPattern(
        name="Funky Piano 4", category="piano", swing=0.2, events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0, True),
            ArpEvent(0.1875, 0, 85, 0.0625, 0, True),
            ArpEvent(0.25, 0, 42, 0.0625, 0, True),
            ArpEvent(0.4375, 0, 90, 0.0625, 0, True),
            ArpEvent(0.5, 0, 95, 0.0625, 0, True),
            ArpEvent(0.6875, 0, 82, 0.0625, 0, True),
            ArpEvent(0.75, 0, 40, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 88, 0.0625, 0, True),
        ],
    ),
    "funky_piano_5": ArpPattern(
        name="Funky Piano 5", category="piano", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0, True),
            ArpEvent(0.125, 1, 75, 0.0625, 0, True),
            ArpEvent(0.1875, 0, 40, 0.0625, 0, True),
            ArpEvent(0.3125, 1, 88, 0.0625, 0, True),
            ArpEvent(0.5, 0, 96, 0.0625, 0, True),
            ArpEvent(0.625, 1, 72, 0.0625, 0, True),
            ArpEvent(0.6875, 0, 42, 0.0625, 0, True),
            ArpEvent(0.8125, 1, 85, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 90, 0.0625, 0, True),
        ],
    ),
    "funky_piano_6": ArpPattern(
        name="Funky Piano 6", category="piano", events=[
            ArpEvent(0.0, 0, 95, 0.0625, 0, True),
            ArpEvent(0.0625, 0, 38, 0.0625, 0, True),
            ArpEvent(0.125, 1, 82, 0.0625, 0, True),
            ArpEvent(0.25, 0, 90, 0.0625, 0, True),
            ArpEvent(0.375, 1, 85, 0.0625, 0, True),
            ArpEvent(0.4375, 0, 40, 0.0625, 0, True),
            ArpEvent(0.5, 0, 92, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 36, 0.0625, 0, True),
            ArpEvent(0.625, 1, 80, 0.0625, 0, True),
            ArpEvent(0.75, 0, 88, 0.0625, 0, True),
            ArpEvent(0.875, 1, 83, 0.0625, 0, True),
            ArpEvent(0.9375, 0, 38, 0.0625, 0, True),
        ],
    ),
    "latin_1": ArpPattern(
        name="Latin Piano 1", category="piano", events=[
            # 몬투노 패턴
            ArpEvent(0.0, 0, 88, 0.0625, 0), ArpEvent(0.0625, 2, 72, 0.0625, 0),
            ArpEvent(0.125, 1, 80, 0.0625, 0), ArpEvent(0.25, 2, 85, 0.0625, 0),
            ArpEvent(0.3125, 0, 70, 0.0625, 0), ArpEvent(0.375, 1, 82, 0.0625, 0),
            ArpEvent(0.5, 0, 86, 0.0625, 0), ArpEvent(0.5625, 2, 70, 0.0625, 0),
            ArpEvent(0.625, 1, 78, 0.0625, 0), ArpEvent(0.75, 2, 82, 0.0625, 0),
            ArpEvent(0.8125, 0, 68, 0.0625, 0), ArpEvent(0.875, 1, 80, 0.0625, 0),
        ],
    ),
    "latin_2": ArpPattern(
        name="Latin Piano 2", category="piano", events=[
            ArpEvent(0.0, 0, 85, 0.0625, 0, True),
            ArpEvent(0.125, 1, 78, 0.0625, 0),
            ArpEvent(0.1875, 2, 72, 0.0625, 0),
            ArpEvent(0.3125, 1, 75, 0.0625, 0),
            ArpEvent(0.375, 0, 82, 0.0625, 0, True),
            ArpEvent(0.5, 2, 76, 0.0625, 0),
            ArpEvent(0.625, 1, 72, 0.0625, 0),
            ArpEvent(0.6875, 0, 80, 0.0625, 0, True),
            ArpEvent(0.8125, 2, 70, 0.0625, 0),
            ArpEvent(0.875, 1, 74, 0.0625, 0),
        ],
    ),
    "latin_3": ArpPattern(
        name="Latin Piano 3", category="piano", events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0), ArpEvent(0.0625, 1, 75, 0.0625, 0),
            ArpEvent(0.1875, 2, 70, 0.0625, 0), ArpEvent(0.25, 0, 85, 0.0625, 0),
            ArpEvent(0.375, 1, 78, 0.0625, 0), ArpEvent(0.4375, 2, 72, 0.0625, 0),
            ArpEvent(0.5, 0, 88, 0.0625, 0), ArpEvent(0.5625, 1, 73, 0.0625, 0),
            ArpEvent(0.6875, 2, 68, 0.0625, 0), ArpEvent(0.75, 0, 83, 0.0625, 0),
            ArpEvent(0.875, 1, 76, 0.0625, 0), ArpEvent(0.9375, 2, 70, 0.0625, 0),
        ],
    ),
    "mambo_1": ArpPattern(
        name="Mambo 1", category="piano", events=[
            ArpEvent(0.0, 0, 92, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 80, 0.0625, 0),
            ArpEvent(0.25, 2, 75, 0.0625, 0),
            ArpEvent(0.375, 0, 88, 0.0625, 0, True),
            ArpEvent(0.5, 1, 82, 0.0625, 0),
            ArpEvent(0.6875, 2, 78, 0.0625, 0),
            ArpEvent(0.75, 0, 85, 0.0625, 0, True),
            ArpEvent(0.875, 1, 76, 0.0625, 0),
        ],
    ),
    "mambo_2": ArpPattern(
        name="Mambo 2", category="piano", events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0), ArpEvent(0.0625, 2, 75, 0.0625, 0),
            ArpEvent(0.1875, 1, 82, 0.0625, 0), ArpEvent(0.25, 0, 45, 0.0625, 0),
            ArpEvent(0.375, 2, 80, 0.0625, 0), ArpEvent(0.4375, 1, 72, 0.0625, 0),
            ArpEvent(0.5, 0, 88, 0.0625, 0), ArpEvent(0.5625, 2, 73, 0.0625, 0),
            ArpEvent(0.6875, 1, 80, 0.0625, 0), ArpEvent(0.75, 0, 43, 0.0625, 0),
            ArpEvent(0.875, 2, 78, 0.0625, 0), ArpEvent(0.9375, 1, 70, 0.0625, 0),
        ],
    ),
    "salsa_1": ArpPattern(
        name="Salsa Piano 1", category="piano", events=[
            ArpEvent(0.0, 0, 88, 0.0625, 0), ArpEvent(0.0625, 1, 72, 0.0625, 0),
            ArpEvent(0.125, 2, 68, 0.0625, 0), ArpEvent(0.25, 0, 85, 0.0625, 0),
            ArpEvent(0.3125, 1, 74, 0.0625, 0), ArpEvent(0.375, 2, 70, 0.0625, 0),
            ArpEvent(0.5, 0, 86, 0.0625, 0), ArpEvent(0.5625, 1, 70, 0.0625, 0),
            ArpEvent(0.625, 2, 66, 0.0625, 0), ArpEvent(0.75, 0, 82, 0.0625, 0),
            ArpEvent(0.8125, 1, 72, 0.0625, 0), ArpEvent(0.875, 2, 68, 0.0625, 0),
        ],
    ),
    "salsa_2": ArpPattern(
        name="Salsa Piano 2", category="piano", events=[
            ArpEvent(0.0, 0, 90, 0.0625, 0, True),
            ArpEvent(0.1875, 1, 78, 0.0625, 0),
            ArpEvent(0.25, 0, 42, 0.0625, 0),
            ArpEvent(0.375, 2, 82, 0.0625, 0),
            ArpEvent(0.5, 0, 88, 0.0625, 0, True),
            ArpEvent(0.6875, 1, 76, 0.0625, 0),
            ArpEvent(0.75, 0, 40, 0.0625, 0),
            ArpEvent(0.875, 2, 80, 0.0625, 0),
        ],
    ),
    "salsa_3": ArpPattern(
        name="Salsa Piano 3", category="piano", events=[
            ArpEvent(0.0, 0, 85, 0.0625, 0), ArpEvent(0.0625, 2, 70, 0.0625, 0),
            ArpEvent(0.1875, 1, 78, 0.0625, 0), ArpEvent(0.3125, 0, 82, 0.0625, 0),
            ArpEvent(0.375, 2, 72, 0.0625, 0), ArpEvent(0.5, 1, 80, 0.0625, 0),
            ArpEvent(0.5625, 0, 83, 0.0625, 0), ArpEvent(0.6875, 2, 68, 0.0625, 0),
            ArpEvent(0.8125, 1, 76, 0.0625, 0), ArpEvent(0.9375, 0, 80, 0.0625, 0),
        ],
    ),
    "samba_piano_1": ArpPattern(
        name="Samba Piano 1", category="piano", events=[
            ArpEvent(0.0, 0, 88, 0.0625, 0, True),
            ArpEvent(0.0625, 0, 42, 0.0625, 0, True),
            ArpEvent(0.125, 1, 80, 0.0625, 0),
            ArpEvent(0.25, 0, 85, 0.0625, 0, True),
            ArpEvent(0.3125, 0, 40, 0.0625, 0, True),
            ArpEvent(0.375, 1, 78, 0.0625, 0),
            ArpEvent(0.5, 0, 86, 0.0625, 0, True),
            ArpEvent(0.5625, 0, 42, 0.0625, 0, True),
            ArpEvent(0.625, 1, 76, 0.0625, 0),
            ArpEvent(0.75, 0, 82, 0.0625, 0, True),
            ArpEvent(0.8125, 0, 38, 0.0625, 0, True),
            ArpEvent(0.875, 1, 74, 0.0625, 0),
        ],
    ),
    "samba_piano_2": ArpPattern(
        name="Samba Piano 2", category="piano", swing=0.15, events=[
            ArpEvent(0.0, 0, 85, 0.0625, 0), ArpEvent(0.0625, 2, 70, 0.0625, 0),
            ArpEvent(0.1875, 1, 75, 0.0625, 0), ArpEvent(0.25, 2, 68, 0.0625, 0),
            ArpEvent(0.375, 0, 82, 0.0625, 0), ArpEvent(0.4375, 2, 66, 0.0625, 0),
            ArpEvent(0.5, 1, 78, 0.0625, 0), ArpEvent(0.5625, 0, 80, 0.0625, 0),
            ArpEvent(0.6875, 2, 72, 0.0625, 0), ArpEvent(0.75, 1, 74, 0.0625, 0),
            ArpEvent(0.875, 0, 78, 0.0625, 0), ArpEvent(0.9375, 2, 65, 0.0625, 0),
        ],
    ),
    "movie_ballade_1": ArpPattern(
        name="Movie Ballade 1", category="piano", events=[
            ArpEvent(0.0, 0, 65, 0.5, 0), ArpEvent(0.125, 1, 50, 0.375, 10),
            ArpEvent(0.25, 2, 48, 0.25, 18), ArpEvent(0.375, 3, 45, 0.25, 25),
            ArpEvent(0.5, 2, 48, 0.25, 0), ArpEvent(0.625, 1, 46, 0.375, 12),
            ArpEvent(0.75, 0, 60, 0.25, 0),
        ],
    ),
    "movie_ballade_2": ArpPattern(
        name="Movie Ballade 2", category="piano", length_bars=2, events=[
            ArpEvent(0.0, 0, 60, 0.5, 0), ArpEvent(0.25, 1, 48, 0.25, 15),
            ArpEvent(0.5, 2, 45, 0.25, 20), ArpEvent(0.75, 3, 42, 0.5, 0),
            ArpEvent(1.0, 2, 46, 0.25, 0), ArpEvent(1.25, 1, 44, 0.25, 12),
            ArpEvent(1.5, 0, 58, 0.5, 0), ArpEvent(1.75, 1, 42, 0.25, 18),
        ],
    ),
    "movie_ballade_3": ArpPattern(
        name="Movie Ballade 3", category="piano", events=[
            ArpEvent(0.0, 0, 62, 0.25, 0),
            ArpEvent(0.0625, 2, 45, 0.1875, 12),
            ArpEvent(0.125, 4, 42, 0.125, 22),
            ArpEvent(0.25, 3, 48, 0.125, 0),
            ArpEvent(0.375, 2, 44, 0.125, 8),
            ArpEvent(0.5, 0, 60, 0.25, 0),
            ArpEvent(0.5625, 1, 46, 0.1875, 10),
            ArpEvent(0.625, 2, 43, 0.125, 18),
            ArpEvent(0.75, 1, 45, 0.25, 0),
        ],
    ),
}

# ---------------------------------------------------------------------------
# 패턴 정의 - Sequence (EDM/Electronic)
# ---------------------------------------------------------------------------

_SEQUENCE_PATTERNS: Dict[str, ArpPattern] = {
    "pop_sequence_1": ArpPattern(
        name="Pop Sequence 1", category="sequence", events=[
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.125, 1, 85, 0.125, 0),
            ArpEvent(0.25, 2, 90, 0.125, 0), ArpEvent(0.375, 1, 80, 0.125, 0),
            ArpEvent(0.5, 0, 95, 0.125, 0), ArpEvent(0.625, 2, 82, 0.125, 0),
            ArpEvent(0.75, 1, 88, 0.125, 0), ArpEvent(0.875, 0, 78, 0.125, 0),
        ],
    ),
    "pop_sequence_2": ArpPattern(
        name="Pop Sequence 2", category="sequence", events=[
            ArpEvent(0.0, 0, 100, 0.25, 0, True),
            ArpEvent(0.25, 1, 80, 0.125, 0),
            ArpEvent(0.375, 2, 75, 0.125, 0),
            ArpEvent(0.5, 0, 90, 0.25, 0, True),
            ArpEvent(0.75, 2, 78, 0.125, 0),
            ArpEvent(0.875, 1, 72, 0.125, 0),
        ],
    ),
    "pop_sequence_3": ArpPattern(
        name="Pop Sequence 3", category="sequence", events=[
            ArpEvent(0.0, 0, 95, 0.125, 0), ArpEvent(0.125, 0, 60, 0.125, 0),
            ArpEvent(0.25, 1, 90, 0.125, 0), ArpEvent(0.375, 1, 55, 0.125, 0),
            ArpEvent(0.5, 2, 88, 0.125, 0), ArpEvent(0.625, 2, 52, 0.125, 0),
            ArpEvent(0.75, 1, 85, 0.125, 0), ArpEvent(0.875, 0, 80, 0.125, 0),
        ],
    ),
    "pop_sequence_4": ArpPattern(
        name="Pop Sequence 4", category="sequence", length_bars=2, events=[
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.25, 1, 85, 0.125, 0),
            ArpEvent(0.5, 2, 90, 0.125, 0), ArpEvent(0.75, 0, 80, 0.25, 0),
            ArpEvent(1.0, 0, 95, 0.125, 0), ArpEvent(1.25, 2, 82, 0.125, 0),
            ArpEvent(1.5, 1, 88, 0.125, 0), ArpEvent(1.75, 0, 78, 0.25, 0),
        ],
    ),
    "tech_sequence_1": ArpPattern(
        name="Tech Sequence 1", category="sequence", events=[
            ArpEvent(i * 0.0625, 0, 110 - (i % 2) * 40, 0.05, 0)
            for i in range(16)
        ],
    ),
    "tech_sequence_2": ArpPattern(
        name="Tech Sequence 2", category="sequence", events=[
            ArpEvent(0.0, 0, 110, 0.0625, 0), ArpEvent(0.0625, 2, 70, 0.0625, 0),
            ArpEvent(0.125, 0, 105, 0.0625, 0), ArpEvent(0.1875, 1, 65, 0.0625, 0),
            ArpEvent(0.25, 0, 108, 0.0625, 0), ArpEvent(0.3125, 2, 72, 0.0625, 0),
            ArpEvent(0.375, 0, 100, 0.0625, 0), ArpEvent(0.4375, 1, 68, 0.0625, 0),
            ArpEvent(0.5, 0, 107, 0.0625, 0), ArpEvent(0.5625, 2, 70, 0.0625, 0),
            ArpEvent(0.625, 0, 103, 0.0625, 0), ArpEvent(0.6875, 3, 75, 0.0625, 0),
            ArpEvent(0.75, 0, 105, 0.0625, 0), ArpEvent(0.8125, 2, 68, 0.0625, 0),
            ArpEvent(0.875, 0, 100, 0.0625, 0), ArpEvent(0.9375, 1, 72, 0.0625, 0),
        ],
    ),
    "tech_sequence_3": ArpPattern(
        name="Tech Sequence 3", category="sequence", events=[
            ArpEvent(0.0, 0, 105, 0.0625, 0), ArpEvent(0.125, 0, 95, 0.0625, 0),
            ArpEvent(0.1875, 2, 80, 0.0625, 0), ArpEvent(0.25, 0, 100, 0.0625, 0),
            ArpEvent(0.375, 1, 85, 0.0625, 0), ArpEvent(0.4375, 0, 90, 0.0625, 0),
            ArpEvent(0.5, 0, 102, 0.0625, 0), ArpEvent(0.625, 0, 92, 0.0625, 0),
            ArpEvent(0.6875, 2, 78, 0.0625, 0), ArpEvent(0.75, 0, 98, 0.0625, 0),
            ArpEvent(0.875, 1, 82, 0.0625, 0), ArpEvent(0.9375, 0, 88, 0.0625, 0),
        ],
    ),
    "tech_sequence_4": ArpPattern(
        name="Tech Sequence 4", category="sequence", events=[
            ArpEvent(0.0, 0, 110, 0.0625, 0, True),
            ArpEvent(0.125, 0, 50, 0.0625, 0),
            ArpEvent(0.25, 0, 105, 0.0625, 0, True),
            ArpEvent(0.375, 2, 75, 0.0625, 0),
            ArpEvent(0.5, 0, 108, 0.0625, 0, True),
            ArpEvent(0.625, 0, 48, 0.0625, 0),
            ArpEvent(0.75, 0, 103, 0.0625, 0, True),
            ArpEvent(0.875, 1, 80, 0.0625, 0),
        ],
    ),
    "tech_sequence_5": ArpPattern(
        name="Tech Sequence 5", category="sequence", length_bars=2, events=[
            ArpEvent(0.0, 0, 108, 0.0625, 0), ArpEvent(0.0625, 2, 72, 0.0625, 0),
            ArpEvent(0.1875, 1, 68, 0.0625, 0), ArpEvent(0.25, 0, 104, 0.0625, 0),
            ArpEvent(0.375, 2, 75, 0.0625, 0), ArpEvent(0.5, 0, 106, 0.0625, 0),
            ArpEvent(0.625, 1, 70, 0.0625, 0), ArpEvent(0.75, 0, 100, 0.0625, 0),
            ArpEvent(0.875, 3, 78, 0.0625, 0),
            ArpEvent(1.0, 0, 106, 0.0625, 0), ArpEvent(1.0625, 2, 70, 0.0625, 0),
            ArpEvent(1.1875, 1, 66, 0.0625, 0), ArpEvent(1.25, 0, 102, 0.0625, 0),
            ArpEvent(1.375, 3, 73, 0.0625, 0), ArpEvent(1.5, 0, 104, 0.0625, 0),
            ArpEvent(1.625, 2, 68, 0.0625, 0), ArpEvent(1.75, 0, 98, 0.0625, 0),
            ArpEvent(1.875, 1, 76, 0.0625, 0),
        ],
    ),
    "prelude_sequence": ArpPattern(
        name="Prelude Sequence", category="sequence", events=[
            ArpEvent(0.0, 0, 80, 0.125, 0), ArpEvent(0.0625, 1, 65, 0.0625, 5),
            ArpEvent(0.125, 2, 70, 0.125, 0), ArpEvent(0.1875, 3, 60, 0.0625, 8),
            ArpEvent(0.25, 2, 68, 0.125, 0), ArpEvent(0.3125, 1, 62, 0.0625, 5),
            ArpEvent(0.375, 0, 72, 0.125, 0), ArpEvent(0.4375, 1, 58, 0.0625, 8),
            ArpEvent(0.5, 0, 78, 0.125, 0), ArpEvent(0.5625, 1, 63, 0.0625, 5),
            ArpEvent(0.625, 2, 68, 0.125, 0), ArpEvent(0.6875, 3, 58, 0.0625, 8),
            ArpEvent(0.75, 2, 66, 0.125, 0), ArpEvent(0.8125, 1, 60, 0.0625, 5),
            ArpEvent(0.875, 0, 70, 0.125, 0), ArpEvent(0.9375, 1, 56, 0.0625, 8),
        ],
    ),
    "sixty_nine_sequence": ArpPattern(
        name="69 Sequence", category="sequence", events=[
            ArpEvent(0.0, 0, 100, 0.0625, 0), ArpEvent(0.0625, 2, 85, 0.0625, 0),
            ArpEvent(0.125, 4, 90, 0.0625, 0), ArpEvent(0.1875, 2, 80, 0.0625, 0),
            ArpEvent(0.25, 0, 95, 0.0625, 0), ArpEvent(0.3125, 1, 78, 0.0625, 0),
            ArpEvent(0.375, 3, 85, 0.0625, 0), ArpEvent(0.4375, 1, 75, 0.0625, 0),
            ArpEvent(0.5, 0, 98, 0.0625, 0), ArpEvent(0.5625, 2, 82, 0.0625, 0),
            ArpEvent(0.625, 4, 88, 0.0625, 0), ArpEvent(0.6875, 3, 78, 0.0625, 0),
            ArpEvent(0.75, 1, 92, 0.0625, 0), ArpEvent(0.8125, 0, 75, 0.0625, 0),
            ArpEvent(0.875, 2, 85, 0.0625, 0), ArpEvent(0.9375, 0, 80, 0.0625, 0),
        ],
    ),
}

# ---------------------------------------------------------------------------
# 패턴 정의 - Bass
# ---------------------------------------------------------------------------

_BASS_PATTERNS: Dict[str, ArpPattern] = {
    "walking_bass": ArpPattern(
        name="Walking Bass", category="bass", events=[
            ArpEvent(0.0, 0, 95, 0.25, 0), ArpEvent(0.25, 1, 85, 0.25, 0),
            ArpEvent(0.5, 2, 88, 0.25, 0), ArpEvent(0.75, 1, 82, 0.25, 0),
        ],
    ),
    "root_fifth": ArpPattern(
        name="Root-Fifth", category="bass", events=[
            ArpEvent(0.0, 0, 100, 0.25, 0), ArpEvent(0.25, 0, 70, 0.125, 0),
            ArpEvent(0.5, 2, 90, 0.25, 0), ArpEvent(0.75, 2, 65, 0.125, 0),
        ],
    ),
    "octave_bass": ArpPattern(
        name="Octave Bass", category="bass", events=[
            ArpEvent(0.0, 0, 100, 0.125, 0), ArpEvent(0.125, 0, 75, 0.125, 0),
            ArpEvent(0.25, 0, 95, 0.125, 0), ArpEvent(0.375, 0, 70, 0.125, 0),
            ArpEvent(0.5, 0, 98, 0.125, 0), ArpEvent(0.625, 0, 72, 0.125, 0),
            ArpEvent(0.75, 0, 92, 0.125, 0), ArpEvent(0.875, 0, 68, 0.125, 0),
        ],
    ),
    "syncopated_bass": ArpPattern(
        name="Syncopated Bass", category="bass", events=[
            ArpEvent(0.0, 0, 100, 0.1875, 0), ArpEvent(0.1875, 0, 75, 0.0625, 0),
            ArpEvent(0.375, 2, 90, 0.125, 0), ArpEvent(0.5, 0, 95, 0.1875, 0),
            ArpEvent(0.6875, 0, 72, 0.0625, 0), ArpEvent(0.875, 1, 85, 0.125, 0),
        ],
    ),
    "funk_bass": ArpPattern(
        name="Funk Bass", category="bass", events=[
            ArpEvent(0.0, 0, 105, 0.0625, 0), ArpEvent(0.0625, 0, 40, 0.0625, 0),
            ArpEvent(0.1875, 0, 90, 0.0625, 0), ArpEvent(0.25, 0, 42, 0.0625, 0),
            ArpEvent(0.375, 2, 95, 0.0625, 0), ArpEvent(0.4375, 0, 38, 0.0625, 0),
            ArpEvent(0.5, 0, 100, 0.0625, 0), ArpEvent(0.5625, 0, 42, 0.0625, 0),
            ArpEvent(0.6875, 0, 88, 0.0625, 0), ArpEvent(0.75, 1, 92, 0.0625, 0),
            ArpEvent(0.875, 0, 85, 0.0625, 0), ArpEvent(0.9375, 0, 40, 0.0625, 0),
        ],
    ),
    "slap_bass": ArpPattern(
        name="Slap Bass", category="bass", events=[
            ArpEvent(0.0, 0, 110, 0.0625, 0), ArpEvent(0.125, 0, 45, 0.0625, 0),
            ArpEvent(0.1875, 2, 95, 0.0625, 0), ArpEvent(0.25, 0, 105, 0.0625, 0),
            ArpEvent(0.375, 0, 42, 0.0625, 0), ArpEvent(0.4375, 1, 90, 0.0625, 0),
            ArpEvent(0.5, 0, 108, 0.0625, 0), ArpEvent(0.625, 0, 44, 0.0625, 0),
            ArpEvent(0.6875, 2, 92, 0.0625, 0), ArpEvent(0.75, 0, 102, 0.0625, 0),
            ArpEvent(0.875, 0, 40, 0.0625, 0), ArpEvent(0.9375, 1, 88, 0.0625, 0),
        ],
    ),
    "reggae_bass": ArpPattern(
        name="Reggae Bass", category="bass", events=[
            ArpEvent(0.0, 0, 95, 0.375, 0),
            ArpEvent(0.5, 0, 85, 0.25, 0),
            ArpEvent(0.875, 2, 78, 0.125, 0),
        ],
    ),
    "latin_bass": ArpPattern(
        name="Latin Bass", category="bass", events=[
            ArpEvent(0.0, 0, 95, 0.125, 0), ArpEvent(0.1875, 2, 80, 0.0625, 0),
            ArpEvent(0.25, 0, 90, 0.125, 0), ArpEvent(0.4375, 1, 78, 0.0625, 0),
            ArpEvent(0.5, 0, 92, 0.125, 0), ArpEvent(0.6875, 2, 82, 0.0625, 0),
            ArpEvent(0.75, 1, 88, 0.125, 0), ArpEvent(0.9375, 0, 75, 0.0625, 0),
        ],
    ),
}

# ---------------------------------------------------------------------------
# 패턴 정의 - Pad
# ---------------------------------------------------------------------------

_PAD_PATTERNS: Dict[str, ArpPattern] = {
    "slow_swell": ArpPattern(
        name="Slow Swell", category="pad", events=[
            ArpEvent(0.0, 0, 30, 1.0, 0, True),
        ],
    ),
    "rhythmic_pad": ArpPattern(
        name="Rhythmic Pad", category="pad", events=[
            ArpEvent(0.0, 0, 70, 0.25, 0, True),
            ArpEvent(0.25, 0, 40, 0.25, 0, True),
            ArpEvent(0.5, 0, 68, 0.25, 0, True),
            ArpEvent(0.75, 0, 38, 0.25, 0, True),
        ],
    ),
    "pulsing_pad": ArpPattern(
        name="Pulsing Pad", category="pad", events=[
            ArpEvent(0.0, 0, 75, 0.125, 0, True),
            ArpEvent(0.125, 0, 45, 0.125, 0, True),
            ArpEvent(0.25, 0, 72, 0.125, 0, True),
            ArpEvent(0.375, 0, 42, 0.125, 0, True),
            ArpEvent(0.5, 0, 70, 0.125, 0, True),
            ArpEvent(0.625, 0, 40, 0.125, 0, True),
            ArpEvent(0.75, 0, 68, 0.125, 0, True),
            ArpEvent(0.875, 0, 38, 0.125, 0, True),
        ],
    ),
    "evolving_pad": ArpPattern(
        name="Evolving Pad", category="pad", length_bars=4, events=[
            ArpEvent(0.0, 0, 40, 1.0, 0, True),
            ArpEvent(1.0, 0, 55, 1.0, 0, True),
            ArpEvent(2.0, 0, 70, 1.0, 0, True),
            ArpEvent(3.0, 0, 50, 1.0, 0, True),
        ],
    ),
}


# ---------------------------------------------------------------------------
# 통합 패턴 딕셔너리
# ---------------------------------------------------------------------------

ARPEGGIATOR_PATTERNS: Dict[str, ArpPattern] = {
    **_CLASSIC_ARP_PATTERNS,
    **_GUITAR_PATTERNS,
    **_PIANO_PATTERNS,
    **_SEQUENCE_PATTERNS,
    **_BASS_PATTERNS,
    **_PAD_PATTERNS,
}

# 카테고리 → 패턴 키 매핑 (빠른 검색용)
_CATEGORY_INDEX: Dict[str, List[str]] = {}
for _key, _pat in ARPEGGIATOR_PATTERNS.items():
    _CATEGORY_INDEX.setdefault(_pat.category, []).append(_key)

# 스타일 → 추천 패턴 매핑
_STYLE_RECOMMENDATIONS: Dict[str, List[str]] = {
    "ambient": [
        "mellow_arp", "slow_swell", "evolving_pad", "prelude_sequence",
        "ballade_3", "movie_ballade_1", "movie_ballade_2",
    ],
    "pop": [
        "classic_arp", "8th_arp", "pop_sequence_1", "pop_sequence_2",
        "pop_sequence_3", "brit_pop_1", "brit_pop_2", "clean_rock_2",
    ],
    "jazz": [
        "bossa_nova_1", "bossa_nova_2", "bossa_piano", "walking_bass",
        "latin_1", "latin_2", "mellow_arp", "ballade_1",
    ],
    "edm": [
        "trance_line", "tech_sequence_1", "tech_sequence_2", "tech_sequence_3",
        "tech_sequence_4", "pulsating", "fast_arp", "pulsing_pad",
    ],
    "funk": [
        "funk_1", "funk_2", "funky_disco", "funky_piano_1", "funky_piano_2",
        "funky_piano_3", "funk_bass", "slap_bass",
    ],
    "latin": [
        "bossa_nova_1", "bossa_nova_2", "samba_1", "samba_2", "salsa",
        "latin_pop_1", "latin_pop_2", "latin_1", "latin_2", "latin_3",
        "mambo_1", "mambo_2", "salsa_1", "salsa_2", "salsa_3",
        "samba_piano_1", "samba_piano_2", "latin_bass",
    ],
    "reggae": [
        "reggae_1", "reggae_2", "reggae_3", "reggae_bass",
    ],
    "rock": [
        "clean_rock_1", "clean_rock_2", "brit_pop_1", "brit_pop_2",
        "octave_bass", "root_fifth",
    ],
    "country": [
        "country_1", "country_2", "root_fifth", "walking_bass",
    ],
    "classical": [
        "prelude_sequence", "ballade_1", "ballade_2", "ballade_3",
        "classic_arp", "sparkling_arp", "movie_ballade_3",
    ],
    "electronic": [
        "trance_line", "hypnotic_arp", "jarre_arp", "yello_sequence",
        "tech_sequence_1", "tech_sequence_2", "tech_sequence_5",
        "sixty_nine_sequence", "pulsating", "fast_arp",
    ],
    "cinematic": [
        "movie_ballade_1", "movie_ballade_2", "movie_ballade_3",
        "slow_swell", "evolving_pad", "ballade_3",
    ],
    "ballad": [
        "ballade_1", "ballade_2", "ballade_3", "movie_ballade_1",
        "movie_ballade_2", "movie_ballade_3", "mellow_arp",
    ],
}


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------

def get_pattern(name: str) -> ArpPattern:
    """이름으로 아르페지에이터 패턴을 조회합니다.

    Args:
        name: 패턴 키 이름 (예: ``"bossa_nova_1"``).

    Returns:
        해당 ArpPattern 객체.

    Raises:
        KeyError: 패턴 이름이 존재하지 않을 때.
    """
    if name not in ARPEGGIATOR_PATTERNS:
        raise KeyError(
            f"패턴 '{name}'을(를) 찾을 수 없습니다. "
            f"사용 가능한 패턴: {sorted(ARPEGGIATOR_PATTERNS.keys())}"
        )
    return ARPEGGIATOR_PATTERNS[name]


def get_patterns_by_category(category: str) -> List[ArpPattern]:
    """카테고리별 패턴 목록을 반환합니다.

    Args:
        category: 카테고리 이름 (classic_arp, guitar, piano, sequence, bass, pad).

    Returns:
        해당 카테고리의 ArpPattern 리스트.
    """
    keys = _CATEGORY_INDEX.get(category, [])
    return [ARPEGGIATOR_PATTERNS[k] for k in keys]


def get_patterns_by_style(style: str) -> List[ArpPattern]:
    """음악 스타일에 적합한 추천 패턴 목록을 반환합니다.

    Args:
        style: 음악 스타일 (ambient, pop, jazz, edm, funk, latin, reggae,
               rock, country, classical, electronic, cinematic, ballad).

    Returns:
        추천 ArpPattern 리스트. 스타일이 없으면 빈 리스트.
    """
    keys = _STYLE_RECOMMENDATIONS.get(style.lower(), [])
    return [ARPEGGIATOR_PATTERNS[k] for k in keys if k in ARPEGGIATOR_PATTERNS]


def apply_pattern(
    pattern: ArpPattern,
    chord_notes: List[int],
    bar_start_tick: int = 0,
    ticks_per_beat: int = 480,
) -> List[Dict]:
    """패턴을 코드 노트에 적용하여 MIDI 이벤트 리스트를 생성합니다.

    voice_index에 따라 chord_notes 리스트에서 실제 MIDI 피치를 선택합니다.
    코드 톤 수보다 큰 voice_index는 옥타브 위로 래핑됩니다.

    Args:
        pattern: 적용할 ArpPattern.
        chord_notes: MIDI 노트 번호 리스트 (예: [60, 64, 67, 71]).
        bar_start_tick: 바의 시작 틱 위치.
        ticks_per_beat: 분기음표당 틱 수 (기본 480).

    Returns:
        MIDI 이벤트 딕셔너리 리스트.
        각 딕셔너리: ``{pitch, velocity, start_tick, duration_ticks, is_chord}``.
    """
    if not chord_notes:
        return []

    ticks_per_bar = ticks_per_beat * pattern.time_signature[0]
    results: List[Dict] = []

    for ev in pattern.events:
        # voice_index → 실제 피치 매핑
        n_chord = len(chord_notes)
        octave_shift = ev.voice_index // n_chord
        idx = ev.voice_index % n_chord
        pitch = chord_notes[idx] + 12 * octave_shift

        # 틱 계산
        bar_idx = int(ev.position)  # 멀티바 패턴 지원
        pos_in_bar = ev.position - bar_idx
        start_tick = bar_start_tick + int(
            bar_idx * ticks_per_bar + pos_in_bar * ticks_per_bar
        )
        # 오프셋(ms → tick 변환: 120 BPM 기준 근사, 실제로는 BPM 필요)
        start_tick += int(ev.offset_ms * ticks_per_beat / 500)

        duration_ticks = max(1, int(ev.duration * ticks_per_bar))

        if ev.is_chord:
            # 블록 코드: 모든 코드 톤을 동시에 연주
            for note in chord_notes:
                results.append({
                    "pitch": note,
                    "velocity": ev.velocity,
                    "start_tick": start_tick,
                    "duration_ticks": duration_ticks,
                    "is_chord": True,
                })
        else:
            results.append({
                "pitch": pitch,
                "velocity": ev.velocity,
                "start_tick": start_tick,
                "duration_ticks": duration_ticks,
                "is_chord": False,
            })

    return results


def humanize_pattern(pattern: ArpPattern, amount: float = 0.3) -> ArpPattern:
    """패턴에 휴머나이즈(타이밍/벨로시티 변화)를 적용합니다.

    원본 패턴을 변경하지 않고 복사본을 반환합니다.

    Args:
        pattern: 원본 ArpPattern.
        amount: 변화 양 (0.0 = 없음, 1.0 = 최대). 기본 0.3.

    Returns:
        휴머나이즈가 적용된 새 ArpPattern.
    """
    new_pattern = copy.deepcopy(pattern)
    for ev in new_pattern.events:
        # 타이밍 오프셋 추가 (최대 +-15ms * amount)
        ev.offset_ms += random.gauss(0, 8 * amount)
        # 벨로시티 변화 (최대 +-12 * amount)
        vel_delta = int(random.gauss(0, 6 * amount))
        ev.velocity = max(1, min(127, ev.velocity + vel_delta))
    return new_pattern


def transpose_pattern(pattern: ArpPattern, semitones: int) -> ArpPattern:
    """패턴의 voice_index를 변경하지 않고 메타데이터에 전조 정보를 기록합니다.

    실제 전조는 apply_pattern 호출 시 chord_notes를 변경하여 수행합니다.
    이 함수는 패턴 이름에 전조 표기를 추가하고 복사본을 반환합니다.

    Args:
        pattern: 원본 ArpPattern.
        semitones: 반음 단위 전조량 (양수=위, 음수=아래).

    Returns:
        전조 표기가 포함된 새 ArpPattern.
    """
    new_pattern = copy.deepcopy(pattern)
    direction = "+" if semitones >= 0 else ""
    new_pattern.name = f"{pattern.name} (T{direction}{semitones})"
    return new_pattern


def combine_patterns(
    bass_pattern: ArpPattern,
    chord_pattern: ArpPattern,
) -> ArpPattern:
    """베이스 패턴과 코드 패턴을 하나로 병합합니다.

    베이스 패턴의 이벤트는 is_chord=False로, 코드 패턴의 이벤트는
    원래 속성을 유지합니다. 두 패턴 중 더 긴 length_bars를 사용합니다.

    Args:
        bass_pattern: 베이스 라인 ArpPattern.
        chord_pattern: 코드 컴핑 ArpPattern.

    Returns:
        병합된 새 ArpPattern.
    """
    combined_events = []

    # 베이스 이벤트 추가 (코드 이벤트가 아닌 것만)
    for ev in bass_pattern.events:
        new_ev = copy.deepcopy(ev)
        new_ev.is_chord = False
        combined_events.append(new_ev)

    # 코드 이벤트 추가
    for ev in chord_pattern.events:
        combined_events.append(copy.deepcopy(ev))

    # 위치 기준으로 정렬
    combined_events.sort(key=lambda e: (e.position, e.voice_index))

    return ArpPattern(
        name=f"{bass_pattern.name} + {chord_pattern.name}",
        category="combined",
        time_signature=chord_pattern.time_signature,
        length_bars=max(bass_pattern.length_bars, chord_pattern.length_bars),
        swing=max(bass_pattern.swing, chord_pattern.swing),
        events=combined_events,
    )


# ---------------------------------------------------------------------------
# 모듈 수준 유틸리티
# ---------------------------------------------------------------------------

def list_all_categories() -> List[str]:
    """사용 가능한 모든 카테고리 이름을 반환합니다."""
    return sorted(_CATEGORY_INDEX.keys())


def list_all_styles() -> List[str]:
    """사용 가능한 모든 음악 스타일 이름을 반환합니다."""
    return sorted(_STYLE_RECOMMENDATIONS.keys())


def list_all_patterns() -> List[str]:
    """등록된 모든 패턴 키를 반환합니다."""
    return sorted(ARPEGGIATOR_PATTERNS.keys())


def pattern_count() -> int:
    """등록된 패턴 총 개수를 반환합니다."""
    return len(ARPEGGIATOR_PATTERNS)
