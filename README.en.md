# MidiGPT — MIDI AI Workstation

> A self-trained MIDI-only LLM (MidiGPT 50M) + Cubase 15-grade expressivity + JUCE-integrated workstation.

[한국어 README](README.md)

![Python](https://img.shields.io/badge/Python-3.13-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-red)
![Model](https://img.shields.io/badge/Model-MidiGPT_50M-orange)
![Vocab](https://img.shields.io/badge/Vocab-448_tokens-green)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## TL;DR

**Feed in MIDI → an in-house LLM that understands music theory generates a variation → drop it straight into your DAW.**

- 50M-parameter in-house LLM (RoPE + RMSNorm + SwiGLU + KV cache)
- Cubase 15-grade expressivity (32 articulations, CC11/CC1/CC64, pitch bend, MPE-ready)
- Harmonic constraint masking (off-scale notes are blocked at sample time)
- LoRA hot-swap (per-style adapters)
- Multi-agent Python backend + JUCE C++ frontend

---

## Standard Specifications

The full design lives under [docs/spec/](docs/spec/) (Korean, BalloonFlow standard format).

| Area | Documents |
|------|-----------|
| 🧠 LLM | Architecture · Tokenizer · Training · Inference |
| 🎵 Music | Harmony Engine · Groove Engine · AI Engine |
| 📊 Data | Data Pipeline |
| 🎛️ Integration | App / Integration |
| 🚀 Roadmap | Improvement Roadmap |
| 📑 INDEX | [Standard Spec Index](docs/spec/MidiGPT_표준명세_INDEX.md) |

---

## Model Spec

| Item | Value |
|------|-------|
| Parameters | ~50M |
| Layers | 12 (decoder-only) |
| Heads | 12 (head_dim 48) |
| Embedding | 576 |
| FFN | 2304 (SwiGLU) |
| Context | 2048 tokens |
| Vocabulary | 448 tokens (hierarchical REMI) |
| Position encoding | RoPE (theta=10000) |
| Norm | RMSNorm |
| LoRA rank | 32 (q/k/v/o + gate/up/down) |

---

## Features

### 🧠 LLM (MidiGPT)
- ✅ 50M decoder-only Transformer
- ✅ KV-cache accelerated inference *(Phase 1)*
- ✅ Repetition penalty *(Phase 1)*
- ✅ No-repeat n-gram block *(Phase 1)*
- ✅ Multi-sample (`num_return_sequences`) *(Phase 1)*
- ✅ Harmonic constraint masking (out-of-scale pitches blocked)
- ✅ LoRA hot-swap
- ✅ EMA checkpoint *(Phase 1)*
- ✅ `min_new_tokens` — prevents premature EOS termination *(2026-04-08)*
- ✅ DPO quantile fallback — auto percentile split when scores cluster *(2026-04-08)*

### 🎵 Music Capabilities
- ✅ Chord analysis (24 qualities, slash chords, harmonic function labels)
- ✅ Song-form detection (intro/verse/chorus/bridge/outro × 10 sections)
- ✅ Groove extraction + 7 swing presets
- ✅ 14 track types (melody/bass/drums/strings/brass/...)
- ✅ 32 articulations (Cubase 15-derived)
- ✅ 13 dynamics (ppp~fff + sfz/sfp/...)
- ✅ CC11 Expression / CC1 Modulation / CC64 Sustain / PitchBend

### 🎛️ App / Integration
- ✅ Python core engines (MIDI / harmony / groove / AI / FX / synth)
- ✅ Multi-agent system (Composer, Manager, Reviewer, Orchestrator)
- ✅ Audio → MIDI (Demucs + Basic Pitch)
- ✅ **Sheet → MIDI (image → MIDI via SMT++ OMR)** — `agents/sheet2midi.py`
- ✅ JUCE C++ frontend
- 🔶 Partial: VST3/CLAP plug-in hosting (planned)

---

## Quick Start

### Musicians
```bash
# Drop your MIDI files in and push.
git add "TEST MIDI/"
git commit -m "data: add MIDI training samples"
git push
```

### Developers — Training
```bash
# All-in-one pipeline (augment → tokenize → train)
python -m midigpt.pipeline --midi_dir "./TEST MIDI" --epochs 10

# With EMA enabled (Phase 1, recommended)
python -m midigpt.training.train_pretrain \
    --data_dir ./midigpt_data \
    --epochs 10 \
    --ema --ema_decay 0.999
```

### Developers — Inference
```python
from midigpt.inference.engine import MidiGPTInference, InferenceConfig
from midigpt.tokenizer.encoder import SongMeta

inf = MidiGPTInference(InferenceConfig(
    model_path="./checkpoints/midigpt_ema.pt",   # EMA recommended
    lora_paths={"jazz": "./loras/jazz.pt"},
))

# Phase 1 + bug-fix additions
variations = inf.generate_variation(
    midi_path="input.mid",
    meta=SongMeta(key="C", style="jazz", section="chorus", tempo=120),
    max_tokens=1024,                    # default 1024 (was 512)
    min_new_tokens=256,                 # prevents premature EOS
    num_return_sequences=3,             # 3 candidate variations
    repetition_penalty=1.1,             # avoid pathological loops
    no_repeat_ngram_size=4,             # block 4-gram repetition
    use_kv_cache=True,                  # O(N) decoding
)
```

---

## Project Layout

```
repo/
├── midigpt/                       # in-house LLM
│   ├── model/
│   │   ├── config.py              # 50M model config
│   │   └── transformer.py         # RoPE + RMSNorm + SwiGLU + KV cache
│   ├── tokenizer/
│   │   ├── vocab.py               # 448-token vocabulary (Cubase 15-extended)
│   │   ├── encoder.py             # MIDI → tokens
│   │   └── decoder.py             # tokens → MIDI
│   ├── training/
│   │   ├── train_pretrain.py      # pre-training (+ EMA, Phase 1)
│   │   ├── train_sft_lora.py      # LoRA SFT
│   │   ├── train_dpo.py           # DPO preference training
│   │   ├── lora.py                # LoRA implementation
│   │   └── ema.py                 # ✅ Phase 1: EMA
│   ├── inference/
│   │   └── engine.py              # inference engine (KV cache, harmonic mask, Phase 1)
│   ├── data/
│   │   └── dataset.py             # MidiDataset, MidiCollator
│   ├── augment_dataset.py         # augmentation (transpose + track dropout)
│   ├── tokenize_dataset.py        # tokenization
│   ├── pipeline.py                # all-in-one
│   └── DATA_GUIDE.md              # data collection guide
├── app/
│   ├── core/                      # MIDI / harmony / groove / AI engines etc.
│   └── ...
├── agents/
│   ├── composer.py
│   ├── manager.py
│   ├── reviewer.py
│   ├── orchestrator.py
│   ├── audio2midi.py              # Demucs + Basic Pitch
│   └── ableton_bridge.py
├── juce_app/                      # JUCE C++ frontend
├── docs/spec/                     # ✅ standard specs (BalloonFlow format)
├── tools/                         # utility scripts
├── TEST MIDI/                     # collaborator upload area
├── midi_data/                     # training MIDI store
├── checkpoints/                   # trained checkpoints
└── README.md
```

---

## Dataset Status

| Item | Count |
|------|------:|
| MAESTRO 2018 | 93 (classical piano) |
| Collaborator uploads | 11+ (J-pop, City Pop, Latin, Hip-hop, Metal, House…) |
| **Originals** | **104+** |
| After ×15 augmentation | ~1,560 |
| **Goal** | **2,000+ originals** |

---

## Roles

### 🎹 Musician (collaborator)
- Compose in your DAW → export Type 1 MIDI → `git push`.
- Hit a wide stylistic range (pop, jazz, classical, Latin, metal…).
- Drums must respect General MIDI mapping.
- CC data (sustain / expression) is encouraged.
- See [DATA_GUIDE.md](midigpt/DATA_GUIDE.md).

### 💻 Developer
- Owns MidiGPT architecture, training, and inference pipeline.
- Augmentation → tokenization → training → model release.
- App integration and deployment.

### Collaboration loop
```
Musician: write MIDI → git push
                       ↓
Developer: augment → tokenize → train → release
                       ↓
Musician: listen to variation → like / dislike
                       ↓
Developer: feed into DPO → improved model
                       ↓
                  iterate (level up)
```

---

## Status

### Phase 1 — Inference / training stabilization ✅
- ✅ 50M Transformer with KV cache
- ✅ 448-token vocabulary (Cubase 15-extended)
- ✅ KV-cache accelerated decoding
- ✅ Repetition penalty / no-repeat n-gram
- ✅ Multi-sample (`num_return_sequences`)
- ✅ EMA checkpoint
- ✅ Harmonic constraint masking
- ✅ LoRA hot-swap
- ✅ `min_new_tokens` EOS early-termination prevention (2026-04-08)
- ✅ DPO quantile fallback (2026-04-08)
- ✅ Token path auto-detection (2026-04-08)
- ✅ Windows UTF-8 encoding enforcement (2026-04-08)

### Phase 2 — Data scaling ← **current**
- 104 → 2,000+ goal
- Automated quality filter (planned)
- Lakh MIDI integration under review (filtering required)

### Phase 3 — Fine-tune for new capabilities
- CFG (classifier-free guidance) — requires conditional dropout during training
- Multi-task pretraining (chord / key / section heads)
- GRPO + voice-leading reward model

### Phase 4 — Major retrain (quarterly cadence)
- Vocab expansion (chord inversion, MPE, tempo curve, micro-tonal, …)
- GQA + Hierarchical / Mamba hybrid
- CLAP-style text conditioning

Full roadmap → [docs/spec/MidiGPT_개선로드맵_명세.md](docs/spec/MidiGPT_개선로드맵_명세.md)

---

## License

MIT License
