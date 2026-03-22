"""
작곡자 (Composer) 에이전트
=========================
역할: MIDI 패턴 생성 및 음악 제작
- 사용자 세팅(BPM, 조성, 악기, 스타일 등)을 기반으로 MIDI 생성
- 기존 MIDI 파일 분석 후 변형/확장
- Ableton MCP를 통한 DAW 연동
"""

import mido
import os
import sys
import json
import random
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── MIDI 유틸리티 ───

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SCALES = {
    'major':         [0, 2, 4, 5, 7, 9, 11],
    'minor':         [0, 2, 3, 5, 7, 8, 10],
    'dorian':        [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':    [0, 2, 4, 5, 7, 9, 10],
    'pentatonic':    [0, 2, 4, 7, 9],
    'minor_penta':   [0, 3, 5, 7, 10],
    'blues':         [0, 3, 5, 6, 7, 10],
    'chromatic':     list(range(12)),
}

CHORD_PATTERNS = {
    'triad':    [0, 4, 7],
    'minor':    [0, 3, 7],
    'seventh':  [0, 4, 7, 11],
    'minor7':   [0, 3, 7, 10],
    'sus2':     [0, 2, 7],
    'sus4':     [0, 5, 7],
    'dim':      [0, 3, 6],
    'aug':      [0, 4, 8],
    'power':    [0, 7],
}

STYLE_PRESETS = {
    'ambient': {
        'bpm': 60, 'velocity_range': (20, 60), 'note_density': 0.3,
        'octave_range': (2, 6), 'sustain': True, 'chord_style': 'pad',
    },
    'pop': {
        'bpm': 120, 'velocity_range': (60, 100), 'note_density': 0.6,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'rhythm',
    },
    'cinematic': {
        'bpm': 80, 'velocity_range': (30, 90), 'note_density': 0.4,
        'octave_range': (1, 6), 'sustain': True, 'chord_style': 'arpeggio',
    },
    'edm': {
        'bpm': 128, 'velocity_range': (80, 127), 'note_density': 0.8,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'rhythm',
    },
    'jazz': {
        'bpm': 100, 'velocity_range': (40, 90), 'note_density': 0.5,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'walk',
    },
}


def note_to_midi(name, octave):
    """음이름+옥타브 → MIDI 번호"""
    return NOTE_NAMES.index(name) + (octave + 1) * 12


def midi_to_name(midi_num):
    """MIDI 번호 → 음이름+옥타브"""
    return f"{NOTE_NAMES[midi_num % 12]}{midi_num // 12 - 1}"


def get_scale_notes(root, scale_name, octave_low, octave_high):
    """스케일 내 모든 MIDI 노트 반환"""
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['major'])
    notes = []
    for oct in range(octave_low, octave_high + 1):
        for interval in intervals:
            midi_num = root_idx + interval + (oct + 1) * 12
            if 0 <= midi_num <= 127:
                notes.append(midi_num)
    return sorted(notes)


def load_settings():
    """설정 파일 로드"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return get_default_settings()


def get_default_settings():
    """기본 설정"""
    return {
        'bpm': 60,
        'key': 'A#',
        'scale': 'minor',
        'time_signature': '4/4',
        'style': 'ambient',
        'octave_range': [2, 6],
        'velocity_range': [20, 60],
        'measures': 16,
        'tracks': [
            {'name': 'Melody', 'channel': 0, 'type': 'melody'},
            {'name': 'Chords', 'channel': 1, 'type': 'chords'},
            {'name': 'Bass', 'channel': 2, 'type': 'bass'},
        ]
    }


# ─── 생성 엔진 ───

def generate_melody(scale_notes, settings, ticks_per_beat=480):
    """멜로디 트랙 생성"""
    track = mido.MidiTrack()
    track.name = 'Melody'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [40, 80])
    density = STYLE_PRESETS.get(settings.get('style', 'ambient'), {}).get('note_density', 0.5)

    # 멜로디 음역 (중간~높은 옥타브)
    melody_notes = [n for n in scale_notes if 60 <= n <= 96]
    if not melody_notes:
        melody_notes = scale_notes

    total_ticks = measures * 4 * ticks_per_beat
    current_tick = 0
    prev_note = random.choice(melody_notes)
    last_event_tick = 0

    while current_tick < total_ticks:
        if random.random() < density:
            # 인접 음 선호 (스텝 모션)
            candidates = [n for n in melody_notes if abs(n - prev_note) <= 5]
            if not candidates:
                candidates = melody_notes
            note = random.choice(candidates)
            vel = random.randint(vel_low, vel_high)

            # 노트 길이 (비트의 1/4 ~ 2배)
            durations = [ticks_per_beat // 4, ticks_per_beat // 2, ticks_per_beat, ticks_per_beat * 2]
            duration = random.choice(durations)

            delta = max(0, current_tick - last_event_tick)
            track.append(mido.Message('note_on', note=note, velocity=vel, time=delta, channel=0))
            track.append(mido.Message('note_off', note=note, velocity=0, time=duration, channel=0))
            last_event_tick = current_tick + delta + duration

            prev_note = note

        current_tick += ticks_per_beat // 2  # 8분음표 단위로 진행

    return track


def generate_chords(root, scale_name, settings, ticks_per_beat=480):
    """코드 트랙 생성"""
    track = mido.MidiTrack()
    track.name = 'Chords'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [30, 60])
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])

    # 코드 진행 생성 (디그리: I, IV, V, vi 등)
    degrees = [0, 3, 4, 0, 5, 3, 4, 0]  # 기본 진행
    chord_duration = ticks_per_beat * 4  # 한 마디

    last_event_tick = 0

    for m in range(measures):
        degree = degrees[m % len(degrees)]
        chord_root = root_idx + intervals[degree % len(intervals)] + 48  # 옥타브 3

        # 코드 타입 결정
        if degree in [0, 3, 4]:
            pattern = CHORD_PATTERNS['triad']
        else:
            pattern = CHORD_PATTERNS['minor']

        chord_notes = [chord_root + p for p in pattern if 0 <= chord_root + p <= 127]
        vel = random.randint(vel_low, vel_high)

        delta = max(0, (m * chord_duration) - last_event_tick)

        # 코드 노트 동시 발음
        for i, note in enumerate(chord_notes):
            track.append(mido.Message('note_on', note=note, velocity=vel, time=delta if i == 0 else 0, channel=1))

        # 코드 노트 동시 해제
        for i, note in enumerate(chord_notes):
            track.append(mido.Message('note_off', note=note, velocity=0, time=chord_duration if i == 0 else 0, channel=1))

        last_event_tick = (m + 1) * chord_duration

    return track


def generate_bass(root, scale_name, settings, ticks_per_beat=480):
    """베이스 트랙 생성"""
    track = mido.MidiTrack()
    track.name = 'Bass'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [40, 70])
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])

    bass_notes = get_scale_notes(root, scale_name, 1, 3)
    degrees = [0, 3, 4, 0, 5, 3, 4, 0]

    last_event_tick = 0

    for m in range(measures):
        degree = degrees[m % len(degrees)]
        bass_root = root_idx + intervals[degree % len(intervals)] + 36  # 옥타브 2
        bass_root = max(24, min(bass_root, 48))

        beat_duration = ticks_per_beat

        for beat in range(4):
            note = bass_root if beat == 0 else random.choice([n for n in bass_notes if abs(n - bass_root) <= 7] or [bass_root])
            vel = random.randint(vel_low, vel_high)
            tick_pos = m * 4 * ticks_per_beat + beat * ticks_per_beat
            delta = max(0, tick_pos - last_event_tick)

            track.append(mido.Message('note_on', note=note, velocity=vel, time=delta, channel=2))
            track.append(mido.Message('note_off', note=note, velocity=0, time=beat_duration, channel=2))
            last_event_tick = tick_pos + beat_duration

    return track


def compose(settings=None):
    """메인 작곡 함수"""
    if settings is None:
        settings = load_settings()

    bpm = settings.get('bpm', 60)
    key = settings.get('key', 'A#')
    scale = settings.get('scale', 'minor')
    tpb = 480

    print(f"🎵 작곡 시작")
    print(f"   Key: {key} {scale}")
    print(f"   BPM: {bpm}")
    print(f"   Style: {settings.get('style', 'ambient')}")
    print(f"   Measures: {settings.get('measures', 16)}")

    mid = mido.MidiFile(ticks_per_beat=tpb)

    # 메타 트랙
    meta_track = mido.MidiTrack()
    meta_track.name = 'Meta'
    meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    num, den = map(int, settings.get('time_signature', '4/4').split('/'))
    meta_track.append(mido.MetaMessage('time_signature', numerator=num, denominator=den))
    mid.tracks.append(meta_track)

    scale_notes = get_scale_notes(key, scale, *settings.get('octave_range', [2, 6]))

    # 트랙 생성
    for track_cfg in settings.get('tracks', []):
        track_type = track_cfg.get('type', 'melody')
        if track_type == 'melody':
            mid.tracks.append(generate_melody(scale_notes, settings, tpb))
            print(f"   ✓ Melody 트랙 생성")
        elif track_type == 'chords':
            mid.tracks.append(generate_chords(key, scale, settings, tpb))
            print(f"   ✓ Chords 트랙 생성")
        elif track_type == 'bass':
            mid.tracks.append(generate_bass(key, scale, settings, tpb))
            print(f"   ✓ Bass 트랙 생성")

    # 저장
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"composed_{key}_{scale}_{bpm}bpm_{timestamp}.mid"
    filepath = os.path.join(OUTPUT_DIR, filename)
    mid.save(filepath)

    # 리뷰용 메타데이터 저장
    meta = {
        'filename': filename,
        'filepath': filepath,
        'settings': settings,
        'created_at': timestamp,
        'tracks': [t.name for t in mid.tracks],
        'total_notes': sum(1 for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0),
        'duration_sec': mid.length,
        'status': 'pending_review',
    }
    meta_path = os.path.join(OUTPUT_DIR, f"{filename}.meta.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n📁 저장: {filepath}")
    print(f"📋 메타: {meta_path}")
    print(f"⏱  길이: {mid.length:.1f}초")
    print(f"🎹 총 노트: {meta['total_notes']}개")

    return filepath, meta


def analyze_midi(filepath):
    """기존 MIDI 파일 분석"""
    mid = mido.MidiFile(filepath)

    print(f"\n{'='*50}")
    print(f"MIDI 분석: {os.path.basename(filepath)}")
    print(f"{'='*50}")
    print(f"타입: Type {mid.type}")
    print(f"트랙: {len(mid.tracks)}개")
    print(f"BPM: ", end="")

    tempos = []
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'set_tempo':
                tempos.append(round(mido.tempo2bpm(msg.tempo), 1))

    if tempos:
        unique_tempos = list(set(tempos))
        print(f"{unique_tempos[0]}" + (f" (변동: {min(unique_tempos)}~{max(unique_tempos)})" if len(unique_tempos) > 1 else ""))
    else:
        print("정보 없음")

    print(f"길이: {mid.length:.1f}초 ({mid.length/60:.1f}분)")

    all_notes = []
    for track in mid.tracks:
        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                all_notes.append(msg.note)

    if all_notes:
        print(f"노트 수: {len(all_notes)}")
        print(f"음역: {midi_to_name(min(all_notes))} ~ {midi_to_name(max(all_notes))}")

        # 음 분포
        note_dist = {}
        for n in all_notes:
            name = NOTE_NAMES[n % 12]
            note_dist[name] = note_dist.get(name, 0) + 1

        print(f"\n음 분포:")
        max_count = max(note_dist.values())
        for name in NOTE_NAMES:
            count = note_dist.get(name, 0)
            bar = '█' * int(count / max_count * 20) if max_count > 0 and count > 0 else ''
            if count > 0:
                print(f"  {name:2s} | {bar} {count}")

    return {'notes': all_notes, 'length': mid.length, 'tracks': len(mid.tracks)}


# ─── CLI ───

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'compose':
            compose()
        elif cmd == 'analyze' and len(sys.argv) > 2:
            analyze_midi(sys.argv[2])
        elif cmd == 'settings':
            s = load_settings()
            print(json.dumps(s, indent=2, ensure_ascii=False))
        else:
            print(f"사용법: python composer.py [compose|analyze <file>|settings]")
    else:
        # 대화형 모드
        print("="*50)
        print("🎵 작곡자 에이전트 (Composer)")
        print("="*50)
        print("명령어:")
        print("  compose  - 현재 설정으로 작곡")
        print("  analyze  - MIDI 파일 분석")
        print("  settings - 현재 설정 확인")
        print("  quit     - 종료")
        print()

        while True:
            try:
                cmd = input("composer> ").strip()
                if cmd == 'quit':
                    break
                elif cmd == 'compose':
                    compose()
                elif cmd.startswith('analyze'):
                    parts = cmd.split(maxsplit=1)
                    if len(parts) > 1:
                        analyze_midi(parts[1])
                    else:
                        analyze_midi(os.path.join(PROJECT_DIR, '11.mid'))
                elif cmd == 'settings':
                    print(json.dumps(load_settings(), indent=2, ensure_ascii=False))
                elif cmd:
                    print(f"알 수 없는 명령: {cmd}")
            except (EOFError, KeyboardInterrupt):
                print()
                break
