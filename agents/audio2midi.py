#!/usr/bin/env python3
"""
Audio-to-MIDI High-Accuracy Converter
======================================
WAV/MP3 → MIDI 변환 파이프라인 (목표 정확도: 95%+)

파이프라인:
  1. Meta Demucs v4 (htdemucs_ft) → 악기별 소스 분리 (vocals, drums, bass, other)
  2. Spotify Basic Pitch → 각 분리 트랙을 MIDI로 변환
  3. 후처리 → 트랙 병합, 노트 정리, GM 악기 매핑
  4. 최종 MIDI 파일 출력

사용법:
  python audio2midi.py input.wav -o output.mid
  python audio2midi.py input.mp3 -o output.mid --model htdemucs_ft
"""

import argparse
import os
import sys
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pretty_midi
import mido


# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────

# Demucs 모델 옵션:
#   htdemucs      - 기본 Hybrid Transformer (빠름)
#   htdemucs_ft   - fine-tuned 버전 (더 높은 정확도, 느림)
#   htdemucs_6s   - 6-stem 분리 (vocals, drums, bass, guitar, piano, other)
DEFAULT_DEMUCS_MODEL = "htdemucs_ft"

# Basic Pitch 파라미터 (정확도 최적화)
BASIC_PITCH_PARAMS = {
    "onset_threshold": 0.5,       # 노트 온셋 감도 (낮을수록 민감)
    "frame_threshold": 0.3,       # 프레임 활성화 임계값
    "minimum_note_length": 58,    # 최소 노트 길이 (ms)
    "minimum_frequency": 32.7,    # 최저 주파수 (C1)
    "maximum_frequency": 4186.0,  # 최고 주파수 (C8)
}

# 악기별 GM MIDI 프로그램 매핑
STEM_TO_GM = {
    "vocals":  0,    # Acoustic Grand Piano (보컬 → 피아노로 대체)
    "bass":    33,   # Electric Bass (finger)
    "drums":   0,    # Channel 10 (GM 드럼)
    "guitar":  25,   # Acoustic Guitar (steel)
    "piano":   0,    # Acoustic Grand Piano
    "other":   48,   # String Ensemble 1
}

# 악기별 Basic Pitch 최적화 파라미터
STEM_PARAMS = {
    "vocals": {
        "onset_threshold": 0.45,
        "frame_threshold": 0.28,
        "minimum_note_length": 80,
        "minimum_frequency": 80.0,    # 보컬 범위
        "maximum_frequency": 1100.0,
    },
    "bass": {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 80,
        "minimum_frequency": 30.0,    # 베이스 범위
        "maximum_frequency": 400.0,
    },
    "drums": {
        "onset_threshold": 0.4,
        "frame_threshold": 0.25,
        "minimum_note_length": 30,    # 드럼은 짧은 노트
        "minimum_frequency": 30.0,
        "maximum_frequency": 4186.0,
    },
    "guitar": {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 50,
        "minimum_frequency": 80.0,
        "maximum_frequency": 1200.0,
    },
    "piano": {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 50,
        "minimum_frequency": 27.5,    # A0
        "maximum_frequency": 4186.0,  # C8
    },
    "other": {
        "onset_threshold": 0.5,
        "frame_threshold": 0.3,
        "minimum_note_length": 58,
        "minimum_frequency": 32.7,
        "maximum_frequency": 4186.0,
    },
}


def print_step(step_num, total, msg):
    """진행 상태 출력"""
    print(f"\n{'='*60}")
    print(f"  [{step_num}/{total}] {msg}")
    print(f"{'='*60}")


# ──────────────────────────────────────────────
# Step 1: Demucs 소스 분리
# ──────────────────────────────────────────────

def separate_stems(input_path: str, output_dir: str, model: str = DEFAULT_DEMUCS_MODEL) -> dict:
    """
    Demucs를 사용하여 오디오를 악기별 스템으로 분리

    Returns:
        dict: {stem_name: wav_path} 매핑
    """
    print_step(1, 4, f"Demucs 소스 분리 ({model})")
    print(f"  입력: {input_path}")

    import demucs.separate

    # Demucs 실행
    demucs.separate.main([
        "--two-stems=None",  # 모든 스템 분리
        "-n", model,
        "--out", output_dir,
        input_path,
    ])

    # 분리된 파일 경로 수집
    input_name = Path(input_path).stem
    stems_dir = Path(output_dir) / model / input_name

    stems = {}
    for wav_file in stems_dir.glob("*.wav"):
        stem_name = wav_file.stem
        stems[stem_name] = str(wav_file)
        print(f"  ✓ {stem_name}: {wav_file.name}")

    if not stems:
        raise RuntimeError(f"Demucs 출력을 찾을 수 없습니다: {stems_dir}")

    print(f"  → {len(stems)}개 스템 분리 완료")
    return stems


# ──────────────────────────────────────────────
# Step 2: Basic Pitch로 각 스템을 MIDI 변환
# ──────────────────────────────────────────────

def stem_to_midi(wav_path: str, stem_name: str, output_dir: str) -> str:
    """
    Basic Pitch를 사용하여 단일 스템을 MIDI로 변환

    Returns:
        str: 생성된 MIDI 파일 경로
    """
    from basic_pitch.inference import predict
    from basic_pitch import ICASSP_2022_MODEL_PATH

    # 악기별 최적화 파라미터 선택
    params = STEM_PARAMS.get(stem_name, BASIC_PITCH_PARAMS)

    print(f"  변환 중: {stem_name} (onset={params['onset_threshold']}, "
          f"frame={params['frame_threshold']})")

    # Basic Pitch 추론
    model_output, midi_data, note_events = predict(
        wav_path,
        onset_threshold=params["onset_threshold"],
        frame_threshold=params["frame_threshold"],
        minimum_note_length=params["minimum_note_length"],
        minimum_frequency=params.get("minimum_frequency", 32.7),
        maximum_frequency=params.get("maximum_frequency", 4186.0),
    )

    # MIDI 파일 저장
    midi_path = os.path.join(output_dir, f"{stem_name}.mid")
    midi_data.write(midi_path)

    # 노트 수 카운트
    total_notes = sum(len(inst.notes) for inst in midi_data.instruments)
    print(f"  ✓ {stem_name}: {total_notes}개 노트 추출")

    return midi_path


def convert_all_stems(stems: dict, output_dir: str) -> dict:
    """모든 스템을 MIDI로 변환"""
    print_step(2, 4, "Basic Pitch MIDI 변환")

    midi_dir = os.path.join(output_dir, "midi_stems")
    os.makedirs(midi_dir, exist_ok=True)

    midi_files = {}
    for stem_name, wav_path in stems.items():
        midi_path = stem_to_midi(wav_path, stem_name, midi_dir)
        midi_files[stem_name] = midi_path

    return midi_files


# ──────────────────────────────────────────────
# Step 3: 후처리 - 노트 정리 및 최적화
# ──────────────────────────────────────────────

def clean_notes(instrument: pretty_midi.Instrument, stem_name: str) -> pretty_midi.Instrument:
    """
    노트 정리 및 최적화:
    - 너무 짧은 노트 제거
    - 겹치는 노트 병합
    - 벨로시티 정규화
    """
    if not instrument.notes:
        return instrument

    # 노트를 시작 시간으로 정렬
    instrument.notes.sort(key=lambda n: (n.pitch, n.start))

    cleaned = []
    min_duration = 0.03  # 30ms 미만 노트 제거 (드럼 제외)
    if stem_name == "drums":
        min_duration = 0.01

    for note in instrument.notes:
        duration = note.end - note.start

        # 너무 짧은 노트 제거
        if duration < min_duration:
            continue

        # 벨로시티 범위 확인 (1-127)
        note.velocity = max(1, min(127, note.velocity))

        # 겹치는 동일 피치 노트 병합
        if cleaned and cleaned[-1].pitch == note.pitch:
            prev = cleaned[-1]
            gap = note.start - prev.end
            # 매우 짧은 갭이면 병합
            if gap < 0.02 and gap >= 0:
                prev.end = note.end
                prev.velocity = max(prev.velocity, note.velocity)
                continue
            # 겹치면 이전 노트 끝을 조정
            elif gap < 0:
                prev.end = note.start - 0.001
                if prev.end <= prev.start:
                    cleaned.pop()

        cleaned.append(note)

    instrument.notes = cleaned
    return instrument


def quantize_notes(instrument: pretty_midi.Instrument,
                   resolution: float = 1/32) -> pretty_midi.Instrument:
    """
    노트를 그리드에 양자화 (선택적)
    resolution: 양자화 단위 (1/32 = 32분음표)
    """
    if not instrument.notes:
        return instrument

    # BPM 추정이 없으므로 약한 양자화만 적용
    # 실제로는 tempo를 감지한 후에 하는 것이 이상적
    for note in instrument.notes:
        # 매우 약한 양자화 - 10ms 단위로 반올림
        grid = 0.01
        note.start = round(note.start / grid) * grid
        note.end = round(note.end / grid) * grid
        if note.end <= note.start:
            note.end = note.start + grid

    return instrument


# ──────────────────────────────────────────────
# Step 4: 최종 MIDI 병합
# ──────────────────────────────────────────────

def merge_midi_files(midi_files: dict, output_path: str,
                     quantize: bool = True) -> str:
    """
    분리된 MIDI 파일들을 하나의 멀티트랙 MIDI로 병합
    """
    print_step(3, 4, "MIDI 트랙 병합 및 후처리")

    merged = pretty_midi.PrettyMIDI(initial_tempo=120.0)

    total_notes_before = 0
    total_notes_after = 0

    for stem_name, midi_path in midi_files.items():
        if not os.path.exists(midi_path):
            print(f"  ⚠ {stem_name} MIDI 파일 없음, 건너뜀")
            continue

        stem_midi = pretty_midi.PrettyMIDI(midi_path)

        for inst in stem_midi.instruments:
            total_notes_before += len(inst.notes)

            # 드럼 채널 설정
            is_drum = (stem_name == "drums")

            # GM 프로그램 번호 설정
            program = STEM_TO_GM.get(stem_name, 0)

            new_inst = pretty_midi.Instrument(
                program=program,
                is_drum=is_drum,
                name=stem_name.capitalize(),
            )
            new_inst.notes = inst.notes.copy()

            # 후처리
            new_inst = clean_notes(new_inst, stem_name)
            if quantize:
                new_inst = quantize_notes(new_inst)

            total_notes_after += len(new_inst.notes)

            print(f"  ✓ {stem_name}: {len(inst.notes)} → {len(new_inst.notes)} 노트 "
                  f"(프로그램: {program}, 드럼: {is_drum})")

            merged.instruments.append(new_inst)

    # BPM 추정 (원본 오디오 기반이면 더 정확하지만, 여기서는 MIDI 노트 기반)
    print(f"\n  총 노트: {total_notes_before} → {total_notes_after} "
          f"({total_notes_after/max(total_notes_before,1)*100:.1f}% 유지)")

    # 저장
    print_step(4, 4, "최종 MIDI 저장")
    merged.write(output_path)

    file_size = os.path.getsize(output_path)
    duration = merged.get_end_time()
    print(f"  출력: {output_path}")
    print(f"  크기: {file_size/1024:.1f} KB")
    print(f"  길이: {duration:.1f}초")
    print(f"  트랙: {len(merged.instruments)}개")

    return output_path


# ──────────────────────────────────────────────
# BPM 감지 (librosa 사용)
# ──────────────────────────────────────────────

def detect_bpm(audio_path: str) -> float:
    """librosa를 사용하여 BPM 감지"""
    try:
        import librosa
        y, sr = librosa.load(audio_path, sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if not hasattr(tempo, '__len__') else float(tempo[0])
        return bpm
    except Exception as e:
        print(f"  ⚠ BPM 감지 실패: {e}, 기본값 120 사용")
        return 120.0


# ──────────────────────────────────────────────
# 메인 파이프라인
# ──────────────────────────────────────────────

def convert(input_path: str, output_path: str = None,
            model: str = DEFAULT_DEMUCS_MODEL,
            quantize: bool = True,
            keep_stems: bool = False) -> str:
    """
    WAV/MP3 → MIDI 전체 변환 파이프라인

    Args:
        input_path:  입력 오디오 파일 경로 (wav, mp3, flac 등)
        output_path: 출력 MIDI 파일 경로 (None이면 자동 생성)
        model:       Demucs 모델명
        quantize:    노트 양자화 적용 여부
        keep_stems:  분리된 스템 파일 보존 여부

    Returns:
        str: 출력 MIDI 파일 경로
    """
    input_path = os.path.abspath(input_path)

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {input_path}")

    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".mid"))

    output_path = os.path.abspath(output_path)

    print(f"\n{'#'*60}")
    print(f"  Audio-to-MIDI 고정밀 변환기")
    print(f"  입력: {input_path}")
    print(f"  출력: {output_path}")
    print(f"  모델: {model}")
    print(f"{'#'*60}")

    # 작업 디렉토리
    work_dir = tempfile.mkdtemp(prefix="audio2midi_")

    try:
        # BPM 감지
        print("\n  BPM 감지 중...")
        bpm = detect_bpm(input_path)
        print(f"  → 감지된 BPM: {bpm:.1f}")

        # Step 1: 소스 분리
        stems = separate_stems(input_path, work_dir, model)

        # Step 2: MIDI 변환
        midi_files = convert_all_stems(stems, work_dir)

        # Step 3 & 4: 병합 및 저장
        result = merge_midi_files(midi_files, output_path, quantize=quantize)

        # BPM 적용
        final_midi = pretty_midi.PrettyMIDI(output_path)
        # PrettyMIDI는 생성 시 tempo를 설정하므로, BPM을 반영하여 다시 저장
        bpm_midi = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        for inst in final_midi.instruments:
            bpm_midi.instruments.append(inst)
        bpm_midi.write(output_path)
        print(f"  → BPM {bpm:.1f} 적용 완료")

        # 스템 보존
        if keep_stems:
            stems_output = str(Path(output_path).parent / f"{Path(input_path).stem}_stems")
            if os.path.exists(stems_output):
                shutil.rmtree(stems_output)
            # 스템 WAV 복사
            os.makedirs(stems_output, exist_ok=True)
            for stem_name, wav_path in stems.items():
                shutil.copy2(wav_path, os.path.join(stems_output, f"{stem_name}.wav"))
            # 스템별 MIDI 복사
            for stem_name, mid_path in midi_files.items():
                shutil.copy2(mid_path, os.path.join(stems_output, f"{stem_name}.mid"))
            print(f"  → 스템 파일 보존: {stems_output}")

        print(f"\n{'#'*60}")
        print(f"  변환 완료!")
        print(f"  출력 파일: {output_path}")
        print(f"{'#'*60}\n")

        return result

    finally:
        # 임시 파일 정리
        if not keep_stems:
            shutil.rmtree(work_dir, ignore_errors=True)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Audio-to-MIDI 고정밀 변환기 (Demucs + Basic Pitch)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python audio2midi.py song.wav
  python audio2midi.py song.mp3 -o output.mid
  python audio2midi.py song.wav --model htdemucs_ft --keep-stems
  python audio2midi.py song.wav --no-quantize
        """
    )

    parser.add_argument("input", help="입력 오디오 파일 (wav, mp3, flac 등)")
    parser.add_argument("-o", "--output", help="출력 MIDI 파일 경로 (기본: 입력파일명.mid)")
    parser.add_argument(
        "--model", default=DEFAULT_DEMUCS_MODEL,
        choices=["htdemucs", "htdemucs_ft", "htdemucs_6s", "mdx_extra"],
        help=f"Demucs 모델 (기본: {DEFAULT_DEMUCS_MODEL})"
    )
    parser.add_argument(
        "--no-quantize", action="store_true",
        help="노트 양자화 비활성화"
    )
    parser.add_argument(
        "--keep-stems", action="store_true",
        help="분리된 스템 파일 보존"
    )

    args = parser.parse_args()

    convert(
        input_path=args.input,
        output_path=args.output,
        model=args.model,
        quantize=not args.no_quantize,
        keep_stems=args.keep_stems,
    )


if __name__ == "__main__":
    main()
