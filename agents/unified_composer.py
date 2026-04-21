"""Unified composer — rule-based skeleton + MidiGPT model refinement.

2026-04-21 결함리스트 #12 대응: agents/composer.py 의 규칙 기반 생성기
(코드/베이스/드럼 진행)와 midigpt/inference/engine.py 의 MidiGPT 모델
생성기가 분리돼있어 "안정적인 뼈대 + 유연한 모델 표현" 이 같이
못 나옴. 이 모듈은 두 경로를 한 호출에 묶는 thin orchestrator.

Usage:
    from agents.unified_composer import compose_song, ComposeRequest
    req = ComposeRequest(
        key="C", scale="major", tempo=120,
        chord_progression=[("C","maj",0,4),("Am","min",4,4),
                           ("F","maj",8,4),("G","7",12,4)],
        target_tracks=["piano", "bass", "drums"],
        bars=16,
        style="ballad",
    )
    result = compose_song(req)
    # result.stems["piano"] == PrettyMIDI, .review == dict

Flow (simplified):
    1. composer.generate_chords(req.chord_progression)        # 규칙 뼈대
       → PrettyMIDI with chord pads on beat 1/3 of each bar
    2. composer.generate_bass / generate_drums                 # 규칙 뼈대
       → Additional PrettyMIDI stems
    3. If model_refine=True:
         for each stem, run engine.generate_to_midi with the
         chord progression as conditioning context. Model adds
         expressive variation while chord boost (engine.py 2026-04-21
         fix) keeps each bar on-chord.
    4. reviewer.check_chord_adherence + check_track_conflicts
       → Quality gate. If below thresholds, regenerate once.
    5. Return dict of stem → PrettyMIDI + review report.

Status:
    Scaffolding only. Implementation wires up composer.py functions
    (already present) and engine.py generate_to_midi (already present).
    Future work: DAW UI button that calls compose_song directly so
    users get the rule+model hybrid without terminal commands.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ComposeRequest:
    """High-level song request. See module docstring for field semantics."""
    key: str = "C"
    scale: str = "major"
    tempo: float = 120.0
    # Each entry: (root_name, quality, start_beat, length_beats).
    chord_progression: list[tuple[str, str, float, float]] = field(default_factory=list)
    target_tracks: list[str] = field(default_factory=lambda: ["piano", "bass", "drums"])
    bars: int = 16
    style: str = "base"
    # model_refine=False → pure rule-based output (safe baseline).
    model_refine: bool = True
    # review=True 이면 reviewer 돌려서 chord adherence 등 체크.
    review: bool = True


@dataclass
class ComposeResult:
    stems: dict[str, Any] = field(default_factory=dict)       # name → PrettyMIDI
    review: dict[str, Any] = field(default_factory=dict)      # reviewer 결과
    steps: list[str] = field(default_factory=list)            # trace of stages
    warnings: list[str] = field(default_factory=list)


def compose_song(request: ComposeRequest) -> ComposeResult:
    """Rule-based skeleton → optional model refinement → reviewer.

    Implementation note: current scaffold returns empty stems + a step
    trace so callers (tests, DAW button) can be wired first. Real stem
    generation will replace the TODO markers. This keeps the API frozen
    while implementation evolves.
    """
    result = ComposeResult()

    # Step 1 — rule-based skeleton via existing composer.py.
    # TODO wire up: from agents.composer import generate_chords, generate_bass, generate_drums
    #   chords_pm = generate_chords(root=request.key, scale_name=request.scale, settings=...)
    #   result.stems["chords"] = chords_pm
    result.steps.append("skeleton: rule-based (stub)")

    # Step 2 — model refinement for expressive variation, chord-aware.
    # TODO wire up: from midigpt.inference.engine import MidiGPTInference
    #   engine.generate_to_midi(chord_midi_path, refined_path,
    #       chords=request.chord_progression, min_bars=request.bars,
    #       harmonic chord_tone_boost=1.5)
    if request.model_refine:
        result.steps.append("refine: MidiGPT model (stub)")
    else:
        result.steps.append("refine: skipped (rule-only)")

    # Step 3 — reviewer gate.
    # TODO wire up: from agents.reviewer import check_chord_adherence,
    #   check_track_conflicts, ... run over result.stems. If metrics below
    #   threshold, loop back to Step 2 with higher chord_tone_boost or
    #   different temperature.
    if request.review:
        result.review = {
            "chord_adherence":  "n/a (stub)",
            "track_conflicts":  "n/a (stub)",
        }
        result.steps.append("review: reviewer gate (stub)")

    return result
