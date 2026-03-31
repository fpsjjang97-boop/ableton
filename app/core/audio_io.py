"""
Audio I/O Manager — real-time recording, playback, and file operations.

Covers: audio recording, audio track, waveform data, file import/export,
time-stretching, pitch-shifting, audio clip editing, bounce/render,
sample rate/buffer config, freeze/flatten, multi-take, punch in/out.
"""
from __future__ import annotations

import logging
import math
import struct
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

import numpy as np

logger = logging.getLogger(__name__)

SAMPLE_RATE = 44100
CHANNELS = 2
BUFFER_SIZE = 512
BIT_DEPTH = 16

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:
    sd = None
    _HAS_SD = False
    logger.warning("sounddevice not available — recording disabled")


# ── Audio Clip ─────────────────────────────────────────────────────────────

@dataclass
class AudioClip:
    """A segment of audio data placed on a timeline."""
    name: str = ""
    data: Optional[np.ndarray] = None    # float32, shape (n_samples,) or (n_samples, 2)
    sample_rate: int = SAMPLE_RATE
    start_tick: int = 0
    # Edit points (sample indices within data)
    clip_start: int = 0                   # trim start
    clip_end: int = -1                    # trim end (-1 = full length)
    # Fades (samples)
    fade_in: int = 0
    fade_out: int = 0
    # Gain
    gain: float = 1.0
    muted: bool = False
    # Warp/stretch
    stretch_ratio: float = 1.0
    pitch_shift_semitones: float = 0.0
    # Source
    source_path: str = ""
    # Takes (for comping)
    take_index: int = 0

    @property
    def duration_samples(self) -> int:
        if self.data is None:
            return 0
        end = self.clip_end if self.clip_end >= 0 else len(self.data)
        return int((end - self.clip_start) * self.stretch_ratio)

    @property
    def duration_seconds(self) -> float:
        return self.duration_samples / self.sample_rate

    def get_mono(self) -> np.ndarray:
        if self.data is None:
            return np.array([], dtype=np.float32)
        d = self.data[self.clip_start:self.clip_end if self.clip_end >= 0 else len(self.data)]
        if d.ndim == 2:
            return d.mean(axis=1).astype(np.float32)
        return d.astype(np.float32)

    def get_waveform_peaks(self, num_points: int = 500) -> np.ndarray:
        """Get peak values for waveform display."""
        mono = self.get_mono()
        if len(mono) == 0:
            return np.zeros(num_points, dtype=np.float32)
        chunk_size = max(1, len(mono) // num_points)
        peaks = np.zeros(num_points, dtype=np.float32)
        for i in range(min(num_points, len(mono) // chunk_size)):
            chunk = mono[i * chunk_size:(i + 1) * chunk_size]
            peaks[i] = np.max(np.abs(chunk)) if len(chunk) > 0 else 0
        return peaks

    def apply_fade(self, audio: np.ndarray) -> np.ndarray:
        """Apply fade in/out to audio."""
        out = audio.copy()
        n = len(out)
        if self.fade_in > 0 and self.fade_in < n:
            fade = np.linspace(0, 1, self.fade_in, dtype=np.float32)
            if out.ndim == 2:
                out[:self.fade_in] *= fade[:, np.newaxis]
            else:
                out[:self.fade_in] *= fade
        if self.fade_out > 0 and self.fade_out < n:
            fade = np.linspace(1, 0, self.fade_out, dtype=np.float32)
            if out.ndim == 2:
                out[-self.fade_out:] *= fade[:, np.newaxis]
            else:
                out[-self.fade_out:] *= fade
        return out

    def split_at(self, sample_pos: int) -> tuple[AudioClip, AudioClip]:
        """Split clip into two at the given sample position."""
        if self.data is None:
            return self, AudioClip()
        abs_pos = self.clip_start + sample_pos
        left = AudioClip(
            name=f"{self.name}_L", data=self.data, sample_rate=self.sample_rate,
            start_tick=self.start_tick, clip_start=self.clip_start, clip_end=abs_pos,
            gain=self.gain, source_path=self.source_path,
        )
        right = AudioClip(
            name=f"{self.name}_R", data=self.data, sample_rate=self.sample_rate,
            start_tick=self.start_tick + int(sample_pos * self.stretch_ratio),
            clip_start=abs_pos,
            clip_end=self.clip_end if self.clip_end >= 0 else len(self.data),
            gain=self.gain, source_path=self.source_path,
        )
        return left, right


# ── Audio Track ────────────────────────────────────────────────────────────

@dataclass
class AudioTrack:
    """An audio track containing clips."""
    name: str = "Audio 1"
    clips: list[AudioClip] = field(default_factory=list)
    volume: float = 1.0          # 0-2
    pan: float = 0.5             # 0=left, 1=right
    muted: bool = False
    solo: bool = False
    color: str = "#B0B0B0"
    armed: bool = False           # recording armed
    monitoring: str = "auto"      # "in", "auto", "off"
    input_device: str = ""
    input_channel: int = 0
    # Insert effects chain indices
    inserts: list[int] = field(default_factory=list)
    # Send levels
    sends: dict[int, float] = field(default_factory=dict)  # bus_id → level
    # Takes for comping
    takes: list[AudioClip] = field(default_factory=list)

    def add_clip(self, clip: AudioClip):
        self.clips.append(clip)
        self.clips.sort(key=lambda c: c.start_tick)

    def remove_clip(self, clip: AudioClip):
        if clip in self.clips:
            self.clips.remove(clip)

    @property
    def duration_samples(self) -> int:
        if not self.clips:
            return 0
        return max(c.start_tick + c.duration_samples for c in self.clips)

    def render(self, n_samples: int, start_sample: int = 0,
               bpm: float = 120.0, tpb: int = 480) -> np.ndarray:
        """Render all clips in this track to a buffer."""
        out = np.zeros(n_samples, dtype=np.float32)
        if self.muted:
            return out
        samples_per_tick = (60.0 / bpm) * self.volume / tpb * SAMPLE_RATE
        for clip in self.clips:
            if clip.muted or clip.data is None:
                continue
            clip_start_sample = int(clip.start_tick * samples_per_tick)
            offset = clip_start_sample - start_sample
            mono = clip.get_mono()
            mono = clip.apply_fade(mono) * clip.gain
            if offset >= n_samples or offset + len(mono) <= 0:
                continue
            src_start = max(0, -offset)
            dst_start = max(0, offset)
            length = min(len(mono) - src_start, n_samples - dst_start)
            if length > 0:
                out[dst_start:dst_start + length] += mono[src_start:src_start + length]
        return out * self.volume


# ── Time Stretching (Phase Vocoder) ───────────────────────────────────────

def time_stretch(audio: np.ndarray, ratio: float,
                 fft_size: int = 2048, hop: int = 512) -> np.ndarray:
    """Stretch audio by ratio using phase vocoder. ratio>1 = slower."""
    if abs(ratio - 1.0) < 0.001:
        return audio
    n = len(audio)
    # Analysis
    hop_a = hop
    hop_s = int(hop * ratio)
    window = np.hanning(fft_size).astype(np.float32)
    n_frames = (n - fft_size) // hop_a + 1
    if n_frames < 2:
        return audio

    # STFT
    phases = np.zeros(fft_size // 2 + 1)
    out_len = int(n * ratio) + fft_size
    output = np.zeros(out_len, dtype=np.float32)
    out_window = np.zeros(out_len, dtype=np.float32)

    prev_phase = np.zeros(fft_size // 2 + 1)

    for i in range(n_frames):
        start = i * hop_a
        frame = audio[start:start + fft_size].astype(np.float64) * window
        if len(frame) < fft_size:
            frame = np.pad(frame, (0, fft_size - len(frame)))

        spectrum = np.fft.rfft(frame)
        magnitude = np.abs(spectrum)
        phase = np.angle(spectrum)

        # Phase advance
        if i == 0:
            phases = phase
        else:
            dp = phase - prev_phase
            dp -= np.round(dp / (2 * np.pi)) * 2 * np.pi  # wrap to [-pi, pi]
            freq = dp / hop_a
            phases += freq * hop_s

        prev_phase = phase

        # Reconstruct
        synth = magnitude * np.exp(1j * phases)
        frame_out = np.fft.irfft(synth).astype(np.float32)[:fft_size]

        out_start = i * hop_s
        out_end = out_start + fft_size
        if out_end > out_len:
            break
        output[out_start:out_end] += frame_out * window
        out_window[out_start:out_end] += window ** 2

    # Normalize
    out_window = np.maximum(out_window, 1e-8)
    output /= out_window
    # Trim
    target_len = int(n * ratio)
    return output[:target_len].astype(np.float32)


def pitch_shift(audio: np.ndarray, semitones: float) -> np.ndarray:
    """Shift pitch by semitones using resample + time stretch."""
    if abs(semitones) < 0.01:
        return audio
    ratio = 2.0 ** (semitones / 12.0)
    # Resample
    n = len(audio)
    new_n = int(n / ratio)
    indices = np.linspace(0, n - 1, new_n, dtype=np.float64)
    idx_floor = indices.astype(np.int32)
    frac = (indices - idx_floor).astype(np.float32)
    idx_next = np.minimum(idx_floor + 1, n - 1)
    resampled = audio[idx_floor] * (1 - frac) + audio[idx_next] * frac
    # Time stretch back to original duration
    return time_stretch(resampled, ratio)


# ── File I/O ───────────────────────────────────────────────────────────────

def load_audio_file(filepath: str) -> Optional[AudioClip]:
    """Load WAV/FLAC/MP3 file into an AudioClip."""
    p = Path(filepath).resolve()
    if not p.exists():
        logger.error(f"File not found: {p}")
        return None

    suffix = p.suffix.lower()
    try:
        if suffix == ".wav":
            return _load_wav(str(p))
        elif suffix in (".mp3", ".flac", ".ogg", ".aiff", ".aif"):
            return _load_with_soundfile(str(p))
        else:
            logger.warning(f"Unsupported audio format: {suffix}")
            return None
    except Exception as e:
        logger.error(f"Failed to load audio: {e}")
        return None


def _load_wav(filepath: str) -> AudioClip:
    """Load WAV using standard library."""
    with wave.open(filepath, 'rb') as wf:
        n_channels = wf.getnchannels()
        sample_width = wf.getsampwidth()
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sample_width == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 3:
        # 24-bit
        samples = np.zeros(n_frames * n_channels, dtype=np.float32)
        for i in range(n_frames * n_channels):
            b = raw[i * 3:(i + 1) * 3]
            val = int.from_bytes(b, 'little', signed=True)
            samples[i] = val / 8388608.0
    elif sample_width == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    if n_channels > 1:
        samples = samples.reshape(-1, n_channels)
        # Convert to mono for processing
        mono = samples.mean(axis=1).astype(np.float32)
    else:
        mono = samples

    return AudioClip(
        name=Path(filepath).stem,
        data=mono,
        sample_rate=sr,
        source_path=filepath,
    )


def _load_with_soundfile(filepath: str) -> AudioClip:
    """Load using soundfile library."""
    try:
        import soundfile as sf
        data, sr = sf.read(filepath, dtype='float32')
        if data.ndim == 2:
            data = data.mean(axis=1).astype(np.float32)
        return AudioClip(name=Path(filepath).stem, data=data,
                         sample_rate=sr, source_path=filepath)
    except ImportError:
        logger.error("soundfile not installed — install with: pip install soundfile")
        return AudioClip(name=Path(filepath).stem)


def save_wav(filepath: str, data: np.ndarray, sample_rate: int = SAMPLE_RATE,
             bit_depth: int = 16):
    """Save audio data to WAV file."""
    p = Path(filepath).resolve()
    if data.ndim == 1:
        n_channels = 1
    else:
        n_channels = data.shape[1]
        data = data.flatten()

    if bit_depth == 16:
        int_data = (np.clip(data, -1, 1) * 32767).astype(np.int16)
        sample_width = 2
    elif bit_depth == 24:
        int_data = (np.clip(data, -1, 1) * 8388607).astype(np.int32)
        sample_width = 3
    else:
        int_data = (np.clip(data, -1, 1) * 32767).astype(np.int16)
        sample_width = 2

    with wave.open(str(p), 'wb') as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        if sample_width == 3:
            raw = b''
            for s in int_data:
                raw += int(s).to_bytes(3, 'little', signed=True)
            wf.writeframes(raw)
        else:
            wf.writeframes(int_data.tobytes())


def save_mp3(filepath: str, data: np.ndarray, sample_rate: int = SAMPLE_RATE,
             bitrate: int = 192):
    """Save as MP3 using ffmpeg or lame if available."""
    import subprocess
    import tempfile
    # Save as temp WAV first, then convert
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
        tmp_path = tmp.name
    save_wav(tmp_path, data, sample_rate)
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', tmp_path,
            '-b:a', f'{bitrate}k', str(Path(filepath).resolve())
        ], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.warning("ffmpeg not found — MP3 export unavailable, saved as WAV instead")
        import shutil
        shutil.copy2(tmp_path, str(Path(filepath).resolve().with_suffix('.wav')))
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def export_stems(tracks: list, output_dir: str, bpm: float = 120.0,
                 sample_rate: int = SAMPLE_RATE):
    """Export each track as a separate WAV file."""
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    for i, track in enumerate(tracks):
        if hasattr(track, 'render'):
            audio = track.render(track.duration_samples)
            save_wav(str(out_path / f"{i:02d}_{track.name}.wav"), audio, sample_rate)


# ── Recording Manager ─────────────────────────────────────────────────────

class RecordingManager:
    """Manages real-time audio recording with sounddevice."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = 1,
                 buffer_size: int = BUFFER_SIZE):
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer_size = buffer_size
        self._recording = False
        self._buffers: list[np.ndarray] = []
        self._stream = None
        self._input_device = None
        self._punch_in_sample: Optional[int] = None
        self._punch_out_sample: Optional[int] = None
        self._loop_recording = False
        self._loop_layers: list[np.ndarray] = []
        self._current_position = 0

    @staticmethod
    def get_input_devices() -> list[dict]:
        """List available audio input devices."""
        if not _HAS_SD:
            return []
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev['max_input_channels'] > 0:
                devices.append({
                    'index': i,
                    'name': dev['name'],
                    'channels': dev['max_input_channels'],
                    'sample_rate': dev['default_samplerate'],
                })
        return devices

    @staticmethod
    def get_output_devices() -> list[dict]:
        if not _HAS_SD:
            return []
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev['max_output_channels'] > 0:
                devices.append({
                    'index': i,
                    'name': dev['name'],
                    'channels': dev['max_output_channels'],
                    'sample_rate': dev['default_samplerate'],
                })
        return devices

    def set_input_device(self, device_index: int):
        self._input_device = device_index

    def set_punch_range(self, start_sample: int, end_sample: int):
        """Set punch in/out recording range."""
        self._punch_in_sample = start_sample
        self._punch_out_sample = end_sample

    def clear_punch_range(self):
        self._punch_in_sample = None
        self._punch_out_sample = None

    def start_recording(self, loop: bool = False):
        """Start recording audio from input device."""
        if not _HAS_SD:
            logger.error("sounddevice not available")
            return
        self._recording = True
        self._loop_recording = loop
        self._buffers.clear()
        self._current_position = 0

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning(f"Recording status: {status}")
            if self._recording:
                # Punch in/out check
                if self._punch_in_sample is not None:
                    if self._current_position < self._punch_in_sample:
                        self._current_position += frames
                        return
                    if (self._punch_out_sample is not None and
                            self._current_position > self._punch_out_sample):
                        self._current_position += frames
                        return
                self._buffers.append(indata.copy())
                self._current_position += frames

        try:
            self._stream = sd.InputStream(
                device=self._input_device,
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.buffer_size,
                dtype='float32',
                callback=callback,
            )
            self._stream.start()
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            self._recording = False

    def stop_recording(self) -> Optional[AudioClip]:
        """Stop recording and return the recorded AudioClip."""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._buffers:
            return None

        data = np.concatenate(self._buffers, axis=0)
        if data.ndim == 2 and data.shape[1] == 1:
            data = data.flatten()

        if self._loop_recording:
            self._loop_layers.append(data)
            # Mix all loop layers
            max_len = max(len(l) for l in self._loop_layers)
            mixed = np.zeros(max_len, dtype=np.float32)
            for layer in self._loop_layers:
                mixed[:len(layer)] += layer.flatten()
            data = mixed

        clip = AudioClip(
            name="Recording",
            data=data.astype(np.float32),
            sample_rate=self.sample_rate,
        )
        self._buffers.clear()
        return clip

    def is_recording(self) -> bool:
        return self._recording


# ── Real-time Audio Playback ──────────────────────────────────────────────

class AudioPlaybackEngine:
    """Real-time audio playback using sounddevice."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, buffer_size: int = BUFFER_SIZE):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self._stream = None
        self._playing = False
        self._callback: Optional[Callable] = None
        self._output_device = None

    def set_output_device(self, device_index: int):
        self._output_device = device_index

    def set_callback(self, callback: Callable):
        """Set callback: fn(n_samples) -> np.ndarray (float32)."""
        self._callback = callback

    def start(self):
        if not _HAS_SD or self._callback is None:
            return
        self._playing = True

        def audio_callback(outdata, frames, time_info, status):
            if not self._playing or self._callback is None:
                outdata[:] = 0
                return
            try:
                samples = self._callback(frames)
                if samples is not None and len(samples) >= frames:
                    outdata[:, 0] = samples[:frames]
                    if outdata.shape[1] > 1:
                        outdata[:, 1] = samples[:frames]
                else:
                    outdata[:] = 0
            except Exception:
                outdata[:] = 0

        try:
            self._stream = sd.OutputStream(
                device=self._output_device,
                samplerate=self.sample_rate,
                channels=2,
                blocksize=self.buffer_size,
                dtype='float32',
                callback=audio_callback,
            )
            self._stream.start()
        except Exception as e:
            logger.error(f"Playback start failed: {e}")
            self._playing = False

    def stop(self):
        self._playing = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    @property
    def is_playing(self) -> bool:
        return self._playing


# ── Bounce / Render ───────────────────────────────────────────────────────

def bounce_project(midi_tracks: list, audio_tracks: list[AudioTrack],
                   synth_engine, audio_engine,
                   bpm: float, total_ticks: int, tpb: int = 480,
                   sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Render entire project (MIDI + audio tracks) to a single audio buffer."""
    total_seconds = (total_ticks / tpb) * (60.0 / bpm)
    total_samples = int(total_seconds * sample_rate) + sample_rate  # +1s buffer
    output = np.zeros(total_samples, dtype=np.float32)

    # Render MIDI via synth engine
    if synth_engine and midi_tracks:
        from core.synth_engine import BLOCK_SIZE
        pos = 0
        samples_per_tick = (60.0 / bpm / tpb) * sample_rate
        # Collect all note events sorted by tick
        events = []
        for track in midi_tracks:
            if track.muted:
                continue
            for note in track.notes:
                events.append((note.start_tick, 'on', track.channel, note.pitch, note.velocity))
                events.append((note.end_tick, 'off', track.channel, note.pitch, 0))
        events.sort(key=lambda e: e[0])

        event_idx = 0
        while pos < total_samples:
            block = min(BLOCK_SIZE, total_samples - pos)
            tick = pos / samples_per_tick
            # Process events up to current tick
            while event_idx < len(events) and events[event_idx][0] <= tick:
                ev = events[event_idx]
                if ev[1] == 'on':
                    synth_engine.note_on(ev[2], ev[3], ev[4])
                else:
                    synth_engine.note_off(ev[2], ev[3])
                event_idx += 1
            output[pos:pos + block] += synth_engine.process(block)[:block]
            pos += block

    # Render audio tracks
    for atrack in audio_tracks:
        rendered = atrack.render(total_samples, bpm=bpm, tpb=tpb)
        output[:len(rendered)] += rendered[:total_samples]

    return np.clip(output, -1.0, 1.0)


# ── Audio Settings ────────────────────────────────────────────────────────

@dataclass
class AudioSettings:
    """Audio engine configuration."""
    sample_rate: int = 44100         # 44100, 48000, 96000
    buffer_size: int = 512           # 64, 128, 256, 512, 1024, 2048
    bit_depth: int = 16              # 16, 24, 32
    input_device: int = -1           # -1 = default
    output_device: int = -1          # -1 = default
    input_channels: int = 1
    output_channels: int = 2

    @property
    def latency_ms(self) -> float:
        return (self.buffer_size / self.sample_rate) * 1000

    SAMPLE_RATES = [44100, 48000, 88200, 96000, 176400, 192000]
    BUFFER_SIZES = [64, 128, 256, 512, 1024, 2048, 4096]
    BIT_DEPTHS = [16, 24, 32]
