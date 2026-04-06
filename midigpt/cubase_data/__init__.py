"""
Cubase 15 기반 데이터 라이브러리
================================
Cubase 15 ISO에서 추출한 데이터를 MidiGPT 엔진에 통합:
- 298개 연주기법 (Playing Techniques)
- 147개 악기 정의 (21 패밀리, Instrument Database)
- 82개 아르페지에이터 패턴 (6 카테고리)
- 24종 코드 품질 x 6 보이싱 타입 (Chord Voicings)
- 13개 그루브 템플릿 (Groove Templates)
- 93개 VST3 기반 이펙트 체인 프리셋 (Effect Chains)
- 11개 익스프레션 맵 (Expression Maps)
"""

from .expression_maps import (
    PLAYING_TECHNIQUES,
    INSTRUMENT_DATABASE,
    EXPRESSION_MAPS,
    MUTUAL_EXCLUSION_GROUPS,
    get_instrument,
    get_techniques_for_instrument,
    apply_technique,
    get_expression_map,
    technique_compatible,
)

from .arpeggiator_patterns import (
    ArpEvent,
    ArpPattern,
    ARPEGGIATOR_PATTERNS,
    get_pattern,
    get_patterns_by_category,
    get_patterns_by_style,
    apply_pattern,
    humanize_pattern,
    transpose_pattern,
    combine_patterns,
    list_all_categories,
    list_all_styles,
    list_all_patterns,
    pattern_count,
)

from .chord_voicings import (
    CHORD_INTERVALS,
    VOICING_LIBRARY,
    GROOVE_TEMPLATES,
    Voicing,
    GrooveTemplate,
    ChordPadEntry,
    voice_lead,
    apply_groove,
    get_voicing,
    get_groove_for_style,
    build_chord_pad_set,
)

from .effect_chains import (
    PLUGIN_CATALOG,
    EFFECT_CHAIN_PRESETS,
    EffectParam,
    EffectSlot,
    EffectChain,
    get_effect_chain,
    get_all_chains_for_style,
    chain_to_daw_metadata,
)

__all__ = [
    # Expression Maps & Instruments
    "PLAYING_TECHNIQUES", "INSTRUMENT_DATABASE", "EXPRESSION_MAPS",
    "MUTUAL_EXCLUSION_GROUPS",
    "get_instrument", "get_techniques_for_instrument",
    "apply_technique", "get_expression_map", "technique_compatible",
    # Arpeggiator Patterns
    "ArpEvent", "ArpPattern", "ARPEGGIATOR_PATTERNS",
    "get_pattern", "get_patterns_by_category", "get_patterns_by_style",
    "apply_pattern", "humanize_pattern", "transpose_pattern", "combine_patterns",
    "list_all_categories", "list_all_styles", "list_all_patterns", "pattern_count",
    # Chord Voicings & Grooves
    "CHORD_INTERVALS", "VOICING_LIBRARY", "GROOVE_TEMPLATES",
    "Voicing", "GrooveTemplate", "ChordPadEntry",
    "voice_lead", "apply_groove", "get_voicing", "get_groove_for_style",
    "build_chord_pad_set",
    # Effect Chains
    "PLUGIN_CATALOG", "EFFECT_CHAIN_PRESETS",
    "EffectParam", "EffectSlot", "EffectChain",
    "get_effect_chain", "get_all_chains_for_style", "chain_to_daw_metadata",
]
