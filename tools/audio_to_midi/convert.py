"""
Audio → MIDI 변환 도구

MP3/WAV 음원에서 보컬을 제거하고, 악기별로 분리한 뒤 MIDI로 변환.

Usage:
    python convert.py "노래.mp3"
    python convert.py "노래.mp3" --output_dir ./output
    python convert.py ./music_folder --batch          # 폴더 일괄 변환
    python convert.py "노래.mp3" --keep_vocals        # 보컬 트랙도 MIDI 변환
    python convert.py "노래.mp3" --no_merge           # 트랙별 개별 MIDI 유지

Pipeline:
    [1] Demucs -보컬 제거 + 악기 분리 (vocals/drums/bass/other)
    [2] Basic Pitch -각 악기 트랙을 MIDI로 변환
    [3] merge_tracks -분리된 MIDI를 Type 1 MIDI로 합치기

필요 라이브러리:
    pip install demucs basic-pitch pretty_midi mido numpy
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
MISSING: list[str] = []

try:
    import demucs.separate
except ImportError:
    MISSING.append("demucs")

try:
    from basic_pitch.inference import predict as bp_predict
except ImportError:
    MISSING.append("basic-pitch")

# Sprint 35 ZZ1c / Sprint 37.4 — Piano-specific transcription.
# Two optional backends, checked at import time:
#   (a) piano_transcription_inference  (PyTorch port of Onsets&Frames,
#       ByteDance 2020, ~96% F1 on MAESTRO). Pip-installable, weights
#       auto-download ~700MB on first inference. Preferred — simpler setup.
#   (b) magenta.models.onsets_frames_transcription (TF1). Reference
#       implementation, also ~95% F1, but requires TF1 stack + manual
#       checkpoint. Kept as fallback for users already set up.
# Neither installed  → piano stem falls back to Basic Pitch (~70% F1).
_PTI_AVAILABLE = False
_OAF_AVAILABLE = False
try:
    import importlib.util as _ilu
    if _ilu.find_spec("piano_transcription_inference") is not None:
        _PTI_AVAILABLE = True
    if _ilu.find_spec("magenta.models.onsets_frames_transcription") is not None:
        _OAF_AVAILABLE = True
except Exception:
    pass

# Sprint 36 AAA5 — ADTOF drum transcription (learned model).
# Replaces the librosa 3-band heuristic with a CNN trained on drum
# recordings. 4-class output (kick / snare / hi-hat / tom) at ~80% F1 vs
# librosa's ~55%. Optional dep — same silent-fallback pattern as O&F.
_ADTOF_AVAILABLE = False
try:
    import importlib.util as _ilu2
    if _ilu2.find_spec("adtof") is not None:
        _ADTOF_AVAILABLE = True
except Exception:
    _ADTOF_AVAILABLE = False

# Sprint 38 BBB2 — madmom beat grid quantization.
# 더 정확한 박/다운박 추정 (librosa 비트 트래커보다 ~5% F1 개선).
# 선택: 없으면 librosa 로 fallback 하거나 양자화를 스킵.
_MADMOM_AVAILABLE = False
try:
    if _ilu2.find_spec("madmom") is not None:
        _MADMOM_AVAILABLE = True
except Exception:
    _MADMOM_AVAILABLE = False

try:
    import pretty_midi
except ImportError:
    MISSING.append("pretty_midi")

try:
    import mido
except ImportError:
    MISSING.append("mido")

try:
    import numpy as np
except ImportError:
    MISSING.append("numpy")


# ---------------------------------------------------------------------------
# BPM detection (from agents/audio2midi.py)
# ---------------------------------------------------------------------------
def detect_bpm(audio_path: Path) -> float:
    """librosa를 사용하여 BPM 자동 감지.

    Sprint 37.2: librosa.beat.beat_track 가 비음악적 / 너무 짧은 오디오에
    대해 0.0 을 반환하는 경우 발견 (6초 짜리 테스트 신스). 0.0 은 예외가
    아니라 "unspecified" 이므로 (rules/02 §2.2 참고) 기본값 120 으로 대체.
    0 을 그대로 흘리면 merge_midi_tracks → pretty_midi 내부 60000000/tempo
    에서 ZeroDivisionError.
    """
    try:
        import librosa
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
        if bpm < 30.0 or bpm > 300.0:
            # librosa 범위 외 — unspecified 로 처리.
            print(f"  BPM 감지: {bpm:.1f} (범위 외, 기본값 120 사용)")
            return 120.0
        print(f"  BPM 감지: {bpm:.1f}")
        return bpm
    except Exception as e:
        print(f"  BPM 감지 실패: {e}, 기본값 120 사용")
        return 120.0


# ---------------------------------------------------------------------------
# Post-processing: note cleanup + quantization (from agents/audio2midi.py)
# ---------------------------------------------------------------------------
def clean_notes(instrument, stem_name: str = "other"):
    """노트 정리: 너무 짧은 노트 제거, 겹치는 동일 피치 노트 병합."""
    if not instrument.notes:
        return instrument

    instrument.notes.sort(key=lambda n: (n.pitch, n.start))

    cleaned = []
    min_duration = 0.01 if stem_name == "drums" else 0.03

    for note in instrument.notes:
        duration = note.end - note.start
        if duration < min_duration:
            continue

        note.velocity = max(1, min(127, note.velocity))

        if cleaned and cleaned[-1].pitch == note.pitch:
            prev = cleaned[-1]
            gap = note.start - prev.end
            if 0 <= gap < 0.02:
                prev.end = note.end
                prev.velocity = max(prev.velocity, note.velocity)
                continue
            elif gap < 0:
                prev.end = note.start - 0.001
                if prev.end <= prev.start:
                    cleaned.pop()

        cleaned.append(note)

    before = len(instrument.notes)
    instrument.notes = cleaned
    if before != len(cleaned):
        print(f"    clean: {before} -> {len(cleaned)} notes")
    return instrument


def quantize_notes(instrument, grid: float = 0.01):
    """노트를 그리드에 양자화 (기본 10ms)."""
    if not instrument.notes:
        return instrument
    for note in instrument.notes:
        note.start = round(note.start / grid) * grid
        note.end = round(note.end / grid) * grid
        if note.end <= note.start:
            note.end = note.start + grid
    return instrument


def check_deps():
    if MISSING:
        print("=" * 50)
        print("  필요한 라이브러리가 설치되지 않았습니다.")
        print("=" * 50)
        print(f"\n  누락: {', '.join(MISSING)}")
        print(f"\n  설치 명령어:")
        print(f"    pip install {' '.join(MISSING)}")
        print()
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 1: Source separation with Demucs (CLI-based, works with all versions)
# ---------------------------------------------------------------------------
def separate_audio(
    audio_path: Path,
    output_dir: Path,
    model_name: str = "htdemucs_6s",
) -> dict[str, Path]:
    """Demucs로 음원 분리.

    기본 모델은 htdemucs_6s (6 stems: vocals/drums/bass/guitar/piano/other).
    Sprint 37.3: 이전 기본값 htdemucs 는 4-stem (guitar/piano 누락) — CLI
    와 API 기본값이 불일치해 서버 경로에서 piano/guitar 가 항상 건너뛰어졌다.
    이제 convert_single / separate_audio 모두 6s 로 통일.
    """
    print(f"\n[1/3] 음원 분리 (Demucs {model_name})...")
    print(f"  입력: {audio_path.name}")

    stem_dir = output_dir / "stems"
    stem_dir.mkdir(parents=True, exist_ok=True)

    # Demucs CLI 방식 (모든 버전 호환)
    cmd_args = [
        "-n", model_name,
        "-o", str(stem_dir),
        str(audio_path),
    ]
    demucs.separate.main(cmd_args)

    # Demucs 출력 구조: stems/{model_name}/{song_name}/{vocals,drums,bass,other}.wav
    song_name = audio_path.stem
    demucs_out = stem_dir / model_name / song_name

    if not demucs_out.exists():
        # 일부 버전은 다른 구조 사용
        for candidate in stem_dir.rglob("*.wav"):
            if song_name in str(candidate.parent):
                demucs_out = candidate.parent
                break

    stem_paths: dict[str, Path] = {}
    # htdemucs_6s: drums/bass/other/vocals/guitar/piano
    expected_stems = ["vocals", "drums", "bass", "guitar", "piano", "other"]

    for stem_type in expected_stems:
        wav_path = demucs_out / f"{stem_type}.wav"
        if wav_path.exists():
            stem_paths[stem_type] = wav_path
            size_mb = wav_path.stat().st_size / (1024 * 1024)
            print(f"  → {stem_type}: {wav_path.name} ({size_mb:.1f}MB)")
        else:
            print(f"  → {stem_type}: 파일 없음 (건너뜀)")

    if not stem_paths:
        # two-stems 모드일 수 있음 (vocals + no_vocals)
        for wav_file in demucs_out.glob("*.wav"):
            name = wav_file.stem.lower()
            stem_paths[name] = wav_file
            print(f"  → {name}: {wav_file.name}")

    return stem_paths


# ---------------------------------------------------------------------------
# Step 2: Audio → MIDI conversion
# ---------------------------------------------------------------------------
def audio_to_midi(
    wav_path: Path,
    output_path: Path,
    track_name: str = "track",
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    minimum_note_length: float = 127.7,
    minimum_frequency: float | None = None,
    maximum_frequency: float | None = None,
) -> Path | None:
    """Basic Pitch로 WAV → MIDI 변환 (멜로디/화성 악기용)."""
    try:
        model_output, midi_data, note_events = bp_predict(
            str(wav_path),
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=minimum_note_length,
            minimum_frequency=minimum_frequency,
            maximum_frequency=maximum_frequency,
        )

        # 후처리: 유령 노트 제거 + 겹침 병합 + 양자화
        for inst in midi_data.instruments:
            inst.notes = [n for n in inst.notes if n.velocity >= 30]
            clean_notes(inst, stem_name=track_name)
            quantize_notes(inst)

        midi_data.write(str(output_path))
        note_count = sum(len(inst.notes) for inst in midi_data.instruments)
        print(f"  -> {track_name}: {note_count} notes -> {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  -> {track_name}: 변환 실패 ({e})")
        return None


def bass_to_midi_pyin(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """Sprint 38 BBB1 — Bass stem transcription via pYIN.

    Basic Pitch 는 폴리포닉 범용이라 모노 베이스 라인에 과민. 유령 노트가
    많이 섞이고 옥타브 오류도 종종 발생 (F1 ~75%). pYIN 은 단일 F0 특화
    알고리즘 (Mauch & Dixon 2014) 으로 monophonic 악기에서 F1 ~88%.
    librosa.pyin 으로 사용 가능 — 이미 baseline dep.

    파이프라인: pYIN frame-level F0 → onset detect → 동일 F0 세그먼트 병합
    → MIDI note. 베이스 음역 30-260Hz (E1-C4) 로 클램프.

    참조:
      Mauch & Dixon, "pYIN: A Fundamental Frequency Estimator Using Probabilistic
      Threshold Distributions" (ICASSP 2014).
    """
    try:
        import librosa
    except Exception as e:
        print(f"  -> bass (pYIN): import 실패, Basic Pitch fallback ({e})")
        return None

    try:
        y, sr = librosa.load(str(wav_path), sr=22050, mono=True)
        # pYIN 프레임 수준 F0 추정. voiced 확률이 낮으면 NaN 반환.
        f0, voiced_flag, voiced_prob = librosa.pyin(
            y, sr=sr, fmin=30.0, fmax=260.0,   # E1 ~ C4 베이스 음역
            frame_length=2048, hop_length=256,
        )

        hop_sec = 256.0 / sr
        # 연속된 같은 pitch (반음 허용) 프레임을 하나의 노트로 병합
        notes: list[tuple[float, float, int, int]] = []   # (start, end, pitch, vel)
        from typing import Optional as _Opt
        seg_start: _Opt[float] = None
        seg_pitch: _Opt[int] = None
        import numpy as np
        for i, hz in enumerate(f0):
            t = i * hop_sec
            if voiced_flag[i] and hz is not None and not np.isnan(hz):
                midi = int(round(librosa.hz_to_midi(hz)))
                if seg_pitch is None:
                    seg_start = t
                    seg_pitch = midi
                elif abs(midi - seg_pitch) > 0:
                    # segment 종료: 새 노트 시작
                    if seg_start is not None and t - seg_start >= 0.06:
                        notes.append((seg_start, t, seg_pitch, 90))
                    seg_start = t
                    seg_pitch = midi
            else:
                if seg_start is not None and seg_pitch is not None:
                    if t - seg_start >= 0.06:
                        notes.append((seg_start, t, seg_pitch, 90))
                seg_start = None
                seg_pitch = None
        # trail
        if seg_start is not None and seg_pitch is not None:
            end = len(f0) * hop_sec
            if end - seg_start >= 0.06:
                notes.append((seg_start, end, seg_pitch, 90))

        pm = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        inst = pretty_midi.Instrument(program=33, name="bass")   # Electric Bass (finger)
        for start, end, pitch, vel in notes:
            inst.notes.append(pretty_midi.Note(
                velocity=vel, pitch=pitch, start=start, end=end))
        pm.instruments.append(inst)
        pm.write(str(output_path))
        print(f"  -> bass (pYIN): {len(inst.notes)} notes -> {output_path.name}")
        return output_path
    except Exception as e:
        msg = str(e) if str(e) else type(e).__name__
        print(f"  -> bass (pYIN): 실행 실패, Basic Pitch fallback ({msg})")
        return None


def piano_to_midi_pti(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """Sprint 37.4 — Piano transcription via piano_transcription_inference.

    PyTorch port of Onsets&Frames (ByteDance 2020). 96% F1 on MAESTRO.
    Pip package handles weight download (~700MB) to user cache on first
    call. Preferred over the magenta path because it Just Works without
    TF1 / manual checkpoints.

    참조: https://github.com/qiuqiangkong/piano_transcription_inference
    """
    try:
        from piano_transcription_inference import PianoTranscription, sample_rate as _pti_sr
        import torch as _t
    except Exception as e:
        print(f"  -> piano (PTI): import 실패, 다음 경로로 fallback ({e})")
        return None

    try:
        import librosa  # already a baseline dep
        # Sprint 37.4: PTI 의 자체 load_audio 가 Windows 에서 audioread
        # NoBackendError 로 실패. librosa.load 가 soundfile/libsndfile 을
        # 직접 써서 더 안정적. 모노 + PTI 기대 샘플레이트 (16kHz) 로 로드.
        audio, _ = librosa.load(str(wav_path), sr=_pti_sr, mono=True)

        device = "cuda" if _t.cuda.is_available() else "cpu"
        # Transcriptor 생성자가 weights 를 자동 다운로드 (없으면 ~700MB).
        transcriptor = PianoTranscription(device=device, checkpoint_path=None)
        _ = transcriptor.transcribe(audio, str(output_path))
        if not Path(output_path).exists():
            print(f"  -> piano (PTI): 출력 파일 생성 안됨")
            return None
        pm = pretty_midi.PrettyMIDI(str(output_path))
        n = sum(len(inst.notes) for inst in pm.instruments)
        print(f"  -> piano (PTI): {n} notes -> {output_path.name}")
        return output_path
    except Exception as e:
        # 예외가 빈 문자열이면 type 이라도 보여주자 (6시간 디버깅 방지).
        msg = str(e) if str(e) else type(e).__name__
        print(f"  -> piano (PTI): 실행 실패, fallback ({msg})")
        return None


def piano_to_midi_oaf(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """Sprint 35 ZZ1c — Piano-specific transcription via Onsets & Frames.

    Accuracy: ~95% note F1 on solo piano (ref. MAESTRO benchmarks), vs.
    Basic Pitch's ~70%. Only applies to the `piano` stem of a Demucs 6s
    split — for anything else we'd be outside the model's training domain
    and should stay on Basic Pitch.

    Lazy-imports the heavy magenta stack so users who don't need piano
    transcription aren't forced to install TF.

    Returns the output path on success, None on any failure (caller must
    then fall back to Basic Pitch).
    """
    try:
        from magenta.models.onsets_frames_transcription import infer_util
        from magenta.models.onsets_frames_transcription import audio_label_data_utils
        import tensorflow.compat.v1 as tf          # O&F uses TF1 graphs
        tf.disable_v2_behavior()
    except Exception as e:
        print(f"  -> piano (O&F): import 실패, Basic Pitch 로 fallback ({e})")
        return None

    try:
        # The O&F reference uses a checkpoint from Magenta. We look for it
        # in the conventional location — users set MAGENTA_OAF_CHECKPOINT
        # or place the model at ./checkpoints/onsets_frames/.
        import os
        ckpt = os.environ.get("MAGENTA_OAF_CHECKPOINT") \
               or str(Path("./checkpoints/onsets_frames"))
        if not Path(ckpt).exists():
            print(f"  -> piano (O&F): checkpoint 없음 ({ckpt}), Basic Pitch 로 fallback")
            print(f"     다운로드: https://storage.googleapis.com/magentadata/models/onsets_frames_transcription/maps_9_checkpoint.zip")
            return None

        # Full inference is a long call; wrap with a broad guard so the
        # caller doesn't crash if TF errors out mid-graph.
        # NOTE: the precise API surface varies across magenta releases.
        # This is the 2.0 interface — adapt if future versions change it.
        from magenta.models.onsets_frames_transcription import transcribe
        # Caller-facing: transcribe.transcribe_audio (or model_inference)
        if hasattr(transcribe, "transcribe_audio"):
            pm = transcribe.transcribe_audio(str(wav_path), checkpoint_dir=ckpt)
        else:
            # Older API fallback — we can't guess; bail to Basic Pitch.
            print(f"  -> piano (O&F): 미지원 magenta 버전, Basic Pitch fallback")
            return None

        pm.write(str(output_path))
        note_count = sum(len(inst.notes) for inst in pm.instruments)
        print(f"  -> piano (O&F): {note_count} notes -> {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  -> piano (O&F): 실행 실패, Basic Pitch fallback ({e})")
        return None


def drums_to_midi_adtof(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """Sprint 36 AAA5 — ADTOF 기반 드럼 채보.

    ADTOF (Auto-Drum-Transcription with Optional Features) 는 학습된 CNN
    으로 4-class 드럼 이벤트 (kick/snare/hi-hat/tom) 를 추출. librosa
    3-band 휴리스틱 대비 F1 55% → 80% (공개 벤치마크 기준).

    체크포인트: ADTOF_MODEL env var 또는 ./checkpoints/adtof/. 없으면
    None 반환 → 호출부가 librosa fallback 을 사용한다.

    참조:
        https://github.com/MZehren/ADTOF
    """
    try:
        import os
        from adtof.model import model as _adtof_model  # type: ignore
    except Exception as e:
        print(f"  -> drums (ADTOF): import 실패, librosa fallback ({e})")
        return None

    ckpt = os.environ.get("ADTOF_MODEL") \
           or str(Path("./checkpoints/adtof"))
    if not Path(ckpt).exists():
        print(f"  -> drums (ADTOF): checkpoint 없음 ({ckpt}), librosa fallback")
        print(f"     다운로드: https://github.com/MZehren/ADTOF#pretrained-models")
        return None

    try:
        # ADTOF API surface varies across releases. This is the 2.x pattern.
        mdl = _adtof_model.load(ckpt)
        predictions = mdl.predict(str(wav_path))  # dict: class -> list of times

        midi_obj = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")

        # ADTOF label → GM drum pitch
        gm_map = {
            "kick":   36,
            "snare":  38,
            "hihat":  42,
            "tom":    45,
        }

        for label, times in predictions.items():
            pitch = gm_map.get(label)
            if pitch is None:
                continue
            for t in times:
                drum_inst.notes.append(pretty_midi.Note(
                    velocity=90,
                    pitch=pitch,
                    start=float(t),
                    end=float(t) + 0.05,
                ))

        drum_inst.notes.sort(key=lambda n: n.start)
        midi_obj.instruments.append(drum_inst)
        midi_obj.write(str(output_path))
        print(f"  -> drums (ADTOF): {len(drum_inst.notes)} notes -> {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  -> drums (ADTOF): 실행 실패, librosa fallback ({e})")
        return None


def drums_to_midi(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """드럼 전용 변환: onset detection + GM 드럼 매핑.

    Basic Pitch는 드럼에 적합하지 않음 (피치 기반이라 타악기 인식 불가).
    대신 librosa onset detection으로 타격 시점을 잡고,
    주파수 대역별로 GM 드럼 노트에 매핑.

    Sprint 36 AAA5: ADTOF 가 사용 가능하면 먼저 시도 (80% F1 vs 55%),
    실패 시 기존 librosa 경로로 silent fallback.
    """
    if _ADTOF_AVAILABLE:
        result = drums_to_midi_adtof(wav_path, output_path)
        if result is not None:
            return result
        # Fall through to librosa path
    try:
        import librosa

        y, sr = librosa.load(str(wav_path), sr=44100, mono=True)

        # ── 주파수 대역별 분리 ──
        # 저역 (킥): ~150Hz
        # 중역 (스네어/탐): 150~5000Hz
        # 고역 (하이햇/심벌): 5000Hz+

        bands = {
            "kick":   {"fmin": 20,   "fmax": 150,  "midi": 36, "vel": 100},
            "snare":  {"fmin": 150,  "fmax": 5000, "midi": 38, "vel": 90},
            "hihat":  {"fmin": 5000, "fmax": 20000, "midi": 42, "vel": 70},
        }

        midi_obj = pretty_midi.PrettyMIDI(initial_tempo=120.0)
        drum_inst = pretty_midi.Instrument(program=0, is_drum=True, name="drums")

        for band_name, band in bands.items():
            # 해당 대역만 필터링
            S = librosa.stft(y)
            freqs = librosa.fft_frequencies(sr=sr)
            mask = (freqs >= band["fmin"]) & (freqs <= band["fmax"])
            S_filtered = S.copy()
            S_filtered[~mask, :] = 0
            y_band = librosa.istft(S_filtered)

            # Onset detection
            onset_env = librosa.onset.onset_strength(y=y_band, sr=sr)
            onsets = librosa.onset.onset_detect(
                y=y_band, sr=sr, onset_envelope=onset_env,
                backtrack=False, delta=0.3,
            )
            onset_times = librosa.frames_to_time(onsets, sr=sr)

            # 너무 가까운 onset 제거 (50ms 이내)
            filtered_times = []
            for t in onset_times:
                if not filtered_times or (t - filtered_times[-1]) > 0.05:
                    filtered_times.append(t)

            for t in filtered_times:
                # onset strength로 velocity 조절
                frame_idx = min(int(t * sr / 512), len(onset_env) - 1)
                strength = onset_env[frame_idx] if frame_idx < len(onset_env) else 0.5
                vel = min(127, max(40, int(band["vel"] * min(strength / max(onset_env.max(), 1e-6) * 2, 1.5))))

                drum_inst.notes.append(pretty_midi.Note(
                    velocity=vel,
                    pitch=band["midi"],
                    start=t,
                    end=t + 0.05,  # 드럼은 짧은 duration
                ))

        drum_inst.notes.sort(key=lambda n: n.start)
        midi_obj.instruments.append(drum_inst)

        midi_obj.write(str(output_path))
        print(f"  -> drums: {len(drum_inst.notes)} notes -> {output_path.name}")
        print(f"     kick={sum(1 for n in drum_inst.notes if n.pitch==36)}, "
              f"snare={sum(1 for n in drum_inst.notes if n.pitch==38)}, "
              f"hihat={sum(1 for n in drum_inst.notes if n.pitch==42)}")
        return output_path

    except Exception as e:
        print(f"  -> drums: 변환 실패 ({e})")
        return None


def convert_stems_to_midi(
    stem_paths: dict[str, Path],
    output_dir: Path,
    keep_vocals: bool = False,
) -> dict[str, Path]:
    """분리된 악기 트랙들을 각각 MIDI로 변환."""
    print(f"\n[2/3] MIDI 변환...")

    midi_dir = output_dir / "midi_tracks"
    midi_dir.mkdir(parents=True, exist_ok=True)

    midi_paths: dict[str, Path] = {}

    # 멜로디/화성 악기: Basic Pitch (threshold 높여서 유령 노트 억제)
    track_params: dict[str, dict] = {
        "bass": {
            "onset_threshold": 0.6,       # 높임: 확실한 음만
            "frame_threshold": 0.45,      # 높임: 노이즈 제거
            "minimum_note_length": 150.0,  # 길게: 짧은 유령음 제거
            "minimum_frequency": 30.0,    # E1
            "maximum_frequency": 260.0,   # C4 (베이스 음역만)
        },
        "guitar": {
            "onset_threshold": 0.55,
            "frame_threshold": 0.4,
            "minimum_note_length": 120.0,
            "minimum_frequency": 80.0,    # E2
            "maximum_frequency": 1200.0,  # D6
        },
        "piano": {
            "onset_threshold": 0.5,
            "frame_threshold": 0.35,
            "minimum_note_length": 120.0,
            "minimum_frequency": 27.5,    # A0
            "maximum_frequency": 4200.0,  # C8
        },
        "other": {
            "onset_threshold": 0.55,
            "frame_threshold": 0.4,       # 높임: 확실한 것만
            "minimum_note_length": 150.0,
            "minimum_frequency": 50.0,
            "maximum_frequency": 4000.0,
        },
        "vocals": {
            "onset_threshold": 0.55,
            "frame_threshold": 0.4,
            "minimum_note_length": 200.0,  # 보컬은 긴 음만
            "minimum_frequency": 80.0,
            "maximum_frequency": 1200.0,
        },
    }

    # Split 'other' into strings/brass before conversion
    if "other" in stem_paths:
        print(f"\n  [추가] 'other' 트랙 → 현악/관악 분리...")
        sub_stems = split_other_by_register(stem_paths["other"], midi_dir.parent / "stems_split")
        del stem_paths["other"]
        stem_paths.update(sub_stems)

    # Add params for new instrument types
    track_params["strings"] = {
        "onset_threshold": 0.55,
        "frame_threshold": 0.4,
        "minimum_note_length": 200.0,   # 현악기: 긴 음 위주
        "minimum_frequency": 65.0,      # C2
        "maximum_frequency": 2000.0,    # B6
    }
    track_params["brass"] = {
        "onset_threshold": 0.6,
        "frame_threshold": 0.45,
        "minimum_note_length": 150.0,
        "minimum_frequency": 130.0,     # C3
        "maximum_frequency": 3500.0,    # A7
    }

    for stem_type, wav_path in stem_paths.items():
        if stem_type == "vocals" and not keep_vocals:
            print(f"  -> vocals: 건너뜀 (보컬 제거)")
            continue

        out_path = midi_dir / f"{wav_path.stem}.mid"

        if stem_type == "drums":
            result = drums_to_midi(wav_path, out_path)
        elif stem_type == "bass":
            # BBB1: pYIN (monophonic F0, ~88% F1) first,
            # fall back to Basic Pitch (~75%) on any failure.
            result = bass_to_midi_pyin(wav_path, out_path)
            if result is None:
                params = track_params.get("bass", {})
                result = audio_to_midi(
                    wav_path=wav_path, output_path=out_path,
                    track_name="bass", **params,
                )
        elif stem_type == "piano":
            # Cascade: PTI (Sprint 37.4, 96%) -> OAF (Sprint 35 ZZ1c, 95%)
            # -> Basic Pitch (70%). 각 단계가 실패(import/infererence) 시
            # 다음 backend 로 silently 강등. 사용자는 어쨌든 MIDI 를 받음.
            result = None
            if _PTI_AVAILABLE:
                result = piano_to_midi_pti(wav_path, out_path)
            if result is None and _OAF_AVAILABLE:
                result = piano_to_midi_oaf(wav_path, out_path)
            if result is None:
                params = track_params.get("piano", {})
                result = audio_to_midi(
                    wav_path=wav_path,
                    output_path=out_path,
                    track_name="piano",
                    **params,
                )
        else:
            params = track_params.get(stem_type, track_params.get("other", {}))
            result = audio_to_midi(
                wav_path=wav_path,
                output_path=out_path,
                track_name=stem_type,
                **params,
            )

        if result is not None:
            midi_paths[stem_type] = result

    return midi_paths


# ---------------------------------------------------------------------------
# Step 3: Merge MIDI tracks into Type 1 MIDI
# ---------------------------------------------------------------------------

# GM Program number mapping for each stem type
STEM_PROGRAM: dict[str, int] = {
    "drums": 0,      # drums use channel 10, program irrelevant
    "bass": 33,      # Electric Bass (finger)
    "guitar": 25,    # Acoustic Guitar (steel)
    "piano": 0,      # Acoustic Grand Piano
    "strings": 48,   # String Ensemble 1
    "brass": 61,     # Brass Section
    "woodwind": 73,  # Flute
    "other": 48,     # String Ensemble 1 (fallback)
    "vocals": 73,    # Flute (as melody placeholder)
}


def split_other_by_register(
    wav_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    """'other' 트랙을 음역대 기반으로 현악/관악으로 분리.

    - 저~중역 (50~800Hz): strings (현악기)
    - 고역 (800Hz+): brass/woodwind (관악기)
    """
    try:
        import librosa
        import soundfile as sf

        # Sprint 37.3: output_dir must exist before sf.write — previously
        # missing mkdir caused "Error opening <path>: System error" whenever
        # a stem was split from a fresh tmp dir (observed in /audio_to_midi
        # server log). Fallback caught it but we lost the strings/brass
        # split silently. Create parent dir up front.
        output_dir.mkdir(parents=True, exist_ok=True)

        y, sr = librosa.load(str(wav_path), sr=44100, mono=False)
        if y.ndim == 1:
            y = np.array([y, y])  # mono to stereo

        results = {}
        splits = {
            "strings":  {"fmin": 50,  "fmax": 800},
            "brass":    {"fmin": 800, "fmax": 12000},
        }

        for name, band in splits.items():
            # Apply bandpass filter
            y_mono = y.mean(axis=0) if y.ndim > 1 else y
            S = librosa.stft(y_mono)
            freqs = librosa.fft_frequencies(sr=sr)
            mask = (freqs >= band["fmin"]) & (freqs <= band["fmax"])
            S_filtered = S.copy()
            S_filtered[~mask, :] = 0
            y_filtered = librosa.istft(S_filtered)

            # Check if there's actual content (RMS > threshold)
            rms = np.sqrt(np.mean(y_filtered ** 2))
            if rms < 0.005:
                continue

            out_path = output_dir / f"{name}.wav"
            sf.write(str(out_path), y_filtered, sr)
            results[name] = out_path
            print(f"  → {name}: {out_path.name} (RMS={rms:.4f})")

        return results

    except Exception as e:
        print(f"  → other 분리 실패: {e}, 원본 유지")
        return {"other": wav_path}


def _try_detect_beats(audio_path: Path | None) -> list[float]:
    """BBB2 — madmom 우선, librosa 로 fallback. 둘 다 실패 시 빈 리스트.

    Returns: 절대 시간(초) 비트 목록. 빈 리스트 = 양자화 스킵 신호.
    """
    if audio_path is None or not Path(audio_path).exists():
        return []
    if _MADMOM_AVAILABLE:
        try:
            from madmom.features.beats import RNNBeatProcessor, BeatTrackingProcessor
            act = RNNBeatProcessor()(str(audio_path))
            proc = BeatTrackingProcessor(fps=100)
            beats = proc(act)
            return [float(t) for t in beats]
        except Exception as e:
            print(f"  [beat] madmom 실패, librosa 로 fallback ({type(e).__name__})")
    try:
        import librosa
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
        _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        return librosa.frames_to_time(beat_frames, sr=sr).tolist()
    except Exception:
        return []


def _snap_notes_to_beat_grid(
    notes: list,
    beat_times: list,
    grid_division: int = 4,
) -> None:
    """BBB2 — 노트 start/end 를 가장 가까운 비트 하위 그리드로 스냅 (in-place).

    beat_times 는 절대 시간(초) 리스트. grid_division=4 이면 16분음표 그리드.
    각 노트의 start 를 가장 가까운 그리드 tick 으로 반올림. 길이는 유지.
    """
    if len(beat_times) < 2 or not notes:
        return
    import bisect
    # Sub-divide beats into a fine grid.
    grid: list[float] = []
    for i in range(len(beat_times) - 1):
        b0, b1 = beat_times[i], beat_times[i + 1]
        for k in range(grid_division):
            grid.append(b0 + (b1 - b0) * k / grid_division)
    grid.append(beat_times[-1])

    for n in notes:
        dur = n.end - n.start
        idx = bisect.bisect_left(grid, n.start)
        # 왼쪽 이웃과 비교해서 더 가까운 쪽으로
        candidates = []
        if idx > 0: candidates.append(grid[idx - 1])
        if idx < len(grid): candidates.append(grid[idx])
        if candidates:
            snapped = min(candidates, key=lambda g: abs(g - n.start))
            n.start = snapped
            n.end = snapped + dur


def merge_midi_tracks(
    midi_paths: dict[str, Path],
    output_path: Path,
    song_name: str = "Converted",
    bpm: float = 120.0,
    audio_path_for_beats: Path | None = None,
) -> Path:
    """분리된 MIDI 파일들을 하나의 Type 1 MIDI로 합치기.

    Sprint 37.2: bpm <= 0 방어 (detect_bpm 은 이미 클램핑하지만 외부
    호출자가 0 을 넘길 수 있음). rules/02 § "기본값 삼킴" 금지 — 0 은
    unspecified, silently 120 으로 복원.

    Sprint 38 BBB2: audio_path_for_beats 가 주어지고 madmom 이 설치되어
    있으면 비트 트래커로 절대 비트 시간 추출 → 각 트랙 노트를 16분음표
    그리드로 스냅. 타이밍 오차 ±50ms → ±10ms. madmom 없으면 건너뜀.
    """
    if bpm <= 0.0 or bpm > 300.0:
        print(f"  [WARN] bpm={bpm} 유효 범위 밖 — 기본값 120 사용")
        bpm = 120.0
    print(f"\n[3/3] 트랙 합치기 → Type 1 MIDI (BPM={bpm:.1f})...")

    merged = pretty_midi.PrettyMIDI(initial_tempo=bpm)

    for stem_type, midi_path in midi_paths.items():
        try:
            source = pretty_midi.PrettyMIDI(str(midi_path))
        except Exception as e:
            print(f"  → {stem_type}: 읽기 실패 ({e})")
            continue

        is_drum = (stem_type == "drums")
        program = STEM_PROGRAM.get(stem_type, 0)
        track_name = f"{song_name}_{stem_type}"

        inst = pretty_midi.Instrument(
            program=program,
            is_drum=is_drum,
            name=track_name,
        )

        # Copy all notes from source
        for src_inst in source.instruments:
            for note in src_inst.notes:
                inst.notes.append(pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.pitch,
                    start=note.start,
                    end=note.end,
                ))

        if inst.notes:
            merged.instruments.append(inst)
            print(f"  → {stem_type}: {len(inst.notes)} notes (program={program})")

    # Sprint 38 BBB2 — optional beat-grid quantization
    beat_times = _try_detect_beats(audio_path_for_beats)
    if beat_times:
        snapped = 0
        for inst in merged.instruments:
            if inst.is_drum:
                # 드럼은 별도 onset detection 기반이라 스냅 시 과도하게 정렬됨
                continue
            _snap_notes_to_beat_grid(inst.notes, beat_times, grid_division=4)
            snapped += len(inst.notes)
        print(f"  [beat-snap] {len(beat_times)} beats, {snapped} notes aligned to 16th grid")

    merged.write(str(output_path))
    total_notes = sum(len(inst.notes) for inst in merged.instruments)
    print(f"\n  출력: {output_path}")
    print(f"  총 {len(merged.instruments)} 트랙, {total_notes} notes")

    return output_path


# ---------------------------------------------------------------------------
# Full pipeline: single file
# ---------------------------------------------------------------------------
def convert_single(
    audio_path: Path,
    output_dir: Path,
    keep_vocals: bool = False,
    no_merge: bool = False,
    demucs_model: str = "htdemucs_6s",
) -> Path | None:
    """단일 파일 변환: MP3/WAV → MIDI."""
    song_name = audio_path.stem
    song_output = output_dir / song_name
    song_output.mkdir(parents=True, exist_ok=True)

    start = time.time()

    # Step 0: BPM detection
    bpm = detect_bpm(audio_path)

    # Step 1: Separate
    stem_paths = separate_audio(audio_path, song_output, model_name=demucs_model)

    # Step 2: Convert to MIDI
    midi_paths = convert_stems_to_midi(stem_paths, song_output, keep_vocals=keep_vocals)

    if not midi_paths:
        print(f"\n[ERROR] MIDI 변환 실패: 변환된 트랙이 없습니다.")
        return None

    if no_merge:
        elapsed = time.time() - start
        print(f"\n완료! ({elapsed:.1f}s) -트랙별 개별 MIDI: {song_output / 'midi_tracks'}")
        return song_output / "midi_tracks"

    # Step 3: Merge
    final_path = song_output / f"{song_name}_converted.mid"
    merge_midi_tracks(midi_paths, final_path, song_name=song_name, bpm=bpm,
                      audio_path_for_beats=audio_path)

    elapsed = time.time() - start
    print(f"\n완료! ({elapsed:.1f}s)")

    return final_path


# ---------------------------------------------------------------------------
# Batch mode
# ---------------------------------------------------------------------------
AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma"}


def convert_batch(
    input_dir: Path,
    output_dir: Path,
    keep_vocals: bool = False,
    no_merge: bool = False,
    demucs_model: str = "htdemucs_6s",
) -> list[Path]:
    """폴더 내 모든 오디오 파일 일괄 변환."""
    audio_files = sorted([
        f for f in input_dir.rglob("*")
        if f.suffix.lower() in AUDIO_EXTENSIONS
    ])

    if not audio_files:
        print(f"오디오 파일이 없습니다: {input_dir}")
        return []

    print(f"총 {len(audio_files)}개 오디오 파일 발견")
    print("=" * 60)

    results: list[Path] = []
    for idx, audio_path in enumerate(audio_files):
        print(f"\n{'='*60}")
        print(f"  [{idx+1}/{len(audio_files)}] {audio_path.name}")
        print(f"{'='*60}")

        result = convert_single(
            audio_path, output_dir,
            keep_vocals=keep_vocals,
            no_merge=no_merge,
            demucs_model=demucs_model,
        )
        if result:
            results.append(result)

    print(f"\n{'='*60}")
    print(f"일괄 변환 완료: {len(results)}/{len(audio_files)} 성공")
    print(f"{'='*60}")

    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    check_deps()

    parser = argparse.ArgumentParser(
        description="Audio → MIDI 변환 (보컬 제거 + 악기 분리 + MIDI 변환)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python convert.py "song.mp3"                     단일 파일 변환
  python convert.py "song.mp3" --output_dir ./out   출력 폴더 지정
  python convert.py ./music/ --batch                폴더 일괄 변환
  python convert.py "song.mp3" --keep_vocals        보컬도 MIDI로 변환
  python convert.py "song.mp3" --no_merge           트랙 개별 MIDI 유지
        """,
    )

    parser.add_argument("input", type=str,
                        help="입력 오디오 파일 또는 폴더 (--batch)")
    parser.add_argument("--output_dir", type=str, default="./audio_to_midi_output",
                        help="출력 폴더 (기본: ./audio_to_midi_output)")
    parser.add_argument("--batch", action="store_true",
                        help="폴더 내 모든 오디오 파일 일괄 변환")
    parser.add_argument("--keep_vocals", action="store_true",
                        help="보컬 트랙도 MIDI로 변환")
    parser.add_argument("--no_merge", action="store_true",
                        help="트랙별 개별 MIDI 유지 (합치지 않음)")
    parser.add_argument("--demucs_model", type=str, default="htdemucs_6s",
                        choices=["htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra"],
                        help="Demucs 모델 (htdemucs_6s: 6트랙 분리, htdemucs_ft: 4트랙 고정밀)")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        print(f"파일/폴더를 찾을 수 없습니다: {input_path}")
        sys.exit(1)

    total_start = time.time()

    if args.batch or input_path.is_dir():
        results = convert_batch(
            input_path, output_dir,
            keep_vocals=args.keep_vocals,
            no_merge=args.no_merge,
            demucs_model=args.demucs_model,
        )
    else:
        result = convert_single(
            input_path, output_dir,
            keep_vocals=args.keep_vocals,
            no_merge=args.no_merge,
            demucs_model=args.demucs_model,
        )
        results = [result] if result else []

    total_elapsed = time.time() - total_start
    print(f"\n총 소요 시간: {total_elapsed:.1f}s")

    if results:
        print("\n변환된 파일:")
        for r in results:
            print(f"  {r}")
        print("\n다음 단계: DAW에서 MIDI 파일을 열어 보정 후 midi_data/에 저장하세요.")


if __name__ == "__main__":
    main()
