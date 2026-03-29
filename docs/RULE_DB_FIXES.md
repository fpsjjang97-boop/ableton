# Rule DB v2.07 — Known Issues & Fixes

**Date**: 2026-03-29
**Integrity Check**: 15/17 passed

---

## Issue 1: scoring_weights not normalized

**Location**: `scoring_model.components[].weight`

**Problem**: Weight values sum to 3.500 instead of ~1.0.
The scoring model components have absolute weight values that are not normalized.

**Current values**:
```json
[
  {"name": "harmonic_fit",                "weight": 0.142},
  {"name": "structural_label_stability",  "weight": 0.067},
  {"name": "timing_boundary_stability",   "weight": 0.027},
  {"name": "duration_occupancy",          "weight": 0.033},
  {"name": "melody_support",              "weight": 0.105},
  {"name": "bass_motion_coherence",       "weight": 0.046},
  {"name": "playability",                 "weight": ...},
  ...
]
// Total: 3.500
```

**Impact**: Low — our HarmonyEngine normalizes by dividing by total_weight at runtime.
The proportional relationships between components are correct.

**Fix**: Either:
1. (Recommended) Divide each weight by 3.5 so they sum to 1.0
2. (Current workaround) Normalize at runtime (already implemented in harmony_engine.py)

---

## Issue 2: generation_pipeline incomplete

**Location**: `voicing_generation_rules.generation_pipeline`

**Problem**: Only 2 steps defined. Should be at least 5 for a complete generation pipeline.

**Current**:
```json
"generation_pipeline": [
  { "step": "bass_line_generation", ... },
  { "step": "voice_leading_generation", ... }
]
```

**Missing steps**:
1. `inversion_selection` — Choose inversion based on progression context
2. `candidate_ranking` — Score multiple voicing candidates
3. `melody_constraint_check` — Verify no melody collision
4. `playability_gate` — Final playability validation
5. `guide_tone_continuity` — Ensure guide tones connect smoothly

**Impact**: Medium — generation works but relies on external orchestration
(harmony_engine.py handles these steps programmatically).

**Recommended addition for v2.08**:
```json
"generation_pipeline": [
  {"step": "chord_label_parsing", "description": "Parse chord label to root + quality + tensions"},
  {"step": "bass_line_generation", "description": "Design bass contour before inner voices"},
  {"step": "inversion_selection", "description": "Choose inversion from progression context and style profile"},
  {"step": "candidate_voicing_generation", "description": "Generate 3-5 voicing candidates per chord"},
  {"step": "melody_constraint_check", "description": "Filter candidates that collide with melody"},
  {"step": "voice_leading_optimization", "description": "Minimize movement between consecutive voicings"},
  {"step": "playability_gate", "description": "Reject candidates exceeding hand span or low register rules"},
  {"step": "final_selection", "description": "Select best candidate by weighted scoring model"}
]
```

---

## Issue 3 (Minor): chord_quality_rules coverage

**Current**: 5 chord qualities defined (maj7, m7, 7, m7b5, dim7)

**Missing common qualities**:
- `sus4` / `7sus4`
- `aug` / `aug7`
- `6` / `m6`
- `add9` / `madd9`
- `9` / `m9` / `maj9`
- `11` / `13`

**Impact**: Low — HarmonyEngine has its own _CHORD_TEMPLATES covering 23 qualities.
But the Rule DB's priority_tones and function_group metadata is missing for these.

**Recommendation**: Add at least sus4, aug, 6, 9 to chord_quality_rules in v2.08.

---

## Issue 4 (Minor): style_inversion_profiles limited

**Current**: 2 profiles only

**Recommended additions for v2.08**:
- `bossa_nova`: chromatic bass approach, sparse voicing
- `classical`: root position preference, complete voicing
- `gospel`: close-position, dense voicing, chromatic passing
- `r_and_b`: extended voicings (9th, 11th, 13th)
- `edm`: power chords, octave bass, minimal inner voices

---

## Summary of Recommended v2.08 Changes

| Item | Priority | Effort |
|------|----------|--------|
| Normalize scoring weights | P0 | 10 min |
| Expand generation_pipeline to 8 steps | P1 | 30 min |
| Add 6+ chord_quality_rules | P1 | 1 hr |
| Add 5+ style_inversion_profiles | P2 | 1 hr |
| Add enharmonic test cases | P3 | 30 min |
