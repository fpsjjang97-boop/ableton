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
    [1] Demucs — 보컬 제거 + 악기 분리 (vocals/drums/bass/other)
    [2] Basic Pitch — 각 악기 트랙을 MIDI로 변환
    [3] merge_tracks — 분리된 MIDI를 Type 1 MIDI로 합치기

필요 라이브러리:
    pip install demucs basic-pitch pretty_midi mido numpy
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
MISSING: list[str] = []

try:
    import demucs.api
except ImportError:
    MISSING.append("demucs")

try:
    from basic_pitch.inference import predict as bp_predict
    from basic_pitch import ICASSP_2022_MODEL_PATH
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
# Step 1: Source separation with Demucs
# ---------------------------------------------------------------------------
def separate_audio(
    audio_path: Path,
    output_dir: Path,
    model_name: str = "htdemucs",
) -> dict[str, Path]:
    """Demucs로 음원 분리. vocals/drums/bass/other 4트랙 반환."""
    print(f"\n[1/3] 음원 분리 (Demucs {model_name})...")
    print(f"  입력: {audio_path.name}")

    separator = demucs.api.Separator(model=model_name)
    _, separated = separator.separate_audio_file(str(audio_path))

    stem_dir = output_dir / "stems"
    stem_dir.mkdir(parents=True, exist_ok=True)

    stem_paths: dict[str, Path] = {}
    stem_name = audio_path.stem

    for stem_type, waveform in separated.items():
        out_path = stem_dir / f"{stem_name}_{stem_type}.wav"
        # Demucs API returns tensor, save via torchaudio
        import torchaudio
        torchaudio.save(str(out_path), waveform.cpu(), sample_rate=44100)
        stem_paths[stem_type] = out_path
        print(f"  → {stem_type}: {out_path.name}")

    return stem_paths


# ---------------------------------------------------------------------------
# Step 2: Audio → MIDI with Basic Pitch
# ---------------------------------------------------------------------------
def audio_to_midi(
    wav_path: Path,
    output_path: Path,
    track_name: str = "track",
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_length: float = 58.0,
    min_freq: float | None = None,
    max_freq: float | None = None,
) -> Path | None:
    """Basic Pitch로 WAV → MIDI 변환."""
    try:
        model_output, midi_data, note_events = bp_predict(
            str(wav_path),
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_length,
            minimum_frequency=min_freq,
            maximum_frequency=max_freq,
        )

        midi_data.write(str(output_path))
        note_count = sum(len(inst.notes) for inst in midi_data.instruments)
        print(f"  → {track_name}: {note_count} notes → {output_path.name}")
        return output_path

    except Exception as e:
        print(f"  → {track_name}: 변환 실패 ({e})")
        return None


def convert_stems_to_midi(
    stem_paths: dict[str, Path],
    output_dir: Path,
    keep_vocals: bool = False,
) -> dict[str, Path]:
    """분리된 악기 트랙들을 각각 MIDI로 변환."""
    print(f"\n[2/3] MIDI 변환 (Basic Pitch)...")

    midi_dir = output_dir / "midi_tracks"
    midi_dir.mkdir(parents=True, exist_ok=True)

    midi_paths: dict[str, Path] = {}

    # 트랙별 최적화된 파라미터
    track_params: dict[str, dict] = {
        "drums": {
            "onset_threshold": 0.6,
            "frame_threshold": 0.4,
            "min_note_length": 30.0,
            # 드럼은 주파수 제한 없음 (GM 매핑이라 피치가 악기)
        },
        "bass": {
            "onset_threshold": 0.5,
            "frame_threshold": 0.3,
            "min_note_length": 58.0,
            "min_freq": 30.0,    # E1 근처
            "max_freq": 300.0,   # D4 근처
        },
        "other": {
            "onset_threshold": 0.45,
            "frame_threshold": 0.25,
            "min_note_length": 58.0,
        },
        "vocals": {
            "onset_threshold": 0.5,
            "frame_threshold": 0.3,
            "min_note_length": 80.0,
            "min_freq": 80.0,    # E2
            "max_freq": 1200.0,  # D6
        },
    }

    for stem_type, wav_path in stem_paths.items():
        if stem_type == "vocals" and not keep_vocals:
            print(f"  → vocals: 건너뜀 (보컬 제거)")
            continue

        out_path = midi_dir / f"{wav_path.stem}.mid"
        params = track_params.get(stem_type, {})

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
    "drums": 0,     # drums use channel 10, program irrelevant
    "bass": 33,     # Electric Bass (finger)
    "other": 0,     # Acoustic Grand Piano
    "vocals": 73,   # Flute (as melody placeholder)
}

STEM_CHANNEL: dict[str, int] = {
    "drums": 9,     # GM standard: channel 10 (0-indexed = 9)
    "bass": 1,
    "other": 0,
    "vocals": 2,
}


def merge_midi_tracks(
    midi_paths: dict[str, Path],
    output_path: Path,
    song_name: str = "Converted",
) -> Path:
    """분리된 MIDI 파일들을 하나의 Type 1 MIDI로 합치기."""
    print(f"\n[3/3] 트랙 합치기 → Type 1 MIDI...")

    merged = pretty_midi.PrettyMIDI(initial_tempo=120.0)

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

    # Step 1: Separate
    stem_paths = separate_audio(audio_path, song_output, model_name=demucs_model)

    # Step 2: Convert to MIDI
    midi_paths = convert_stems_to_midi(stem_paths, song_output, keep_vocals=keep_vocals)

    if not midi_paths:
        print(f"\n[ERROR] MIDI 변환 실패: 변환된 트랙이 없습니다.")
        return None

    if no_merge:
        elapsed = time.time() - start
        print(f"\n완료! ({elapsed:.1f}s) — 트랙별 개별 MIDI: {song_output / 'midi_tracks'}")
        return song_output / "midi_tracks"

    # Step 3: Merge
    final_path = song_output / f"{song_name}_converted.mid"
    merge_midi_tracks(midi_paths, final_path, song_name=song_name)

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
    parser.add_argument("--demucs_model", type=str, default="htdemucs",
                        choices=["htdemucs", "htdemucs_ft", "mdx_extra"],
                        help="Demucs 모델 (htdemucs_ft가 가장 정확, 느림)")

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
