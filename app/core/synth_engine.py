"""
Synthesizer Engine — real-time DSP synthesis with multiple engines.

Provides:
  1. Subtractive Synth  (Osc → Filter → Amp Env)
  2. FM Synth           (4-operator FM)
  3. Wavetable Synth    (morphable wavetables)
  4. Granular Engine     (grain-cloud synthesis)
  5. Sampler            (multi-sample playback)
  6. Drum Machine       (16-pad sample trigger)
  7. Modulation Matrix  (source → destination routing)
  8. Effects            (Filter, LFO, ADSR)

All engines produce float32 numpy arrays at 44100 Hz.
Integration: AudioEngine.get_synth_samples() mixes synth output with FluidSynth.
"""
from __future__ import annotations

import math
import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

SAMPLE_RATE = 44100
BLOCK_SIZE = 512
MAX_POLYPHONY = 16
TWO_PI = 2.0 * np.pi

# Precomputed single-cycle waveforms (2048 samples)
_TABLE_SIZE = 2048
_t = np.linspace(0, 1, _TABLE_SIZE, endpoint=False, dtype=np.float32)

WAVE_SINE = np.sin(TWO_PI * _t).astype(np.float32)
WAVE_SAW = (2.0 * _t - 1.0).astype(np.float32)
WAVE_SQUARE = np.where(_t < 0.5, 1.0, -1.0).astype(np.float32)
WAVE_TRIANGLE = (2.0 * np.abs(2.0 * _t - 1.0) - 1.0).astype(np.float32)

# Band-limited saw (additive, 32 harmonics) for anti-aliasing
_bl_saw = np.zeros(_TABLE_SIZE, dtype=np.float32)
for _k in range(1, 33):
    _bl_saw += ((-1.0) ** (_k + 1)) * (2.0 / (np.pi * _k)) * np.sin(TWO_PI * _k * _t)
WAVE_SAW_BL = _bl_saw.astype(np.float32)

# Band-limited square (odd harmonics)
_bl_sq = np.zeros(_TABLE_SIZE, dtype=np.float32)
for _k in range(1, 33, 2):
    _bl_sq += (4.0 / (np.pi * _k)) * np.sin(TWO_PI * _k * _t)
WAVE_SQUARE_BL = _bl_sq.astype(np.float32)

WAVEFORMS = {
    "sine": WAVE_SINE,
    "saw": WAVE_SAW_BL,
    "square": WAVE_SQUARE_BL,
    "triangle": WAVE_TRIANGLE,
    "saw_naive": WAVE_SAW,
    "square_naive": WAVE_SQUARE,
}

del _t, _bl_saw, _bl_sq, _k


# ── ADSR Envelope ──────────────────────────────────────────────────────────

@dataclass
class ADSRParams:
    attack: float = 0.01      # seconds
    decay: float = 0.1        # seconds
    sustain: float = 0.7      # level 0-1
    release: float = 0.3      # seconds

    def copy(self) -> ADSRParams:
        return ADSRParams(self.attack, self.decay, self.sustain, self.release)


class ADSREnvelope:
    """Per-voice ADSR envelope generator."""

    __slots__ = ("params", "_stage", "_level", "_rate", "_released")

    IDLE, ATTACK, DECAY, SUSTAIN, RELEASE = range(5)

    def __init__(self, params: ADSRParams):
        self.params = params
        self._stage = self.IDLE
        self._level = 0.0
        self._rate = 0.0
        self._released = False

    def trigger(self):
        self._stage = self.ATTACK
        self._rate = 1.0 / max(self.params.attack * SAMPLE_RATE, 1)
        self._released = False

    def release(self):
        if self._stage != self.IDLE:
            self._stage = self.RELEASE
            self._rate = self._level / max(self.params.release * SAMPLE_RATE, 1)
            self._released = True

    @property
    def is_active(self) -> bool:
        return self._stage != self.IDLE

    def process(self, n_samples: int) -> np.ndarray:
        out = np.empty(n_samples, dtype=np.float32)
        for i in range(n_samples):
            if self._stage == self.ATTACK:
                self._level += self._rate
                if self._level >= 1.0:
                    self._level = 1.0
                    self._stage = self.DECAY
                    self._rate = (1.0 - self.params.sustain) / max(self.params.decay * SAMPLE_RATE, 1)
            elif self._stage == self.DECAY:
                self._level -= self._rate
                if self._level <= self.params.sustain:
                    self._level = self.params.sustain
                    self._stage = self.SUSTAIN
            elif self._stage == self.SUSTAIN:
                self._level = self.params.sustain
            elif self._stage == self.RELEASE:
                self._level -= self._rate
                if self._level <= 0.0:
                    self._level = 0.0
                    self._stage = self.IDLE
            out[i] = self._level
        return out


# ── LFO ────────────────────────────────────────────────────────────────────

@dataclass
class LFOParams:
    rate: float = 2.0          # Hz
    depth: float = 0.5         # 0-1
    waveform: str = "sine"     # sine, saw, square, triangle
    sync: bool = False
    phase: float = 0.0         # 0-1

    def copy(self) -> LFOParams:
        return LFOParams(self.rate, self.depth, self.waveform, self.sync, self.phase)


class LFO:
    __slots__ = ("params", "_phase")

    def __init__(self, params: LFOParams):
        self.params = params
        self._phase = params.phase

    def process(self, n_samples: int) -> np.ndarray:
        table = WAVEFORMS.get(self.params.waveform, WAVE_SINE)
        inc = self.params.rate * _TABLE_SIZE / SAMPLE_RATE
        indices = np.arange(n_samples, dtype=np.float64) * inc + self._phase * _TABLE_SIZE
        indices = indices % _TABLE_SIZE
        self._phase = (self._phase + n_samples * self.params.rate / SAMPLE_RATE) % 1.0
        # Linear interpolation
        idx_floor = indices.astype(np.int32)
        frac = (indices - idx_floor).astype(np.float32)
        idx_next = (idx_floor + 1) % _TABLE_SIZE
        out = table[idx_floor] * (1 - frac) + table[idx_next] * frac
        return out * self.params.depth


# ── Biquad Filter ──────────────────────────────────────────────────────────

class BiquadFilter:
    """Biquad filter: lowpass, highpass, bandpass, notch."""

    LOWPASS, HIGHPASS, BANDPASS, NOTCH = range(4)
    _TYPE_NAMES = {"lowpass": 0, "highpass": 1, "bandpass": 2, "notch": 3,
                   "lp": 0, "hp": 1, "bp": 2}

    def __init__(self, filter_type: str = "lowpass", cutoff: float = 8000.0,
                 resonance: float = 0.707):
        self._type = self._TYPE_NAMES.get(filter_type, 0)
        self._cutoff = cutoff
        self._resonance = resonance
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0
        self._b0 = self._b1 = self._b2 = 0.0
        self._a1 = self._a2 = 0.0
        self._compute_coeffs()

    @property
    def cutoff(self) -> float:
        return self._cutoff

    @cutoff.setter
    def cutoff(self, value: float):
        self._cutoff = max(20.0, min(value, SAMPLE_RATE * 0.49))
        self._compute_coeffs()

    @property
    def resonance(self) -> float:
        return self._resonance

    @resonance.setter
    def resonance(self, value: float):
        self._resonance = max(0.1, min(value, 30.0))
        self._compute_coeffs()

    def _compute_coeffs(self):
        w0 = TWO_PI * self._cutoff / SAMPLE_RATE
        cos_w0 = math.cos(w0)
        sin_w0 = math.sin(w0)
        alpha = sin_w0 / (2.0 * self._resonance)

        if self._type == self.LOWPASS:
            self._b0 = (1.0 - cos_w0) / 2.0
            self._b1 = 1.0 - cos_w0
            self._b2 = (1.0 - cos_w0) / 2.0
        elif self._type == self.HIGHPASS:
            self._b0 = (1.0 + cos_w0) / 2.0
            self._b1 = -(1.0 + cos_w0)
            self._b2 = (1.0 + cos_w0) / 2.0
        elif self._type == self.BANDPASS:
            self._b0 = alpha
            self._b1 = 0.0
            self._b2 = -alpha
        elif self._type == self.NOTCH:
            self._b0 = 1.0
            self._b1 = -2.0 * cos_w0
            self._b2 = 1.0

        a0 = 1.0 + alpha
        self._a1 = -2.0 * cos_w0 / a0
        self._a2 = (1.0 - alpha) / a0
        self._b0 /= a0
        self._b1 /= a0
        self._b2 /= a0

    def process(self, data: np.ndarray) -> np.ndarray:
        out = np.empty_like(data)
        x1, x2, y1, y2 = self._x1, self._x2, self._y1, self._y2
        b0, b1, b2, a1, a2 = self._b0, self._b1, self._b2, self._a1, self._a2
        for i in range(len(data)):
            x = float(data[i])
            y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, x
            y2, y1 = y1, y
            out[i] = y
        self._x1, self._x2, self._y1, self._y2 = x1, x2, y1, y2
        return out

    def reset(self):
        self._x1 = self._x2 = self._y1 = self._y2 = 0.0


# ── Oscillator ─────────────────────────────────────────────────────────────

class Oscillator:
    """Wavetable oscillator with optional unison, detune, PWM."""

    __slots__ = ("_phase", "_table", "_detune", "_level", "_pw")

    def __init__(self, waveform: str = "saw", detune: float = 0.0,
                 level: float = 1.0, pulse_width: float = 0.5):
        self._phase = 0.0
        self._table = WAVEFORMS.get(waveform, WAVE_SAW_BL)
        self._detune = detune
        self._level = level
        self._pw = pulse_width

    def set_waveform(self, name: str):
        self._table = WAVEFORMS.get(name, WAVE_SAW_BL)

    def process(self, freq: float, n_samples: int,
                fm_mod: Optional[np.ndarray] = None) -> np.ndarray:
        """Generate samples at given frequency, optionally FM modulated."""
        f = freq * (2.0 ** (self._detune / 1200.0))  # detune in cents
        inc = f * _TABLE_SIZE / SAMPLE_RATE
        phases = np.arange(n_samples, dtype=np.float64) * inc + self._phase
        if fm_mod is not None:
            phases = phases + fm_mod.astype(np.float64) * _TABLE_SIZE
        phases = phases % _TABLE_SIZE
        self._phase = phases[-1] + inc if n_samples > 0 else self._phase
        self._phase %= _TABLE_SIZE
        # Linear interpolation
        idx = phases.astype(np.int32)
        frac = (phases - idx).astype(np.float32)
        idx_next = (idx + 1) % _TABLE_SIZE
        out = self._table[idx] * (1 - frac) + self._table[idx_next] * frac
        return out * self._level


# ── Synth Voice (Subtractive) ──────────────────────────────────────────────

class SynthVoice:
    """Single voice: 2 oscillators → mixer → filter → amp envelope."""

    def __init__(self, patch: SubtractivePatch):
        self.patch = patch
        self.note = -1
        self.velocity = 0
        self.active = False

        self.osc1 = Oscillator(patch.osc1_wave, patch.osc1_detune, patch.osc1_level)
        self.osc2 = Oscillator(patch.osc2_wave, patch.osc2_detune, patch.osc2_level)
        self.filt = BiquadFilter(patch.filter_type, patch.filter_cutoff, patch.filter_reso)
        self.amp_env = ADSREnvelope(patch.amp_env)
        self.filt_env = ADSREnvelope(patch.filt_env)
        self.lfo = LFO(patch.lfo)

    def trigger(self, note: int, velocity: int):
        self.note = note
        self.velocity = velocity
        self.active = True
        self.amp_env.trigger()
        self.filt_env.trigger()
        self.filt.reset()
        self.osc1._phase = 0.0
        self.osc2._phase = 0.0

    def release(self):
        self.amp_env.release()
        self.filt_env.release()

    def process(self, n_samples: int) -> np.ndarray:
        if not self.active:
            return np.zeros(n_samples, dtype=np.float32)

        freq = 440.0 * (2.0 ** ((self.note - 69) / 12.0))
        vel_gain = self.velocity / 127.0

        # Oscillators
        out1 = self.osc1.process(freq, n_samples)
        freq2 = freq * (2.0 ** (self.patch.osc2_semi / 12.0))
        out2 = self.osc2.process(freq2, n_samples)
        mix = out1 * self.patch.osc_mix + out2 * (1.0 - self.patch.osc_mix)

        # Noise
        if self.patch.noise_level > 0:
            noise = np.random.default_rng().standard_normal(n_samples).astype(np.float32)
            mix = mix * (1 - self.patch.noise_level) + noise * self.patch.noise_level

        # Filter envelope modulation
        filt_env = self.filt_env.process(n_samples)
        base_cutoff = self.patch.filter_cutoff
        mod_range = self.patch.filt_env_depth
        # LFO to filter
        lfo_out = self.lfo.process(n_samples)
        cutoff_mod = base_cutoff + filt_env * mod_range + lfo_out * self.patch.lfo_to_filter
        # Clamp and apply per-sample (simplified: use average for block)
        avg_cutoff = float(np.clip(np.mean(cutoff_mod), 20, SAMPLE_RATE * 0.49))
        self.filt.cutoff = avg_cutoff
        filtered = self.filt.process(mix)

        # Amp envelope
        amp = self.amp_env.process(n_samples)
        result = filtered * amp * vel_gain * self.patch.master_level

        if not self.amp_env.is_active:
            self.active = False

        return result


# ── Subtractive Synth Patch ────────────────────────────────────────────────

@dataclass
class SubtractivePatch:
    name: str = "Init"
    # Oscillator 1
    osc1_wave: str = "saw"
    osc1_detune: float = 0.0     # cents
    osc1_level: float = 1.0
    # Oscillator 2
    osc2_wave: str = "saw"
    osc2_detune: float = 7.0     # cents (slight detuning for richness)
    osc2_level: float = 0.8
    osc2_semi: int = 0           # semitone offset
    # Mix
    osc_mix: float = 0.6         # 1=osc1 only, 0=osc2 only
    noise_level: float = 0.0     # 0-1
    # Filter
    filter_type: str = "lowpass"
    filter_cutoff: float = 4000.0
    filter_reso: float = 1.0
    # Envelopes
    amp_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.005, 0.2, 0.7, 0.4))
    filt_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.01, 0.3, 0.3, 0.5))
    filt_env_depth: float = 3000.0  # Hz range of filter envelope
    # LFO
    lfo: LFOParams = field(default_factory=LFOParams)
    lfo_to_filter: float = 0.0    # LFO → filter cutoff depth (Hz)
    lfo_to_pitch: float = 0.0     # LFO → pitch depth (cents)
    # Master
    master_level: float = 0.7

    def copy(self) -> SubtractivePatch:
        p = SubtractivePatch(
            name=self.name,
            osc1_wave=self.osc1_wave, osc1_detune=self.osc1_detune, osc1_level=self.osc1_level,
            osc2_wave=self.osc2_wave, osc2_detune=self.osc2_detune, osc2_level=self.osc2_level,
            osc2_semi=self.osc2_semi,
            osc_mix=self.osc_mix, noise_level=self.noise_level,
            filter_type=self.filter_type, filter_cutoff=self.filter_cutoff,
            filter_reso=self.filter_reso,
            amp_env=self.amp_env.copy(), filt_env=self.filt_env.copy(),
            filt_env_depth=self.filt_env_depth,
            lfo=self.lfo.copy(),
            lfo_to_filter=self.lfo_to_filter, lfo_to_pitch=self.lfo_to_pitch,
            master_level=self.master_level,
        )
        return p


# ── FM Synth ───────────────────────────────────────────────────────────────

@dataclass
class FMOperator:
    """Single FM operator: sine oscillator with envelope."""
    ratio: float = 1.0         # freq multiplier relative to note freq
    level: float = 1.0         # output amplitude
    detune: float = 0.0        # cents
    env: ADSRParams = field(default_factory=lambda: ADSRParams(0.01, 0.3, 0.6, 0.4))

    def copy(self) -> FMOperator:
        return FMOperator(self.ratio, self.level, self.detune, self.env.copy())


@dataclass
class FMPatch:
    """4-operator FM synth patch."""
    name: str = "FM Init"
    ops: list = field(default_factory=lambda: [
        FMOperator(1.0, 1.0),    # Op 1 (carrier)
        FMOperator(2.0, 0.5),    # Op 2 (modulator → Op1)
        FMOperator(3.0, 0.3),    # Op 3 (modulator → Op2)
        FMOperator(4.0, 0.1),    # Op 4 (modulator → Op3)
    ])
    # Algorithm: chain (4→3→2→1→out), parallel, etc.
    algorithm: int = 0  # 0=chain, 1=parallel, 2=stack
    feedback: float = 0.0
    master_level: float = 0.7
    amp_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.005, 0.2, 0.7, 0.3))


class FMVoice:
    """Single FM voice with 4 operators."""

    def __init__(self, patch: FMPatch):
        self.patch = patch
        self.note = -1
        self.velocity = 0
        self.active = False
        self._phases = [0.0, 0.0, 0.0, 0.0]
        self._op_envs = [ADSREnvelope(op.env) for op in patch.ops]
        self._amp_env = ADSREnvelope(patch.amp_env)
        self._fb_sample = 0.0

    def trigger(self, note: int, velocity: int):
        self.note = note
        self.velocity = velocity
        self.active = True
        self._phases = [0.0, 0.0, 0.0, 0.0]
        self._fb_sample = 0.0
        for env in self._op_envs:
            env.trigger()
        self._amp_env.trigger()

    def release(self):
        for env in self._op_envs:
            env.release()
        self._amp_env.release()

    def process(self, n_samples: int) -> np.ndarray:
        if not self.active:
            return np.zeros(n_samples, dtype=np.float32)

        freq = 440.0 * (2.0 ** ((self.note - 69) / 12.0))
        vel_gain = self.velocity / 127.0
        ops = self.patch.ops
        out = np.zeros(n_samples, dtype=np.float32)

        # Process operator envelopes
        op_envs = [env.process(n_samples) for env in self._op_envs]
        amp_env = self._amp_env.process(n_samples)

        # Per-sample FM synthesis
        for i in range(n_samples):
            op_out = [0.0] * 4
            for j in range(3, -1, -1):  # Process from op4 to op1
                op = ops[j]
                f = freq * op.ratio * (2.0 ** (op.detune / 1200.0))
                phase_inc = f / SAMPLE_RATE

                # Get modulation input based on algorithm
                mod_input = 0.0
                if self.patch.algorithm == 0:  # Chain: 4→3→2→1
                    if j < 3:
                        mod_input = op_out[j + 1] * ops[j + 1].level
                    if j == 3 and self.patch.feedback > 0:
                        mod_input = self._fb_sample * self.patch.feedback
                elif self.patch.algorithm == 1:  # Parallel: all carriers
                    if j == 3 and self.patch.feedback > 0:
                        mod_input = self._fb_sample * self.patch.feedback
                elif self.patch.algorithm == 2:  # Stack: (3→1), (4→2), 1+2 out
                    if j == 0 and len(op_out) > 2:
                        mod_input = op_out[2] * ops[2].level
                    elif j == 1 and len(op_out) > 3:
                        mod_input = op_out[3] * ops[3].level

                self._phases[j] += phase_inc + mod_input
                self._phases[j] %= 1.0
                op_out[j] = math.sin(TWO_PI * self._phases[j]) * op_envs[j][i]

            if self.patch.algorithm == 0:
                sample = op_out[0] * ops[0].level
            elif self.patch.algorithm == 1:
                sample = sum(op_out[k] * ops[k].level for k in range(4)) / 4.0
            else:
                sample = (op_out[0] * ops[0].level + op_out[1] * ops[1].level) / 2.0

            self._fb_sample = sample
            out[i] = sample * amp_env[i] * vel_gain

        if not self._amp_env.is_active:
            self.active = False

        return out * self.patch.master_level


# ── Wavetable Synth ────────────────────────────────────────────────────────

@dataclass
class WavetablePatch:
    name: str = "WT Init"
    # Wavetable: list of single-cycle waveforms to morph between
    tables: list = field(default_factory=lambda: ["sine", "triangle", "saw", "square"])
    morph_position: float = 0.0   # 0-1 position across tables
    # Filter
    filter_type: str = "lowpass"
    filter_cutoff: float = 6000.0
    filter_reso: float = 1.0
    # Envelopes
    amp_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.01, 0.3, 0.6, 0.5))
    filt_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.01, 0.4, 0.2, 0.4))
    filt_env_depth: float = 4000.0
    # Morph LFO
    morph_lfo_rate: float = 0.2  # Hz
    morph_lfo_depth: float = 0.0  # 0-1
    master_level: float = 0.7


class WavetableVoice:
    def __init__(self, patch: WavetablePatch):
        self.patch = patch
        self.note = -1
        self.velocity = 0
        self.active = False
        self._phase = 0.0
        self._morph_phase = 0.0
        self._amp_env = ADSREnvelope(patch.amp_env)
        self._filt_env = ADSREnvelope(patch.filt_env)
        self._filter = BiquadFilter(patch.filter_type, patch.filter_cutoff, patch.filter_reso)
        # Resolve table arrays
        self._tables = [WAVEFORMS.get(t, WAVE_SINE) for t in patch.tables]

    def trigger(self, note: int, velocity: int):
        self.note = note
        self.velocity = velocity
        self.active = True
        self._phase = 0.0
        self._amp_env.trigger()
        self._filt_env.trigger()
        self._filter.reset()

    def release(self):
        self._amp_env.release()
        self._filt_env.release()

    def process(self, n_samples: int) -> np.ndarray:
        if not self.active:
            return np.zeros(n_samples, dtype=np.float32)

        freq = 440.0 * (2.0 ** ((self.note - 69) / 12.0))
        vel_gain = self.velocity / 127.0
        n_tables = len(self._tables)
        if n_tables == 0:
            return np.zeros(n_samples, dtype=np.float32)

        inc = freq * _TABLE_SIZE / SAMPLE_RATE
        out = np.zeros(n_samples, dtype=np.float32)

        for i in range(n_samples):
            # Morph position with LFO
            morph = self.patch.morph_position
            if self.patch.morph_lfo_depth > 0:
                morph += math.sin(TWO_PI * self._morph_phase) * self.patch.morph_lfo_depth
                self._morph_phase += self.patch.morph_lfo_rate / SAMPLE_RATE
            morph = max(0.0, min(morph, 1.0))

            # Interpolate between two adjacent tables
            table_pos = morph * (n_tables - 1)
            t_idx = int(table_pos)
            t_frac = table_pos - t_idx
            t_idx = min(t_idx, n_tables - 2) if n_tables > 1 else 0

            # Sample from wavetable with linear interpolation
            idx = int(self._phase) % _TABLE_SIZE
            idx_next = (idx + 1) % _TABLE_SIZE
            phase_frac = self._phase - int(self._phase)

            if n_tables > 1:
                s1 = self._tables[t_idx][idx] * (1 - phase_frac) + self._tables[t_idx][idx_next] * phase_frac
                s2 = self._tables[t_idx + 1][idx] * (1 - phase_frac) + self._tables[t_idx + 1][idx_next] * phase_frac
                out[i] = s1 * (1 - t_frac) + s2 * t_frac
            else:
                out[i] = self._tables[0][idx] * (1 - phase_frac) + self._tables[0][idx_next] * phase_frac

            self._phase = (self._phase + inc) % _TABLE_SIZE

        # Filter
        filt_env = self._filt_env.process(n_samples)
        avg_cutoff = self.patch.filter_cutoff + float(np.mean(filt_env)) * self.patch.filt_env_depth
        self._filter.cutoff = max(20, min(avg_cutoff, SAMPLE_RATE * 0.49))
        out = self._filter.process(out)

        # Amp
        amp = self._amp_env.process(n_samples)
        out = out * amp * vel_gain * self.patch.master_level

        if not self._amp_env.is_active:
            self.active = False

        return out


# ── Granular Engine ────────────────────────────────────────────────────────

@dataclass
class GranularPatch:
    name: str = "Granular Init"
    grain_size_ms: float = 60.0      # grain duration in ms
    grain_density: float = 8.0       # grains per second
    position: float = 0.5           # position in source (0-1)
    position_spread: float = 0.1    # random offset around position
    pitch_spread: float = 0.0       # random pitch variation (semitones)
    stereo_spread: float = 0.5      # pan randomization
    amp_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.01, 0.1, 0.8, 0.5))
    master_level: float = 0.7


@dataclass
class _Grain:
    start_idx: int = 0
    length: int = 0
    phase: float = 0.0
    pitch_ratio: float = 1.0
    pan: float = 0.5
    age: int = 0


class GranularVoice:
    """Granular synthesis voice — generates grain clouds from a source buffer."""

    def __init__(self, patch: GranularPatch, source: Optional[np.ndarray] = None):
        self.patch = patch
        # Default source: single-cycle saw repeated
        if source is None:
            self._source = np.tile(WAVE_SAW_BL, 20).astype(np.float32)
        else:
            self._source = source.astype(np.float32)
        self.note = -1
        self.velocity = 0
        self.active = False
        self._amp_env = ADSREnvelope(patch.amp_env)
        self._grains: list[_Grain] = []
        self._spawn_counter = 0.0
        self._rng = np.random.default_rng()

    def trigger(self, note: int, velocity: int):
        self.note = note
        self.velocity = velocity
        self.active = True
        self._amp_env.trigger()
        self._grains.clear()
        # Spawn first grain immediately
        self._spawn_counter = SAMPLE_RATE  # force immediate spawn

    def release(self):
        self._amp_env.release()

    def process(self, n_samples: int) -> np.ndarray:
        if not self.active:
            return np.zeros(n_samples, dtype=np.float32)

        freq = 440.0 * (2.0 ** ((self.note - 69) / 12.0))
        pitch_ratio = freq / 440.0
        vel_gain = self.velocity / 127.0
        grain_len = int(self.patch.grain_size_ms * SAMPLE_RATE / 1000)
        grain_len = max(64, grain_len)
        src_len = len(self._source)
        out = np.zeros(n_samples, dtype=np.float32)

        amp_env = self._amp_env.process(n_samples)

        # Spawn new grains
        spawn_interval = SAMPLE_RATE / max(self.patch.grain_density, 0.1)
        for i in range(n_samples):
            self._spawn_counter += 1.0
            if self._spawn_counter >= spawn_interval:
                self._spawn_counter -= spawn_interval
                pos = self.patch.position + self._rng.uniform(-1, 1) * self.patch.position_spread
                pos = max(0, min(pos, 0.99))
                start = int(pos * max(src_len - grain_len, 1))
                start = max(0, min(start, src_len - grain_len - 1))
                pr = pitch_ratio * (2.0 ** (self._rng.uniform(-1, 1) * self.patch.pitch_spread / 12.0))
                self._grains.append(_Grain(
                    start_idx=start, length=grain_len,
                    phase=0.0, pitch_ratio=pr,
                    pan=0.5 + self._rng.uniform(-1, 1) * self.patch.stereo_spread * 0.5,
                    age=0,
                ))

        # Process grains
        alive = []
        for g in self._grains:
            remaining = g.length - g.age
            if remaining <= 0:
                continue
            samples_to_render = min(n_samples, remaining)
            # Hann window envelope
            t_arr = np.arange(g.age, g.age + samples_to_render, dtype=np.float32)
            window = 0.5 * (1 - np.cos(TWO_PI * t_arr / max(g.length, 1)))
            # Read from source with pitch ratio
            read_pos = g.start_idx + t_arr * g.pitch_ratio
            read_pos = np.clip(read_pos, 0, src_len - 2).astype(np.int32)
            grain_samples = self._source[read_pos] * window
            out[:samples_to_render] += grain_samples
            g.age += samples_to_render
            if g.age < g.length:
                alive.append(g)
        self._grains = alive

        out = out * amp_env * vel_gain * self.patch.master_level

        if not self._amp_env.is_active and len(self._grains) == 0:
            self.active = False

        return out


# ── Sampler ────────────────────────────────────────────────────────────────

@dataclass
class SampleZone:
    """A single sample zone: covers a key range."""
    name: str = ""
    data: Optional[np.ndarray] = None   # float32 mono audio
    root_note: int = 60                 # MIDI note this sample is tuned to
    lo_key: int = 0
    hi_key: int = 127
    lo_vel: int = 0
    hi_vel: int = 127
    loop: bool = False
    loop_start: int = 0
    loop_end: int = 0


@dataclass
class SamplerPatch:
    name: str = "Sampler Init"
    zones: list = field(default_factory=list)
    filter_type: str = "lowpass"
    filter_cutoff: float = 12000.0
    filter_reso: float = 0.707
    amp_env: ADSRParams = field(default_factory=lambda: ADSRParams(0.001, 0.1, 1.0, 0.3))
    master_level: float = 0.8


class SamplerVoice:
    def __init__(self, patch: SamplerPatch):
        self.patch = patch
        self.note = -1
        self.velocity = 0
        self.active = False
        self._amp_env = ADSREnvelope(patch.amp_env)
        self._filter = BiquadFilter(patch.filter_type, patch.filter_cutoff, patch.filter_reso)
        self._zone: Optional[SampleZone] = None
        self._pos = 0.0
        self._pitch_ratio = 1.0

    def trigger(self, note: int, velocity: int):
        self.note = note
        self.velocity = velocity
        # Find matching zone
        self._zone = None
        for z in self.patch.zones:
            if z.lo_key <= note <= z.hi_key and z.lo_vel <= velocity <= z.hi_vel:
                if z.data is not None and len(z.data) > 0:
                    self._zone = z
                    break
        if self._zone is None:
            self.active = False
            return
        self.active = True
        self._pos = 0.0
        self._pitch_ratio = 2.0 ** ((note - self._zone.root_note) / 12.0)
        self._amp_env.trigger()
        self._filter.reset()

    def release(self):
        self._amp_env.release()

    def process(self, n_samples: int) -> np.ndarray:
        if not self.active or self._zone is None or self._zone.data is None:
            return np.zeros(n_samples, dtype=np.float32)

        data = self._zone.data
        data_len = len(data)
        vel_gain = self.velocity / 127.0
        out = np.zeros(n_samples, dtype=np.float32)

        for i in range(n_samples):
            idx = int(self._pos)
            if idx >= data_len - 1:
                if self._zone.loop and self._zone.loop_end > self._zone.loop_start:
                    self._pos = float(self._zone.loop_start)
                    idx = int(self._pos)
                else:
                    self.active = False
                    break
            frac = self._pos - idx
            out[i] = data[idx] * (1 - frac) + data[min(idx + 1, data_len - 1)] * frac
            self._pos += self._pitch_ratio

        out = self._filter.process(out)
        amp = self._amp_env.process(n_samples)
        out = out * amp * vel_gain * self.patch.master_level

        if not self._amp_env.is_active:
            self.active = False

        return out


# ── Drum Machine ───────────────────────────────────────────────────────────

@dataclass
class DrumPad:
    """Single drum pad — holds a sample and tuning."""
    name: str = ""
    note: int = 36             # Trigger MIDI note
    data: Optional[np.ndarray] = None  # float32 mono sample
    tune: float = 0.0          # semitones
    level: float = 1.0
    pan: float = 0.5           # 0=left, 1=right
    decay: float = 1.0         # decay multiplier
    muted: bool = False
    solo: bool = False
    # Generated default sounds
    synth_type: str = "kick"   # kick, snare, hihat, clap, tom, rim, cymbal, perc


def _generate_drum_sample(drum_type: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """Generate a basic synthesized drum sound."""
    rng = np.random.default_rng(42)
    if drum_type == "kick":
        t = np.linspace(0, 0.3, int(sr * 0.3), dtype=np.float32)
        freq = 150 * np.exp(-t * 15) + 40
        phase = np.cumsum(freq / sr) * TWO_PI
        osc = np.sin(phase) * np.exp(-t * 8)
        click = rng.standard_normal(int(sr * 0.005)).astype(np.float32) * 0.3
        out = np.zeros(len(t), dtype=np.float32)
        out[:len(click)] += click
        out += osc * 0.9
        return out

    elif drum_type == "snare":
        t = np.linspace(0, 0.2, int(sr * 0.2), dtype=np.float32)
        body = np.sin(TWO_PI * 200 * t) * np.exp(-t * 20) * 0.6
        noise = rng.standard_normal(len(t)).astype(np.float32) * np.exp(-t * 12) * 0.5
        return body + noise

    elif drum_type == "hihat":
        t = np.linspace(0, 0.08, int(sr * 0.08), dtype=np.float32)
        noise = rng.standard_normal(len(t)).astype(np.float32)
        # Highpass-like: differentiate
        hp = np.diff(noise, prepend=0) * 5
        return (hp * np.exp(-t * 40) * 0.4).astype(np.float32)

    elif drum_type == "clap":
        t = np.linspace(0, 0.15, int(sr * 0.15), dtype=np.float32)
        noise = rng.standard_normal(len(t)).astype(np.float32)
        env = np.exp(-t * 15) * 0.5
        # Add a few "clap" bursts
        for offset in [0.0, 0.01, 0.02]:
            idx = int(offset * sr)
            burst_len = int(0.005 * sr)
            if idx + burst_len < len(env):
                env[idx:idx + burst_len] += 0.3
        return (noise * env).astype(np.float32)

    elif drum_type == "tom":
        t = np.linspace(0, 0.25, int(sr * 0.25), dtype=np.float32)
        freq = 120 * np.exp(-t * 8) + 60
        phase = np.cumsum(freq / sr) * TWO_PI
        return (np.sin(phase) * np.exp(-t * 10) * 0.7).astype(np.float32)

    elif drum_type == "rim":
        t = np.linspace(0, 0.05, int(sr * 0.05), dtype=np.float32)
        click = np.sin(TWO_PI * 800 * t) * np.exp(-t * 60) * 0.8
        return click.astype(np.float32)

    elif drum_type == "cymbal":
        t = np.linspace(0, 0.8, int(sr * 0.8), dtype=np.float32)
        noise = rng.standard_normal(len(t)).astype(np.float32)
        metallic = np.sin(TWO_PI * 3000 * t) * 0.1 + np.sin(TWO_PI * 5500 * t) * 0.05
        return ((noise * 0.3 + metallic) * np.exp(-t * 3) * 0.4).astype(np.float32)

    else:  # perc
        t = np.linspace(0, 0.1, int(sr * 0.1), dtype=np.float32)
        return (np.sin(TWO_PI * 400 * t) * np.exp(-t * 25) * 0.5).astype(np.float32)


_DEFAULT_DRUM_MAP = [
    ("Kick", 36, "kick"), ("Snare", 38, "snare"),
    ("Closed HH", 42, "hihat"), ("Open HH", 46, "cymbal"),
    ("Clap", 39, "clap"), ("Rim", 37, "rim"),
    ("Low Tom", 41, "tom"), ("Mid Tom", 43, "tom"),
    ("Hi Tom", 45, "tom"), ("Crash", 49, "cymbal"),
    ("Ride", 51, "cymbal"), ("Perc 1", 47, "perc"),
    ("Perc 2", 48, "perc"), ("Perc 3", 50, "perc"),
    ("Perc 4", 52, "perc"), ("Perc 5", 53, "perc"),
]


class DrumMachine:
    """16-pad drum machine with synthesized or sample-based sounds."""

    def __init__(self):
        self.pads: list[DrumPad] = []
        self._active_samples: list[tuple[DrumPad, float, float]] = []  # (pad, position, vel_gain)
        self._init_default_pads()

    def _init_default_pads(self):
        self.pads.clear()
        for name, note, synth_type in _DEFAULT_DRUM_MAP:
            sample = _generate_drum_sample(synth_type)
            self.pads.append(DrumPad(
                name=name, note=note, data=sample, synth_type=synth_type
            ))

    def get_pad_for_note(self, note: int) -> Optional[DrumPad]:
        for pad in self.pads:
            if pad.note == note:
                return pad
        return None

    def trigger(self, note: int, velocity: int):
        pad = self.get_pad_for_note(note)
        if pad is None or pad.muted or pad.data is None:
            return
        solo_active = any(p.solo for p in self.pads)
        if solo_active and not pad.solo:
            return
        vel_gain = velocity / 127.0 * pad.level
        self._active_samples.append((pad, 0.0, vel_gain))

    def process(self, n_samples: int) -> np.ndarray:
        out = np.zeros(n_samples, dtype=np.float32)
        alive = []
        for pad, pos, vel_gain in self._active_samples:
            if pad.data is None:
                continue
            data = pad.data
            pitch_ratio = 2.0 ** (pad.tune / 12.0)
            start = int(pos)
            end_pos = pos + n_samples * pitch_ratio
            if start >= len(data):
                continue
            # Simple playback with pitch
            for i in range(n_samples):
                read_idx = int(pos + i * pitch_ratio)
                if read_idx >= len(data):
                    break
                out[i] += data[read_idx] * vel_gain * pad.decay
            new_pos = pos + n_samples * pitch_ratio
            if new_pos < len(data):
                alive.append((pad, new_pos, vel_gain))
        self._active_samples = alive
        return out


# ── Modulation Matrix ──────────────────────────────────────────────────────

@dataclass
class ModRoute:
    """Single modulation routing."""
    source: str = ""       # "lfo1", "lfo2", "env_filt", "env_amp", "velocity", "mod_wheel", "aftertouch"
    destination: str = ""  # "filter_cutoff", "osc1_pitch", "osc2_pitch", "osc_mix", "amp", "pan"
    amount: float = 0.0    # -1 to 1


class ModMatrix:
    """Routes modulation sources to destinations."""

    def __init__(self, routes: Optional[list[ModRoute]] = None):
        self.routes: list[ModRoute] = routes or []

    def add_route(self, source: str, destination: str, amount: float):
        self.routes.append(ModRoute(source, destination, amount))

    def remove_route(self, index: int):
        if 0 <= index < len(self.routes):
            self.routes.pop(index)

    def compute(self, sources: dict[str, float]) -> dict[str, float]:
        """Given source values, compute modulation offsets per destination."""
        result: dict[str, float] = {}
        for route in self.routes:
            src_val = sources.get(route.source, 0.0)
            mod = src_val * route.amount
            result[route.destination] = result.get(route.destination, 0.0) + mod
        return result


# ── Polyphonic Synth Manager ──────────────────────────────────────────────

class PolySynth:
    """Manages polyphonic voice allocation for any synth type."""

    SUBTRACTIVE = "subtractive"
    FM = "fm"
    WAVETABLE = "wavetable"
    GRANULAR = "granular"
    SAMPLER = "sampler"

    def __init__(self, synth_type: str = SUBTRACTIVE, max_voices: int = MAX_POLYPHONY):
        self.synth_type = synth_type
        self.max_voices = max_voices
        self._voices: list = []
        self._patch = None
        self._master_filter: Optional[BiquadFilter] = None

        # Default patches
        if synth_type == self.SUBTRACTIVE:
            self._patch = SubtractivePatch()
        elif synth_type == self.FM:
            self._patch = FMPatch()
        elif synth_type == self.WAVETABLE:
            self._patch = WavetablePatch()
        elif synth_type == self.GRANULAR:
            self._patch = GranularPatch()
        elif synth_type == self.SAMPLER:
            self._patch = SamplerPatch()

    @property
    def patch(self):
        return self._patch

    @patch.setter
    def patch(self, p):
        self._patch = p

    def _create_voice(self):
        if self.synth_type == self.SUBTRACTIVE:
            return SynthVoice(self._patch)
        elif self.synth_type == self.FM:
            return FMVoice(self._patch)
        elif self.synth_type == self.WAVETABLE:
            return WavetableVoice(self._patch)
        elif self.synth_type == self.GRANULAR:
            return GranularVoice(self._patch)
        elif self.synth_type == self.SAMPLER:
            return SamplerVoice(self._patch)
        return SynthVoice(SubtractivePatch())

    def note_on(self, note: int, velocity: int):
        # Check for existing voice on same note
        for v in self._voices:
            if hasattr(v, 'note') and v.note == note and v.active:
                v.release()
                break

        # Voice stealing if at max polyphony
        if len(self._voices) >= self.max_voices:
            # Release oldest
            inactive = [v for v in self._voices if not v.active]
            if inactive:
                self._voices.remove(inactive[0])
            elif self._voices:
                self._voices[0].release()
                self._voices.pop(0)

        voice = self._create_voice()
        voice.trigger(note, velocity)
        self._voices.append(voice)

    def note_off(self, note: int):
        for v in self._voices:
            if hasattr(v, 'note') and v.note == note and v.active:
                v.release()
                break

    def all_notes_off(self):
        for v in self._voices:
            if v.active:
                v.release()

    def process(self, n_samples: int) -> np.ndarray:
        out = np.zeros(n_samples, dtype=np.float32)
        alive = []
        for v in self._voices:
            if v.active:
                out += v.process(n_samples)
                if v.active:  # Still active after processing
                    alive.append(v)
            # Keep recently released voices until envelope finishes
            elif hasattr(v, 'amp_env') and v.amp_env is not None:
                pass  # Already handled by active check
        self._voices = alive
        # Soft clip
        out = np.tanh(out)
        return out


# ── Preset Library ─────────────────────────────────────────────────────────

SUBTRACTIVE_PRESETS: dict[str, SubtractivePatch] = {
    "Init": SubtractivePatch(),
    "Bass": SubtractivePatch(
        name="Bass", osc1_wave="saw", osc2_wave="square",
        osc2_semi=-12, osc_mix=0.5,
        filter_cutoff=800, filter_reso=2.0,
        amp_env=ADSRParams(0.005, 0.1, 0.8, 0.15),
        filt_env=ADSRParams(0.005, 0.2, 0.1, 0.1),
        filt_env_depth=2000, master_level=0.8,
    ),
    "Pad": SubtractivePatch(
        name="Pad", osc1_wave="saw", osc2_wave="triangle",
        osc1_detune=-5, osc2_detune=5, osc_mix=0.5,
        filter_cutoff=2000, filter_reso=0.8,
        amp_env=ADSRParams(0.5, 0.3, 0.8, 1.0),
        filt_env=ADSRParams(0.8, 0.5, 0.4, 1.0),
        filt_env_depth=2000,
        lfo=LFOParams(0.3, 0.15, "triangle"),
        lfo_to_filter=300, master_level=0.6,
    ),
    "Lead": SubtractivePatch(
        name="Lead", osc1_wave="square", osc2_wave="saw",
        osc2_semi=7, osc_mix=0.7,
        filter_cutoff=3000, filter_reso=3.0,
        amp_env=ADSRParams(0.01, 0.1, 0.9, 0.2),
        filt_env=ADSRParams(0.01, 0.15, 0.5, 0.2),
        filt_env_depth=4000, master_level=0.7,
    ),
    "Pluck": SubtractivePatch(
        name="Pluck", osc1_wave="saw", osc2_wave="saw",
        osc2_detune=10, osc_mix=0.5,
        filter_cutoff=5000, filter_reso=1.5,
        amp_env=ADSRParams(0.001, 0.15, 0.0, 0.1),
        filt_env=ADSRParams(0.001, 0.1, 0.0, 0.05),
        filt_env_depth=6000, master_level=0.7,
    ),
    "Strings": SubtractivePatch(
        name="Strings", osc1_wave="saw", osc2_wave="saw",
        osc1_detune=-8, osc2_detune=8, osc_mix=0.5,
        filter_cutoff=3000, filter_reso=0.5,
        amp_env=ADSRParams(0.3, 0.2, 0.9, 0.5),
        filt_env=ADSRParams(0.4, 0.3, 0.5, 0.5),
        filt_env_depth=1500,
        lfo=LFOParams(5.0, 0.03, "sine"),
        lfo_to_pitch=10, master_level=0.6,
    ),
    "Brass": SubtractivePatch(
        name="Brass", osc1_wave="saw", osc2_wave="square",
        osc_mix=0.6,
        filter_cutoff=1500, filter_reso=1.2,
        amp_env=ADSRParams(0.08, 0.1, 0.85, 0.15),
        filt_env=ADSRParams(0.08, 0.3, 0.4, 0.2),
        filt_env_depth=5000, master_level=0.7,
    ),
    "Sub Bass": SubtractivePatch(
        name="Sub Bass", osc1_wave="sine", osc2_wave="sine",
        osc2_semi=-12, osc_mix=0.7,
        filter_cutoff=300, filter_reso=1.5,
        amp_env=ADSRParams(0.005, 0.05, 0.95, 0.2),
        master_level=0.9,
    ),
    "Noise Sweep": SubtractivePatch(
        name="Noise Sweep", osc1_wave="saw",
        noise_level=0.4,
        filter_cutoff=500, filter_reso=4.0,
        amp_env=ADSRParams(0.1, 0.5, 0.5, 1.0),
        filt_env=ADSRParams(0.5, 1.0, 0.1, 0.5),
        filt_env_depth=8000, master_level=0.5,
    ),
}

FM_PRESETS: dict[str, FMPatch] = {
    "FM Init": FMPatch(),
    "E.Piano": FMPatch(
        name="E.Piano",
        ops=[
            FMOperator(1.0, 1.0, 0, ADSRParams(0.001, 0.8, 0.0, 0.2)),
            FMOperator(1.0, 0.7, 0, ADSRParams(0.001, 0.3, 0.0, 0.1)),
            FMOperator(3.0, 0.2, 0, ADSRParams(0.001, 0.1, 0.0, 0.05)),
            FMOperator(1.0, 0.0),
        ],
        algorithm=0, master_level=0.7,
        amp_env=ADSRParams(0.001, 1.0, 0.0, 0.3),
    ),
    "Bell": FMPatch(
        name="Bell",
        ops=[
            FMOperator(1.0, 1.0, 0, ADSRParams(0.001, 2.0, 0.0, 1.0)),
            FMOperator(3.5, 0.8, 0, ADSRParams(0.001, 1.5, 0.0, 0.8)),
            FMOperator(7.0, 0.3, 0, ADSRParams(0.001, 0.5, 0.0, 0.3)),
            FMOperator(1.0, 0.0),
        ],
        algorithm=0, master_level=0.5,
        amp_env=ADSRParams(0.001, 3.0, 0.0, 1.5),
    ),
    "Organ": FMPatch(
        name="Organ",
        ops=[
            FMOperator(1.0, 1.0, 0, ADSRParams(0.01, 0.05, 0.9, 0.1)),
            FMOperator(2.0, 0.3, 0, ADSRParams(0.01, 0.05, 0.7, 0.1)),
            FMOperator(3.0, 0.2, 0, ADSRParams(0.01, 0.05, 0.5, 0.1)),
            FMOperator(4.0, 0.1, 0, ADSRParams(0.01, 0.05, 0.3, 0.1)),
        ],
        algorithm=1, master_level=0.6,
        amp_env=ADSRParams(0.005, 0.05, 0.95, 0.08),
    ),
}


# ── Synth Engine (Top-level Manager) ──────────────────────────────────────

class SynthEngine:
    """Top-level synthesizer engine managing all synth types.

    Integrates with AudioEngine by providing mixed output samples.
    """

    def __init__(self):
        self.synths: dict[int, PolySynth] = {}       # channel → PolySynth
        self.drum_machine = DrumMachine()
        self.drum_channel = 9                          # GM drum channel
        self.mod_matrix = ModMatrix()
        self.master_level = 0.8
        self._active = True

    def assign_synth(self, channel: int, synth_type: str = PolySynth.SUBTRACTIVE):
        """Assign a synth type to a MIDI channel."""
        self.synths[channel] = PolySynth(synth_type)

    def get_synth(self, channel: int) -> Optional[PolySynth]:
        return self.synths.get(channel)

    def set_patch(self, channel: int, patch):
        """Set a patch on a channel's synth."""
        synth = self.synths.get(channel)
        if synth:
            synth.patch = patch

    def note_on(self, channel: int, note: int, velocity: int):
        if channel == self.drum_channel:
            self.drum_machine.trigger(note, velocity)
            return
        synth = self.synths.get(channel)
        if synth:
            synth.note_on(note, velocity)

    def note_off(self, channel: int, note: int):
        if channel == self.drum_channel:
            return  # Drums are one-shot
        synth = self.synths.get(channel)
        if synth:
            synth.note_off(note)

    def all_notes_off(self):
        for synth in self.synths.values():
            synth.all_notes_off()

    def process(self, n_samples: int = BLOCK_SIZE) -> np.ndarray:
        """Mix all synths and drum machine into a single output buffer."""
        out = np.zeros(n_samples, dtype=np.float32)
        for synth in self.synths.values():
            out += synth.process(n_samples)
        out += self.drum_machine.process(n_samples)
        out *= self.master_level
        # Hard clip protection
        return np.clip(out, -1.0, 1.0)

    def get_preset_list(self, synth_type: str) -> list[str]:
        if synth_type == PolySynth.SUBTRACTIVE:
            return list(SUBTRACTIVE_PRESETS.keys())
        elif synth_type == PolySynth.FM:
            return list(FM_PRESETS.keys())
        return []

    def load_preset(self, channel: int, preset_name: str):
        synth = self.synths.get(channel)
        if not synth:
            return
        if synth.synth_type == PolySynth.SUBTRACTIVE:
            preset = SUBTRACTIVE_PRESETS.get(preset_name)
            if preset:
                synth.patch = preset.copy()
        elif synth.synth_type == PolySynth.FM:
            preset = FM_PRESETS.get(preset_name)
            if preset:
                synth.patch = preset
