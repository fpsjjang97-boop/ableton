"""
Cubase 15 기반 VST3 이펙트 체인 프리셋 시스템
=============================================
Cubase 15의 93개 VST3 플러그인 파라미터 구조를 기반으로
장르별/트랙별 이펙트 체인 프리셋을 정의.

MIDI 엔진에서 직접 오디오를 처리하지는 않지만,
DAW 연동 시 이펙트 체인을 자동으로 설정하기 위한 메타데이터를 제공.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


# ─── 이펙트 파라미터 정의 (Cubase 15 VST3 XML 기반) ───

@dataclass
class EffectParam:
    """이펙트 파라미터."""
    name: str
    value: float          # 0.0 ~ 1.0 정규화
    display_value: str    # 표시용 값
    unit: str = ""        # 단위 (dB, Hz, ms, % 등)


@dataclass
class EffectSlot:
    """이펙트 슬롯."""
    plugin_name: str      # VST3 플러그인 이름
    plugin_id: str        # VST3 Class ID
    category: str         # Fx|Dynamics, Fx|EQ, Fx|Reverb 등
    bypass: bool = False
    params: dict[str, EffectParam] = field(default_factory=dict)


@dataclass
class EffectChain:
    """이펙트 체인 프리셋."""
    name: str
    description: str
    target_track: str     # 대상 트랙 타입
    target_style: str     # 대상 스타일
    inserts: list[EffectSlot] = field(default_factory=list)
    sends: list[dict] = field(default_factory=list)  # 센드 이펙트 라우팅


# ─── Cubase 15 VST3 플러그인 카탈로그 (93개 중 핵심) ───

PLUGIN_CATALOG = {
    # ─── Dynamics ───
    "Compressor": {
        "id": "5B38F28281144FFE80285FF7CCF20483",
        "category": "Fx|Dynamics",
        "params": ["Threshold", "Ratio", "Attack", "Release", "MakeUp",
                    "AutoMakeUp", "SoftKnee", "DryMix", "Hold"],
    },
    "Tube Compressor": {
        "id": "tube_comp_id",
        "category": "Fx|Dynamics",
        "params": ["Input", "Output", "Drive", "Ratio", "Attack", "Release",
                    "Mix", "Saturation"],
    },
    "Limiter": {
        "id": "limiter_id",
        "category": "Fx|Dynamics",
        "params": ["Input", "Output", "Release"],
    },
    "Brickwall Limiter": {
        "id": "brickwall_id",
        "category": "Fx|Dynamics",
        "params": ["Threshold", "Release", "Ceiling", "Link"],
    },
    "Maximizer": {
        "id": "maximizer_id",
        "category": "Fx|Dynamics",
        "params": ["Optimize", "Output", "Mix", "SoftClip"],
    },
    "Gate": {
        "id": "gate_id",
        "category": "Fx|Dynamics",
        "params": ["Threshold", "Range", "Attack", "Hold", "Release",
                    "SideChain", "FilterFreq"],
    },
    "DeEsser": {
        "id": "deesser_id",
        "category": "Fx|Dynamics",
        "params": ["Threshold", "Reduction", "Frequency", "Monitor"],
    },
    "EnvelopeShaper": {
        "id": "env_shaper_id",
        "category": "Fx|Dynamics",
        "params": ["Attack", "Length", "Sustain", "Release", "Output"],
    },
    "VocalChain": {
        "id": "vocalchain_id",
        "category": "Fx|Dynamics",
        "params": ["Gate", "Compressor", "EQ", "Saturation", "DeEsser",
                    "Limiter", "Output"],
    },
    "VoxComp": {
        "id": "voxcomp_id",
        "category": "Fx|Dynamics",
        "params": ["Threshold", "Ratio", "Attack", "Release", "Mix", "Output"],
    },

    # ─── EQ ───
    "Studio EQ": {
        "id": "studio_eq_id",
        "category": "Fx|EQ",
        "params": ["LowFreq", "LowGain", "LowMidFreq", "LowMidGain", "LowMidQ",
                    "HighMidFreq", "HighMidGain", "HighMidQ", "HighFreq", "HighGain",
                    "Output"],
    },
    "Frequency": {
        "id": "frequency_id",
        "category": "Fx|EQ",
        "params": [f"Band{i}_{p}" for i in range(1, 9)
                    for p in ["Freq", "Gain", "Q", "Type"]],
    },
    "GEQ-30": {
        "id": "geq30_id",
        "category": "Fx|EQ",
        "params": [f"Band_{i}" for i in range(30)] + ["Output", "Flatten"],
    },

    # ─── Reverb ───
    "REVelation": {
        "id": "revelation_id",
        "category": "Fx|Reverb",
        "params": ["PreDelay", "Size", "Time", "Diffusion", "DampingHigh",
                    "DampingLow", "Mix", "Width", "Modulation", "ER_Mix"],
    },
    "REVerence": {
        "id": "reverence_id",
        "category": "Fx|Reverb",
        "params": ["IRFile", "PreDelay", "Time", "Size", "Mix",
                    "DampingHigh", "DampingLow", "Width", "ER_Tail_Mix"],
    },
    "RoomWorks": {
        "id": "roomworks_id",
        "category": "Fx|Reverb",
        "params": ["PreDelay", "Size", "Time", "Diffusion", "Mix",
                    "DampingHigh", "DampingLow", "Width", "Hold",
                    "ER_TailMix", "Efficiency"],
    },

    # ─── Delay ───
    "StereoDelay": {
        "id": "stereo_delay_id",
        "category": "Fx|Delay",
        "params": ["DelayL", "DelayR", "Feedback", "Filter", "Mix",
                    "Sync", "Width", "Pan"],
    },
    "PingPongDelay": {
        "id": "pingpong_id",
        "category": "Fx|Delay",
        "params": ["Delay", "Feedback", "Mix", "Filter", "Spatial", "Sync"],
    },
    "MultiTap Delay": {
        "id": "multitap_id",
        "category": "Fx|Delay",
        "params": [f"Tap{i}_{p}" for i in range(1, 5)
                    for p in ["Delay", "Level", "Pan"]] + ["Feedback", "Mix"],
    },

    # ─── Modulation ───
    "Chorus": {
        "id": "chorus_id",
        "category": "Fx|Modulation",
        "params": ["Rate", "Width", "Delay", "Mix", "Shape", "Spatial"],
    },
    "Flanger": {
        "id": "flanger_id",
        "category": "Fx|Modulation",
        "params": ["Rate", "Width", "Delay", "Feedback", "Mix",
                    "Manual", "Shape"],
    },
    "Phaser": {
        "id": "phaser_id",
        "category": "Fx|Modulation",
        "params": ["Rate", "Width", "Feedback", "Mix", "Manual",
                    "Stages", "Spatial"],
    },
    "Tremolo": {
        "id": "tremolo_id",
        "category": "Fx|Modulation",
        "params": ["Rate", "Depth", "Shape", "Sync", "SpatialSpread"],
    },
    "Rotary": {
        "id": "rotary_id",
        "category": "Fx|Modulation",
        "params": ["Speed", "Slow", "Fast", "Acceleration", "Amp", "Mix"],
    },
    "AutoPan": {
        "id": "autopan_id",
        "category": "Fx|Modulation",
        "params": ["Rate", "Width", "Shape", "Sync"],
    },

    # ─── Distortion ───
    "Distortion": {
        "id": "distortion_id",
        "category": "Fx|Distortion",
        "params": ["Boost", "Feedback", "Tone", "Mix", "Output",
                    "Spatial", "Oversampling"],
    },
    "VST Amp Rack": {
        "id": "amprack_id",
        "category": "Fx|Distortion",
        "params": ["AmpModel", "Drive", "Bass", "Mid", "Treble",
                    "Presence", "Volume", "Master", "Cabinet",
                    "Mic", "MicPosition"],
    },
    "VST Bass Amp": {
        "id": "bassamp_id",
        "category": "Fx|Distortion",
        "params": ["AmpModel", "Drive", "Bass", "LoMid", "HiMid",
                    "Treble", "Volume", "Master", "Cabinet"],
    },
    "Magneto II": {
        "id": "magneto_id",
        "category": "Fx|Distortion",
        "params": ["Saturation", "TapeFreq", "HFAdjust", "HFRolloff",
                    "Output", "DualMode"],
    },

    # ─── Pitch ───
    "Pitch Correct": {
        "id": "pitch_correct_id",
        "category": "Fx|Pitch",
        "params": ["Speed", "Tolerance", "Scale", "Transpose",
                    "Formant", "FormantShift"],
    },

    # ─── Spatial ───
    "Imager": {
        "id": "imager_id",
        "category": "Fx|Spatial",
        "params": [f"Band{i}_{p}" for i in range(1, 5)
                    for p in ["Width", "Pan", "Solo"]],
    },
    "StereoEnhancer": {
        "id": "stereo_enh_id",
        "category": "Fx|Spatial",
        "params": ["Width", "Delay", "Color", "Mono"],
    },

    # ─── Analysis ───
    "SuperVision": {
        "id": "supervision_id",
        "category": "Fx|Analysis",
        "params": ["Mode", "MaxLevel", "MeterType"],
    },
}


# ─── 장르별 이펙트 체인 프리셋 ───

EFFECT_CHAIN_PRESETS: dict[str, dict[str, EffectChain]] = {
    # ─── 보컬 체인 ───
    "vocal": {
        "pop_vocal": EffectChain(
            name="Pop Vocal Chain",
            description="팝 보컬 — 게이트 → EQ → 컴프 → 디에서 → 리버브 센드",
            target_track="vocal",
            target_style="pop",
            inserts=[
                EffectSlot("Gate", "gate_id", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.3, "-35 dB", "dB"),
                    "Attack": EffectParam("Attack", 0.01, "0.5 ms", "ms"),
                    "Release": EffectParam("Release", 0.3, "100 ms", "ms"),
                }),
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.15, "80 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "HighMidFreq": EffectParam("HighMidFreq", 0.6, "3.5 kHz", "Hz"),
                    "HighMidGain": EffectParam("HighMidGain", 0.55, "+2 dB", "dB"),
                    "HighMidQ": EffectParam("HighMidQ", 0.4, "1.5", ""),
                }),
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.4, "-18 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.3, "3:1", ""),
                    "Attack": EffectParam("Attack", 0.15, "5 ms", "ms"),
                    "Release": EffectParam("Release", 0.3, "80 ms", "ms"),
                    "MakeUp": EffectParam("MakeUp", 0.55, "+4 dB", "dB"),
                }),
                EffectSlot("DeEsser", "deesser_id", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.5, "-20 dB", "dB"),
                    "Frequency": EffectParam("Frequency", 0.7, "6.5 kHz", "Hz"),
                }),
            ],
            sends=[
                {"plugin": "REVelation", "level": 0.25, "params": {
                    "PreDelay": "30 ms", "Time": "1.8s", "Mix": "100%"}},
                {"plugin": "StereoDelay", "level": 0.15, "params": {
                    "DelayL": "1/4", "DelayR": "1/8d", "Mix": "100%"}},
            ],
        ),
        "jazz_vocal": EffectChain(
            name="Jazz Vocal Chain",
            description="재즈 보컬 — 따뜻한 EQ, 부드러운 컴프, 플레이트 리버브",
            target_track="vocal",
            target_style="jazz",
            inserts=[
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.1, "60 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "LowMidFreq": EffectParam("LowMidFreq", 0.25, "250 Hz", "Hz"),
                    "LowMidGain": EffectParam("LowMidGain", 0.52, "+1 dB", "dB"),
                }),
                EffectSlot("Tube Compressor", "tube_comp_id", "Fx|Dynamics", params={
                    "Input": EffectParam("Input", 0.5, "0 dB", "dB"),
                    "Drive": EffectParam("Drive", 0.3, "Light", ""),
                    "Ratio": EffectParam("Ratio", 0.2, "2:1", ""),
                    "Attack": EffectParam("Attack", 0.2, "10 ms", "ms"),
                    "Release": EffectParam("Release", 0.4, "150 ms", "ms"),
                }),
            ],
            sends=[
                {"plugin": "REVerence", "level": 0.3, "params": {
                    "IRFile": "Plate Medium", "PreDelay": "15 ms", "Mix": "100%"}},
            ],
        ),
    },

    # ─── 드럼 체인 ───
    "drums": {
        "pop_drums": EffectChain(
            name="Pop Drums Bus",
            description="팝 드럼 — 컴프 → EQ → 리미터",
            target_track="drums",
            target_style="pop",
            inserts=[
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.35, "-20 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.35, "4:1", ""),
                    "Attack": EffectParam("Attack", 0.05, "1 ms", "ms"),
                    "Release": EffectParam("Release", 0.25, "60 ms", "ms"),
                }),
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.05, "30 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "HighFreq": EffectParam("HighFreq", 0.8, "10 kHz", "Hz"),
                    "HighGain": EffectParam("HighGain", 0.55, "+2 dB", "dB"),
                }),
            ],
            sends=[
                {"plugin": "RoomWorks", "level": 0.1, "params": {
                    "Size": "Small Room", "Time": "0.5s", "Mix": "100%"}},
            ],
        ),
        "edm_drums": EffectChain(
            name="EDM Drums Bus",
            description="EDM 드럼 — 하드 컴프 → 디스토션 → 리미터",
            target_track="drums",
            target_style="edm",
            inserts=[
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.3, "-24 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.5, "6:1", ""),
                    "Attack": EffectParam("Attack", 0.02, "0.3 ms", "ms"),
                    "Release": EffectParam("Release", 0.2, "40 ms", "ms"),
                }),
                EffectSlot("Magneto II", "magneto_id", "Fx|Distortion", params={
                    "Saturation": EffectParam("Saturation", 0.3, "30%", "%"),
                    "Output": EffectParam("Output", 0.45, "-2 dB", "dB"),
                }),
                EffectSlot("Limiter", "limiter_id", "Fx|Dynamics", params={
                    "Input": EffectParam("Input", 0.6, "+3 dB", "dB"),
                    "Release": EffectParam("Release", 0.15, "10 ms", "ms"),
                }),
            ],
        ),
    },

    # ─── 베이스 체인 ───
    "bass": {
        "pop_bass": EffectChain(
            name="Pop Bass",
            description="팝 베이스 — EQ → 컴프 → 세츄레이션",
            target_track="bass",
            target_style="pop",
            inserts=[
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.03, "20 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "LowMidFreq": EffectParam("LowMidFreq", 0.15, "100 Hz", "Hz"),
                    "LowMidGain": EffectParam("LowMidGain", 0.55, "+2 dB", "dB"),
                }),
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.35, "-20 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.4, "4:1", ""),
                    "Attack": EffectParam("Attack", 0.1, "3 ms", "ms"),
                    "Release": EffectParam("Release", 0.3, "80 ms", "ms"),
                }),
            ],
        ),
        "edm_bass": EffectChain(
            name="EDM Bass",
            description="EDM 베이스 — 사이드체인 컴프 → 디스토션 → 리미터",
            target_track="bass",
            target_style="edm",
            inserts=[
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.25, "-30 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.6, "8:1", ""),
                    "Attack": EffectParam("Attack", 0.01, "0.1 ms", "ms"),
                    "Release": EffectParam("Release", 0.35, "100 ms", "ms"),
                }),
                EffectSlot("Distortion", "distortion_id", "Fx|Distortion", params={
                    "Boost": EffectParam("Boost", 0.4, "40%", "%"),
                    "Tone": EffectParam("Tone", 0.5, "50%", "%"),
                    "Mix": EffectParam("Mix", 0.3, "30%", "%"),
                }),
            ],
        ),
    },

    # ─── 기타 체인 ───
    "guitar": {
        "clean_guitar": EffectChain(
            name="Clean Guitar",
            description="클린 기타 — 코러스 → EQ → 리버브 센드",
            target_track="guitar",
            target_style="pop",
            inserts=[
                EffectSlot("Chorus", "chorus_id", "Fx|Modulation", params={
                    "Rate": EffectParam("Rate", 0.4, "1.2 Hz", "Hz"),
                    "Width": EffectParam("Width", 0.5, "50%", "%"),
                    "Mix": EffectParam("Mix", 0.3, "30%", "%"),
                }),
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.1, "80 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "HighFreq": EffectParam("HighFreq", 0.7, "8 kHz", "Hz"),
                    "HighGain": EffectParam("HighGain", 0.53, "+1.5 dB", "dB"),
                }),
            ],
            sends=[
                {"plugin": "REVelation", "level": 0.25, "params": {
                    "PreDelay": "20 ms", "Time": "1.5s", "Mix": "100%"}},
            ],
        ),
        "rock_guitar": EffectChain(
            name="Rock Guitar",
            description="록 기타 — 앰프 → EQ → 딜레이 센드",
            target_track="guitar",
            target_style="metal",
            inserts=[
                EffectSlot("VST Amp Rack", "amprack_id", "Fx|Distortion", params={
                    "AmpModel": EffectParam("AmpModel", 0.6, "Crunch", ""),
                    "Drive": EffectParam("Drive", 0.6, "60%", "%"),
                    "Bass": EffectParam("Bass", 0.5, "5", ""),
                    "Mid": EffectParam("Mid", 0.6, "6", ""),
                    "Treble": EffectParam("Treble", 0.55, "5.5", ""),
                    "Cabinet": EffectParam("Cabinet", 0.5, "4x12 V30", ""),
                }),
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "HighMidFreq": EffectParam("HighMidFreq", 0.5, "2.5 kHz", "Hz"),
                    "HighMidGain": EffectParam("HighMidGain", 0.53, "+1.5 dB", "dB"),
                }),
            ],
            sends=[
                {"plugin": "StereoDelay", "level": 0.2, "params": {
                    "DelayL": "1/4", "DelayR": "1/8", "Feedback": "30%",
                    "Mix": "100%"}},
            ],
        ),
    },

    # ─── 스트링 체인 ───
    "strings": {
        "orchestral_strings": EffectChain(
            name="Orchestral Strings",
            description="오케스트라 스트링 — EQ → 리버브 센드",
            target_track="strings",
            target_style="orchestral",
            inserts=[
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.1, "60 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "HighMidFreq": EffectParam("HighMidFreq", 0.55, "3 kHz", "Hz"),
                    "HighMidGain": EffectParam("HighMidGain", 0.52, "+1 dB", "dB"),
                }),
            ],
            sends=[
                {"plugin": "REVerence", "level": 0.35, "params": {
                    "IRFile": "Concert Hall Large", "PreDelay": "25 ms",
                    "Time": "2.5s", "Mix": "100%"}},
            ],
        ),
    },

    # ─── 피아노 체인 ───
    "keyboard": {
        "grand_piano": EffectChain(
            name="Grand Piano",
            description="그랜드 피아노 — EQ → 컴프 → 홀 리버브",
            target_track="accomp",
            target_style="classical",
            inserts=[
                EffectSlot("Studio EQ", "studio_eq_id", "Fx|EQ", params={
                    "LowFreq": EffectParam("LowFreq", 0.05, "30 Hz", "Hz"),
                    "LowGain": EffectParam("LowGain", 0.0, "-inf (HPF)", "dB"),
                    "HighFreq": EffectParam("HighFreq", 0.85, "12 kHz", "Hz"),
                    "HighGain": EffectParam("HighGain", 0.53, "+1 dB", "dB"),
                }),
                EffectSlot("Compressor", "5B38F28281144FFE80285FF7CCF20483", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.5, "-12 dB", "dB"),
                    "Ratio": EffectParam("Ratio", 0.15, "2:1", ""),
                    "Attack": EffectParam("Attack", 0.2, "10 ms", "ms"),
                    "Release": EffectParam("Release", 0.4, "150 ms", "ms"),
                }),
            ],
            sends=[
                {"plugin": "REVerence", "level": 0.3, "params": {
                    "IRFile": "Concert Hall", "PreDelay": "20 ms",
                    "Time": "2.0s", "Mix": "100%"}},
            ],
        ),
    },

    # ─── 마스터 체인 ───
    "master": {
        "pop_master": EffectChain(
            name="Pop Mastering",
            description="팝 마스터링 — EQ → 멀티밴드컴프 → 이미저 → 리미터",
            target_track="master",
            target_style="pop",
            inserts=[
                EffectSlot("Frequency", "frequency_id", "Fx|EQ", params={
                    "Band1_Freq": EffectParam("LF", 0.03, "30 Hz", "Hz"),
                    "Band1_Gain": EffectParam("LF Gain", 0.0, "-inf (HPF)", "dB"),
                    "Band5_Freq": EffectParam("Presence", 0.6, "4 kHz", "Hz"),
                    "Band5_Gain": EffectParam("Presence Gain", 0.52, "+1 dB", "dB"),
                    "Band7_Freq": EffectParam("Air", 0.85, "12 kHz", "Hz"),
                    "Band7_Gain": EffectParam("Air Gain", 0.53, "+1.5 dB", "dB"),
                }),
                EffectSlot("Imager", "imager_id", "Fx|Spatial", params={
                    "Band1_Width": EffectParam("Low Width", 0.4, "Narrow", ""),
                    "Band3_Width": EffectParam("Mid Width", 0.55, "Normal", ""),
                    "Band4_Width": EffectParam("High Width", 0.7, "Wide", ""),
                }),
                EffectSlot("Maximizer", "maximizer_id", "Fx|Dynamics", params={
                    "Optimize": EffectParam("Optimize", 0.6, "60%", "%"),
                    "Output": EffectParam("Output", 0.95, "-0.3 dB", "dB"),
                }),
            ],
        ),
        "edm_master": EffectChain(
            name="EDM Mastering",
            description="EDM 마스터링 — EQ → 새츄레이션 → 리미터 (라우드)",
            target_track="master",
            target_style="edm",
            inserts=[
                EffectSlot("Frequency", "frequency_id", "Fx|EQ", params={
                    "Band1_Freq": EffectParam("Sub Cut", 0.02, "25 Hz", "Hz"),
                    "Band1_Gain": EffectParam("Sub Cut Gain", 0.0, "-inf (HPF)", "dB"),
                    "Band3_Freq": EffectParam("Low Mid", 0.2, "200 Hz", "Hz"),
                    "Band3_Gain": EffectParam("Low Mid Cut", 0.47, "-1.5 dB", "dB"),
                }),
                EffectSlot("Magneto II", "magneto_id", "Fx|Distortion", params={
                    "Saturation": EffectParam("Saturation", 0.2, "20%", "%"),
                    "Output": EffectParam("Output", 0.48, "-1 dB", "dB"),
                }),
                EffectSlot("Brickwall Limiter", "brickwall_id", "Fx|Dynamics", params={
                    "Threshold": EffectParam("Threshold", 0.85, "-1 dB", "dB"),
                    "Release": EffectParam("Release", 0.1, "3 ms", "ms"),
                    "Ceiling": EffectParam("Ceiling", 0.97, "-0.1 dB", "dB"),
                }),
            ],
        ),
    },
}


# ─── 헬퍼 함수 ───

def get_effect_chain(
    track_type: str,
    style: str = "pop",
) -> Optional[EffectChain]:
    """트랙 타입과 스타일에 맞는 이펙트 체인 반환.

    Args:
        track_type: 트랙 타입 (vocal, drums, bass, guitar, strings, keyboard, master)
        style: 음악 스타일

    Returns:
        매칭되는 EffectChain, 없으면 None
    """
    chains = EFFECT_CHAIN_PRESETS.get(track_type, {})

    # 스타일 매칭 시도
    for name, chain in chains.items():
        if style in name or chain.target_style == style:
            return chain

    # 첫 번째 체인 폴백
    if chains:
        return next(iter(chains.values()))

    return None


def get_all_chains_for_style(style: str) -> dict[str, EffectChain]:
    """스타일에 맞는 모든 트랙의 이펙트 체인 세트 반환.

    Args:
        style: 음악 스타일

    Returns:
        {track_type: EffectChain} 딕셔너리
    """
    result = {}
    for track_type in EFFECT_CHAIN_PRESETS:
        chain = get_effect_chain(track_type, style)
        if chain:
            result[track_type] = chain
    return result


def chain_to_daw_metadata(chain: EffectChain) -> dict:
    """이펙트 체인을 DAW 연동용 메타데이터로 변환.

    Ableton/Cubase MCP 브릿지를 통해 전송할 수 있는 형태.

    Args:
        chain: 이펙트 체인

    Returns:
        JSON 직렬화 가능한 메타데이터 dict
    """
    return {
        "name": chain.name,
        "description": chain.description,
        "target_track": chain.target_track,
        "target_style": chain.target_style,
        "inserts": [
            {
                "plugin": slot.plugin_name,
                "category": slot.category,
                "bypass": slot.bypass,
                "params": {
                    name: {"value": p.value, "display": p.display_value, "unit": p.unit}
                    for name, p in slot.params.items()
                },
            }
            for slot in chain.inserts
        ],
        "sends": chain.sends,
    }
