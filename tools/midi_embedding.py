"""
MIDI Embedding Pipeline
- 93개 MAESTRO 2018 피아노 MIDI 파일을 분석/임베딩
- 노트 시퀀스, 통계, 피아노롤 임베딩 생성
- 데이터 누락 없이 전체 파일 처리
"""

import os
import sys
import json
import glob
import numpy as np
import pretty_midi
from collections import Counter

# Windows 콘솔 UTF-8 출력
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

MIDI_DIR = os.path.join(os.path.dirname(__file__), '..', 'Ableton', 'midi_raw')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'embeddings')
PIANOROLL_RES = 100  # 피아노롤 해상도 (100 steps/beat)
EMBED_DIM = 128      # 임베딩 차원


def analyze_midi(filepath):
    """단일 MIDI 파일 분석 — 모든 노트 데이터 보존"""
    midi = pretty_midi.PrettyMIDI(filepath)
    filename = os.path.basename(filepath)

    all_notes = []
    for inst in midi.instruments:
        for note in inst.notes:
            all_notes.append({
                'pitch': note.pitch,
                'start': round(note.start, 4),
                'end': round(note.end, 4),
                'duration': round(note.end - note.start, 4),
                'velocity': note.velocity,
                'instrument': inst.program,
                'instrument_name': pretty_midi.program_to_instrument_name(inst.program),
                'is_drum': inst.is_drum
            })

    all_notes.sort(key=lambda x: x['start'])

    # 통계 계산
    if all_notes:
        pitches = [n['pitch'] for n in all_notes]
        velocities = [n['velocity'] for n in all_notes]
        durations = [n['duration'] for n in all_notes]

        # 피치 히스토그램 (128 MIDI pitches)
        pitch_hist = np.zeros(128)
        for p in pitches:
            pitch_hist[p] += 1
        if pitch_hist.sum() > 0:
            pitch_hist = pitch_hist / pitch_hist.sum()

        # 피치 클래스 히스토그램 (12 semitones)
        pitch_class_hist = np.zeros(12)
        for p in pitches:
            pitch_class_hist[p % 12] += 1
        if pitch_class_hist.sum() > 0:
            pitch_class_hist = pitch_class_hist / pitch_class_hist.sum()

        # 인터벌 히스토그램
        intervals = [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]
        interval_hist = np.zeros(25)  # -12 ~ +12
        for iv in intervals:
            idx = max(0, min(24, iv + 12))
            interval_hist[idx] += 1
        if interval_hist.sum() > 0:
            interval_hist = interval_hist / interval_hist.sum()

        # 벨로시티 히스토그램 (8 bins)
        vel_hist = np.zeros(8)
        for v in velocities:
            vel_hist[min(7, v // 16)] += 1
        if vel_hist.sum() > 0:
            vel_hist = vel_hist / vel_hist.sum()

        # 듀레이션 히스토그램 (10 bins: 0-0.1, 0.1-0.25, 0.25-0.5, 0.5-1, 1-2, 2-4, 4-8, 8-16, 16-32, 32+)
        dur_bins = [0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, float('inf')]
        dur_hist = np.zeros(10)
        for d in durations:
            for i in range(10):
                if dur_bins[i] <= d < dur_bins[i+1]:
                    dur_hist[i] += 1
                    break
        if dur_hist.sum() > 0:
            dur_hist = dur_hist / dur_hist.sum()

        # 추정 조성
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        estimated_key_idx = int(np.argmax(pitch_class_hist))
        estimated_key = key_names[estimated_key_idx]

        # 템포
        tempos = midi.get_tempo_changes()
        avg_tempo = float(np.mean(tempos[1])) if len(tempos[1]) > 0 else 120.0

        stats = {
            'filename': filename,
            'total_notes': len(all_notes),
            'total_duration_sec': round(midi.get_end_time(), 2),
            'avg_tempo': round(avg_tempo, 1),
            'pitch_range': [int(min(pitches)), int(max(pitches))],
            'pitch_mean': round(float(np.mean(pitches)), 1),
            'pitch_std': round(float(np.std(pitches)), 1),
            'velocity_range': [int(min(velocities)), int(max(velocities))],
            'velocity_mean': round(float(np.mean(velocities)), 1),
            'velocity_std': round(float(np.std(velocities)), 1),
            'duration_mean': round(float(np.mean(durations)), 4),
            'duration_std': round(float(np.std(durations)), 4),
            'estimated_key': estimated_key,
            'num_instruments': len(midi.instruments),
            'time_signatures': [f"{ts.numerator}/{ts.denominator}" for ts in midi.time_signature_changes],
        }
    else:
        pitch_hist = np.zeros(128)
        pitch_class_hist = np.zeros(12)
        interval_hist = np.zeros(25)
        vel_hist = np.zeros(8)
        dur_hist = np.zeros(10)
        stats = {
            'filename': filename,
            'total_notes': 0,
            'total_duration_sec': round(midi.get_end_time(), 2),
            'error': 'no notes found'
        }

    # 임베딩 벡터 생성 (128차원)
    # [pitch_hist_12 | interval_hist_25 | vel_hist_8 | dur_hist_10 | stats_73]
    embedding = np.zeros(EMBED_DIM)
    embedding[0:12] = pitch_class_hist
    embedding[12:37] = interval_hist
    embedding[37:45] = vel_hist
    embedding[45:55] = dur_hist
    if all_notes:
        embedding[55] = stats['pitch_mean'] / 127.0
        embedding[56] = stats['pitch_std'] / 40.0
        embedding[57] = stats['velocity_mean'] / 127.0
        embedding[58] = stats['velocity_std'] / 40.0
        embedding[59] = stats['duration_mean'] / 10.0
        embedding[60] = stats['duration_std'] / 10.0
        embedding[61] = stats['avg_tempo'] / 200.0
        embedding[62] = stats['total_duration_sec'] / 600.0
        embedding[63] = stats['total_notes'] / 10000.0
        # 나머지는 pitch histogram 상위 65개
        sorted_pitches = np.argsort(pitch_hist)[::-1][:65]
        for i, p in enumerate(sorted_pitches):
            embedding[63 + i] = pitch_hist[p]

    return {
        'stats': stats,
        'notes': all_notes,
        'embedding': embedding.tolist(),
        'pitch_histogram': pitch_hist.tolist(),
        'pitch_class_histogram': pitch_class_hist.tolist(),
        'interval_histogram': interval_hist.tolist(),
        'velocity_histogram': vel_hist.tolist(),
        'duration_histogram': dur_hist.tolist(),
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    midi_files = sorted(glob.glob(os.path.join(MIDI_DIR, '*.midi')) +
                        glob.glob(os.path.join(MIDI_DIR, '*.mid')))

    print(f"Found {len(midi_files)} MIDI files")

    all_stats = []
    all_embeddings = []
    failed = []
    total_notes = 0

    for i, filepath in enumerate(midi_files):
        filename = os.path.basename(filepath)
        try:
            result = analyze_midi(filepath)

            # 개별 파일 저장 (노트 데이터 포함 — 누락 없음)
            individual_path = os.path.join(OUTPUT_DIR, 'individual',
                                           filename.replace('.midi', '.json').replace('.mid', '.json'))
            os.makedirs(os.path.dirname(individual_path), exist_ok=True)
            with open(individual_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, cls=NumpyEncoder)

            all_stats.append(result['stats'])
            all_embeddings.append(result['embedding'])
            total_notes += result['stats']['total_notes']

            print(f"  [{i+1:3d}/{len(midi_files)}] {filename} — "
                  f"{result['stats']['total_notes']} notes, "
                  f"{result['stats']['total_duration_sec']}s")

        except Exception as e:
            failed.append({'file': filename, 'error': str(e)})
            print(f"  [{i+1:3d}/{len(midi_files)}] FAILED: {filename} — {e}")

    # 전체 임베딩 매트릭스 저장 (numpy)
    embedding_matrix = np.array(all_embeddings)
    np.save(os.path.join(OUTPUT_DIR, 'embedding_matrix.npy'), embedding_matrix)

    # 전체 통계 요약 저장
    summary = {
        'total_files': len(midi_files),
        'processed': len(all_stats),
        'failed': len(failed),
        'failed_files': failed,
        'total_notes': total_notes,
        'embedding_shape': list(embedding_matrix.shape),
        'embedding_dim': EMBED_DIM,
        'stats': all_stats,
    }

    with open(os.path.join(OUTPUT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

    # 임베딩 메타데이터 (파일명 ↔ 인덱스 매핑)
    meta = {
        'files': [s['filename'] for s in all_stats],
        'embedding_file': 'embedding_matrix.npy',
        'embedding_dim': EMBED_DIM,
        'total_files': len(all_stats),
    }
    with open(os.path.join(OUTPUT_DIR, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Complete: {len(all_stats)}/{len(midi_files)} files processed")
    print(f"Total notes: {total_notes:,}")
    print(f"Embedding matrix: {embedding_matrix.shape}")
    print(f"Failed: {len(failed)}")
    if failed:
        for f_info in failed:
            print(f"  - {f_info['file']}: {f_info['error']}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
