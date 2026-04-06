"""
Effects Engine — audio processing effects chain.

Covers: EQ, Compressor, Reverb, Delay, Chorus, Flanger, Phaser,
Distortion/Saturation, Limiter, Gate, Insert/Send routing,
presets, bypass, dry/wet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

SAMPLE_RATE = 44100
TWO_PI = 2.0 * np.pi


# ── Base Effect ────────────────────────────────────────────────────────────

class Effect:
    """Base class for all audio effects."""
    name: str = "Effect"
    enabled: bool = True
    dry_wet: float = 1.0  # 0=dry, 1=wet

    def process(self, audio: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return audio
        wet = self._process(audio)
        if self.dry_wet >= 1.0:
            return wet
        return audio * (1 - self.dry_wet) + wet * self.dry_wet

    def _process(self, audio: np.ndarray) -> np.ndarray:
        return audio

    def reset(self):
        pass


# ── Parametric EQ ──────────────────────────────────────────────────────────

@dataclass
class EQBand:
    freq: float = 1000.0
    gain_db: float = 0.0
    q: float = 1.0
    band_type: str = "peak"  # peak, lowshelf, highshelf, lowpass, highpass
    enabled: bool = True


class ParametricEQ(Effect):
    """8-band parametric EQ."""

    def __init__(self, bands: Optional[list[EQBand]] = None):
        self.name = "Parametric EQ"
        self.enabled = True
        self.dry_wet = 1.0
        self.bands = bands or [
            EQBand(80, 0, 0.7, "lowshelf"),
            EQBand(200, 0, 1.0, "peak"),
            EQBand(500, 0, 1.0, "peak"),
            EQBand(1000, 0, 1.0, "peak"),
            EQBand(2500, 0, 1.0, "peak"),
            EQBand(5000, 0, 1.0, "peak"),
            EQBand(8000, 0, 1.0, "peak"),
            EQBand(12000, 0, 0.7, "highshelf"),
        ]
        self._filters = [_BiquadState() for _ in self.bands]
        self._update_coeffs()

    def _update_coeffs(self):
        for i, band in enumerate(self.bands):
            if not band.enabled or band.gain_db == 0:
                self._filters[i].bypass = True
                continue
            self._filters[i].bypass = False
            w0 = TWO_PI * band.freq / SAMPLE_RATE
            A = 10 ** (band.gain_db / 40.0)
            alpha = math.sin(w0) / (2 * band.q)
            cos_w0 = math.cos(w0)

            if band.band_type == "peak":
                b0 = 1 + alpha * A
                b1 = -2 * cos_w0
                b2 = 1 - alpha * A
                a0 = 1 + alpha / A
                a1 = -2 * cos_w0
                a2 = 1 - alpha / A
            elif band.band_type == "lowshelf":
                sq = 2 * math.sqrt(A) * alpha
                b0 = A * ((A + 1) - (A - 1) * cos_w0 + sq)
                b1 = 2 * A * ((A - 1) - (A + 1) * cos_w0)
                b2 = A * ((A + 1) - (A - 1) * cos_w0 - sq)
                a0 = (A + 1) + (A - 1) * cos_w0 + sq
                a1 = -2 * ((A - 1) + (A + 1) * cos_w0)
                a2 = (A + 1) + (A - 1) * cos_w0 - sq
            elif band.band_type == "highshelf":
                sq = 2 * math.sqrt(A) * alpha
                b0 = A * ((A + 1) + (A - 1) * cos_w0 + sq)
                b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
                b2 = A * ((A + 1) + (A - 1) * cos_w0 - sq)
                a0 = (A + 1) - (A - 1) * cos_w0 + sq
                a1 = 2 * ((A - 1) - (A + 1) * cos_w0)
                a2 = (A + 1) - (A - 1) * cos_w0 - sq
            else:
                continue

            f = self._filters[i]
            f.b0, f.b1, f.b2 = b0 / a0, b1 / a0, b2 / a0
            f.a1, f.a2 = a1 / a0, a2 / a0

    def set_band(self, index: int, freq=None, gain_db=None, q=None):
        if 0 <= index < len(self.bands):
            if freq is not None:
                self.bands[index].freq = freq
            if gain_db is not None:
                self.bands[index].gain_db = gain_db
            if q is not None:
                self.bands[index].q = q
            self._update_coeffs()

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = audio.copy()
        for f in self._filters:
            if f.bypass:
                continue
            out = f.process(out)
        return out


class _BiquadState:
    def __init__(self):
        self.b0 = 1.0
        self.b1 = 0.0
        self.b2 = 0.0
        self.a1 = 0.0
        self.a2 = 0.0
        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0
        self.bypass = True

    def process(self, data: np.ndarray) -> np.ndarray:
        out = np.empty_like(data)
        for i in range(len(data)):
            x = float(data[i])
            y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
            self.x2, self.x1 = self.x1, x
            self.y2, self.y1 = self.y1, y
            out[i] = y
        return out

    def reset(self):
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0


# ── Compressor ─────────────────────────────────────────────────────────────

class Compressor(Effect):
    def __init__(self, threshold_db: float = -20.0, ratio: float = 4.0,
                 attack_ms: float = 5.0, release_ms: float = 50.0,
                 makeup_db: float = 0.0, knee_db: float = 6.0):
        self.name = "Compressor"
        self.enabled = True
        self.dry_wet = 1.0
        self.threshold = threshold_db
        self.ratio = ratio
        self.attack = attack_ms
        self.release = release_ms
        self.makeup = makeup_db
        self.knee = knee_db
        self._env = 0.0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.empty_like(audio)
        att_coeff = math.exp(-1.0 / (self.attack * 0.001 * SAMPLE_RATE))
        rel_coeff = math.exp(-1.0 / (self.release * 0.001 * SAMPLE_RATE))
        makeup_lin = 10 ** (self.makeup / 20.0)

        for i in range(len(audio)):
            x = float(audio[i])
            x_db = 20 * math.log10(abs(x) + 1e-10)

            # Soft knee
            half_knee = self.knee / 2.0
            if x_db < self.threshold - half_knee:
                gain_db = 0.0
            elif x_db > self.threshold + half_knee:
                gain_db = (self.threshold - x_db) * (1 - 1 / self.ratio)
            else:
                t = x_db - self.threshold + half_knee
                gain_db = (1 - 1 / self.ratio) * t * t / (2 * self.knee) * -1

            target = 10 ** (gain_db / 20.0)
            if target < self._env:
                self._env = att_coeff * self._env + (1 - att_coeff) * target
            else:
                self._env = rel_coeff * self._env + (1 - rel_coeff) * target

            out[i] = x * self._env * makeup_lin
        return out


# ── Reverb (Schroeder) ─────────────────────────────────────────────────────

class Reverb(Effect):
    def __init__(self, room_size: float = 0.7, damping: float = 0.5,
                 pre_delay_ms: float = 20.0):
        self.name = "Reverb"
        self.enabled = True
        self.dry_wet = 0.3
        self.room_size = room_size
        self.damping = damping
        self.pre_delay_ms = pre_delay_ms
        self._init_buffers()

    def _init_buffers(self):
        # Comb filter delays (in samples)
        base_delays = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
        scale = self.room_size
        self._comb_delays = [int(d * scale) for d in base_delays]
        self._comb_buffers = [np.zeros(d + 1, dtype=np.float32) for d in self._comb_delays]
        self._comb_indices = [0] * len(self._comb_delays)
        self._comb_filters = [0.0] * len(self._comb_delays)

        # All-pass delays
        ap_delays = [225, 556, 441, 341]
        self._ap_delays = ap_delays
        self._ap_buffers = [np.zeros(d + 1, dtype=np.float32) for d in ap_delays]
        self._ap_indices = [0] * len(ap_delays)

        # Pre-delay
        pd_samples = int(self.pre_delay_ms * SAMPLE_RATE / 1000)
        self._pd_buffer = np.zeros(max(pd_samples, 1), dtype=np.float32)
        self._pd_idx = 0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.zeros_like(audio)
        damp = self.damping

        for i in range(len(audio)):
            # Pre-delay
            pd_len = len(self._pd_buffer)
            x = float(audio[i])
            delayed = self._pd_buffer[self._pd_idx]
            self._pd_buffer[self._pd_idx] = x
            self._pd_idx = (self._pd_idx + 1) % pd_len
            x = delayed

            # Parallel comb filters
            comb_sum = 0.0
            for c in range(len(self._comb_delays)):
                buf = self._comb_buffers[c]
                idx = self._comb_indices[c]
                d_len = len(buf)
                buf_out = buf[idx]
                self._comb_filters[c] = buf_out * (1 - damp) + self._comb_filters[c] * damp
                buf[idx] = x + self._comb_filters[c] * self.room_size
                self._comb_indices[c] = (idx + 1) % d_len
                comb_sum += buf_out

            comb_sum /= len(self._comb_delays)

            # Series all-pass filters
            ap_out = comb_sum
            for a in range(len(self._ap_delays)):
                buf = self._ap_buffers[a]
                idx = self._ap_indices[a]
                d_len = len(buf)
                buf_out = buf[idx]
                buf[idx] = ap_out + buf_out * 0.5
                ap_out = buf_out - ap_out * 0.5
                self._ap_indices[a] = (idx + 1) % d_len

            out[i] = ap_out

        return out


# ── Delay ──────────────────────────────────────────────────────────────────

class Delay(Effect):
    def __init__(self, time_ms: float = 375.0, feedback: float = 0.4,
                 sync: bool = False):
        self.name = "Delay"
        self.enabled = True
        self.dry_wet = 0.35
        self.time_ms = time_ms
        self.feedback = feedback
        self.sync = sync
        self._delay_samples = int(time_ms * SAMPLE_RATE / 1000)
        self._buffer = np.zeros(max(self._delay_samples, 1), dtype=np.float32)
        self._idx = 0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.empty_like(audio)
        for i in range(len(audio)):
            x = float(audio[i])
            delayed = self._buffer[self._idx]
            self._buffer[self._idx] = x + delayed * self.feedback
            self._idx = (self._idx + 1) % len(self._buffer)
            out[i] = delayed
        return out


# ── Chorus ─────────────────────────────────────────────────────────────────

class Chorus(Effect):
    def __init__(self, rate: float = 1.5, depth: float = 0.003,
                 voices: int = 2):
        self.name = "Chorus"
        self.enabled = True
        self.dry_wet = 0.5
        self.rate = rate
        self.depth = depth
        self.voices = voices
        max_delay = int((depth + 0.01) * SAMPLE_RATE) + 1
        self._buffer = np.zeros(max_delay * 2, dtype=np.float32)
        self._write_idx = 0
        self._phase = 0.0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.zeros_like(audio)
        buf_len = len(self._buffer)
        center_delay = int(0.007 * SAMPLE_RATE)

        for i in range(len(audio)):
            x = float(audio[i])
            self._buffer[self._write_idx] = x

            sample = 0.0
            for v in range(self.voices):
                phase = self._phase + v * (TWO_PI / self.voices)
                mod = math.sin(phase) * self.depth * SAMPLE_RATE
                delay = center_delay + mod
                read_pos = (self._write_idx - int(delay)) % buf_len
                sample += self._buffer[read_pos]

            out[i] = sample / self.voices
            self._write_idx = (self._write_idx + 1) % buf_len
            self._phase += TWO_PI * self.rate / SAMPLE_RATE

        return out


# ── Phaser ─────────────────────────────────────────────────────────────────

class Phaser(Effect):
    def __init__(self, rate: float = 0.5, depth: float = 0.7, stages: int = 4):
        self.name = "Phaser"
        self.enabled = True
        self.dry_wet = 0.5
        self.rate = rate
        self.depth = depth
        self.stages = stages
        self._phase = 0.0
        self._ap_states = [[0.0, 0.0] for _ in range(stages)]

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.empty_like(audio)
        min_freq, max_freq = 200.0, 4000.0

        for i in range(len(audio)):
            x = float(audio[i])
            mod = (math.sin(self._phase) + 1) * 0.5  # 0-1
            freq = min_freq + mod * (max_freq - min_freq) * self.depth
            w = TWO_PI * freq / SAMPLE_RATE
            coeff = (1 - math.tan(w / 2)) / (1 + math.tan(w / 2))

            y = x
            for s in range(self.stages):
                ap_in = y
                y = coeff * (ap_in - self._ap_states[s][1]) + self._ap_states[s][0]
                self._ap_states[s][0] = ap_in
                self._ap_states[s][1] = y

            out[i] = y
            self._phase += TWO_PI * self.rate / SAMPLE_RATE

        return out


# ── Flanger ────────────────────────────────────────────────────────────────

class Flanger(Effect):
    def __init__(self, rate: float = 0.3, depth: float = 0.7, feedback: float = 0.5):
        self.name = "Flanger"
        self.enabled = True
        self.dry_wet = 0.5
        self.rate = rate
        self.depth = depth
        self.feedback = feedback
        max_delay = int(0.01 * SAMPLE_RATE) + 1
        self._buffer = np.zeros(max_delay, dtype=np.float32)
        self._write_idx = 0
        self._phase = 0.0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        out = np.empty_like(audio)
        buf_len = len(self._buffer)
        max_d = buf_len - 2

        for i in range(len(audio)):
            x = float(audio[i])
            mod = (math.sin(self._phase) + 1) * 0.5
            delay = 1 + mod * self.depth * max_d
            d_int = int(delay)
            d_frac = delay - d_int
            idx1 = (self._write_idx - d_int) % buf_len
            idx2 = (self._write_idx - d_int - 1) % buf_len
            delayed = self._buffer[idx1] * (1 - d_frac) + self._buffer[idx2] * d_frac

            self._buffer[self._write_idx] = x + delayed * self.feedback
            self._write_idx = (self._write_idx + 1) % buf_len
            out[i] = delayed
            self._phase += TWO_PI * self.rate / SAMPLE_RATE

        return out


# ── Distortion ─────────────────────────────────────────────────────────────

class Distortion(Effect):
    def __init__(self, drive: float = 0.5, tone: float = 0.5,
                 dist_type: str = "soft_clip"):
        self.name = "Distortion"
        self.enabled = True
        self.dry_wet = 1.0
        self.drive = drive       # 0-1
        self.tone = tone         # 0-1 (low-high)
        self.dist_type = dist_type  # soft_clip, hard_clip, foldback, bitcrush

    def _process(self, audio: np.ndarray) -> np.ndarray:
        gain = 1 + self.drive * 20
        x = audio * gain

        if self.dist_type == "soft_clip":
            out = np.tanh(x)
        elif self.dist_type == "hard_clip":
            out = np.clip(x, -1, 1)
        elif self.dist_type == "foldback":
            out = np.abs(np.abs(np.fmod(x - 1, 4)) - 2) - 1
        elif self.dist_type == "bitcrush":
            bits = max(2, 16 - int(self.drive * 14))
            scale = 2 ** bits
            out = np.round(x * scale) / scale
            out = np.clip(out, -1, 1)
        else:
            out = np.tanh(x)

        # Simple tone filter
        if self.tone < 0.5:
            # Low-pass
            alpha = self.tone * 2
            out_filtered = np.empty_like(out)
            prev = 0.0
            for i in range(len(out)):
                prev = prev + alpha * (float(out[i]) - prev)
                out_filtered[i] = prev
            out = out_filtered

        return out * (1 / gain * 2)


# ── Limiter ────────────────────────────────────────────────────────────────

class Limiter(Effect):
    def __init__(self, ceiling_db: float = -0.3, release_ms: float = 100.0):
        self.name = "Limiter"
        self.enabled = True
        self.dry_wet = 1.0
        self.ceiling = ceiling_db
        self.release = release_ms
        self._env = 1.0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        ceiling_lin = 10 ** (self.ceiling / 20.0)
        rel_coeff = math.exp(-1.0 / (self.release * 0.001 * SAMPLE_RATE))
        out = np.empty_like(audio)

        for i in range(len(audio)):
            x = abs(float(audio[i]))
            if x > ceiling_lin:
                target = ceiling_lin / (x + 1e-10)
            else:
                target = 1.0
            if target < self._env:
                self._env = target
            else:
                self._env = rel_coeff * self._env + (1 - rel_coeff) * target
            out[i] = float(audio[i]) * self._env
        return out


# ── Gate ───────────────────────────────────────────────────────────────────

class Gate(Effect):
    def __init__(self, threshold_db: float = -40.0, attack_ms: float = 1.0,
                 release_ms: float = 50.0):
        self.name = "Gate"
        self.enabled = True
        self.dry_wet = 1.0
        self.threshold = threshold_db
        self.attack = attack_ms
        self.release = release_ms
        self._env = 0.0

    def _process(self, audio: np.ndarray) -> np.ndarray:
        thresh_lin = 10 ** (self.threshold / 20.0)
        att_coeff = math.exp(-1.0 / (self.attack * 0.001 * SAMPLE_RATE))
        rel_coeff = math.exp(-1.0 / (self.release * 0.001 * SAMPLE_RATE))
        out = np.empty_like(audio)

        for i in range(len(audio)):
            x = abs(float(audio[i]))
            if x > thresh_lin:
                target = 1.0
                self._env = att_coeff * self._env + (1 - att_coeff) * target
            else:
                target = 0.0
                self._env = rel_coeff * self._env + (1 - rel_coeff) * target
            out[i] = float(audio[i]) * self._env
        return out


# ── Effects Chain ──────────────────────────────────────────────────────────

class EffectsChain:
    """Chain of effects for insert or send bus."""

    def __init__(self, name: str = "Chain"):
        self.name = name
        self.effects: list[Effect] = []
        self.enabled = True

    def add(self, effect: Effect) -> int:
        self.effects.append(effect)
        return len(self.effects) - 1

    def remove(self, index: int):
        if 0 <= index < len(self.effects):
            self.effects.pop(index)

    def move(self, from_idx: int, to_idx: int):
        if 0 <= from_idx < len(self.effects) and 0 <= to_idx < len(self.effects):
            fx = self.effects.pop(from_idx)
            self.effects.insert(to_idx, fx)

    def process(self, audio: np.ndarray) -> np.ndarray:
        if not self.enabled:
            return audio
        out = audio
        for fx in self.effects:
            out = fx.process(out)
        return out

    def reset(self):
        for fx in self.effects:
            fx.reset()


# ── Mixer Bus ──────────────────────────────────────────────────────────────

class MixerBus:
    """A mixer bus (group, send/return, or master)."""

    def __init__(self, name: str = "Bus", bus_type: str = "group"):
        self.name = name
        self.bus_type = bus_type  # group, send, master
        self.chain = EffectsChain(name)
        self.volume: float = 1.0
        self.pan: float = 0.5
        self.muted: bool = False
        self.solo: bool = False

    def process(self, audio: np.ndarray) -> np.ndarray:
        if self.muted:
            return np.zeros_like(audio)
        out = self.chain.process(audio)
        return out * self.volume


# ── Mixer ──────────────────────────────────────────────────────────────────

class Mixer:
    """Full mixer with inserts, sends, groups, and master."""

    def __init__(self):
        self.track_chains: dict[int, EffectsChain] = {}   # track_index → insert chain
        self.send_buses: list[MixerBus] = [
            MixerBus("Reverb Send", "send"),
            MixerBus("Delay Send", "send"),
        ]
        self.group_buses: list[MixerBus] = []
        self.master = MixerBus("Master", "master")
        self.master.chain.add(Limiter(-0.3))
        # Track send levels: track_idx → {send_idx: level}
        self.send_levels: dict[int, dict[int, float]] = {}

    def get_insert_chain(self, track_idx: int) -> EffectsChain:
        if track_idx not in self.track_chains:
            self.track_chains[track_idx] = EffectsChain(f"Track {track_idx}")
        return self.track_chains[track_idx]

    def add_insert(self, track_idx: int, effect: Effect) -> int:
        chain = self.get_insert_chain(track_idx)
        return chain.add(effect)

    def set_insert_bypass(self, track_idx: int, slot_idx: int, bypassed: bool):
        """인서트 슬롯 바이패스 설정."""
        chain = self.track_chains.get(track_idx)
        if chain and 0 <= slot_idx < len(chain.effects):
            chain.effects[slot_idx].bypassed = bypassed

    def set_insert_mix(self, track_idx: int, slot_idx: int, mix: float):
        """인서트 슬롯 dry/wet 믹스 (0.0=dry, 1.0=wet)."""
        chain = self.track_chains.get(track_idx)
        if chain and 0 <= slot_idx < len(chain.effects):
            if hasattr(chain.effects[slot_idx], 'mix'):
                chain.effects[slot_idx].mix = mix

    def remove_insert(self, track_idx: int, slot_idx: int):
        """인서트 슬롯에서 이펙트 제거."""
        chain = self.track_chains.get(track_idx)
        if chain and 0 <= slot_idx < len(chain.effects):
            chain.effects.pop(slot_idx)

    def set_send_level(self, track_idx: int, send_idx: int, level: float):
        if track_idx not in self.send_levels:
            self.send_levels[track_idx] = {}
        self.send_levels[track_idx][send_idx] = level

    def process_track(self, track_idx: int, audio: np.ndarray) -> np.ndarray:
        """Process a single track through its insert chain."""
        chain = self.track_chains.get(track_idx)
        if chain:
            return chain.process(audio)
        return audio

    def process_sends(self, track_idx: int, audio: np.ndarray) -> list[np.ndarray]:
        """Get send outputs for a track."""
        outputs = []
        levels = self.send_levels.get(track_idx, {})
        for i, bus in enumerate(self.send_buses):
            level = levels.get(i, 0.0)
            if level > 0:
                sent = audio * level
                outputs.append(bus.process(sent))
            else:
                outputs.append(np.zeros_like(audio))
        return outputs

    def process_master(self, audio: np.ndarray) -> np.ndarray:
        return self.master.process(audio)


# ── Effect Presets ─────────────────────────────────────────────────────────

EFFECT_PRESETS = {
    "Clean EQ": lambda: ParametricEQ(),
    "Vocal EQ": lambda: ParametricEQ([
        EQBand(80, -6, 0.7, "highshelf"), EQBand(200, -2, 1.0),
        EQBand(500, 0, 1.0), EQBand(2000, 3, 1.5),
        EQBand(4000, 2, 1.0), EQBand(8000, 1, 0.7),
        EQBand(12000, 2, 0.7, "highshelf"), EQBand(16000, 0, 0.7),
    ]),
    "Light Comp": lambda: Compressor(-20, 3, 10, 100, 3),
    "Heavy Comp": lambda: Compressor(-15, 8, 2, 50, 6),
    "Small Room": lambda: Reverb(0.3, 0.7, 5),
    "Large Hall": lambda: Reverb(0.85, 0.3, 30),
    "Plate Reverb": lambda: Reverb(0.6, 0.4, 10),
    "Short Delay": lambda: Delay(125, 0.3),
    "Long Delay": lambda: Delay(500, 0.5),
    "Ping Pong": lambda: Delay(375, 0.45),
    "Chorus": lambda: Chorus(1.5, 0.003, 2),
    "Thick Chorus": lambda: Chorus(0.8, 0.005, 4),
    "Phaser": lambda: Phaser(0.5, 0.7, 4),
    "Flanger": lambda: Flanger(0.3, 0.7, 0.5),
    "Soft Clip": lambda: Distortion(0.3, 0.6, "soft_clip"),
    "Hard Clip": lambda: Distortion(0.5, 0.5, "hard_clip"),
    "Bitcrush": lambda: Distortion(0.6, 0.3, "bitcrush"),
    "Limiter": lambda: Limiter(-0.3, 100),
    "Gate": lambda: Gate(-40, 1, 50),
}
