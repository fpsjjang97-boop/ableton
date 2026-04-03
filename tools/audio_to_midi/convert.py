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
    """librosa를 사용하여 BPM 자동 감지."""
    try:
        import librosa
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
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
    model_name: str = "htdemucs",
) -> dict[str, Path]:
    """Demucs로 음원 분리. vocals/drums/bass/other 4트랙 반환."""
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


def drums_to_midi(
    wav_path: Path,
    output_path: Path,
) -> Path | None:
    """드럼 전용 변환: onset detection + GM 드럼 매핑.

    Basic Pitch는 드럼에 적합하지 않음 (피치 기반이라 타악기 인식 불가).
    대신 librosa onset detection으로 타격 시점을 잡고,
    주파수 대역별로 GM 드럼 노트에 매핑.
    """
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


def merge_midi_tracks(
    midi_paths: dict[str, Path],
    output_path: Path,
    song_name: str = "Converted",
    bpm: float = 120.0,
) -> Path:
    """분리된 MIDI 파일들을 하나의 Type 1 MIDI로 합치기."""
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
    demucs_model: str = "htdemucs",
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
    merge_midi_tracks(midi_paths, final_path, song_name=song_name, bpm=bpm)

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
    demucs_model: str = "htdemucs",
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
