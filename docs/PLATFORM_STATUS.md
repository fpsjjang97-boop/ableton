# MIDI AI Workstation — Platform Status Report

**Date**: 2026-03-29
**Rule DB**: v2.07 (song_form_added)
**Test Result**: 18/18 PASS | Rule DB Integrity: 15/17 PASS

---

## 1. Verified Features (18/18 PASS)

### Generation
| Feature | Status | Detail |
|---------|--------|--------|
| Melody Generation | **PASS** | Random walk + phrase tension curve |
| Chord Generation (Basic) | **PASS** | 5 progression templates, 3 voicing types |
| Chord Generation (Rule DB) | **PASS** | v2.07 voicing rules, melody protection |
| Bass Generation | **PASS** | walking / pop / octave / sustained |
| Voicing Generation | **PASS** | Playability constraints + voice leading |
| Generate from settings.json | **PASS** | Chord progression → voiced MIDI track |

### Transformation
| Feature | Status | Detail |
|---------|--------|--------|
| Variation (5 types) | **PASS** | rhythm / melody / harmony / dynamics / ornament |
| Humanize | **PASS** | Timing + velocity randomization |

### Analysis
| Feature | Status | Detail |
|---------|--------|--------|
| Track Basic Analysis | **PASS** | scale / dynamics / rhythm / diversity scoring |
| Chord Identification | **PASS** | Pitch-set → chord label (bass-first pipeline) |
| Harmony Analysis (Rule DB) | **PASS** | Per-segment labeling + alternatives + confidence |
| Melody-Protected Voicing | **PASS** | Collision avoidance verified |
| Song Form Analysis | **PASS** | intro/verse/chorus/bridge/outro inference |
| Playability Validation | **PASS** | Hand span / low register interval rules |

### Infrastructure
| Feature | Status | Detail |
|---------|--------|--------|
| FluidSynth Audio | **PASS** | dsound driver, GM soundfont |
| PyQt6 UI | **PASS** | DAW-style workstation (Ableton-like) |
| MAESTRO Embeddings | **PASS** | 93 files, 873,158 notes vectorized |
| Rule DB v2.07 | **PASS** | 15/17 integrity checks |

---

## 2. Rule DB v2.07 Integrity

### Passed (15/17)
- schema_version: 2.07
- All 29 top-level keys present
- 28 hard constraints
- 22 soft constraints
- 40-step analysis pipeline
- 5 chord quality definitions
- 6 voicing templates
- Playability constraints (hand span, low register rules)
- Song form: 11 labels, inference pipeline, multi-cue scoring
- DB storage schema
- 47 developer notes
- 19 candidate interpretation examples
- 2 style inversion profiles

### Failed (2/17) — Action Required
1. **scoring_weights total = 3.5** (should be ~1.0)
   - Weights are absolute values, not normalized proportions
   - Fix: normalize by dividing each weight by 3.5
   - Impact: scoring model outputs are proportionally correct but not 0-100 scaled

2. **generation_pipeline only 2 steps** (should be ≥3)
   - Current: bass_line_generation → voice_leading_generation
   - Missing: inversion_selection, candidate_ranking, melody_constraint_check
   - Impact: generation pipeline relies on external orchestration rather than self-contained steps

---

## 3. Current Data Assets in Git

| Asset | Location | Count | Status |
|-------|----------|-------|--------|
| Rule DB JSON | `260327_최종본_v2.07_song_form_added.json` | 1 file, 212KB | Complete |
| MAESTRO MIDI raw | `Ableton/midi_raw/` | 93 files | Complete |
| MIDI embeddings | `embeddings/individual/` | 93 JSON + matrix.npy | Complete |
| Catalog metadata | `embeddings/catalog.json` | 1 file | Complete |
| Reviews | `reviews/` | 3 review JSON | Partial |
| Reference MIDI | `싱코.mid`, `11.mid` | 2 files | Complete |
| Settings | `settings.json` | 1 file (D maj jazz) | Complete |

---

## 4. What's Missing — Pattern Data Layer

The Rule DB provides **how to analyze/generate** (rules).
What's missing is **what patterns exist** (data).

### Required Pattern Collections

#### 4.1 `analyzed_chords/` — Chord Progression Patterns
- Auto-analyze each MAESTRO MIDI → chord label sequence
- Store: chord labels, confidence, voicing patterns, key estimates
- Target: 93 files initially → expand to 500+
- **Status**: Auto-analysis pipeline built, running on 93 MAESTRO files

#### 4.2 `pattern_library/chord_progressions.json` — Common Progressions
- Extract recurring chord progression patterns from analyzed data
- Cluster by similarity (cosine distance on chord-degree sequences)
- Store with: frequency count, genre tags, example sources
- **Status**: Not yet built. Requires Phase 1 (analyzed_chords) complete.

#### 4.3 `pattern_library/voicing_examples.json` — Style-Specific Voicings
- For each chord quality (maj7, m7, 7, etc.) × style (jazz, pop, classical)
- Store actual MIDI pitch sets from real performances
- Rank by: voice leading smoothness, playability score, frequency
- **Status**: Not yet built. Requires Phase 1 complete.

#### 4.4 `pattern_library/form_templates.json` — Song Structure Templates
- Common song forms with bar counts and energy profiles
- AABA, verse-chorus, verse-chorus-bridge, strophic, through-composed
- With statistical confidence from analyzed corpus
- **Status**: Not yet built. Requires Phase 1 complete.

#### 4.5 `pattern_library/bass_patterns.json` — Bass Line Patterns
- Genre-specific bass motion patterns (root-fifth, walking, pedal, etc.)
- Rhythmic patterns (quarter, eighth, syncopated, etc.)
- **Status**: Not yet built.

#### 4.6 `pattern_library/rhythm_patterns.json` — Rhythmic Pattern Library
- Comp patterns, arpeggio patterns, strum patterns by genre
- Time-signature-specific patterns (4/4, 3/4, 6/8)
- **Status**: Not yet built.

---

## 5. Auto-Accumulation Roadmap

### Phase 1: Corpus Analysis (Current)
```
93 MAESTRO MIDI files
    → HarmonyEngine.analyze_harmony()
    → HarmonyEngine.analyze_song_form()
    → HarmonyEngine.validate_playability()
    → Save to analyzed_chords/*.json
```
**Threshold**: ~100 analyzed files enables basic pattern extraction.

### Phase 2: Pattern Extraction (~100 files)
```
analyzed_chords/*.json
    → Extract chord progression n-grams (2-gram, 4-gram, 8-gram)
    → Cluster similar progressions
    → Compute genre/style statistics
    → Generate pattern_library/chord_progressions.json
```
**Threshold**: ~100 files gives statistically meaningful chord patterns.

### Phase 3: Auto-Classification (~500 files)
```
New MIDI input
    → Analyze with HarmonyEngine
    → Compare embedding with existing corpus
    → Auto-classify genre/style
    → Apply best-matching voicing patterns
    → Auto-save analysis to DB (self-reinforcing loop)
```
**Threshold**: ~500 files enables reliable auto-classification.

### Phase 4: Full Auto-Accumulation (~1000+ files)
```
Any new MIDI input automatically:
    1. Genre classification (from embedding similarity)
    2. Chord labeling (rule DB + pattern matching)
    3. Optimal voicing suggestion (from similar songs' voicings)
    4. Song form inference (statistical + rule-based)
    5. Quality scoring (rule DB constraints)
    6. Auto-save to pattern DB (if confidence > threshold)
```
**Result**: System improves with every file processed.

---

## 6. Immediate Action Items

| Priority | Task | Effort | Dependency |
|----------|------|--------|------------|
| **P0** | Fix scoring_weights normalization in Rule DB | 10 min | None |
| **P0** | Complete MAESTRO 93-file auto-analysis | Running | None |
| **P1** | Expand generation_pipeline in Rule DB (3→5 steps) | 30 min | None |
| **P1** | Build chord progression pattern extractor | 2 hrs | P0 analysis done |
| **P2** | Add voicing example collection from MAESTRO | 3 hrs | P0 analysis done |
| **P2** | Build auto-accumulation pipeline | 4 hrs | P1 patterns done |
| **P3** | Expand corpus: Jazz Real Book MIDI | External | Data sourcing |
| **P3** | Expand corpus: Pop/Rock MIDI | External | Data sourcing |

---

## 7. Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│                 MIDI AI Workstation              │
│                  (PyQt6 GUI)                     │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ AIEngine │──│HarmonyEngine │──│ Rule DB   │ │
│  │          │  │  (v2.07)     │  │  (JSON)   │ │
│  └────┬─────┘  └──────┬───────┘  └───────────┘ │
│       │               │                         │
│       │        ┌──────┴───────┐                 │
│       │        │Pattern Library│ ← auto-grows   │
│       │        │(chord/voicing/│                 │
│       │        │ form/bass/    │                 │
│       │        │ rhythm)       │                 │
│       │        └──────┬───────┘                 │
│       │               │                         │
│  ┌────┴───────────────┴──────┐                  │
│  │      MAESTRO Embeddings   │                  │
│  │   93 files → 873K notes   │                  │
│  │   + analyzed_chords/ DB   │                  │
│  └───────────────────────────┘                  │
│                                                  │
├─────────────────────────────────────────────────┤
│  Agents: composer, orchestrator, reviewer,       │
│          music_transformer, ableton_bridge       │
└─────────────────────────────────────────────────┘
```
