"""
Music Transformer 에이전트
==========================
역할: Magenta Music Transformer 기반 MIDI 생성/분석/변형
- 기존 MIDI를 기반으로 연속 생성 (continuation)
- 스타일 변환
- 멜로디 하모나이제이션
- 패턴 추출 및 재조합

Note: magenta 패키지가 설치 안 된 경우 순수 Python 기반 transformer 로직으로 대체
"""

import os
import sys
import json
import random
import mido
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SCALES = {
    'major':       [0, 2, 4, 5, 7, 9, 11],
    'minor':       [0, 2, 3, 5, 7, 8, 10],
    'dorian':      [0, 2, 3, 5, 7, 9, 10],
    'pentatonic':  [0, 2, 4, 7, 9],
    'minor_penta': [0, 3, 5, 7, 10],
    'blues':       [0, 3, 5, 6, 7, 10],
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def extract_patterns(midi_path, window_beats=4):
    """MIDI에서 패턴 추출 (윈도우 단위)"""
    mid = mido.MidiFile(midi_path)
    tpb = mid.ticks_per_beat
    window_ticks = window_beats * tpb

    patterns = []

    for track in mid.tracks:
        notes = []
        abs_tick = 0
        active = {}

        for msg in track:
            abs_tick += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                active[msg.note] = (abs_tick, msg.velocity)
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active:
                    start, vel = active.pop(msg.note)
                    notes.append({
                        'pitch': msg.note,
                        'start': start,
                        'duration': abs_tick - start,
                        'velocity': vel,
                    })

        if not notes:
            continue

        # 윈도우별로 분할
        max_tick = max(n['start'] + n['duration'] for n in notes)
        for w_start in range(0, int(max_tick), window_ticks):
            w_end = w_start + window_ticks
            window_notes = []
            for n in notes:
                if n['start'] >= w_start and n['start'] < w_end:
                    window_notes.append({
                        'pitch': n['pitch'],
                        'offset': n['start'] - w_start,  # 윈도우 내 상대 위치
                        'duration': n['duration'],
                        'velocity': n['velocity'],
                    })
            if window_notes:
                patterns.append({
                    'notes': window_notes,
                    'window_start': w_start,
                    'note_count': len(window_notes),
                })

    return patterns


def analyze_patterns(patterns):
    """패턴 분석 — 반복, 유사성, 모티프 검출"""
    if not patterns:
        print("패턴 없음")
        return

    print(f"\n[패턴 분석]")
    print(f"  총 패턴 수: {len(patterns)}")

    # 피치 클래스 시퀀스로 추상화
    pc_sequences = []
    for p in patterns:
        pcs = tuple(sorted(set(n['pitch'] % 12 for n in p['notes'])))
        pc_sequences.append(pcs)

    # 반복 패턴 찾기
    from collections import Counter
    pc_counter = Counter(pc_sequences)
    repeated = [(pcs, count) for pcs, count in pc_counter.most_common() if count > 1]

    if repeated:
        print(f"  반복 패턴: {len(repeated)}개")
        for pcs, count in repeated[:5]:
            names = [NOTE_NAMES[p] for p in pcs]
            print(f"    {', '.join(names)} — {count}회 반복")
    else:
        print(f"  반복 패턴: 없음 (모든 패턴 고유)")

    # 노트 밀도 분석
    densities = [p['note_count'] for p in patterns]
    print(f"  노트 밀도: 평균 {sum(densities)/len(densities):.1f}, 범위 {min(densities)}~{max(densities)}")

    # 음역 변화
    for i, p in enumerate(patterns[:8]):
        pitches = [n['pitch'] for n in p['notes']]
        low = min(pitches)
        high = max(pitches)
        print(f"    패턴 {i}: {NOTE_NAMES[low%12]}{low//12-1}~{NOTE_NAMES[high%12]}{high//12-1} ({len(pitches)}노트)")


def continue_midi(midi_path, additional_measures=8):
    """기존 MIDI를 기반으로 연속 생성 (마르코프 체인 기반)"""
    mid = mido.MidiFile(midi_path)
    settings = load_settings()
    tpb = mid.ticks_per_beat

    print(f"\n🎵 연속 생성: {os.path.basename(midi_path)} + {additional_measures}마디")

    # 모든 노트 이벤트 수집
    all_notes = []
    for track in mid.tracks:
        abs_tick = 0
        active = {}
        for msg in track:
            abs_tick += msg.time
            if msg.type == 'note_on' and msg.velocity > 0:
                active[msg.note] = (abs_tick, msg.velocity)
            elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
                if msg.note in active:
                    start, vel = active.pop(msg.note)
                    all_notes.append({
                        'pitch': msg.note,
                        'start': start,
                        'duration': abs_tick - start,
                        'velocity': vel,
                    })

    if not all_notes:
        print("✗ 원본에 노트 없음")
        return None

    all_notes.sort(key=lambda n: n['start'])

    # 마르코프 체인: 현재 음 → 다음 음 확률
    transitions = {}
    for i in range(len(all_notes) - 1):
        curr = all_notes[i]['pitch']
        next_p = all_notes[i+1]['pitch']
        if curr not in transitions:
            transitions[curr] = []
        transitions[curr].append(next_p)

    # 벨로시티/듀레이션 통계
    velocities = [n['velocity'] for n in all_notes]
    durations = [n['duration'] for n in all_notes]
    vel_avg = sum(velocities) / len(velocities)
    vel_std = max(1, int((sum((v - vel_avg)**2 for v in velocities) / len(velocities)) ** 0.5))
    common_durations = list(set(durations))

    # 인터벌 통계
    intervals = []
    for i in range(len(all_notes) - 1):
        intervals.append(all_notes[i+1]['start'] - all_notes[i]['start'])
    common_intervals = list(set(intervals)) if intervals else [tpb]

    # 새 MIDI 생성
    new_mid = mido.MidiFile(ticks_per_beat=tpb)

    # 원본 트랙 복사
    for track in mid.tracks:
        new_mid.tracks.append(track.copy())

    # 연속 트랙 생성
    cont_track = mido.MidiTrack()
    cont_track.name = 'Continuation'

    # 마지막 음에서 시작
    last_note = all_notes[-1]
    current_pitch = last_note['pitch']
    max_tick = max(n['start'] + n['duration'] for n in all_notes)
    current_tick = 0
    last_event_tick = 0

    target_ticks = additional_measures * 4 * tpb

    while current_tick < target_ticks:
        # 마르코프 체인으로 다음 음 선택
        if current_pitch in transitions:
            next_pitch = random.choice(transitions[current_pitch])
        else:
            # 전이가 없으면 인접 음 선택
            all_pitches = list(transitions.keys())
            if all_pitches:
                next_pitch = random.choice([p for p in all_pitches if abs(p - current_pitch) <= 7] or all_pitches)
            else:
                next_pitch = current_pitch + random.choice([-2, -1, 1, 2])

        next_pitch = max(24, min(108, next_pitch))

        vel = max(1, min(127, int(random.gauss(vel_avg, vel_std))))
        dur = random.choice(common_durations) if common_durations else tpb
        interval = random.choice(common_intervals) if common_intervals else tpb

        delta = max(0, current_tick - last_event_tick)
        cont_track.append(mido.Message('note_on', note=next_pitch, velocity=vel, time=delta, channel=0))
        cont_track.append(mido.Message('note_off', note=next_pitch, velocity=0, time=dur, channel=0))
        last_event_tick = current_tick + delta + dur

        current_pitch = next_pitch
        current_tick += interval

    new_mid.tracks.append(cont_track)

    # 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    basename = os.path.splitext(os.path.basename(midi_path))[0]
    filename = f"continued_{basename}_{timestamp}.mid"
    filepath = os.path.join(OUTPUT_DIR, filename)
    new_mid.save(filepath)

    # 메타데이터
    meta = {
        'filename': filename,
        'filepath': filepath,
        'source': os.path.basename(midi_path),
        'method': 'markov_continuation',
        'additional_measures': additional_measures,
        'created_at': timestamp,
        'status': 'pending_review',
    }
    with open(filepath + '.meta.json', 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"✓ 저장: {filepath}")
    print(f"  원본: {mid.length:.1f}초 → 연속: {new_mid.length:.1f}초")
    return filepath


def transform_style(midi_path, target_style):
    """스타일 변환 (BPM, 벨로시티, 밀도 조정)"""
    style_params = {
        'ambient':   {'bpm_factor': 0.5, 'vel_factor': 0.5, 'density': 0.3},
        'pop':       {'bpm_factor': 1.0, 'vel_factor': 0.8, 'density': 0.6},
        'cinematic': {'bpm_factor': 0.7, 'vel_factor': 0.7, 'density': 0.4},
        'edm':       {'bpm_factor': 1.1, 'vel_factor': 1.0, 'density': 0.8},
        'jazz':      {'bpm_factor': 0.8, 'vel_factor': 0.6, 'density': 0.5},
    }

    if target_style not in style_params:
        print(f"✗ 알 수 없는 스타일: {target_style}")
        print(f"  가능: {', '.join(style_params.keys())}")
        return None

    params = style_params[target_style]
    mid = mido.MidiFile(midi_path)

    print(f"\n🎨 스타일 변환: {os.path.basename(midi_path)} → {target_style}")

    new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)

    for track in mid.tracks:
        new_track = mido.MidiTrack()
        new_track.name = track.name

        for msg in track:
            if msg.type == 'set_tempo':
                original_bpm = mido.tempo2bpm(msg.tempo)
                new_bpm = original_bpm * params['bpm_factor']
                new_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(new_bpm), time=msg.time))
            elif msg.type == 'note_on' and msg.velocity > 0:
                # 밀도 조절: 일부 노트 스킵
                if random.random() < params['density'] or params['density'] >= 0.8:
                    new_vel = max(1, min(127, int(msg.velocity * params['vel_factor'])))
                    new_track.append(msg.copy(velocity=new_vel))
                else:
                    # 스킵된 노트: note_on vel=0으로 대체 (무음)
                    new_track.append(msg.copy(velocity=0))
            else:
                new_track.append(msg.copy())

        new_mid.tracks.append(new_track)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    basename = os.path.splitext(os.path.basename(midi_path))[0]
    filename = f"style_{target_style}_{basename}_{timestamp}.mid"
    filepath = os.path.join(OUTPUT_DIR, filename)
    new_mid.save(filepath)

    meta = {
        'filename': filename,
        'source': os.path.basename(midi_path),
        'method': 'style_transform',
        'target_style': target_style,
        'params': params,
        'created_at': timestamp,
        'status': 'pending_review',
    }
    with open(filepath + '.meta.json', 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"✓ 저장: {filepath}")
    return filepath


def harmonize(midi_path, harmony_type='thirds'):
    """멜로디에 하모니 추가"""
    mid = mido.MidiFile(midi_path)
    settings = load_settings()
    tpb = mid.ticks_per_beat

    root = settings.get('key', 'C')
    scale_name = settings.get('scale', 'minor')
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])
    scale_pcs = set((root_idx + i) % 12 for i in intervals)

    harmony_intervals = {
        'thirds': [3, 4],     # 3도
        'fifths': [7],         # 5도
        'octave': [12],        # 옥타브
        'power':  [7, 12],     # 파워코드
    }

    h_intervals = harmony_intervals.get(harmony_type, [3, 4])

    print(f"\n🎶 하모나이제이션: {os.path.basename(midi_path)} ({harmony_type})")

    new_mid = mido.MidiFile(ticks_per_beat=tpb)

    # 원본 복사
    for track in mid.tracks:
        new_mid.tracks.append(track.copy())

    # 하모니 트랙 생성
    harmony_track = mido.MidiTrack()
    harmony_track.name = f'Harmony ({harmony_type})'

    # 멜로디 트랙에서 노트 추출 (첫 번째 노트 트랙)
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on':
                if msg.velocity > 0:
                    # 하모니 노트 생성
                    h_interval = random.choice(h_intervals)
                    h_note = msg.note + h_interval

                    # 스케일 내로 조정
                    while h_note % 12 not in scale_pcs and h_note < 127:
                        h_note += 1

                    if 0 <= h_note <= 127:
                        h_vel = max(1, msg.velocity - 15)  # 하모니는 약간 작게
                        harmony_track.append(mido.Message('note_on', note=h_note, velocity=h_vel, time=msg.time, channel=1))
                    else:
                        harmony_track.append(mido.Message('note_on', note=msg.note, velocity=0, time=msg.time, channel=1))
                else:
                    harmony_track.append(msg.copy(channel=1))
            elif msg.type == 'note_off':
                harmony_track.append(msg.copy(channel=1))
            elif not msg.is_meta:
                harmony_track.append(msg.copy())
            else:
                harmony_track.append(msg)

    new_mid.tracks.append(harmony_track)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    basename = os.path.splitext(os.path.basename(midi_path))[0]
    filename = f"harmonized_{harmony_type}_{basename}_{timestamp}.mid"
    filepath = os.path.join(OUTPUT_DIR, filename)
    new_mid.save(filepath)

    meta = {
        'filename': filename,
        'source': os.path.basename(midi_path),
        'method': 'harmonization',
        'harmony_type': harmony_type,
        'created_at': timestamp,
        'status': 'pending_review',
    }
    with open(filepath + '.meta.json', 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"✓ 저장: {filepath}")
    return filepath


# ─── CLI ───

def print_help():
    print("""
명령어:
  patterns <file>           - MIDI 패턴 추출/분석
  continue <file> [마디수]  - 연속 생성 (마르코프 체인)
  style <file> <스타일>     - 스타일 변환 (ambient/pop/cinematic/edm/jazz)
  harmonize <file> [타입]   - 하모니 추가 (thirds/fifths/octave/power)
  list                      - output/ 파일 목록
  help                      - 도움말
  quit                      - 종료
""")


def resolve_path(filepath):
    """파일 경로 해석"""
    if os.path.isabs(filepath) and os.path.exists(filepath):
        return filepath
    candidate = os.path.join(OUTPUT_DIR, filepath)
    if os.path.exists(candidate):
        return candidate
    candidate = os.path.join(PROJECT_DIR, filepath)
    if os.path.exists(candidate):
        return candidate
    return filepath


if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'patterns' and len(sys.argv) > 2:
            patterns = extract_patterns(sys.argv[2])
            analyze_patterns(patterns)
        elif cmd == 'continue' and len(sys.argv) > 2:
            measures = int(sys.argv[3]) if len(sys.argv) > 3 else 8
            continue_midi(sys.argv[2], measures)
        elif cmd == 'style' and len(sys.argv) > 3:
            transform_style(sys.argv[2], sys.argv[3])
        elif cmd == 'harmonize' and len(sys.argv) > 2:
            h_type = sys.argv[3] if len(sys.argv) > 3 else 'thirds'
            harmonize(sys.argv[2], h_type)
        else:
            print_help()
    else:
        print("="*50)
        print("🧠 Music Transformer 에이전트")
        print("="*50)
        print_help()

        while True:
            try:
                cmd = input("transformer> ").strip()
                if not cmd:
                    continue
                elif cmd == 'quit':
                    break
                elif cmd.startswith('patterns '):
                    filepath = resolve_path(cmd.split(maxsplit=1)[1])
                    patterns = extract_patterns(filepath)
                    analyze_patterns(patterns)
                elif cmd.startswith('continue '):
                    parts = cmd.split()
                    filepath = resolve_path(parts[1])
                    measures = int(parts[2]) if len(parts) > 2 else 8
                    continue_midi(filepath, measures)
                elif cmd.startswith('style '):
                    parts = cmd.split()
                    if len(parts) >= 3:
                        filepath = resolve_path(parts[1])
                        transform_style(filepath, parts[2])
                    else:
                        print("사용법: style <file> <스타일>")
                elif cmd.startswith('harmonize '):
                    parts = cmd.split()
                    filepath = resolve_path(parts[1])
                    h_type = parts[2] if len(parts) > 2 else 'thirds'
                    harmonize(filepath, h_type)
                elif cmd == 'list':
                    import glob
                    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
                    if files:
                        for f in files:
                            print(f"  {os.path.basename(f)}")
                    else:
                        print("  (파일 없음)")
                elif cmd == 'help':
                    print_help()
                else:
                    print(f"알 수 없는 명령: {cmd}")
            except (EOFError, KeyboardInterrupt):
                print()
                break
