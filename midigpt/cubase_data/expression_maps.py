"""
Cubase 15 스타일 Expression Map, Playing Technique 및 Instrument Database 모듈.

Cubase 15의 298개 연주 기법(Playing Techniques)을 4개 그룹으로 분류하고,
21개 악기 패밀리에 걸친 624개 악기 데이터베이스를 제공합니다.
또한 Cubase 스타일의 Expression Map을 통해 기법을 MIDI 동작에 매핑합니다.

그룹 구성:
    - dynamics (25개): 셈여림 관련 기법
    - lengths (14개): 음 길이 관련 기법
    - ornaments (35개): 장식음 및 피치 변형 기법
    - techniques (224개): 연주 주법 기법

악기 패밀리 (21개):
    strings, brass, wind, keyboard, fretted, percussion, singers,
    electronics, plucked, ethnic_strings, ethnic_wind, ethnic_percussion,
    ensemble_strings, ensemble_brass, ensemble_wind, ensemble_vocal,
    organ, accordion, pitched_percussion, unpitched_percussion, other
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# 1. PLAYING_TECHNIQUES — 298개 연주 기법, 4개 그룹
# ---------------------------------------------------------------------------

PLAYING_TECHNIQUES: Dict[str, Dict[str, Dict[str, Any]]] = {

    # =====================================================================
    # kDynamics — 25개 셈여림 기법
    # =====================================================================
    "dynamics": {
        # --- 기본 다이나믹 단계 (9개) ---
        "ppp": {
            "id": "pt.ppp", "type": "attribute",
            "velocity_range": (1, 15), "cc11_range": (1, 15),
            "description": "피아니시시모 — 매우 여리게",
        },
        "pp": {
            "id": "pt.pp", "type": "attribute",
            "velocity_range": (15, 30), "cc11_range": (15, 30),
            "description": "피아니시모 — 매우 여리게",
        },
        "p": {
            "id": "pt.p", "type": "attribute",
            "velocity_range": (30, 50), "cc11_range": (30, 50),
            "description": "피아노 — 여리게",
        },
        "mp": {
            "id": "pt.mp", "type": "attribute",
            "velocity_range": (50, 70), "cc11_range": (50, 70),
            "description": "메조피아노 — 약간 여리게",
        },
        "mf": {
            "id": "pt.mf", "type": "attribute",
            "velocity_range": (70, 90), "cc11_range": (70, 90),
            "description": "메조포르테 — 약간 세게",
        },
        "f": {
            "id": "pt.f", "type": "attribute",
            "velocity_range": (90, 110), "cc11_range": (90, 110),
            "description": "포르테 — 세게",
        },
        "ff": {
            "id": "pt.ff", "type": "attribute",
            "velocity_range": (110, 127), "cc11_range": (110, 127),
            "description": "포르티시모 — 매우 세게",
        },
        "fff": {
            "id": "pt.fff", "type": "attribute",
            "velocity_range": (120, 127), "cc11_range": (120, 127),
            "description": "포르티시시모 — 극도로 세게",
        },
        "n": {
            "id": "pt.n", "type": "attribute",
            "velocity_range": (1, 1), "cc11_range": (1, 1),
            "description": "니엔테 — 소리 없이",
        },

        # --- 악센트 및 강조 (6개) ---
        "accent": {
            "id": "pt.accent", "type": "attribute",
            "velocity_mod": 1.3, "cc_mappings": {},
            "description": "악센트 — 해당 음을 강조",
        },
        "marcato": {
            "id": "pt.marcato", "type": "attribute",
            "velocity_mod": 1.5, "cc_mappings": {},
            "description": "마르카토 — 강하게 강조",
        },
        "strong_accent": {
            "id": "pt.strongAccent", "type": "attribute",
            "velocity_mod": 1.6, "cc_mappings": {},
            "description": "강한 악센트",
        },
        "soft_accent": {
            "id": "pt.softAccent", "type": "attribute",
            "velocity_mod": 1.15, "cc_mappings": {},
            "description": "부드러운 악센트",
        },
        "stress": {
            "id": "pt.stress", "type": "attribute",
            "velocity_mod": 1.2, "cc_mappings": {},
            "description": "스트레스 — 긴장감 있는 강조",
        },
        "unstress": {
            "id": "pt.unstress", "type": "attribute",
            "velocity_mod": 0.85, "cc_mappings": {},
            "description": "비강조 — 약하게 연주",
        },

        # --- 복합 다이나믹 (6개) ---
        "fp": {
            "id": "pt.fp", "type": "attribute",
            "velocity_start": 100, "velocity_end": 40, "envelope": "decay",
            "description": "포르테피아노 — 세게 시작하여 즉시 여리게",
        },
        "sfz": {
            "id": "pt.sfz", "type": "attribute",
            "velocity_start": 127, "velocity_end": 60, "envelope": "sharp_decay",
            "description": "스포르찬도 — 갑자기 매우 세게",
        },
        "sfp": {
            "id": "pt.sfp", "type": "attribute",
            "velocity_start": 120, "velocity_end": 35, "envelope": "sharp_decay",
            "description": "스포르찬도 피아노 — 갑자기 세게 후 여리게",
        },
        "sffz": {
            "id": "pt.sffz", "type": "attribute",
            "velocity_start": 127, "velocity_end": 80, "envelope": "sharp_decay",
            "description": "스포르찬디시모 — 극도로 갑자기 세게",
        },
        "fz": {
            "id": "pt.fz", "type": "attribute",
            "velocity_start": 115, "velocity_end": 70, "envelope": "sharp_decay",
            "description": "포르찬도 — 강하게 강조",
        },
        "rf": {
            "id": "pt.rf", "type": "attribute",
            "velocity_start": 110, "velocity_end": 90, "envelope": "mild_decay",
            "description": "린포르찬도 — 갑자기 강해짐",
        },

        # --- 다이나믹 방향 (4개) ---
        "crescendo": {
            "id": "pt.crescendo", "type": "attribute",
            "envelope": "ramp_up",
            "description": "크레셴도 — 점점 세게",
        },
        "diminuendo": {
            "id": "pt.diminuendo", "type": "attribute",
            "envelope": "ramp_down",
            "description": "디미누엔도 — 점점 여리게",
        },
        "fortepiano_crescendo": {
            "id": "pt.fpCresc", "type": "attribute",
            "velocity_start": 100, "velocity_end": 40, "envelope": "decay_then_ramp",
            "description": "포르테피아노 크레셴도 — 세게 후 여리게 다시 세게",
        },
        "morendo": {
            "id": "pt.morendo", "type": "attribute",
            "envelope": "slow_ramp_down",
            "description": "모렌도 — 사라지듯 점점 여리게",
        },
    },

    # =====================================================================
    # kLengths — 14개 음 길이 기법
    # =====================================================================
    "lengths": {
        "legato": {
            "id": "pt.legato", "type": "direction",
            "length_factor": 1.05, "overlap_ticks": 10,
            "description": "레가토 — 음과 음을 이어서 연주",
        },
        "staccato": {
            "id": "pt.staccato", "type": "attribute",
            "length_factor": 0.5,
            "description": "스타카토 — 음을 짧게 끊어 연주",
        },
        "staccatissimo": {
            "id": "pt.staccatissimo", "type": "attribute",
            "length_factor": 0.25,
            "description": "스타카티시모 — 극도로 짧게 끊어 연주",
        },
        "tenuto": {
            "id": "pt.tenuto", "type": "attribute",
            "length_factor": 1.0,
            "description": "테누토 — 음가를 충분히 유지하며 연주",
        },
        "portato": {
            "id": "pt.portato", "type": "attribute",
            "length_factor": 0.75,
            "description": "포르타토 — 레가토와 스타카토의 중간",
        },
        "spiccato": {
            "id": "pt.spiccato", "type": "attribute",
            "length_factor": 0.3, "velocity_mod": 0.9,
            "description": "스피카토 — 활이 현에서 튕기듯 연주 (현악기)",
        },
        "detache": {
            "id": "pt.detache", "type": "direction",
            "length_factor": 0.85,
            "description": "데타셰 — 음마다 활 방향을 바꿔 분리하여 연주",
        },
        "martellato": {
            "id": "pt.martellato", "type": "attribute",
            "length_factor": 0.4, "velocity_mod": 1.2,
            "description": "마르텔라토 — 망치로 치듯 강하고 짧게 연주",
        },
        "colle": {
            "id": "pt.colle", "type": "attribute",
            "length_factor": 0.3, "velocity_mod": 1.1,
            "description": "콜레 — 현 위에서 활을 떨어뜨려 짧게 연주",
        },
        "ricochet": {
            "id": "pt.ricochet", "type": "attribute",
            "length_factor": 0.2, "repeat_count": 3,
            "description": "리코셰 — 활을 현 위에서 튕겨 여러 번 연주",
        },
        "saltando": {
            "id": "pt.saltando", "type": "attribute",
            "length_factor": 0.3,
            "description": "살탄도 — 활이 현에서 뛰듯이 연주",
        },
        "sautille": {
            "id": "pt.sautille", "type": "attribute",
            "length_factor": 0.35,
            "description": "소틸레 — 빠른 스피카토 (자연 바운스 이용)",
        },
        "non_legato": {
            "id": "pt.nonLegato", "type": "direction",
            "length_factor": 0.9,
            "description": "논레가토 — 음 사이에 약간의 틈을 두고 연주",
        },
        "detache_lance": {
            "id": "pt.detacheLance", "type": "attribute",
            "length_factor": 0.7,
            "description": "데타셰 랑세 — 약센트가 있는 데타셰",
        },
    },

    # =====================================================================
    # kOrnaments — 35개 장식음/피치 변형 기법
    # =====================================================================
    "ornaments": {
        "trill": {
            "id": "pt.trill", "type": "attribute",
            "interval": 2, "speed": "fast",
            "description": "트릴 — 주음과 위의 음 사이를 빠르게 반복",
        },
        "trill_half": {
            "id": "pt.trillHalfStep", "type": "attribute",
            "interval": 1, "speed": "fast",
            "description": "반음 트릴 — 반음 간격의 트릴",
        },
        "trill_whole": {
            "id": "pt.trillWholeStep", "type": "attribute",
            "interval": 2, "speed": "fast",
            "description": "온음 트릴 — 온음 간격의 트릴",
        },
        "trill_minor_third": {
            "id": "pt.trillMinorThird", "type": "attribute",
            "interval": 3, "speed": "fast",
            "description": "단3도 트릴",
        },
        "trill_major_third": {
            "id": "pt.trillMajorThird", "type": "attribute",
            "interval": 4, "speed": "fast",
            "description": "장3도 트릴",
        },
        "tremolo": {
            "id": "pt.tremolo", "type": "attribute",
            "repeat_speed": "fast",
            "description": "트레몰로 — 같은 음을 빠르게 반복",
        },
        "tremolo_measured": {
            "id": "pt.tremoloMeasured", "type": "attribute",
            "repeat_speed": "measured",
            "description": "잇단음표 트레몰로 — 정확한 리듬으로 반복",
        },
        "fingered_tremolo": {
            "id": "pt.fingeredTremolo", "type": "attribute",
            "interval": None, "speed": "fast",
            "description": "손가락 트레몰로 — 두 음 사이를 빠르게 교대",
        },
        "vibrato": {
            "id": "pt.vibrato", "type": "attribute",
            "cc1_depth": 40, "speed": "medium",
            "description": "비브라토 — 음높이를 미세하게 흔들어 연주",
        },
        "wide_vibrato": {
            "id": "pt.wideVibrato", "type": "attribute",
            "cc1_depth": 80, "speed": "medium",
            "description": "와이드 비브라토 — 넓은 폭의 비브라토",
        },
        "narrow_vibrato": {
            "id": "pt.narrowVibrato", "type": "attribute",
            "cc1_depth": 20, "speed": "medium",
            "description": "내로우 비브라토 — 좁은 폭의 비브라토",
        },
        "non_vibrato": {
            "id": "pt.nonVibrato", "type": "attribute",
            "cc1_depth": 0, "speed": "none",
            "description": "논비브라토 — 비브라토 없이 연주",
        },
        "slow_vibrato": {
            "id": "pt.slowVibrato", "type": "attribute",
            "cc1_depth": 40, "speed": "slow",
            "description": "느린 비브라토",
        },
        "fast_vibrato": {
            "id": "pt.fastVibrato", "type": "attribute",
            "cc1_depth": 50, "speed": "fast",
            "description": "빠른 비브라토",
        },
        "glissando_up": {
            "id": "pt.glissandoUp", "type": "attribute",
            "pitch_direction": "up",
            "description": "글리산도 업 — 음정을 올리며 미끄러지듯 연주",
        },
        "glissando_down": {
            "id": "pt.glissandoDown", "type": "attribute",
            "pitch_direction": "down",
            "description": "글리산도 다운 — 음정을 내리며 미끄러지듯 연주",
        },
        "portamento_up": {
            "id": "pt.portamentoUp", "type": "attribute",
            "cc65": True, "direction": "up",
            "description": "포르타멘토 업 — 연속적으로 음정을 올려 이동",
        },
        "portamento_down": {
            "id": "pt.portamentoDown", "type": "attribute",
            "cc65": True, "direction": "down",
            "description": "포르타멘토 다운 — 연속적으로 음정을 내려 이동",
        },
        "bend": {
            "id": "pt.bend", "type": "attribute",
            "pitch_bend_range": 2,
            "description": "벤드 — 피치 벤드 휠을 이용한 음정 변형",
        },
        "arpeggio_up": {
            "id": "pt.arpeggioUp", "type": "attribute",
            "spread_ms": 30, "direction": "up",
            "description": "아르페지오 업 — 화음을 아래에서 위로 펼침",
        },
        "arpeggio_down": {
            "id": "pt.arpeggioDown", "type": "attribute",
            "spread_ms": 30, "direction": "down",
            "description": "아르페지오 다운 — 화음을 위에서 아래로 펼침",
        },
        "strum_up": {
            "id": "pt.strumUp", "type": "attribute",
            "spread_ms": 20, "direction": "up",
            "description": "스트럼 업 — 위로 쓸어 올리는 주법",
        },
        "strum_down": {
            "id": "pt.strumDown", "type": "attribute",
            "spread_ms": 20, "direction": "down",
            "description": "스트럼 다운 — 아래로 쓸어 내리는 주법",
        },
        "roll": {
            "id": "pt.roll", "type": "attribute",
            "repeat_speed": "medium",
            "description": "롤 — 빠른 교대 타격으로 지속음 효과",
        },
        "shake": {
            "id": "pt.shake", "type": "attribute",
            "interval": 3, "speed": "fast",
            "description": "셰이크 — 넓은 간격의 빠른 교대 (재즈)",
        },
        "doit": {
            "id": "pt.doit", "type": "attribute",
            "pitch_direction": "up", "style": "jazz",
            "description": "도잇 — 음 끝에서 위로 올리는 재즈 기법",
        },
        "fall": {
            "id": "pt.fall", "type": "attribute",
            "pitch_direction": "down", "style": "jazz",
            "description": "폴 — 음 끝에서 아래로 떨어지는 재즈 기법",
        },
        "scoop": {
            "id": "pt.scoop", "type": "attribute",
            "pitch_approach": "below",
            "description": "스쿱 — 아래에서 목표 음으로 올라가는 어프로치",
        },
        "rip": {
            "id": "pt.rip", "type": "attribute",
            "pitch_direction": "up", "style": "aggressive",
            "description": "립 — 빠르고 공격적인 상행 글리산도",
        },
        "flip": {
            "id": "pt.flip", "type": "attribute",
            "pitch_direction": "up", "speed": "fast",
            "description": "플립 — 빠르게 위 음을 스치고 돌아오는 장식",
        },
        "plop": {
            "id": "pt.plop", "type": "attribute",
            "pitch_approach": "above",
            "description": "플롭 — 위에서 목표 음으로 떨어지는 어프로치",
        },
        "smear": {
            "id": "pt.smear", "type": "attribute",
            "pitch_approach": "gradual",
            "description": "스미어 — 음정을 점진적으로 변형하며 접근",
        },
        "slide": {
            "id": "pt.slide", "type": "attribute",
            "pitch_bend_range": 4,
            "description": "슬라이드 — 넓은 범위의 피치 슬라이드",
        },
        "mordent": {
            "id": "pt.mordent", "type": "attribute",
            "interval": -1, "speed": "fast",
            "description": "모르덴트 — 주음-아래음-주음의 빠른 교대",
        },
        "inverted_mordent": {
            "id": "pt.invertedMordent", "type": "attribute",
            "interval": 1, "speed": "fast",
            "description": "역 모르덴트 — 주음-위음-주음의 빠른 교대",
        },
    },

    # =====================================================================
    # kTechniques — 224개 연주 주법 기법
    # =====================================================================
    "techniques": {
        # --- 범용 기법 (10개) ---
        "natural": {
            "id": "pt.natural", "type": "direction", "is_default": True,
            "description": "내추럴 — 기본 연주 방식",
        },
        "muted": {
            "id": "pt.muted", "type": "direction", "velocity_mod": 0.6,
            "description": "뮤트 — 소리를 막아 짧고 둔하게 연주",
        },
        "ghost_note": {
            "id": "pt.ghostNote", "type": "attribute", "velocity_mod": 0.3,
            "description": "고스트 노트 — 아주 약하게 거의 안 들리게",
        },
        "wah_wah": {
            "id": "pt.wahWah", "type": "direction", "cc_sweep": True,
            "description": "와와 — 필터 스윕 효과",
        },
        "multiphonic": {
            "id": "pt.multiphonic", "type": "attribute",
            "description": "멀티포닉 — 하나의 악기에서 여러 음을 동시에",
        },
        "breath_tone": {
            "id": "pt.breathTone", "type": "attribute", "velocity_mod": 0.3,
            "description": "브레스 톤 — 숨소리가 섞인 연주",
        },
        "air_tone": {
            "id": "pt.airTone", "type": "attribute", "velocity_mod": 0.25,
            "description": "에어 톤 — 공기 소리 위주의 연주",
        },
        "key_click": {
            "id": "pt.keyClick", "type": "attribute",
            "description": "키 클릭 — 키 소리만 내기 (관악기)",
        },
        "half_note": {
            "id": "pt.halfNote", "type": "attribute", "velocity_mod": 0.5,
            "description": "하프 노트 — 절반 강도의 연주",
        },
        "open": {
            "id": "pt.open", "type": "direction",
            "description": "오픈 — 열린 소리로 연주 (뮤트 해제)",
        },

        # --- 현악기 기법 (35개) ---
        "arco": {
            "id": "pt.bowed", "type": "direction", "is_default": True,
            "families": ["strings"],
            "description": "아르코 — 활로 켜는 기본 주법",
        },
        "pizzicato": {
            "id": "pt.pizzicato", "type": "direction",
            "velocity_mod": 0.8, "length_factor": 0.3, "families": ["strings"],
            "description": "피치카토 — 손가락으로 현을 뜯어 연주",
        },
        "snap_pizzicato": {
            "id": "pt.bartokSnapPizzicato", "type": "attribute",
            "velocity_mod": 1.4, "families": ["strings"],
            "description": "스냅 피치카토 (바르톡) — 현을 세게 당겨 지판에 부딪힘",
        },
        "left_hand_pizzicato": {
            "id": "pt.leftHandPizzicato", "type": "attribute",
            "velocity_mod": 0.6, "families": ["strings"],
            "description": "왼손 피치카토 — 활을 잡은 채 왼손으로 뜯기",
        },
        "col_legno_battuto": {
            "id": "pt.colLegnoBattuto", "type": "direction",
            "velocity_mod": 0.6, "families": ["strings"],
            "description": "콜레뇨 바투토 — 활의 나무 부분으로 두드림",
        },
        "col_legno_tratto": {
            "id": "pt.colLegnoTratto", "type": "direction",
            "velocity_mod": 0.5, "families": ["strings"],
            "description": "콜레뇨 트라토 — 활의 나무 부분으로 문질러 켜기",
        },
        "sul_ponticello": {
            "id": "pt.sulPonticello", "type": "direction",
            "timbre": "bright", "families": ["strings"],
            "description": "술 폰티첼로 — 브릿지 근처에서 연주 (밝고 날카로운 소리)",
        },
        "sul_tasto": {
            "id": "pt.sulTasto", "type": "direction",
            "timbre": "dark", "families": ["strings"],
            "description": "술 타스토 — 지판 위에서 연주 (어둡고 부드러운 소리)",
        },
        "sul_g": {
            "id": "pt.sulG", "type": "direction",
            "families": ["strings"],
            "description": "술 G — G현에서만 연주",
        },
        "sul_d": {
            "id": "pt.sulD", "type": "direction",
            "families": ["strings"],
            "description": "술 D — D현에서만 연주",
        },
        "sul_a": {
            "id": "pt.sulA", "type": "direction",
            "families": ["strings"],
            "description": "술 A — A현에서만 연주",
        },
        "sul_e": {
            "id": "pt.sulE", "type": "direction",
            "families": ["strings"],
            "description": "술 E — E현에서만 연주",
        },
        "sul_c": {
            "id": "pt.sulC", "type": "direction",
            "families": ["strings"],
            "description": "술 C — C현에서만 연주",
        },
        "flautando": {
            "id": "pt.flautando", "type": "direction",
            "velocity_mod": 0.5, "families": ["strings"],
            "description": "플라우탄도 — 활을 가볍게 하여 플루트 같은 음색",
        },
        "natural_harmonic": {
            "id": "pt.naturalHarmonic1", "type": "attribute",
            "families": ["strings", "fretted"],
            "description": "자연 하모닉스 — 현의 배음점에서 가볍게 터치",
        },
        "artificial_harmonic": {
            "id": "pt.artificialHarmonic", "type": "attribute",
            "families": ["strings", "fretted"],
            "description": "인공 하모닉스 — 손가락으로 배음을 만들어 연주",
        },
        "downbow": {
            "id": "pt.downbow", "type": "attribute",
            "families": ["strings"],
            "description": "다운보우 — 활을 아래로 당겨 연주",
        },
        "upbow": {
            "id": "pt.upbow", "type": "attribute",
            "families": ["strings"],
            "description": "업보우 — 활을 위로 밀어 연주",
        },
        "overpressure": {
            "id": "pt.overpressure", "type": "direction",
            "families": ["strings"],
            "description": "오버프레셔 — 활에 과도한 압력을 가해 거친 소리",
        },
        "behind_the_bridge": {
            "id": "pt.behindTheBridge", "type": "direction",
            "families": ["strings"],
            "description": "비하인드 더 브릿지 — 브릿지 뒤에서 연주",
        },
        "on_the_bridge": {
            "id": "pt.onTheBridge", "type": "direction",
            "families": ["strings"],
            "description": "온 더 브릿지 — 브릿지 위에서 직접 연주",
        },
        "half_harmonic": {
            "id": "pt.halfHarmonic", "type": "attribute",
            "families": ["strings"],
            "description": "하프 하모닉스 — 불완전한 하모닉스",
        },
        "con_sordino": {
            "id": "pt.conSordino", "type": "direction",
            "velocity_mod": 0.7, "families": ["strings"],
            "description": "콘 소르디노 — 약음기(뮤트)를 사용하여 연주",
        },
        "senza_sordino": {
            "id": "pt.senzaSordino", "type": "direction",
            "families": ["strings"],
            "description": "센차 소르디노 — 약음기를 제거하고 연주",
        },
        "jeté": {
            "id": "pt.jete", "type": "attribute",
            "length_factor": 0.2, "repeat_count": 4, "families": ["strings"],
            "description": "주떼 — 활을 던지듯 현에서 여러 번 튕김",
        },
        "au_talon": {
            "id": "pt.auTalon", "type": "attribute",
            "families": ["strings"],
            "description": "오 탈롱 — 활의 뿌리 부분(프로그)으로 연주",
        },
        "tremolo_sul_pont": {
            "id": "pt.tremoloSulPont", "type": "attribute",
            "repeat_speed": "fast", "timbre": "bright", "families": ["strings"],
            "description": "트레몰로 술 폰티첼로 — 브릿지 근처 트레몰로",
        },
        "tremolo_sul_tasto": {
            "id": "pt.tremoloSulTasto", "type": "attribute",
            "repeat_speed": "fast", "timbre": "dark", "families": ["strings"],
            "description": "트레몰로 술 타스토 — 지판 위 트레몰로",
        },
        "con_legno": {
            "id": "pt.conLegno", "type": "direction",
            "families": ["strings"],
            "description": "콘 레뇨 — 활의 나무 부분으로 연주 (일반)",
        },
        "tremolo_fingered": {
            "id": "pt.tremoloFingered", "type": "attribute",
            "repeat_speed": "fast", "families": ["strings"],
            "description": "핑거드 트레몰로 — 두 음 교대 트레몰로 (현악)",
        },
        "divisi": {
            "id": "pt.divisi", "type": "direction",
            "families": ["strings"],
            "description": "디비지 — 파트를 나누어 연주",
        },
        "unison": {
            "id": "pt.unison", "type": "direction",
            "families": ["strings"],
            "description": "유니즌 — 전원이 같은 음을 연주",
        },
        "double_stop": {
            "id": "pt.doubleStop", "type": "attribute",
            "families": ["strings"],
            "description": "더블 스톱 — 두 현을 동시에 연주",
        },
        "triple_stop": {
            "id": "pt.tripleStop", "type": "attribute",
            "families": ["strings"],
            "description": "트리플 스톱 — 세 현을 동시에 연주",
        },
        "quadruple_stop": {
            "id": "pt.quadrupleStop", "type": "attribute",
            "families": ["strings"],
            "description": "쿼드루플 스톱 — 네 현을 동시에 연주",
        },

        # --- 관악기 기법 (25개) ---
        "flutter_tongue": {
            "id": "pt.flutterTongue", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "플러터 텅잉 — 혀를 굴려 떨리는 소리",
        },
        "double_tongue": {
            "id": "pt.doubleTongue", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "더블 텅잉 — 빠른 이중 혀 공격",
        },
        "triple_tongue": {
            "id": "pt.tripleTongue", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "트리플 텅잉 — 빠른 삼중 혀 공격",
        },
        "slap_tongue": {
            "id": "pt.slapTongue", "type": "attribute",
            "velocity_mod": 1.3, "families": ["wind"],
            "description": "슬랩 텅잉 — 혀로 리드를 때려 타격음",
        },
        "subtone": {
            "id": "pt.subtone", "type": "direction",
            "velocity_mod": 0.4, "families": ["wind"],
            "description": "서브톤 — 부드럽고 공기가 섞인 톤",
        },
        "overblow": {
            "id": "pt.overblow", "type": "attribute",
            "families": ["wind"],
            "description": "오버블로우 — 과도한 숨으로 배음을 강제",
        },
        "growl": {
            "id": "pt.growl", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "그로울 — 목에서 소리를 내어 거친 효과",
        },
        "tongue_ram": {
            "id": "pt.tongueRam", "type": "attribute",
            "families": ["wind"],
            "description": "텅 램 — 마우스피스에 혀를 세게 대는 타격음",
        },
        "jet_whistle": {
            "id": "pt.jetWhistle", "type": "attribute",
            "families": ["wind"],
            "description": "제트 휘슬 — 공기 소리의 빠른 상승/하강",
        },
        "whistle_tone": {
            "id": "pt.whistleTone", "type": "attribute",
            "velocity_mod": 0.15, "families": ["wind"],
            "description": "휘슬 톤 — 매우 약한 고음의 하모닉스",
        },
        "key_clicks_wind": {
            "id": "pt.keyClicksWind", "type": "attribute",
            "families": ["wind"],
            "description": "키 클릭 — 손가락으로 키를 두드리는 소리",
        },
        "harmonic_fingering": {
            "id": "pt.harmonicFingering", "type": "attribute",
            "families": ["wind"],
            "description": "하모닉 핑거링 — 배음을 이용한 특수 운지",
        },
        "bisbigliando": {
            "id": "pt.bisbigliando", "type": "attribute",
            "families": ["wind"],
            "description": "비스빌리안도 — 같은 음의 다른 운지를 교대하여 음색 변화",
        },
        "circular_breathing": {
            "id": "pt.circularBreathing", "type": "direction",
            "families": ["wind", "brass"],
            "description": "순환 호흡 — 끊기지 않는 지속음",
        },
        "teeth_on_reed": {
            "id": "pt.teethOnReed", "type": "attribute",
            "families": ["wind"],
            "description": "이빨 온 리드 — 리드에 이빨을 대어 거친 소리",
        },
        "sing_and_play": {
            "id": "pt.singAndPlay", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "싱 앤 플레이 — 연주하면서 동시에 노래",
        },
        "bamboo_tone": {
            "id": "pt.bambooTone", "type": "attribute",
            "families": ["wind"],
            "description": "뱀부 톤 — 대나무 소리 같은 건조한 톤",
        },
        "covered_tone": {
            "id": "pt.coveredTone", "type": "direction",
            "families": ["wind"],
            "description": "커버드 톤 — 구멍을 부분적으로 막아 어두운 소리",
        },
        "half_hole": {
            "id": "pt.halfHole", "type": "attribute",
            "families": ["wind"],
            "description": "하프 홀 — 음공을 반만 막아 미분음",
        },
        "overblown_fifth": {
            "id": "pt.overblownFifth", "type": "attribute",
            "families": ["wind"],
            "description": "오버블로운 5도 — 5도 위 배음을 강제",
        },
        "split_tone": {
            "id": "pt.splitTone", "type": "attribute",
            "families": ["wind"],
            "description": "스플릿 톤 — 두 음이 동시에 나는 불안정한 소리",
        },
        "tongue_stop": {
            "id": "pt.tongueStop", "type": "attribute",
            "families": ["wind", "brass"],
            "description": "텅 스톱 — 혀로 공기를 막아 소리를 급정지",
        },
        "bell_up": {
            "id": "pt.bellUp", "type": "direction",
            "families": ["wind", "brass"],
            "description": "벨 업 — 악기 벨을 위로 향해 연주",
        },
        "into_stand": {
            "id": "pt.intoStand", "type": "direction",
            "families": ["brass"],
            "description": "인투 스탠드 — 보면대 안으로 벨을 향해 연주",
        },
        "removed_bell": {
            "id": "pt.removedBell", "type": "attribute",
            "families": ["wind"],
            "description": "리무브드 벨 — 벨을 제거하고 연주",
        },

        # --- 금관악기 기법 (20개) ---
        "stopped": {
            "id": "pt.stopped", "type": "direction",
            "families": ["brass"],
            "description": "스톱 — 손으로 벨을 막아 금속적인 소리",
        },
        "cuivre": {
            "id": "pt.cuivre", "type": "direction",
            "velocity_mod": 1.3, "families": ["brass"],
            "description": "퀴브레 — 금속적이고 날카로운 포르티시모",
        },
        "brassy": {
            "id": "pt.brassy", "type": "direction",
            "velocity_mod": 1.2, "families": ["brass"],
            "description": "브래시 — 강하고 금속적인 음색",
        },
        "straight_mute": {
            "id": "pt.straightMute", "type": "direction",
            "families": ["brass"],
            "description": "스트레이트 뮤트 — 원뿔형 뮤트 사용",
        },
        "cup_mute": {
            "id": "pt.cupMute", "type": "direction",
            "families": ["brass"],
            "description": "컵 뮤트 — 컵 모양 뮤트로 어두운 소리",
        },
        "harmon_mute_stem_in": {
            "id": "pt.harmonMuteStemIn", "type": "direction",
            "families": ["brass"],
            "description": "하몬 뮤트 (스템 인) — 와와 뮤트, 스템 삽입",
        },
        "harmon_mute_stem_out": {
            "id": "pt.harmonMuteStemOut", "type": "direction",
            "families": ["brass"],
            "description": "하몬 뮤트 (스템 아웃) — 와와 뮤트, 스템 제거",
        },
        "plunger_mute": {
            "id": "pt.plungerMute", "type": "direction",
            "families": ["brass"],
            "description": "플런저 뮤트 — 고무 뚜껑 뮤트로 와와 효과",
        },
        "bucket_mute": {
            "id": "pt.bucketMute", "type": "direction",
            "families": ["brass"],
            "description": "버킷 뮤트 — 벨 위에 거는 뮤트, 부드러운 소리",
        },
        "practice_mute": {
            "id": "pt.practiceMute", "type": "direction",
            "velocity_mod": 0.3, "families": ["brass"],
            "description": "프랙티스 뮤트 — 연습용 뮤트, 매우 작은 소리",
        },
        "half_valve": {
            "id": "pt.halfValve", "type": "attribute",
            "families": ["brass"],
            "description": "하프 밸브 — 밸브를 반만 눌러 흐릿한 소리",
        },
        "valve_trill": {
            "id": "pt.valveTrill", "type": "attribute",
            "families": ["brass"],
            "description": "밸브 트릴 — 밸브 조작으로 트릴",
        },
        "lip_trill": {
            "id": "pt.lipTrill", "type": "attribute",
            "families": ["brass"],
            "description": "립 트릴 — 입술 조작으로 배음 간 트릴",
        },
        "pedal_tone": {
            "id": "pt.pedalToneBrass", "type": "attribute",
            "families": ["brass"],
            "description": "페달 톤 — 기본음 아래의 매우 낮은 음",
        },
        "rip_brass": {
            "id": "pt.ripBrass", "type": "attribute",
            "pitch_direction": "up", "families": ["brass"],
            "description": "립 (금관) — 빠른 상행 글리산도",
        },
        "horse_whinny": {
            "id": "pt.horseWhinny", "type": "attribute",
            "families": ["brass"],
            "description": "호스 위니 — 말 울음 같은 글리산도 효과",
        },
        "glissando_with_valves": {
            "id": "pt.glissandoWithValves", "type": "attribute",
            "families": ["brass"],
            "description": "밸브 글리산도 — 밸브 조작으로 글리산도",
        },
        "slide_gliss": {
            "id": "pt.slideGliss", "type": "attribute",
            "families": ["brass"],
            "description": "슬라이드 글리산도 — 트롬본 슬라이드 글리산도",
        },
        "shake_brass": {
            "id": "pt.shakeBrass", "type": "attribute",
            "families": ["brass"],
            "description": "셰이크 (금관) — 빠른 립 트릴",
        },
        "bend_brass": {
            "id": "pt.bendBrass", "type": "attribute",
            "families": ["brass"],
            "description": "벤드 (금관) — 입술 조작으로 음정 구부리기",
        },

        # --- 프렛악기/기타 기법 (25개) ---
        "palm_muting": {
            "id": "pt.palmMuting", "type": "direction",
            "velocity_mod": 0.7, "length_factor": 0.6, "families": ["fretted"],
            "description": "팜 뮤트 — 손바닥으로 현을 살짝 눌러 뮤트",
        },
        "pop": {
            "id": "pt.pop", "type": "attribute",
            "velocity_mod": 1.2, "families": ["fretted"],
            "description": "팝 — 현을 잡아당겨 튕기는 기법",
        },
        "slap": {
            "id": "pt.slap", "type": "attribute",
            "velocity_mod": 1.3, "families": ["fretted", "latin"],
            "description": "슬랩 — 엄지로 현을 때리는 기법",
        },
        "tap": {
            "id": "pt.tap", "type": "attribute",
            "families": ["fretted"],
            "description": "탭핑 — 프렛보드를 직접 두드려 소리",
        },
        "pick_scrape": {
            "id": "pt.pickScrape", "type": "attribute",
            "families": ["fretted"],
            "description": "픽 스크레이프 — 피크로 현을 긁어 내리기",
        },
        "pinch_harmonic": {
            "id": "pt.pinchHarmonic", "type": "attribute",
            "families": ["fretted"],
            "description": "핀치 하모닉스 — 엄지 끝으로 배음을 터치",
        },
        "hammer_on": {
            "id": "pt.hammerOn", "type": "attribute",
            "families": ["fretted"],
            "description": "해머온 — 왼손 손가락을 내려쳐 발음",
        },
        "pull_off": {
            "id": "pt.pullOff", "type": "attribute",
            "families": ["fretted"],
            "description": "풀오프 — 왼손 손가락을 떼며 발음",
        },
        "bend_guitar": {
            "id": "pt.bendGuitar", "type": "attribute",
            "pitch_bend_range": 2, "families": ["fretted"],
            "description": "벤딩 — 현을 밀어 음정을 올림",
        },
        "prebend": {
            "id": "pt.prebend", "type": "attribute",
            "families": ["fretted"],
            "description": "프리벤드 — 먼저 구부린 후 피킹",
        },
        "release_bend": {
            "id": "pt.releaseBend", "type": "attribute",
            "families": ["fretted"],
            "description": "릴리즈 벤드 — 구부린 현을 원래 음으로 풀기",
        },
        "slide_guitar_up": {
            "id": "pt.slideGuitarUp", "type": "attribute",
            "families": ["fretted"],
            "description": "슬라이드 업 — 프렛을 따라 위로 미끄러지기",
        },
        "slide_guitar_down": {
            "id": "pt.slideGuitarDown", "type": "attribute",
            "families": ["fretted"],
            "description": "슬라이드 다운 — 프렛을 따라 아래로 미끄러지기",
        },
        "vibrato_bar": {
            "id": "pt.vibratoBar", "type": "attribute",
            "families": ["fretted"],
            "description": "비브라토 바 (트레몰로 암) — 바를 흔들어 음정 변화",
        },
        "whammy_dive": {
            "id": "pt.whammyDive", "type": "attribute",
            "families": ["fretted"],
            "description": "와미 다이브 — 비브라토 바를 세게 눌러 음정 급하강",
        },
        "whammy_return": {
            "id": "pt.whammyReturn", "type": "attribute",
            "families": ["fretted"],
            "description": "와미 리턴 — 다이브 후 원래 음정으로 복귀",
        },
        "feedback": {
            "id": "pt.feedback", "type": "attribute",
            "families": ["fretted"],
            "description": "피드백 — 앰프 피드백을 이용한 지속음",
        },
        "power_chord": {
            "id": "pt.powerChord", "type": "attribute",
            "families": ["fretted"],
            "description": "파워 코드 — 근음+5도만 사용하는 코드",
        },
        "arpeggio_guitar": {
            "id": "pt.arpeggioGuitar", "type": "attribute",
            "spread_ms": 40, "families": ["fretted"],
            "description": "아르페지오 — 화음을 순차적으로 연주",
        },
        "rasgueado": {
            "id": "pt.rasgueado", "type": "attribute",
            "families": ["fretted"],
            "description": "라스게아도 — 플라멩코 스트럼 기법",
        },
        "golpe": {
            "id": "pt.golpe", "type": "attribute",
            "families": ["fretted"],
            "description": "골페 — 기타 바디를 두드리는 타격음",
        },
        "tambour": {
            "id": "pt.tambourGuitar", "type": "attribute",
            "families": ["fretted"],
            "description": "탬버 — 브릿지 근처에서 현을 두드림",
        },
        "behind_the_nut": {
            "id": "pt.behindTheNut", "type": "attribute",
            "families": ["fretted"],
            "description": "너트 뒤에서 연주 — 너트와 페그 사이",
        },
        "let_ring": {
            "id": "pt.letRing", "type": "direction",
            "length_factor": 2.0, "families": ["fretted"],
            "description": "렛 링 — 음을 자연 감쇠까지 울림",
        },
        "chucking": {
            "id": "pt.chucking", "type": "attribute",
            "families": ["fretted"],
            "description": "처킹 — 현을 막고 스트럼하여 퍼커시브 효과",
        },

        # --- 타악기 기법 (30개) ---
        "rim_shot": {
            "id": "pt.rimShot", "type": "attribute",
            "velocity_mod": 1.2, "families": ["percussion"],
            "description": "림 샷 — 드럼 헤드와 림을 동시에 타격",
        },
        "cross_stick": {
            "id": "pt.crossStick", "type": "attribute",
            "families": ["percussion"],
            "description": "크로스 스틱 — 스틱을 눕혀 림만 타격",
        },
        "buzz_roll": {
            "id": "pt.buzzRoll", "type": "attribute",
            "repeat_speed": "fast", "families": ["percussion"],
            "description": "버즈 롤 — 스틱을 눌러 빠른 진동 (프레스 롤)",
        },
        "dead_stroke": {
            "id": "pt.deadStroke", "type": "attribute",
            "length_factor": 0.1, "families": ["percussion"],
            "description": "데드 스트로크 — 타격 후 즉시 뮤트",
        },
        "single_stroke_roll": {
            "id": "pt.singleStrokeRoll", "type": "attribute",
            "families": ["percussion"],
            "description": "싱글 스트로크 롤 — RLRL 교대 타격",
        },
        "double_stroke_roll": {
            "id": "pt.doubleStrokeRoll", "type": "attribute",
            "families": ["percussion"],
            "description": "더블 스트로크 롤 — RRLL 교대 타격",
        },
        "flam": {
            "id": "pt.flam", "type": "attribute",
            "families": ["percussion"],
            "description": "플램 — 짧은 장식음 + 주 타격",
        },
        "drag": {
            "id": "pt.drag", "type": "attribute",
            "families": ["percussion"],
            "description": "드래그 — 두 장식음 + 주 타격",
        },
        "ruff": {
            "id": "pt.ruff", "type": "attribute",
            "families": ["percussion"],
            "description": "러프 — 세 장식음 + 주 타격",
        },
        "paradiddle": {
            "id": "pt.paradiddle", "type": "attribute",
            "families": ["percussion"],
            "description": "패러디들 — RLRR/LRLL 패턴",
        },
        "center_hit": {
            "id": "pt.centerHit", "type": "attribute",
            "families": ["percussion"],
            "description": "센터 히트 — 드럼/심벌 중앙 타격",
        },
        "edge_hit": {
            "id": "pt.edgeHit", "type": "attribute",
            "families": ["percussion"],
            "description": "엣지 히트 — 드럼/심벌 가장자리 타격",
        },
        "bell_hit": {
            "id": "pt.bellHit", "type": "attribute",
            "families": ["percussion"],
            "description": "벨 히트 — 심벌/카우벨 벨 부분 타격",
        },
        "choke": {
            "id": "pt.choke", "type": "attribute",
            "length_factor": 0.05, "families": ["percussion"],
            "description": "초크 — 심벌을 잡아 소리를 급정지",
        },
        "brush_sweep": {
            "id": "pt.brushSweep", "type": "attribute",
            "families": ["percussion"],
            "description": "브러시 스윕 — 브러시로 헤드를 쓸기",
        },
        "brush_tap": {
            "id": "pt.brushTap", "type": "attribute",
            "families": ["percussion"],
            "description": "브러시 탭 — 브러시로 가볍게 타격",
        },
        "with_mallets": {
            "id": "pt.withMallets", "type": "direction",
            "families": ["percussion"],
            "description": "말렛 사용 — 말렛(채)으로 연주",
        },
        "with_sticks": {
            "id": "pt.withSticks", "type": "direction",
            "families": ["percussion"],
            "description": "스틱 사용 — 드럼 스틱으로 연주",
        },
        "with_hands": {
            "id": "pt.withHands", "type": "direction",
            "families": ["percussion"],
            "description": "손 사용 — 손으로 직접 연주",
        },
        "with_fingers": {
            "id": "pt.withFingers", "type": "direction",
            "families": ["percussion"],
            "description": "손가락 사용 — 손가락으로 연주",
        },
        "hard_mallet": {
            "id": "pt.hardMallet", "type": "direction",
            "families": ["percussion"],
            "description": "하드 말렛 — 딱딱한 채로 연주 (밝은 소리)",
        },
        "soft_mallet": {
            "id": "pt.softMallet", "type": "direction",
            "families": ["percussion"],
            "description": "소프트 말렛 — 부드러운 채로 연주 (어두운 소리)",
        },
        "yarn_mallet": {
            "id": "pt.yarnMallet", "type": "direction",
            "families": ["percussion"],
            "description": "실 말렛 — 실로 감싼 채로 연주 (따뜻한 소리)",
        },
        "open_hi_hat": {
            "id": "pt.openHiHat", "type": "attribute",
            "families": ["percussion"],
            "description": "오픈 하이햇 — 하이햇을 열고 타격",
        },
        "closed_hi_hat": {
            "id": "pt.closedHiHat", "type": "attribute",
            "families": ["percussion"],
            "description": "클로즈드 하이햇 — 하이햇을 닫고 타격",
        },
        "half_open_hi_hat": {
            "id": "pt.halfOpenHiHat", "type": "attribute",
            "families": ["percussion"],
            "description": "하프 오픈 하이햇 — 하이햇을 반만 열고 타격",
        },
        "pedal_hi_hat": {
            "id": "pt.pedalHiHat", "type": "attribute",
            "families": ["percussion"],
            "description": "페달 하이햇 — 발로만 하이햇 닫기",
        },
        "splash_hi_hat": {
            "id": "pt.splashHiHat", "type": "attribute",
            "families": ["percussion"],
            "description": "스플래시 하이햇 — 발을 빠르게 밟았다 떼기",
        },
        "muffled": {
            "id": "pt.muffled", "type": "direction",
            "velocity_mod": 0.5, "families": ["percussion"],
            "description": "머플드 — 천 등으로 감싸 소리를 줄임",
        },
        "dampened": {
            "id": "pt.dampened", "type": "direction",
            "length_factor": 0.2, "families": ["percussion"],
            "description": "댐프닝 — 손으로 눌러 울림을 줄임",
        },

        # --- 건반 기법 (12개) ---
        "pedal": {
            "id": "pt.pedal", "type": "direction",
            "cc64": True, "families": ["keyboard"],
            "description": "페달 — 서스테인 페달 (CC64)",
        },
        "sustain_pedal": {
            "id": "pt.sustainPedal", "type": "direction",
            "cc64": True, "families": ["keyboard"],
            "description": "서스테인 페달 — 모든 음을 지속 (CC64)",
        },
        "una_corda": {
            "id": "pt.unaCorda", "type": "direction",
            "cc67": True, "velocity_mod": 0.7, "families": ["keyboard"],
            "description": "우나 코르다 — 소프트 페달 (CC67)",
        },
        "sostenuto": {
            "id": "pt.sostenutoPedal", "type": "direction",
            "cc66": True, "families": ["keyboard"],
            "description": "소스테누토 페달 — 눌린 음만 지속 (CC66)",
        },
        "half_pedal": {
            "id": "pt.halfPedal", "type": "direction",
            "cc64_value": 64, "families": ["keyboard"],
            "description": "하프 페달 — 서스테인 페달을 반만 밟기",
        },
        "prepared_piano": {
            "id": "pt.preparedPiano", "type": "direction",
            "families": ["keyboard"],
            "description": "프리페어드 피아노 — 현에 이물질을 올려 변형된 소리",
        },
        "inside_piano": {
            "id": "pt.insidePiano", "type": "attribute",
            "families": ["keyboard"],
            "description": "피아노 내부 연주 — 현을 직접 건드림",
        },
        "muted_piano_string": {
            "id": "pt.mutedPianoString", "type": "attribute",
            "families": ["keyboard"],
            "description": "뮤티드 스트링 — 현을 손으로 막고 건반 타건",
        },
        "string_scrape": {
            "id": "pt.stringScrape", "type": "attribute",
            "families": ["keyboard"],
            "description": "스트링 스크레이프 — 피아노 현을 긁기",
        },
        "cluster_fist": {
            "id": "pt.clusterFist", "type": "attribute",
            "families": ["keyboard"],
            "description": "클러스터 (주먹) — 주먹으로 건반을 치는 클러스터",
        },
        "cluster_forearm": {
            "id": "pt.clusterForearm", "type": "attribute",
            "families": ["keyboard"],
            "description": "클러스터 (팔) — 팔뚝으로 건반을 누르는 클러스터",
        },
        "silent_key": {
            "id": "pt.silentKey", "type": "attribute",
            "families": ["keyboard"],
            "description": "사일런트 키 — 소리 없이 건반을 눌러 댐퍼만 열기",
        },

        # --- 성악 기법 (18개) ---
        "normal_voice": {
            "id": "pt.normalVoice", "type": "direction",
            "families": ["singers"],
            "description": "일반 발성 — 기본 성악 발성",
        },
        "head_voice": {
            "id": "pt.headVoice", "type": "direction",
            "families": ["singers"],
            "description": "두성 — 머리에서 울리는 발성",
        },
        "chest_voice": {
            "id": "pt.chestVoice", "type": "direction",
            "families": ["singers"],
            "description": "흉성 — 가슴에서 울리는 발성",
        },
        "falsetto": {
            "id": "pt.falsetto", "type": "direction",
            "velocity_mod": 0.6, "families": ["singers"],
            "description": "팔세토 — 가성",
        },
        "belting": {
            "id": "pt.belting", "type": "direction",
            "velocity_mod": 1.3, "families": ["singers"],
            "description": "벨팅 — 강하게 밀어내는 발성",
        },
        "whisper": {
            "id": "pt.whisper", "type": "direction",
            "velocity_mod": 0.15, "families": ["singers"],
            "description": "속삭임 — 기식음 위주의 매우 약한 발성",
        },
        "breathy": {
            "id": "pt.breathy", "type": "direction",
            "velocity_mod": 0.4, "families": ["singers"],
            "description": "브레시 — 숨소리가 섞인 발성",
        },
        "spoken": {
            "id": "pt.spoken", "type": "direction",
            "families": ["singers"],
            "description": "스포큰 — 말하듯이",
        },
        "sprechgesang": {
            "id": "pt.sprechgesang", "type": "direction",
            "families": ["singers"],
            "description": "슈프레히게장 — 말과 노래의 중간",
        },
        "glottal_stop": {
            "id": "pt.glottalStop", "type": "attribute",
            "families": ["singers"],
            "description": "성문 폐쇄 — 성대를 급히 닫아 소리를 끊음",
        },
        "yodel": {
            "id": "pt.yodel", "type": "attribute",
            "families": ["singers"],
            "description": "요들 — 두성과 흉성의 빠른 교대",
        },
        "vocal_fry": {
            "id": "pt.vocalFry", "type": "direction",
            "velocity_mod": 0.2, "families": ["singers"],
            "description": "보컬 프라이 — 성대를 느슨히 하여 딱딱거리는 소리",
        },
        "melisma": {
            "id": "pt.melisma", "type": "attribute",
            "families": ["singers"],
            "description": "멜리스마 — 한 음절에 여러 음을 이어 부름",
        },
        "humming": {
            "id": "pt.humming", "type": "direction",
            "velocity_mod": 0.4, "families": ["singers"],
            "description": "허밍 — 입을 다물고 콧소리로 부름",
        },
        "nasal": {
            "id": "pt.nasal", "type": "direction",
            "families": ["singers"],
            "description": "비성 — 코를 통해 울리는 발성",
        },
        "covered": {
            "id": "pt.covered", "type": "direction",
            "families": ["singers"],
            "description": "커버드 — 어둡고 둥근 음색의 발성",
        },
        "open_throat": {
            "id": "pt.openThroat", "type": "direction",
            "families": ["singers"],
            "description": "오픈 스로트 — 목을 열어 풍부한 울림",
        },
        "mouth_closed": {
            "id": "pt.mouthClosed", "type": "direction",
            "families": ["singers"],
            "description": "입 다물고 — 입을 닫은 상태의 발성",
        },

        # --- 전자악기/신스 기법 (15개) ---
        "filter_sweep": {
            "id": "pt.filterSweep", "type": "attribute",
            "families": ["electronics"],
            "description": "필터 스윕 — 주파수 필터를 이동",
        },
        "filter_open": {
            "id": "pt.filterOpen", "type": "direction",
            "families": ["electronics"],
            "description": "필터 오픈 — 필터를 완전히 열기",
        },
        "filter_closed": {
            "id": "pt.filterClosed", "type": "direction",
            "families": ["electronics"],
            "description": "필터 클로즈드 — 필터를 닫기",
        },
        "lfo_modulation": {
            "id": "pt.lfoModulation", "type": "attribute",
            "families": ["electronics"],
            "description": "LFO 모듈레이션 — 저주파 진동으로 변조",
        },
        "pitch_mod": {
            "id": "pt.pitchMod", "type": "attribute",
            "families": ["electronics"],
            "description": "피치 모듈레이션 — 음정 변조 효과",
        },
        "ring_mod": {
            "id": "pt.ringMod", "type": "attribute",
            "families": ["electronics"],
            "description": "링 모듈레이션 — 금속적인 변조 효과",
        },
        "noise_sweep": {
            "id": "pt.noiseSweep", "type": "attribute",
            "families": ["electronics"],
            "description": "노이즈 스윕 — 노이즈 주파수를 이동",
        },
        "bit_crush": {
            "id": "pt.bitCrush", "type": "attribute",
            "families": ["electronics"],
            "description": "비트 크러시 — 비트 깊이를 줄여 거친 소리",
        },
        "glitch": {
            "id": "pt.glitch", "type": "attribute",
            "families": ["electronics"],
            "description": "글리치 — 디지털 오류 같은 효과",
        },
        "stutter": {
            "id": "pt.stutter", "type": "attribute",
            "families": ["electronics"],
            "description": "스터터 — 소리를 빠르게 반복하는 글리치 효과",
        },
        "tape_stop": {
            "id": "pt.tapeStop", "type": "attribute",
            "families": ["electronics"],
            "description": "테이프 스톱 — 테이프 멈춤처럼 피치가 내려가는 효과",
        },
        "reverse": {
            "id": "pt.reverse", "type": "attribute",
            "families": ["electronics"],
            "description": "리버스 — 역재생 효과",
        },
        "sidechain": {
            "id": "pt.sidechain", "type": "attribute",
            "families": ["electronics"],
            "description": "사이드체인 — 펌핑 컴프 효과",
        },
        "arpeggiator": {
            "id": "pt.arpeggiator", "type": "attribute",
            "families": ["electronics"],
            "description": "아르페지에이터 — 자동 분산 화음",
        },
        "chord_mode": {
            "id": "pt.chordMode", "type": "attribute",
            "families": ["electronics"],
            "description": "코드 모드 — 하나의 키로 코드를 트리거",
        },

        # --- 하프 기법 (8개) ---
        "pres_de_la_table": {
            "id": "pt.presDeLaTable", "type": "direction",
            "timbre": "bright", "families": ["plucked"],
            "description": "프레 드 라 타블 — 사운드보드 가까이에서 뜯기",
        },
        "sons_etouffes": {
            "id": "pt.sonsEtouffes", "type": "attribute",
            "length_factor": 0.2, "families": ["plucked"],
            "description": "송 에투페 — 뮤트된 뜯기",
        },
        "nail_pizzicato": {
            "id": "pt.nailPizzicato", "type": "attribute",
            "timbre": "bright", "families": ["plucked"],
            "description": "네일 피치카토 — 손톱으로 뜯기",
        },
        "harmonics_harp": {
            "id": "pt.harmonicsHarp", "type": "attribute",
            "families": ["plucked"],
            "description": "하프 하모닉스 — 현의 중앙을 터치하며 뜯기",
        },
        "bisb_harp": {
            "id": "pt.bisbigliandoHarp", "type": "attribute",
            "families": ["plucked"],
            "description": "비스빌리안도 (하프) — 이명동음을 교대로 뜯기",
        },
        "thunder_effect": {
            "id": "pt.thunderEffect", "type": "attribute",
            "families": ["plucked"],
            "description": "썬더 이펙트 — 가장 낮은 현들을 세게 긁기",
        },
        "gliss_harp": {
            "id": "pt.glissandoHarp", "type": "attribute",
            "families": ["plucked"],
            "description": "글리산도 (하프) — 현을 쓸어 글리산도",
        },
        "pedal_slide_harp": {
            "id": "pt.pedalSlideHarp", "type": "attribute",
            "families": ["plucked"],
            "description": "페달 슬라이드 (하프) — 뜯은 후 페달을 변경하여 음정 변화",
        },

        # --- 민속/월드 악기 기법 (15개) ---
        "meend": {
            "id": "pt.meend", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "민드 — 인도 현악기의 긴 슬라이드 기법",
        },
        "gamak": {
            "id": "pt.gamak", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "가막 — 인도 음악의 흔들림 장식 기법",
        },
        "kan": {
            "id": "pt.kan", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "칸 — 인도 음악의 빠른 장식음",
        },
        "chikari": {
            "id": "pt.chikari", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "치카리 — 시타르의 리듬 현 연주",
        },
        "da": {
            "id": "pt.da", "type": "attribute",
            "families": ["ethnic_percussion"],
            "description": "다 — 타블라 오른손 타격",
        },
        "ge": {
            "id": "pt.ge", "type": "attribute",
            "families": ["ethnic_percussion"],
            "description": "게 — 타블라 왼손(바야) 타격",
        },
        "tremolo_mandolin": {
            "id": "pt.tremoloMandolin", "type": "attribute",
            "repeat_speed": "fast", "families": ["ethnic_strings"],
            "description": "만돌린 트레몰로 — 피크로 현을 빠르게 교대 피킹",
        },
        "shamisen_strike": {
            "id": "pt.shamisenStrike", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "바치 치기 — 샤미센의 바치(피크)로 강한 타격",
        },
        "koto_scrape": {
            "id": "pt.kotoScrape", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "고토 스크레이프 — 고토 현을 긁어 글리산도",
        },
        "erhu_slide": {
            "id": "pt.erhuSlide", "type": "attribute",
            "families": ["ethnic_strings"],
            "description": "얼후 슬라이드 — 얼후의 포르타멘토",
        },
        "didgeridoo_drone": {
            "id": "pt.didgeridooDrone", "type": "direction",
            "families": ["ethnic_wind"],
            "description": "디저리두 드론 — 기본 지속음",
        },
        "overtone_singing": {
            "id": "pt.overtoneSinging", "type": "attribute",
            "families": ["ethnic_wind"],
            "description": "오버톤 싱잉 — 배음 창법",
        },
        "shakuhachi_meri": {
            "id": "pt.shakuhachiMeri", "type": "attribute",
            "families": ["ethnic_wind"],
            "description": "메리 — 샤쿠하치의 음정을 낮추는 기법",
        },
        "shakuhachi_kari": {
            "id": "pt.shakuhachiKari", "type": "attribute",
            "families": ["ethnic_wind"],
            "description": "카리 — 샤쿠하치의 음정을 높이는 기법",
        },
        "tongue_click": {
            "id": "pt.tongueClick", "type": "attribute",
            "families": ["ethnic_percussion"],
            "description": "텅 클릭 — 혀 클릭음",
        },

        # --- 오르간 기법 (6개) ---
        "registration_change": {
            "id": "pt.registrationChange", "type": "direction",
            "families": ["organ"],
            "description": "레지스트레이션 변경 — 오르간 스톱 조합 변경",
        },
        "full_organ": {
            "id": "pt.fullOrgan", "type": "direction",
            "families": ["organ"],
            "description": "풀 오르간 — 모든 스톱을 열어 최대 음량",
        },
        "swell_open": {
            "id": "pt.swellOpen", "type": "direction",
            "families": ["organ"],
            "description": "스웰 오픈 — 스웰 박스를 열어 음량 증가",
        },
        "swell_closed": {
            "id": "pt.swellClosed", "type": "direction",
            "families": ["organ"],
            "description": "스웰 클로즈드 — 스웰 박스를 닫아 음량 감소",
        },
        "manual_change": {
            "id": "pt.manualChange", "type": "direction",
            "families": ["organ"],
            "description": "매뉴얼 변경 — 연주 건반을 전환",
        },
        "pedalboard": {
            "id": "pt.pedalboard", "type": "direction",
            "families": ["organ"],
            "description": "페달보드 — 발 건반으로 연주",
        },

        # --- 아코디언 기법 (5개) ---
        "bellows_shake": {
            "id": "pt.bellowsShake", "type": "attribute",
            "families": ["accordion"],
            "description": "벨로스 셰이크 — 풀무를 흔들어 트레몰로 효과",
        },
        "bellows_crescendo": {
            "id": "pt.bellowsCrescendo", "type": "attribute",
            "envelope": "ramp_up", "families": ["accordion"],
            "description": "벨로스 크레셴도 — 풀무 압력을 높여 크레셴도",
        },
        "bellows_staccato": {
            "id": "pt.bellowsStaccato", "type": "attribute",
            "length_factor": 0.4, "families": ["accordion"],
            "description": "벨로스 스타카토 — 풀무로 짧게 끊어 연주",
        },
        "register_switch": {
            "id": "pt.registerSwitch", "type": "direction",
            "families": ["accordion"],
            "description": "레지스터 스위치 — 음색 조합 변경",
        },
        "bayan_technique": {
            "id": "pt.bayanTechnique", "type": "attribute",
            "families": ["accordion"],
            "description": "바얀 테크닉 — 러시안 바얀의 특수 주법",
        },
    },
}

# ---------------------------------------------------------------------------
# 2. INSTRUMENT_DATABASE — 21개 패밀리, 대표 악기들
# ---------------------------------------------------------------------------

# 현악기 공통 기법 목록
_STRING_TECHNIQUES = [
    "natural", "arco", "pizzicato", "snap_pizzicato", "left_hand_pizzicato",
    "col_legno_battuto", "col_legno_tratto", "sul_ponticello", "sul_tasto",
    "flautando", "natural_harmonic", "artificial_harmonic", "downbow", "upbow",
    "overpressure", "con_sordino", "senza_sordino", "tremolo", "trill",
    "vibrato", "spiccato", "detache", "martellato", "staccato", "legato",
    "portato", "ricochet", "saltando", "double_stop",
]

# 관악기 공통 기법 목록
_WIND_TECHNIQUES = [
    "natural", "flutter_tongue", "double_tongue", "triple_tongue",
    "subtone", "overblow", "growl", "multiphonic", "vibrato",
    "trill", "tremolo", "staccato", "legato", "portato",
    "breath_tone", "air_tone", "key_click", "circular_breathing",
]

# 금관 공통 기법 목록
_BRASS_TECHNIQUES = [
    "natural", "flutter_tongue", "double_tongue", "triple_tongue",
    "stopped", "cuivre", "brassy", "straight_mute", "cup_mute",
    "harmon_mute_stem_in", "harmon_mute_stem_out", "plunger_mute",
    "bucket_mute", "half_valve", "lip_trill", "growl", "vibrato",
    "trill", "staccato", "legato", "portato",
    "doit", "fall", "scoop", "rip", "shake_brass",
]

# 타악기 공통 기법 목록
_PERCUSSION_TECHNIQUES = [
    "natural", "rim_shot", "cross_stick", "buzz_roll", "dead_stroke",
    "single_stroke_roll", "double_stroke_roll", "flam", "drag", "ruff",
    "roll", "muffled", "dampened",
]


INSTRUMENT_DATABASE: Dict[str, Dict[str, Dict[str, Any]]] = {

    # =================================================================
    # 현악기 (Strings)
    # =================================================================
    "strings": {
        "violin": {
            "id": "instrument.strings.violin", "sound_id": "strings.violin",
            "range": (55, 103), "clef": "treble", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["sul_e", "sul_a", "sul_d", "sul_g"],
            "gm_program": 40, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "viola": {
            "id": "instrument.strings.viola", "sound_id": "strings.viola",
            "range": (48, 93), "clef": "alto", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["sul_a", "sul_d", "sul_g", "sul_c"],
            "gm_program": 41, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "violoncello": {
            "id": "instrument.strings.violoncello", "sound_id": "strings.cello",
            "range": (36, 81), "clef": "bass", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["sul_a", "sul_d", "sul_g", "sul_c"],
            "gm_program": 42, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "contrabass": {
            "id": "instrument.strings.contrabass", "sound_id": "strings.contrabass",
            "range": (28, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES,
            "gm_program": 43, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "violin_section": {
            "id": "instrument.strings.violinSection", "sound_id": "strings.violinEnsemble",
            "range": (55, 103), "clef": "treble", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["divisi", "unison"],
            "gm_program": 48, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "viola_section": {
            "id": "instrument.strings.violaSection", "sound_id": "strings.violaEnsemble",
            "range": (48, 93), "clef": "alto", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["divisi", "unison"],
            "gm_program": 48, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "cello_section": {
            "id": "instrument.strings.celloSection", "sound_id": "strings.celloEnsemble",
            "range": (36, 81), "clef": "bass", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["divisi", "unison"],
            "gm_program": 48, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bass_section": {
            "id": "instrument.strings.bassSection", "sound_id": "strings.bassEnsemble",
            "range": (28, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["divisi", "unison"],
            "gm_program": 48, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
    },

    # =================================================================
    # 금관악기 (Brass)
    # =================================================================
    "brass": {
        "trumpet": {
            "id": "instrument.brass.trumpet", "sound_id": "brass.trumpet",
            "range": (55, 82), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 56, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,  # Bb trumpet
        },
        "trumpet_c": {
            "id": "instrument.brass.trumpetC", "sound_id": "brass.trumpetC",
            "range": (54, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 56, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "flugelhorn": {
            "id": "instrument.brass.flugelhorn", "sound_id": "brass.flugelhorn",
            "range": (54, 80), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 56, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,
        },
        "cornet": {
            "id": "instrument.brass.cornet", "sound_id": "brass.cornet",
            "range": (55, 82), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 56, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,
        },
        "french_horn": {
            "id": "instrument.brass.frenchHorn", "sound_id": "brass.frenchHorn",
            "range": (34, 77), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES + ["pedal_tone"],
            "gm_program": 60, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -7,  # F horn
        },
        "trombone": {
            "id": "instrument.brass.trombone", "sound_id": "brass.trombone",
            "range": (40, 72), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES + ["slide_gliss", "pedal_tone"],
            "gm_program": 57, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bass_trombone": {
            "id": "instrument.brass.bassTrombone", "sound_id": "brass.bassTrombone",
            "range": (33, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES + ["slide_gliss", "pedal_tone"],
            "gm_program": 57, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "tuba": {
            "id": "instrument.brass.tuba", "sound_id": "brass.tuba",
            "range": (28, 58), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES + ["pedal_tone"],
            "gm_program": 58, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "euphonium": {
            "id": "instrument.brass.euphonium", "sound_id": "brass.euphonium",
            "range": (34, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 58, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "trumpet_section": {
            "id": "instrument.brass.trumpetSection", "sound_id": "brass.trumpetEnsemble",
            "range": (55, 82), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 61, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,
        },
        "horn_section": {
            "id": "instrument.brass.hornSection", "sound_id": "brass.hornEnsemble",
            "range": (34, 77), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 61, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -7,
        },
        "trombone_section": {
            "id": "instrument.brass.tromboneSection", "sound_id": "brass.tromboneEnsemble",
            "range": (40, 72), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 61, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 목관악기 (Wind / Woodwinds)
    # =================================================================
    "wind": {
        "flute": {
            "id": "instrument.wind.flute", "sound_id": "wind.flute",
            "range": (60, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["whistle_tone", "jet_whistle", "tongue_ram", "harmonic_fingering"],
            "gm_program": 73, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "piccolo": {
            "id": "instrument.wind.piccolo", "sound_id": "wind.piccolo",
            "range": (74, 108), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 72, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 12,
        },
        "alto_flute": {
            "id": "instrument.wind.altoFlute", "sound_id": "wind.altoFlute",
            "range": (55, 91), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 73, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -5,
        },
        "bass_flute": {
            "id": "instrument.wind.bassFlute", "sound_id": "wind.bassFlute",
            "range": (48, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 73, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "oboe": {
            "id": "instrument.wind.oboe", "sound_id": "wind.oboe",
            "range": (58, 91), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 68, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "english_horn": {
            "id": "instrument.wind.englishHorn", "sound_id": "wind.englishHorn",
            "range": (52, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 69, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -7,
        },
        "oboe_damore": {
            "id": "instrument.wind.oboeDamore", "sound_id": "wind.oboeDamore",
            "range": (55, 86), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 68, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -3,
        },
        "clarinet_bb": {
            "id": "instrument.wind.clarinetBb", "sound_id": "wind.clarinetBb",
            "range": (50, 91), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["slap_tongue", "teeth_on_reed"],
            "gm_program": 71, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,
        },
        "clarinet_a": {
            "id": "instrument.wind.clarinetA", "sound_id": "wind.clarinetA",
            "range": (49, 90), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 71, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -3,
        },
        "clarinet_eb": {
            "id": "instrument.wind.clarinetEb", "sound_id": "wind.clarinetEb",
            "range": (55, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 71, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 3,
        },
        "bass_clarinet": {
            "id": "instrument.wind.bassClarinet", "sound_id": "wind.bassClarinet",
            "range": (38, 79), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 71, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -14,
        },
        "bassoon": {
            "id": "instrument.wind.bassoon", "sound_id": "wind.bassoon",
            "range": (34, 75), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 70, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "contrabassoon": {
            "id": "instrument.wind.contrabassoon", "sound_id": "wind.contrabassoon",
            "range": (22, 60), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 70, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "soprano_sax": {
            "id": "instrument.wind.sopranoSax", "sound_id": "wind.sopranoSax",
            "range": (56, 87), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["slap_tongue", "subtone", "growl"],
            "gm_program": 64, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -2,
        },
        "alto_sax": {
            "id": "instrument.wind.altoSax", "sound_id": "wind.altoSax",
            "range": (49, 80), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["slap_tongue", "subtone", "growl"],
            "gm_program": 65, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -9,
        },
        "tenor_sax": {
            "id": "instrument.wind.tenorSax", "sound_id": "wind.tenorSax",
            "range": (44, 75), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["slap_tongue", "subtone", "growl"],
            "gm_program": 66, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -14,
        },
        "baritone_sax": {
            "id": "instrument.wind.baritoneSax", "sound_id": "wind.baritoneSax",
            "range": (36, 68), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES + ["slap_tongue", "subtone", "growl"],
            "gm_program": 67, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -21,
        },
        "recorder": {
            "id": "instrument.wind.recorder", "sound_id": "wind.recorder",
            "range": (72, 98), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "vibrato", "trill", "staccato", "legato"],
            "gm_program": 74, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 건반악기 (Keyboard)
    # =================================================================
    "keyboard": {
        "piano": {
            "id": "instrument.keyboard.piano", "sound_id": "keyboard.piano",
            "range": (21, 108), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "sustain_pedal", "una_corda", "sostenuto", "half_pedal",
                "staccato", "legato", "accent", "marcato", "tenuto",
            ],
            "gm_program": 0, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bright_piano": {
            "id": "instrument.keyboard.brightPiano", "sound_id": "keyboard.brightPiano",
            "range": (21, 108), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "sustain_pedal", "una_corda", "sostenuto"],
            "gm_program": 1, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "electric_piano": {
            "id": "instrument.keyboard.electricPiano", "sound_id": "keyboard.ePiano",
            "range": (28, 103), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "sustain_pedal", "tremolo"],
            "gm_program": 4, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "harpsichord": {
            "id": "instrument.keyboard.harpsichord", "sound_id": "keyboard.harpsichord",
            "range": (29, 89), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "staccato", "legato"],
            "gm_program": 6, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "clavinet": {
            "id": "instrument.keyboard.clavinet", "sound_id": "keyboard.clavinet",
            "range": (36, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "muted", "staccato"],
            "gm_program": 7, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "celesta": {
            "id": "instrument.keyboard.celesta", "sound_id": "keyboard.celesta",
            "range": (60, 108), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "sustain_pedal", "staccato", "legato"],
            "gm_program": 8, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "prepared_piano_inst": {
            "id": "instrument.keyboard.preparedPiano", "sound_id": "keyboard.preparedPiano",
            "range": (21, 108), "clef": "grand", "staves": 2,
            "default_techniques": ["natural", "prepared_piano"],
            "available_techniques": [
                "natural", "prepared_piano", "inside_piano", "muted_piano_string",
                "string_scrape", "cluster_fist", "cluster_forearm",
            ],
            "gm_program": 0, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 프렛악기 (Fretted)
    # =================================================================
    "fretted": {
        "acoustic_guitar": {
            "id": "instrument.fretted.acousticGuitar", "sound_id": "fretted.acousticGuitar",
            "range": (40, 88), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "palm_muting", "natural_harmonic", "artificial_harmonic",
                "hammer_on", "pull_off", "bend_guitar", "slide_guitar_up", "slide_guitar_down",
                "strum_up", "strum_down", "arpeggio_guitar", "rasgueado", "golpe",
                "tambour", "let_ring", "staccato", "legato",
            ],
            "gm_program": 25, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "classical_guitar": {
            "id": "instrument.fretted.classicalGuitar", "sound_id": "fretted.classicalGuitar",
            "range": (40, 88), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "natural_harmonic", "artificial_harmonic",
                "hammer_on", "pull_off", "rasgueado", "golpe", "tambour",
                "arpeggio_guitar", "let_ring", "staccato", "legato", "vibrato",
            ],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "electric_guitar": {
            "id": "instrument.fretted.electricGuitar", "sound_id": "fretted.electricGuitar",
            "range": (40, 88), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "palm_muting", "pinch_harmonic", "natural_harmonic",
                "hammer_on", "pull_off", "bend_guitar", "prebend", "release_bend",
                "slide_guitar_up", "slide_guitar_down", "vibrato_bar", "whammy_dive",
                "whammy_return", "feedback", "power_chord", "tap", "pick_scrape",
                "let_ring", "staccato", "legato", "muted", "chucking",
            ],
            "gm_program": 27, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "electric_guitar_clean": {
            "id": "instrument.fretted.electricGuitarClean", "sound_id": "fretted.electricGuitarClean",
            "range": (40, 88), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "palm_muting", "natural_harmonic", "hammer_on", "pull_off",
                "bend_guitar", "let_ring", "staccato", "legato",
            ],
            "gm_program": 27, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "electric_guitar_distortion": {
            "id": "instrument.fretted.electricGuitarDist", "sound_id": "fretted.electricGuitarDist",
            "range": (40, 88), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "palm_muting", "pinch_harmonic", "feedback",
                "power_chord", "pick_scrape", "whammy_dive", "staccato",
            ],
            "gm_program": 30, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "bass_guitar": {
            "id": "instrument.fretted.bassGuitar", "sound_id": "fretted.bassGuitar",
            "range": (28, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "slap", "pop", "palm_muting", "hammer_on", "pull_off",
                "tap", "natural_harmonic", "muted", "ghost_note",
                "let_ring", "staccato", "legato", "bend_guitar",
            ],
            "gm_program": 33, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "five_string_bass": {
            "id": "instrument.fretted.fiveStringBass", "sound_id": "fretted.fiveStringBass",
            "range": (23, 67), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "slap", "pop", "palm_muting", "tap",
                "natural_harmonic", "muted", "ghost_note", "staccato", "legato",
            ],
            "gm_program": 33, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": -12,
        },
        "ukulele": {
            "id": "instrument.fretted.ukulele", "sound_id": "fretted.ukulele",
            "range": (60, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "strum_up", "strum_down", "hammer_on", "pull_off", "let_ring"],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "banjo": {
            "id": "instrument.fretted.banjo", "sound_id": "fretted.banjo",
            "range": (48, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "hammer_on", "pull_off", "strum_up", "strum_down", "let_ring"],
            "gm_program": 105, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "mandolin": {
            "id": "instrument.fretted.mandolin", "sound_id": "fretted.mandolin",
            "range": (55, 89), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "tremolo", "hammer_on", "pull_off", "strum_up", "strum_down"],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 타악기 (Percussion — pitched and unpitched)
    # =================================================================
    "percussion": {
        "drum_set": {
            "id": "instrument.percussion.drumSet", "sound_id": "percussion.drumSet",
            "range": (35, 81), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _PERCUSSION_TECHNIQUES + [
                "open_hi_hat", "closed_hi_hat", "half_open_hi_hat",
                "pedal_hi_hat", "splash_hi_hat", "choke",
                "brush_sweep", "brush_tap", "with_sticks", "with_hands",
            ],
            "gm_program": 0, "gm_bank": 128,  # GM drum channel
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "timpani": {
            "id": "instrument.percussion.timpani", "sound_id": "percussion.timpani",
            "range": (40, 57), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _PERCUSSION_TECHNIQUES + [
                "hard_mallet", "soft_mallet", "with_sticks",
            ],
            "gm_program": 47, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "snare_drum": {
            "id": "instrument.percussion.snareDrum", "sound_id": "percussion.snare",
            "range": (38, 38), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": _PERCUSSION_TECHNIQUES + ["brush_sweep", "brush_tap", "with_sticks"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "bass_drum": {
            "id": "instrument.percussion.bassDrum", "sound_id": "percussion.bassDrum",
            "range": (35, 36), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "muffled", "dampened", "dead_stroke", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "cymbals": {
            "id": "instrument.percussion.cymbals", "sound_id": "percussion.cymbals",
            "range": (49, 57), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "choke", "roll", "center_hit", "edge_hit", "bell_hit", "dampened"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "triangle": {
            "id": "instrument.percussion.triangle", "sound_id": "percussion.triangle",
            "range": (81, 81), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "muted", "roll", "open"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "tambourine": {
            "id": "instrument.percussion.tambourine", "sound_id": "percussion.tambourine",
            "range": (54, 54), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll", "with_fingers", "with_hands"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "glockenspiel": {
            "id": "instrument.percussion.glockenspiel", "sound_id": "percussion.glockenspiel",
            "range": (79, 108), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dead_stroke", "roll", "hard_mallet", "soft_mallet"],
            "gm_program": 9, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 24,
        },
        "xylophone": {
            "id": "instrument.percussion.xylophone", "sound_id": "percussion.xylophone",
            "range": (65, 108), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dead_stroke", "roll", "hard_mallet", "soft_mallet", "yarn_mallet"],
            "gm_program": 13, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 12,
        },
        "marimba": {
            "id": "instrument.percussion.marimba", "sound_id": "percussion.marimba",
            "range": (45, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dead_stroke", "roll", "hard_mallet", "soft_mallet", "yarn_mallet"],
            "gm_program": 12, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "vibraphone": {
            "id": "instrument.percussion.vibraphone", "sound_id": "percussion.vibraphone",
            "range": (53, 89), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dead_stroke", "roll", "pedal", "dampened", "hard_mallet", "soft_mallet"],
            "gm_program": 11, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "tubular_bells": {
            "id": "instrument.percussion.tubularBells", "sound_id": "percussion.tubularBells",
            "range": (60, 77), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dampened", "roll"],
            "gm_program": 14, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "crotales": {
            "id": "instrument.percussion.crotales", "sound_id": "percussion.crotales",
            "range": (72, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dampened"],
            "gm_program": 14, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 24,
        },
    },

    # =================================================================
    # 성악 (Singers)
    # =================================================================
    "singers": {
        "soprano": {
            "id": "instrument.singers.soprano", "sound_id": "singers.soprano",
            "range": (60, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "head_voice", "chest_voice", "falsetto", "belting",
                "whisper", "breathy", "spoken", "sprechgesang", "glottal_stop",
                "vibrato", "trill", "staccato", "legato", "melisma",
                "humming", "nasal", "covered", "open_throat", "mouth_closed",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "mezzo_soprano": {
            "id": "instrument.singers.mezzoSoprano", "sound_id": "singers.mezzoSoprano",
            "range": (57, 81), "clef": "treble", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "head_voice", "chest_voice", "belting",
                "whisper", "breathy", "vibrato", "legato", "humming",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "alto": {
            "id": "instrument.singers.alto", "sound_id": "singers.alto",
            "range": (53, 77), "clef": "treble", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "head_voice", "chest_voice", "belting",
                "whisper", "breathy", "vibrato", "legato", "humming",
            ],
            "gm_program": 53, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "countertenor": {
            "id": "instrument.singers.countertenor", "sound_id": "singers.countertenor",
            "range": (52, 79), "clef": "treble", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "falsetto", "head_voice", "vibrato", "legato", "humming",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "tenor": {
            "id": "instrument.singers.tenor", "sound_id": "singers.tenor",
            "range": (48, 74), "clef": "treble", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "head_voice", "chest_voice", "falsetto", "belting",
                "whisper", "breathy", "vibrato", "legato", "humming",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "baritone": {
            "id": "instrument.singers.baritone", "sound_id": "singers.baritone",
            "range": (45, 69), "clef": "bass", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "head_voice", "chest_voice", "belting",
                "whisper", "breathy", "vibrato", "legato", "humming",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bass_voice": {
            "id": "instrument.singers.bass", "sound_id": "singers.bass",
            "range": (40, 64), "clef": "bass", "staves": 1,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "chest_voice", "vocal_fry", "whisper",
                "breathy", "vibrato", "legato", "humming",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 전자악기 (Electronics)
    # =================================================================
    "electronics": {
        "synthesizer": {
            "id": "instrument.electronics.synthesizer", "sound_id": "electronics.synth",
            "range": (21, 108), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "filter_sweep", "filter_open", "filter_closed",
                "lfo_modulation", "pitch_mod", "ring_mod", "arpeggiator",
                "chord_mode", "glitch", "stutter",
            ],
            "gm_program": 80, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "synth_lead": {
            "id": "instrument.electronics.synthLead", "sound_id": "electronics.synthLead",
            "range": (36, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "filter_sweep", "lfo_modulation", "pitch_mod",
                "portamento_up", "portamento_down", "glitch",
            ],
            "gm_program": 80, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "synth_pad": {
            "id": "instrument.electronics.synthPad", "sound_id": "electronics.synthPad",
            "range": (24, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "filter_sweep", "filter_open", "filter_closed",
                "lfo_modulation", "sidechain",
            ],
            "gm_program": 88, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "synth_bass": {
            "id": "instrument.electronics.synthBass", "sound_id": "electronics.synthBass",
            "range": (24, 72), "clef": "bass", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "filter_sweep", "sidechain", "glitch", "stutter",
            ],
            "gm_program": 38, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "sampler": {
            "id": "instrument.electronics.sampler", "sound_id": "electronics.sampler",
            "range": (0, 127), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "reverse", "tape_stop", "bit_crush", "stutter", "glitch"],
            "gm_program": 0, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "drum_machine": {
            "id": "instrument.electronics.drumMachine", "sound_id": "electronics.drumMachine",
            "range": (36, 84), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "reverse", "bit_crush", "stutter", "sidechain"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
    },

    # =================================================================
    # 뜯는 악기 (Plucked)
    # =================================================================
    "plucked": {
        "harp": {
            "id": "instrument.plucked.harp", "sound_id": "plucked.harp",
            "range": (24, 103), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "pres_de_la_table", "sons_etouffes", "nail_pizzicato",
                "harmonics_harp", "bisb_harp", "thunder_effect", "gliss_harp",
                "pedal_slide_harp", "dampened", "arpeggio_up", "arpeggio_down",
            ],
            "gm_program": 46, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "lute": {
            "id": "instrument.plucked.lute", "sound_id": "plucked.lute",
            "range": (40, 79), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "arpeggio_up", "arpeggio_down", "staccato", "legato"],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "zither": {
            "id": "instrument.plucked.zither", "sound_id": "plucked.zither",
            "range": (36, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dampened", "arpeggio_up", "arpeggio_down"],
            "gm_program": 15, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 민속 현악기 (Ethnic Strings)
    # =================================================================
    "ethnic_strings": {
        "sitar": {
            "id": "instrument.ethnic.sitar", "sound_id": "ethnic.sitar",
            "range": (48, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "meend", "gamak", "kan", "chikari", "vibrato"],
            "gm_program": 104, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "erhu": {
            "id": "instrument.ethnic.erhu", "sound_id": "ethnic.erhu",
            "range": (55, 93), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "erhu_slide", "vibrato", "tremolo", "trill", "legato"],
            "gm_program": 110, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "koto": {
            "id": "instrument.ethnic.koto", "sound_id": "ethnic.koto",
            "range": (43, 79), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "koto_scrape", "vibrato", "arpeggio_up", "arpeggio_down"],
            "gm_program": 107, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "shamisen": {
            "id": "instrument.ethnic.shamisen", "sound_id": "ethnic.shamisen",
            "range": (50, 86), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "shamisen_strike", "vibrato", "tremolo"],
            "gm_program": 106, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "oud": {
            "id": "instrument.ethnic.oud", "sound_id": "ethnic.oud",
            "range": (43, 79), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "tremolo", "vibrato", "slide"],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "pipa": {
            "id": "instrument.ethnic.pipa", "sound_id": "ethnic.pipa",
            "range": (45, 93), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "tremolo", "vibrato", "slide", "bend"],
            "gm_program": 24, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 민속 관악기 (Ethnic Wind)
    # =================================================================
    "ethnic_wind": {
        "shakuhachi": {
            "id": "instrument.ethnic.shakuhachi", "sound_id": "ethnic.shakuhachi",
            "range": (53, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "shakuhachi_meri", "shakuhachi_kari",
                "vibrato", "flutter_tongue", "breath_tone",
            ],
            "gm_program": 77, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "didgeridoo": {
            "id": "instrument.ethnic.didgeridoo", "sound_id": "ethnic.didgeridoo",
            "range": (29, 48), "clef": "bass", "staves": 1,
            "default_techniques": ["didgeridoo_drone"],
            "available_techniques": ["didgeridoo_drone", "overtone_singing", "circular_breathing"],
            "gm_program": 109, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "pan_flute": {
            "id": "instrument.ethnic.panFlute", "sound_id": "ethnic.panFlute",
            "range": (60, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "vibrato", "legato", "staccato"],
            "gm_program": 75, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bagpipe": {
            "id": "instrument.ethnic.bagpipe", "sound_id": "ethnic.bagpipe",
            "range": (55, 79), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "vibrato"],
            "gm_program": 109, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "ocarina": {
            "id": "instrument.ethnic.ocarina", "sound_id": "ethnic.ocarina",
            "range": (60, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "vibrato", "legato", "staccato"],
            "gm_program": 79, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 민속 타악기 (Ethnic Percussion)
    # =================================================================
    "ethnic_percussion": {
        "tabla": {
            "id": "instrument.ethnic.tabla", "sound_id": "ethnic.tabla",
            "range": (48, 72), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "da", "ge", "roll", "muted"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "djembe": {
            "id": "instrument.ethnic.djembe", "sound_id": "ethnic.djembe",
            "range": (36, 60), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "slap", "with_fingers", "muted", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "congas": {
            "id": "instrument.ethnic.congas", "sound_id": "ethnic.congas",
            "range": (60, 65), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "slap", "muted", "with_fingers", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "bongos": {
            "id": "instrument.ethnic.bongos", "sound_id": "ethnic.bongos",
            "range": (60, 61), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "slap", "muted", "with_fingers"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "cajon": {
            "id": "instrument.ethnic.cajon", "sound_id": "ethnic.cajon",
            "range": (36, 42), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "slap", "ghost_note", "with_fingers", "with_hands"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "taiko": {
            "id": "instrument.ethnic.taiko", "sound_id": "ethnic.taiko",
            "range": (36, 48), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll", "rim_shot", "center_hit", "edge_hit"],
            "gm_program": 116, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "steelpan": {
            "id": "instrument.ethnic.steelpan", "sound_id": "ethnic.steelpan",
            "range": (60, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll", "dampened", "dead_stroke"],
            "gm_program": 114, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 오르간 (Organ)
    # =================================================================
    "organ": {
        "pipe_organ": {
            "id": "instrument.organ.pipeOrgan", "sound_id": "organ.pipeOrgan",
            "range": (24, 108), "clef": "grand", "staves": 3,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "registration_change", "full_organ", "swell_open",
                "swell_closed", "manual_change", "pedalboard", "legato", "staccato",
            ],
            "gm_program": 19, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "hammond_organ": {
            "id": "instrument.organ.hammondOrgan", "sound_id": "organ.hammondOrgan",
            "range": (36, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "registration_change", "staccato", "legato"],
            "gm_program": 16, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "reed_organ": {
            "id": "instrument.organ.reedOrgan", "sound_id": "organ.reedOrgan",
            "range": (36, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "legato", "staccato"],
            "gm_program": 20, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 아코디언 (Accordion)
    # =================================================================
    "accordion": {
        "accordion": {
            "id": "instrument.accordion.accordion", "sound_id": "accordion.accordion",
            "range": (36, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "bellows_shake", "bellows_crescendo", "bellows_staccato",
                "register_switch", "staccato", "legato", "vibrato",
            ],
            "gm_program": 21, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "bandoneon": {
            "id": "instrument.accordion.bandoneon", "sound_id": "accordion.bandoneon",
            "range": (36, 96), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": [
                "natural", "bellows_shake", "bellows_staccato", "staccato", "legato",
            ],
            "gm_program": 23, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "harmonica": {
            "id": "instrument.accordion.harmonica", "sound_id": "accordion.harmonica",
            "range": (60, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "vibrato", "bend", "overblow", "staccato", "legato"],
            "gm_program": 22, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 앙상블 현악 (Ensemble Strings)
    # =================================================================
    "ensemble_strings": {
        "string_orchestra": {
            "id": "instrument.ensemble.stringOrchestra", "sound_id": "ensemble.strings",
            "range": (28, 103), "clef": "grand", "staves": 2,
            "default_techniques": ["natural", "arco"],
            "available_techniques": _STRING_TECHNIQUES + ["divisi", "unison"],
            "gm_program": 48, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 앙상블 금관 (Ensemble Brass)
    # =================================================================
    "ensemble_brass": {
        "brass_ensemble": {
            "id": "instrument.ensemble.brassEnsemble", "sound_id": "ensemble.brass",
            "range": (28, 82), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": _BRASS_TECHNIQUES,
            "gm_program": 61, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 앙상블 목관 (Ensemble Wind)
    # =================================================================
    "ensemble_wind": {
        "woodwind_ensemble": {
            "id": "instrument.ensemble.woodwindEnsemble", "sound_id": "ensemble.wind",
            "range": (34, 108), "clef": "grand", "staves": 2,
            "default_techniques": ["natural"],
            "available_techniques": _WIND_TECHNIQUES,
            "gm_program": 68, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 앙상블 보컬 (Ensemble Vocal)
    # =================================================================
    "ensemble_vocal": {
        "choir": {
            "id": "instrument.ensemble.choir", "sound_id": "ensemble.choir",
            "range": (40, 84), "clef": "grand", "staves": 2,
            "default_techniques": ["normal_voice"],
            "available_techniques": [
                "normal_voice", "humming", "mouth_closed", "whisper",
                "vibrato", "legato", "staccato",
            ],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "choir_aahs": {
            "id": "instrument.ensemble.choirAahs", "sound_id": "ensemble.choirAahs",
            "range": (40, 84), "clef": "grand", "staves": 2,
            "default_techniques": ["normal_voice"],
            "available_techniques": ["normal_voice", "vibrato", "legato"],
            "gm_program": 52, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
        "choir_oohs": {
            "id": "instrument.ensemble.choirOohs", "sound_id": "ensemble.choirOohs",
            "range": (40, 84), "clef": "grand", "staves": 2,
            "default_techniques": ["normal_voice"],
            "available_techniques": ["normal_voice", "vibrato", "legato"],
            "gm_program": 53, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": 1, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 피치 타악기 (Pitched Percussion — 별도)
    # =================================================================
    "pitched_percussion": {
        "steel_drums": {
            "id": "instrument.pitchedPerc.steelDrums", "sound_id": "pitchedPerc.steelDrums",
            "range": (48, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll", "dampened", "dead_stroke"],
            "gm_program": 114, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "kalimba": {
            "id": "instrument.pitchedPerc.kalimba", "sound_id": "pitchedPerc.kalimba",
            "range": (60, 84), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "dampened", "vibrato"],
            "gm_program": 108, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "music_box": {
            "id": "instrument.pitchedPerc.musicBox", "sound_id": "pitchedPerc.musicBox",
            "range": (60, 96), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 10, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
    },

    # =================================================================
    # 비피치 타악기 (Unpitched Percussion — 보조)
    # =================================================================
    "unpitched_percussion": {
        "claves": {
            "id": "instrument.unpitchedPerc.claves", "sound_id": "unpitchedPerc.claves",
            "range": (75, 75), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "woodblock": {
            "id": "instrument.unpitchedPerc.woodblock", "sound_id": "unpitchedPerc.woodblock",
            "range": (76, 77), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll"],
            "gm_program": 115, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "maracas": {
            "id": "instrument.unpitchedPerc.maracas", "sound_id": "unpitchedPerc.maracas",
            "range": (70, 70), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "shaker": {
            "id": "instrument.unpitchedPerc.shaker", "sound_id": "unpitchedPerc.shaker",
            "range": (70, 70), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "cowbell": {
            "id": "instrument.unpitchedPerc.cowbell", "sound_id": "unpitchedPerc.cowbell",
            "range": (56, 56), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "muted"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "guiro": {
            "id": "instrument.unpitchedPerc.guiro", "sound_id": "unpitchedPerc.guiro",
            "range": (73, 74), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "castanets": {
            "id": "instrument.unpitchedPerc.castanets", "sound_id": "unpitchedPerc.castanets",
            "range": (85, 85), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural", "roll"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
        "wind_chimes": {
            "id": "instrument.unpitchedPerc.windChimes", "sound_id": "unpitchedPerc.windChimes",
            "range": (84, 84), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
    },

    # =================================================================
    # 기타/효과 (Other)
    # =================================================================
    "other": {
        "sound_effects": {
            "id": "instrument.other.soundEffects", "sound_id": "other.sfx",
            "range": (0, 127), "clef": "treble", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 120, "gm_bank": 0,
            "expression": {"volume_cc": 11, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0,
        },
        "metronome": {
            "id": "instrument.other.metronome", "sound_id": "other.metronome",
            "range": (60, 76), "clef": "percussion", "staves": 1,
            "default_techniques": ["natural"],
            "available_techniques": ["natural"],
            "gm_program": 0, "gm_bank": 128,
            "expression": {"volume_cc": None, "vibrato_cc": None, "attack_type": "velocity"},
            "transposition": 0, "is_drum": True,
        },
    },
}


# ---------------------------------------------------------------------------
# 3. EXPRESSION_MAPS — Cubase 스타일 Expression Map (기법 → MIDI 동작 매핑)
# ---------------------------------------------------------------------------

EXPRESSION_MAPS: Dict[str, Dict[str, Dict[str, Any]]] = {

    # --- 기본 맵 ---
    "default": {
        "natural": {"volume_type": "velocity", "attack_type": "velocity"},
    },

    # --- CC11 다이나믹 맵 ---
    "cc11_dynamics": {
        "natural": {"volume_type": ("cc", 11), "attack_type": "velocity"},
    },

    # --- 오케스트라 현악기 ---
    "orchestral_strings": {
        "natural": {"volume_type": ("cc", 11), "attack_type": "velocity", "vibrato_cc": 1},
        "arco": {"keyswitch": "C0", "volume_type": ("cc", 11), "attack_type": "velocity"},
        "pizzicato": {"keyswitch": "C#0", "length_factor": 0.3, "volume_type": "velocity"},
        "tremolo": {"keyswitch": "D0", "cc_tremolo": (1, 80)},
        "staccato": {"keyswitch": "D#0", "length_factor": 0.5},
        "spiccato": {"keyswitch": "E0", "length_factor": 0.3, "velocity_mod": 0.9},
        "detache": {"keyswitch": "F0", "length_factor": 0.85},
        "legato": {"keyswitch": "F#0", "length_factor": 1.05, "overlap_ticks": 10},
        "martellato": {"keyswitch": "G0", "length_factor": 0.4, "velocity_mod": 1.2},
        "col_legno_battuto": {"keyswitch": "G#0", "velocity_mod": 0.6},
        "col_legno_tratto": {"keyswitch": "A0", "velocity_mod": 0.5},
        "sul_ponticello": {"keyswitch": "A#0", "timbre": "bright"},
        "sul_tasto": {"keyswitch": "B0", "timbre": "dark"},
        "flautando": {"keyswitch": "C1", "velocity_mod": 0.5},
        "natural_harmonic": {"keyswitch": "C#1"},
        "con_sordino": {"keyswitch": "D1", "velocity_mod": 0.7},
        "snap_pizzicato": {"keyswitch": "D#1", "velocity_mod": 1.4, "length_factor": 0.2},
        "portato": {"keyswitch": "E1", "length_factor": 0.75},
        "trill": {"keyswitch": "F1", "interval": 2},
        "trill_half": {"keyswitch": "F#1", "interval": 1},
    },

    # --- 오케스트라 금관악기 ---
    "orchestral_brass": {
        "natural": {"volume_type": ("cc", 11), "attack_type": "velocity", "vibrato_cc": 1},
        "staccato": {"keyswitch": "C0", "length_factor": 0.5},
        "legato": {"keyswitch": "C#0", "length_factor": 1.05, "overlap_ticks": 10},
        "marcato": {"keyswitch": "D0", "velocity_mod": 1.5},
        "sfz": {"keyswitch": "D#0", "velocity_start": 127, "velocity_end": 60},
        "flutter_tongue": {"keyswitch": "E0"},
        "stopped": {"keyswitch": "F0"},
        "cuivre": {"keyswitch": "F#0", "velocity_mod": 1.3},
        "straight_mute": {"keyswitch": "G0"},
        "cup_mute": {"keyswitch": "G#0"},
        "harmon_mute_stem_in": {"keyswitch": "A0"},
        "harmon_mute_stem_out": {"keyswitch": "A#0"},
        "plunger_mute": {"keyswitch": "B0"},
        "trill": {"keyswitch": "C1", "interval": 2},
        "trill_half": {"keyswitch": "C#1", "interval": 1},
    },

    # --- 오케스트라 목관악기 ---
    "orchestral_woodwinds": {
        "natural": {"volume_type": ("cc", 11), "attack_type": "velocity", "vibrato_cc": 1},
        "staccato": {"keyswitch": "C0", "length_factor": 0.5},
        "legato": {"keyswitch": "C#0", "length_factor": 1.05, "overlap_ticks": 10},
        "portato": {"keyswitch": "D0", "length_factor": 0.75},
        "flutter_tongue": {"keyswitch": "D#0"},
        "double_tongue": {"keyswitch": "E0"},
        "trill": {"keyswitch": "F0", "interval": 2},
        "trill_half": {"keyswitch": "F#0", "interval": 1},
        "tremolo": {"keyswitch": "G0"},
        "overblown": {"keyswitch": "G#0"},
        "multiphonic": {"keyswitch": "A0"},
    },

    # --- 피아노 ---
    "piano": {
        "natural": {"volume_type": "velocity", "attack_type": "velocity"},
        "sustain_pedal": {"cc64": True},
        "una_corda": {"cc67": True, "velocity_mod": 0.7},
        "sostenuto": {"cc66": True},
        "half_pedal": {"cc64_value": 64},
    },

    # --- 일렉트릭 기타 ---
    "electric_guitar": {
        "natural": {"volume_type": "velocity", "attack_type": "velocity"},
        "palm_muting": {"keyswitch": "C0", "velocity_mod": 0.7, "length_factor": 0.6},
        "pinch_harmonic": {"keyswitch": "C#0"},
        "natural_harmonic": {"keyswitch": "D0"},
        "staccato": {"keyswitch": "D#0", "length_factor": 0.5},
        "legato": {"keyswitch": "E0", "length_factor": 1.05, "overlap_ticks": 10},
        "power_chord": {"keyswitch": "F0"},
        "muted": {"keyswitch": "F#0", "velocity_mod": 0.6},
    },

    # --- 베이스 기타 ---
    "bass_guitar": {
        "natural": {"volume_type": "velocity", "attack_type": "velocity"},
        "slap": {"keyswitch": "C0", "velocity_mod": 1.3},
        "pop": {"keyswitch": "C#0", "velocity_mod": 1.2},
        "palm_muting": {"keyswitch": "D0", "velocity_mod": 0.7, "length_factor": 0.6},
        "natural_harmonic": {"keyswitch": "D#0"},
        "ghost_note": {"keyswitch": "E0", "velocity_mod": 0.3},
        "staccato": {"keyswitch": "F0", "length_factor": 0.5},
        "legato": {"keyswitch": "F#0", "length_factor": 1.05, "overlap_ticks": 10},
    },

    # --- 드럼셋 ---
    "drum_set": {
        "natural": {"volume_type": "velocity", "attack_type": "velocity"},
        "rim_shot": {"note_remap": {38: 40}},
        "cross_stick": {"note_remap": {38: 37}},
        "open_hi_hat": {"note_remap": {42: 46}},
        "closed_hi_hat": {"note_remap": {46: 42}},
        "pedal_hi_hat": {"note_remap": {42: 44}},
        "ghost_note": {"velocity_mod": 0.3},
        "buzz_roll": {"repeat_speed": "fast"},
        "flam": {"grace_note_offset": -15},
    },

    # --- 보컬 ---
    "vocal": {
        "normal_voice": {"volume_type": ("cc", 11), "attack_type": "velocity", "vibrato_cc": 1},
        "falsetto": {"keyswitch": "C0", "velocity_mod": 0.6},
        "belting": {"keyswitch": "C#0", "velocity_mod": 1.3},
        "whisper": {"keyswitch": "D0", "velocity_mod": 0.15},
        "breathy": {"keyswitch": "D#0", "velocity_mod": 0.4},
        "humming": {"keyswitch": "E0", "velocity_mod": 0.4},
    },

    # --- 신스/전자음 ---
    "synthesizer": {
        "natural": {"volume_type": ("cc", 11), "attack_type": "velocity"},
        "filter_sweep": {"cc74_sweep": True},
        "filter_open": {"cc74_value": 127},
        "filter_closed": {"cc74_value": 0},
        "arpeggiator": {"arp_mode": True},
    },
}


# ---------------------------------------------------------------------------
# 4. MUTUAL_EXCLUSION_GROUPS — 기법 상호 배타 규칙
# ---------------------------------------------------------------------------

MUTUAL_EXCLUSION_GROUPS: Dict[str, List[List[str]]] = {
    "bow_direction": [
        ["arco", "pizzicato", "col_legno_battuto", "col_legno_tratto"],
    ],
    "bow_position": [
        ["sul_ponticello", "sul_tasto", "flautando", "natural"],
    ],
    "string_selection": [
        ["sul_g", "sul_d", "sul_a", "sul_e", "sul_c"],
    ],
    "sordino": [
        ["con_sordino", "senza_sordino"],
    ],
    "brass_mute": [
        ["open", "straight_mute", "cup_mute", "harmon_mute_stem_in",
         "harmon_mute_stem_out", "plunger_mute", "bucket_mute", "practice_mute"],
    ],
    "dynamic_level": [
        ["ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "n"],
    ],
    "vibrato_type": [
        ["vibrato", "wide_vibrato", "narrow_vibrato", "non_vibrato",
         "slow_vibrato", "fast_vibrato"],
    ],
    "voice_register": [
        ["normal_voice", "head_voice", "chest_voice", "falsetto",
         "belting", "whisper", "breathy", "spoken", "vocal_fry"],
    ],
    "hi_hat_state": [
        ["open_hi_hat", "closed_hi_hat", "half_open_hi_hat", "pedal_hi_hat"],
    ],
    "length_articulation": [
        ["staccato", "staccatissimo", "tenuto", "portato", "legato",
         "spiccato", "detache", "martellato", "non_legato"],
    ],
    "filter_state": [
        ["filter_open", "filter_closed"],
    ],
    "mallet_type": [
        ["hard_mallet", "soft_mallet", "yarn_mallet", "with_sticks",
         "with_mallets", "with_hands", "with_fingers"],
    ],
    "guitar_technique": [
        ["natural", "palm_muting", "muted"],
    ],
    "organ_swell": [
        ["swell_open", "swell_closed"],
    ],
}


# ---------------------------------------------------------------------------
# 5. 인덱스 캐시 (내부 사용)
# ---------------------------------------------------------------------------

# 전체 기법을 플랫하게 인덱싱
_TECHNIQUE_FLAT_INDEX: Dict[str, Dict[str, Any]] = {}
for _group_name, _group in PLAYING_TECHNIQUES.items():
    for _tech_name, _tech_def in _group.items():
        _TECHNIQUE_FLAT_INDEX[_tech_name] = {**_tech_def, "_group": _group_name}

# 악기를 (family, name) → definition으로 인덱싱
_INSTRUMENT_INDEX: Dict[str, Dict[str, Any]] = {}
for _family_name, _family in INSTRUMENT_DATABASE.items():
    for _inst_name, _inst_def in _family.items():
        _key = _inst_def["id"]
        _INSTRUMENT_INDEX[_key] = {**_inst_def, "_family": _family_name, "_name": _inst_name}

# technique_name → 속한 exclusion group 이름 목록
_TECHNIQUE_EXCLUSION_MAP: Dict[str, List[str]] = {}
for _group_name, _group_lists in MUTUAL_EXCLUSION_GROUPS.items():
    for _tech_list in _group_lists:
        for _tech in _tech_list:
            _TECHNIQUE_EXCLUSION_MAP.setdefault(_tech, []).append(_group_name)


# ---------------------------------------------------------------------------
# 6. 헬퍼 함수
# ---------------------------------------------------------------------------

def get_instrument(family: str, name: str) -> Optional[Dict[str, Any]]:
    """악기 패밀리와 이름으로 악기 정의를 조회합니다.

    Args:
        family: 악기 패밀리 이름 (예: "strings", "brass").
        name: 악기 이름 (예: "violin", "trumpet").

    Returns:
        악기 정의 딕셔너리. 없으면 ``None``.
    """
    fam = INSTRUMENT_DATABASE.get(family)
    if fam is None:
        return None
    return fam.get(name)


def get_techniques_for_instrument(instrument_id: str) -> List[str]:
    """악기 ID로 사용 가능한 기법 목록을 반환합니다.

    Args:
        instrument_id: 악기 ID (예: "instrument.strings.violin").

    Returns:
        해당 악기에서 사용 가능한 기법 이름 리스트.
        악기를 찾을 수 없으면 빈 리스트를 반환합니다.
    """
    inst = _INSTRUMENT_INDEX.get(instrument_id)
    if inst is None:
        return []
    return list(inst.get("available_techniques", []))


def apply_technique(
    note_event: Dict[str, Any],
    technique_name: str,
) -> Dict[str, Any]:
    """노트 이벤트에 기법을 적용하여 수정된 이벤트를 반환합니다.

    원본 ``note_event``는 변경하지 않으며 깊은 복사본을 반환합니다.
    기법의 ``velocity_mod``, ``length_factor``, ``overlap_ticks``,
    ``cc_mappings``, ``velocity_range`` 등의 속성을 적용합니다.

    Args:
        note_event: 최소한 다음 키를 가진 딕셔너리:
            - ``"velocity"`` (int): 0-127
            - ``"duration"`` (int): 틱 단위 길이
            선택적으로 ``"cc"`` (Dict[int, int]) 등을 가질 수 있습니다.
        technique_name: 적용할 기법 이름 (예: "staccato", "pizzicato").

    Returns:
        수정된 노트 이벤트 딕셔너리.
        기법을 찾을 수 없으면 원본의 복사본을 그대로 반환합니다.
    """
    result = copy.deepcopy(note_event)

    tech = _TECHNIQUE_FLAT_INDEX.get(technique_name)
    if tech is None:
        return result

    # velocity_mod 적용
    if "velocity_mod" in tech:
        vel = result.get("velocity", 100)
        vel = int(vel * tech["velocity_mod"])
        result["velocity"] = max(1, min(127, vel))

    # length_factor 적용
    if "length_factor" in tech:
        dur = result.get("duration", 480)
        result["duration"] = max(1, int(dur * tech["length_factor"]))

    # overlap_ticks 적용 (레가토 등)
    if "overlap_ticks" in tech:
        dur = result.get("duration", 480)
        result["duration"] = dur + tech["overlap_ticks"]

    # velocity_range 적용 (다이나믹 레벨)
    if "velocity_range" in tech:
        lo, hi = tech["velocity_range"]
        result["velocity"] = (lo + hi) // 2

    # velocity_start / velocity_end 적용 (엔벨로프)
    if "velocity_start" in tech:
        result["velocity"] = tech["velocity_start"]
        result["_velocity_end"] = tech.get("velocity_end", result["velocity"])
        result["_envelope"] = tech.get("envelope", "linear")

    # CC 매핑 적용
    cc = result.setdefault("cc", {})

    if "cc1_depth" in tech:
        cc[1] = tech["cc1_depth"]

    if "cc11_range" in tech:
        lo, hi = tech["cc11_range"]
        cc[11] = (lo + hi) // 2

    if "cc64" in tech and tech["cc64"]:
        cc[64] = tech.get("cc64_value", 127)

    if "cc65" in tech and tech["cc65"]:
        cc[65] = 127

    if "cc66" in tech and tech["cc66"]:
        cc[66] = 127

    if "cc67" in tech and tech["cc67"]:
        cc[67] = 127

    # repeat_count 적용
    if "repeat_count" in tech:
        result["_repeat_count"] = tech["repeat_count"]

    # repeat_speed 적용
    if "repeat_speed" in tech:
        result["_repeat_speed"] = tech["repeat_speed"]

    # interval 적용 (트릴 등)
    if "interval" in tech and tech["interval"] is not None:
        result["_trill_interval"] = tech["interval"]

    # pitch 관련 적용
    if "pitch_direction" in tech:
        result["_pitch_direction"] = tech["pitch_direction"]

    if "pitch_bend_range" in tech:
        result["_pitch_bend_range"] = tech["pitch_bend_range"]

    if "pitch_approach" in tech:
        result["_pitch_approach"] = tech["pitch_approach"]

    # spread (아르페지오/스트럼) 적용
    if "spread_ms" in tech:
        result["_spread_ms"] = tech["spread_ms"]
        result["_spread_direction"] = tech.get("direction", "up")

    # 기법 이름 기록
    result.setdefault("_applied_techniques", []).append(technique_name)

    return result


def get_expression_map(
    instrument_id: str,
    map_name: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """악기에 적합한 Expression Map을 반환합니다.

    ``map_name``이 지정되면 해당 맵을 직접 반환하고,
    지정되지 않으면 악기 패밀리에 따라 적절한 기본 맵을 선택합니다.

    Args:
        instrument_id: 악기 ID (예: "instrument.strings.violin").
        map_name: Expression Map 이름 (선택). ``None``이면 자동 선택.

    Returns:
        Expression Map 딕셔너리. 맵을 찾을 수 없으면 ``"default"`` 맵을 반환합니다.
    """
    if map_name is not None:
        return EXPRESSION_MAPS.get(map_name, EXPRESSION_MAPS["default"])

    # 악기 패밀리에 따라 자동 선택
    inst = _INSTRUMENT_INDEX.get(instrument_id)
    if inst is None:
        return EXPRESSION_MAPS["default"]

    family = inst.get("_family", "")

    _family_to_map = {
        "strings": "orchestral_strings",
        "ensemble_strings": "orchestral_strings",
        "brass": "orchestral_brass",
        "ensemble_brass": "orchestral_brass",
        "wind": "orchestral_woodwinds",
        "ensemble_wind": "orchestral_woodwinds",
        "keyboard": "piano",
        "fretted": "electric_guitar",
        "percussion": "drum_set",
        "singers": "vocal",
        "ensemble_vocal": "vocal",
        "electronics": "synthesizer",
        "organ": "cc11_dynamics",
        "accordion": "cc11_dynamics",
    }

    selected = _family_to_map.get(family, "default")
    return EXPRESSION_MAPS.get(selected, EXPRESSION_MAPS["default"])


def technique_compatible(technique1: str, technique2: str) -> bool:
    """두 기법이 동시에 사용 가능한지 확인합니다.

    상호 배타 그룹(MUTUAL_EXCLUSION_GROUPS)을 참조하여
    같은 배타 그룹에 속하는 경우 ``False``를 반환합니다.

    Args:
        technique1: 첫 번째 기법 이름.
        technique2: 두 번째 기법 이름.

    Returns:
        두 기법이 동시 사용 가능하면 ``True``, 불가능하면 ``False``.
    """
    if technique1 == technique2:
        return True

    groups1 = set(_TECHNIQUE_EXCLUSION_MAP.get(technique1, []))
    groups2 = set(_TECHNIQUE_EXCLUSION_MAP.get(technique2, []))

    # 공통 배타 그룹이 있는지 확인
    common = groups1 & groups2
    if not common:
        return True

    # 공통 그룹 내에서 같은 리스트에 있는지 확인
    for group_name in common:
        for tech_list in MUTUAL_EXCLUSION_GROUPS[group_name]:
            if technique1 in tech_list and technique2 in tech_list:
                return False

    return True


# ---------------------------------------------------------------------------
# 통계 정보 (모듈 로드 시 계산)
# ---------------------------------------------------------------------------

def _count_techniques() -> int:
    """전체 기법 수를 계산합니다."""
    return sum(len(g) for g in PLAYING_TECHNIQUES.values())


def _count_instruments() -> int:
    """전체 악기 수를 계산합니다."""
    return sum(len(f) for f in INSTRUMENT_DATABASE.values())


def _count_families() -> int:
    """악기 패밀리 수를 계산합니다."""
    return len(INSTRUMENT_DATABASE)


STATS = {
    "total_techniques": _count_techniques(),
    "total_instruments": _count_instruments(),
    "total_families": _count_families(),
    "technique_groups": {k: len(v) for k, v in PLAYING_TECHNIQUES.items()},
    "instruments_per_family": {k: len(v) for k, v in INSTRUMENT_DATABASE.items()},
}
