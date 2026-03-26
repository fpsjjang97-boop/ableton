"""
POP909 Dataset 통합 파이프라인
==============================
- GitHub에서 POP909 데이터셋 클론/다운로드
- MIDI 파일 분석 + 작곡가 관점 태그 자동 추출
- 기존 임베딩 파이프라인(midi_embedding.py)과 동일 포맷으로 저장
- catalog에 pop909 카테고리로 편입

POP909: 909곡의 유명 팝송을 피아노로 편곡한 MIDI 데이터셋
- 멜로디 / 브릿지 (반주) / 피아노 트랙 분리
- 코드 진행 어노테이션 포함
- https://github.com/music-x-lab/POP909-Dataset
"""

import os
import sys
import json
import glob
import shutil
import subprocess

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
POP909_REPO = 'https://github.com/music-x-lab/POP909-Dataset.git'
POP909_DIR = os.path.join(BASE_DIR, 'datasets', 'POP909-Dataset')
MIDI_OUTPUT_DIR = os.path.join(BASE_DIR, 'Ableton', 'midi_raw', 'pop909')
EMBED_DIR = os.path.join(BASE_DIR, 'embeddings')
INDIVIDUAL_DIR = os.path.join(EMBED_DIR, 'individual', 'pop909')


def clone_dataset():
    """POP909 데이터셋 클론"""
    datasets_dir = os.path.join(BASE_DIR, 'datasets')
    os.makedirs(datasets_dir, exist_ok=True)

    if os.path.exists(POP909_DIR):
        print(f"POP909 이미 존재: {POP909_DIR}")
        return True

    print(f"POP909 클론 중... {POP909_REPO}")
    try:
        subprocess.run(
            ['git', 'clone', '--depth', '1', POP909_REPO, POP909_DIR],
            check=True, capture_output=True, text=True
        )
        print("클론 완료")
        return True
    except subprocess.CalledProcessError as e:
        print(f"클론 실패: {e.stderr}")
        return False
    except FileNotFoundError:
        print("git이 설치되어 있지 않습니다")
        return False


def find_midi_files():
    """POP909 내 MIDI 파일 탐색"""
    patterns = [
        os.path.join(POP909_DIR, '**', '*.mid'),
        os.path.join(POP909_DIR, '**', '*.midi'),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))
    # 중복 제거 + 정렬
    files = sorted(set(files))
    print(f"MIDI 파일 발견: {len(files)}개")
    return files


def parse_chord_annotation(song_dir):
    """POP909 코드 어노테이션 파싱 (있는 경우)"""
    chord_file = os.path.join(song_dir, 'chord_midi.txt')
    if not os.path.exists(chord_file):
        chord_file = os.path.join(song_dir, 'chord_audio.txt')
    if not os.path.exists(chord_file):
        return []

    chords = []
    try:
        with open(chord_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 3:
                    start = float(parts[0])
                    end = float(parts[1])
                    chord_name = parts[2]
                    chords.append({
                        'start': start,
                        'end': end,
                        'chord': chord_name,
                    })
    except Exception:
        pass
    return chords


def parse_song_metadata(song_dir):
    """POP909 곡 메타데이터 파싱"""
    meta = {}

    # beat annotation
    beat_file = os.path.join(song_dir, 'beat_audio.txt')
    if os.path.exists(beat_file):
        try:
            with open(beat_file, 'r', encoding='utf-8') as f:
                beats = [line.strip().split() for line in f if line.strip()]
            if beats:
                meta['total_beats'] = len(beats)
                # BPM 추정: 인접 비트 간격
                if len(beats) >= 4:
                    intervals = []
                    for i in range(min(len(beats) - 1, 50)):
                        try:
                            dt = float(beats[i + 1][0]) - float(beats[i][0])
                            if 0.1 < dt < 3.0:
                                intervals.append(dt)
                        except (ValueError, IndexError):
                            pass
                    if intervals:
                        avg_interval = sum(intervals) / len(intervals)
                        meta['estimated_bpm'] = round(60.0 / avg_interval, 1)
        except Exception:
            pass

    # chord progression
    chords = parse_chord_annotation(song_dir)
    if chords:
        meta['chord_progression'] = chords
        unique_chords = list(dict.fromkeys(c['chord'] for c in chords))
        meta['unique_chords'] = unique_chords
        meta['num_unique_chords'] = len(unique_chords)

    return meta


def ingest_single(midi_path, song_dir=None):
    """단일 MIDI 파일 분석 — midi_embedding.py의 analyze_midi 재사용"""
    # 동적 임포트
    sys.path.insert(0, os.path.dirname(__file__))
    from midi_embedding import analyze_midi

    try:
        result = analyze_midi(midi_path)
    except Exception as e:
        return None, str(e)

    # POP909 고유 메타데이터 추가
    if song_dir:
        pop_meta = parse_song_metadata(song_dir)
        result['pop909_metadata'] = pop_meta
    else:
        result['pop909_metadata'] = {}

    # 트랙 유형 식별 (POP909 파일명 규칙)
    basename = os.path.basename(midi_path).lower()
    if 'melody' in basename:
        result['pop909_metadata']['track_type'] = 'melody'
    elif 'bridge' in basename:
        result['pop909_metadata']['track_type'] = 'bridge'  # 반주/브릿지
    elif 'piano' in basename:
        result['pop909_metadata']['track_type'] = 'piano'
    else:
        result['pop909_metadata']['track_type'] = 'full'

    return result, None


def copy_midi_files(midi_files):
    """MIDI 파일을 프로젝트 midi_raw/pop909 디렉토리로 복사"""
    os.makedirs(MIDI_OUTPUT_DIR, exist_ok=True)
    copied = 0
    for src in midi_files:
        # 파일명에 곡 번호 포함시키기
        rel = os.path.relpath(src, POP909_DIR)
        # e.g. POP909/001/001.mid → pop909_001_001.mid
        safe_name = rel.replace(os.sep, '_').replace('/', '_')
        dst = os.path.join(MIDI_OUTPUT_DIR, safe_name)
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
            copied += 1
    print(f"MIDI 복사: {copied}개 (총 {len(midi_files)}개)")
    return copied


def main():
    print("=" * 60)
    print("POP909 Dataset Integration Pipeline")
    print("=" * 60)

    # 1. 클론
    print("\n[1] 데이터셋 다운로드")
    if not clone_dataset():
        print("데이터셋 다운로드 실패. 수동으로 다운로드 후 재시도:")
        print(f"  git clone {POP909_REPO} {POP909_DIR}")
        return

    # 2. MIDI 파일 탐색
    print("\n[2] MIDI 파일 탐색")
    midi_files = find_midi_files()
    if not midi_files:
        print("MIDI 파일을 찾지 못했습니다")
        return

    # 3. MIDI 복사
    print("\n[3] MIDI 파일 복사")
    copy_midi_files(midi_files)

    # 4. 분석 + 임베딩
    print(f"\n[4] 분석 및 임베딩 생성")
    os.makedirs(INDIVIDUAL_DIR, exist_ok=True)

    results = []
    failed = []

    for i, midi_path in enumerate(midi_files):
        filename = os.path.basename(midi_path)
        song_dir = os.path.dirname(midi_path)

        result, error = ingest_single(midi_path, song_dir)
        if error:
            failed.append({'file': filename, 'error': error})
            print(f"  [{i+1:4d}/{len(midi_files)}] FAILED: {filename} — {error}")
            continue

        # 저장
        json_name = filename.replace('.midi', '.json').replace('.mid', '.json')
        json_path = os.path.join(INDIVIDUAL_DIR, json_name)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)

        results.append(result)
        tags = result.get('composer_tags', {})
        track_type = result.get('pop909_metadata', {}).get('track_type', '?')
        print(f"  [{i+1:4d}/{len(midi_files)}] {filename} — "
              f"{result['stats']['total_notes']} notes | "
              f"type={track_type} | "
              f"{tags.get('rhythm_type', '?')}/{tags.get('accompaniment_pattern', '?')}")

    # 5. 요약
    print(f"\n{'=' * 60}")
    print(f"완료: {len(results)}/{len(midi_files)} 파일 처리")
    print(f"실패: {len(failed)}개")
    if results:
        total_notes = sum(r['stats']['total_notes'] for r in results)
        print(f"총 노트: {total_notes:,}")

        # 트랙 유형별 통계
        track_types = {}
        for r in results:
            tt = r.get('pop909_metadata', {}).get('track_type', 'unknown')
            track_types[tt] = track_types.get(tt, 0) + 1
        print(f"트랙 유형: {track_types}")

        # 작곡가 태그 분포
        rhythm_dist = {}
        accomp_dist = {}
        for r in results:
            tags = r.get('composer_tags', {})
            rt = tags.get('rhythm_type', 'unknown')
            ap = tags.get('accompaniment_pattern', 'unknown')
            rhythm_dist[rt] = rhythm_dist.get(rt, 0) + 1
            accomp_dist[ap] = accomp_dist.get(ap, 0) + 1
        print(f"리듬 유형: {rhythm_dist}")
        print(f"반주 구조: {accomp_dist}")

    print(f"\n임베딩 저장: {INDIVIDUAL_DIR}")
    print(f"다음 단계: python tools/build_catalog.py 실행하여 카탈로그 갱신")
    print("=" * 60)


if __name__ == '__main__':
    main()
