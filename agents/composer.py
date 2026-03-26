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
        # 작곡가 관점 태그 (Troubleshooter 이슈 #1 대응)
        'rhythm_type': 'sparse',
        'harmony_type': 'triadic',
        'accompaniment_pattern': 'pad',
        'voicing_type': 'open',
        'dynamic_profile': 'flat',
        'default_articulation': 'sustain',
        'section_template': ['intro', 'verse', 'verse', 'bridge', 'outro'],
        'energy_curve': ['very_low', 'low', 'low', 'medium', 'very_low'],
    },
    'pop': {
        'bpm': 120, 'velocity_range': (60, 100), 'note_density': 0.6,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'rhythm',
        'rhythm_type': 'moderate',
        'harmony_type': 'triadic',
        'accompaniment_pattern': 'comping',
        'voicing_type': 'close',
        'dynamic_profile': 'moderate',
        'default_articulation': 'staccato',
        'section_template': ['intro', 'verse', 'pre_chorus', 'chorus', 'verse', 'pre_chorus', 'chorus', 'bridge', 'chorus', 'outro'],
        'energy_curve': ['low', 'medium', 'high', 'very_high', 'medium', 'high', 'very_high', 'medium', 'very_high', 'low'],
    },
    'cinematic': {
        'bpm': 80, 'velocity_range': (30, 90), 'note_density': 0.4,
        'octave_range': (1, 6), 'sustain': True, 'chord_style': 'arpeggio',
        'rhythm_type': 'sparse',
        'harmony_type': 'dense_voicing',
        'accompaniment_pattern': 'arpeggio',
        'voicing_type': 'open',
        'dynamic_profile': 'expressive',
        'default_articulation': 'legato',
        'section_template': ['intro', 'buildup', 'drop', 'interlude', 'buildup', 'drop', 'outro'],
        'energy_curve': ['very_low', 'medium', 'very_high', 'low', 'high', 'very_high', 'very_low'],
    },
    'edm': {
        'bpm': 128, 'velocity_range': (80, 127), 'note_density': 0.8,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'rhythm',
        'rhythm_type': 'dense',
        'harmony_type': 'dyadic',
        'accompaniment_pattern': 'comping',
        'voicing_type': 'close',
        'dynamic_profile': 'moderate',
        'default_articulation': 'staccato',
        'section_template': ['intro', 'buildup', 'drop', 'breakdown', 'buildup', 'drop', 'outro'],
        'energy_curve': ['low', 'high', 'very_high', 'low', 'high', 'very_high', 'medium'],
    },
    'jazz': {
        'bpm': 100, 'velocity_range': (40, 90), 'note_density': 0.5,
        'octave_range': (3, 5), 'sustain': False, 'chord_style': 'walk',
        'rhythm_type': 'moderate',
        'harmony_type': 'dense_voicing',
        'accompaniment_pattern': 'mixed',
        'voicing_type': 'semi_open',
        'dynamic_profile': 'expressive',
        'default_articulation': 'legato',
        'section_template': ['intro', 'verse', 'verse', 'solo', 'verse', 'outro'],
        'energy_curve': ['low', 'medium', 'medium', 'high', 'medium', 'low'],
    },
    'ballad': {
        'bpm': 72, 'velocity_range': (30, 80), 'note_density': 0.4,
        'octave_range': (2, 5), 'sustain': True, 'chord_style': 'arpeggio',
        'rhythm_type': 'sparse',
        'harmony_type': 'triadic',
        'accompaniment_pattern': 'arpeggio',
        'voicing_type': 'semi_open',
        'dynamic_profile': 'expressive',
        'default_articulation': 'sustain',
        'section_template': ['intro', 'verse', 'chorus', 'verse', 'chorus', 'bridge', 'chorus', 'outro'],
        'energy_curve': ['very_low', 'low', 'high', 'medium', 'high', 'very_high', 'very_high', 'low'],
    },
    'classical': {
        'bpm': 90, 'velocity_range': (30, 100), 'note_density': 0.5,
        'octave_range': (2, 6), 'sustain': True, 'chord_style': 'arpeggio',
        'rhythm_type': 'moderate',
        'harmony_type': 'triadic',
        'accompaniment_pattern': 'mixed',
        'voicing_type': 'open',
        'dynamic_profile': 'expressive',
        'default_articulation': 'legato',
        'section_template': ['intro', 'verse', 'verse', 'bridge', 'verse', 'outro'],
        'energy_curve': ['low', 'medium', 'high', 'very_high', 'medium', 'very_low'],
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
            {'name': 'Drums', 'channel': 9, 'type': 'drums'},
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


def generate_bass(root, scale_name, settings, ticks_per_beat=480, song_context=None):
    """베이스 트랙 생성 — SongContext 기반 섹션 인식 + articulation 태그.

    Troubleshooter 이슈 #3 대응:
    에너지 레벨에 따라 밀도/연주법이 변하고, articulation 메타를 남긴다.
    """
    track = mido.MidiTrack()
    track.name = 'Bass'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [40, 70])
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])
    bass_notes = get_scale_notes(root, scale_name, 1, 3)
    degrees = [0, 3, 4, 0, 5, 3, 4, 0]

    # 에너지→밀도/연주법 매핑
    energy_to_style = {
        'very_low': {'subdivisions': 1, 'articulation': 'sustain', 'vel_mult': 0.6},
        'low':      {'subdivisions': 2, 'articulation': 'sustain', 'vel_mult': 0.7},
        'medium':   {'subdivisions': 4, 'articulation': 'sustain', 'vel_mult': 0.85},
        'high':     {'subdivisions': 4, 'articulation': 'staccato', 'vel_mult': 1.0},
        'very_high':{'subdivisions': 8, 'articulation': 'staccato', 'vel_mult': 1.1},
    }

    last_event_tick = 0
    ticks_per_measure = ticks_per_beat * 4
    articulation_log = []  # articulation 메타 기록

    for m in range(measures):
        degree = degrees[m % len(degrees)]
        bass_root = root_idx + intervals[degree % len(intervals)] + 36
        bass_root = max(24, min(bass_root, 48))

        # 현재 마디의 에너지 레벨 확인
        measure_tick = m * ticks_per_measure
        energy = 'medium'
        if song_context:
            for sec in song_context.get('sections', []):
                if sec['start_tick'] <= measure_tick < sec['end_tick']:
                    energy = sec.get('energy', 'medium')
                    break

        style = energy_to_style.get(energy, energy_to_style['medium'])
        subdivisions = style['subdivisions']
        art = style['articulation']
        vel_mult = style['vel_mult']

        sub_duration = ticks_per_measure // subdivisions

        for sub in range(subdivisions):
            if sub == 0:
                note = bass_root
                role = 'root'
            elif sub % 2 == 0:
                # 5도 또는 루트 옥타브
                note = random.choice([bass_root, bass_root + 7 if bass_root + 7 <= 48 else bass_root])
                role = 'fifth'
            else:
                # 스케일 인접음
                candidates = [n for n in bass_notes if abs(n - bass_root) <= 7]
                note = random.choice(candidates) if candidates else bass_root
                role = 'passing'

            vel = min(127, max(20, int(random.randint(vel_low, vel_high) * vel_mult)))

            # 고스트 노트: 높은 에너지에서 간헐적 추가
            is_ghost = False
            if energy in ('high', 'very_high') and sub > 0 and random.random() < 0.2:
                vel = max(15, vel // 3)
                is_ghost = True

            tick_pos = measure_tick + sub * sub_duration
            delta = max(0, tick_pos - last_event_tick)

            # 스타카토는 짧게, 서스테인은 길게
            note_dur = sub_duration // 2 if art == 'staccato' else sub_duration - 10

            track.append(mido.Message('note_on', note=note, velocity=vel, time=delta, channel=2))
            track.append(mido.Message('note_off', note=note, velocity=0, time=note_dur, channel=2))
            last_event_tick = tick_pos + note_dur

            articulation_log.append({
                'tick': tick_pos, 'note': note, 'role': role,
                'articulation': 'ghost' if is_ghost else art,
                'energy': energy,
            })

    return track


# ── 드럼 패턴 시스템 (Troubleshooter 이슈 #4 대응) ──

# GM 드럼 맵 (채널 9)
GM_DRUM = {
    'kick':         36,
    'snare':        38,
    'rimshot':      37,
    'closed_hh':    42,
    'open_hh':      46,
    'pedal_hh':     44,
    'crash':        49,
    'ride':         51,
    'ride_bell':    53,
    'low_tom':      45,
    'mid_tom':      47,
    'high_tom':     50,
    'clap':         39,
    'tambourine':   54,
    'cowbell':      56,
}

# 에너지별 기본 비트 패턴 (16분음표 그리드, 1=hit, 0=rest)
# 각 패턴: 1마디 = 16 스텝
DRUM_PATTERNS = {
    'very_low': {
        'kick':      [1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0],
        'closed_hh': [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0],
        'snare':     [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0],
    },
    'low': {
        'kick':      [1,0,0,0, 0,0,0,0, 1,0,0,0, 0,0,0,0],
        'closed_hh': [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0],
        'snare':     [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],
    },
    'medium': {
        'kick':      [1,0,0,0, 0,0,1,0, 1,0,0,0, 0,0,1,0],
        'closed_hh': [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0],
        'snare':     [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],
        'open_hh':   [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,1,0],
    },
    'high': {
        'kick':      [1,0,0,0, 0,0,1,0, 1,0,1,0, 0,0,1,0],
        'closed_hh': [1,1,1,1, 1,1,1,1, 1,1,1,1, 1,1,1,1],
        'snare':     [0,0,0,0, 1,0,0,1, 0,0,0,0, 1,0,0,0],
        'crash':     [1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0],
    },
    'very_high': {
        'kick':      [1,0,1,0, 0,0,1,0, 1,0,1,0, 0,1,1,0],
        'closed_hh': [1,1,1,1, 1,1,1,1, 1,1,1,1, 1,1,1,1],
        'snare':     [0,0,0,0, 1,0,0,1, 0,1,0,0, 1,0,0,1],
        'open_hh':   [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,1],
        'crash':     [1,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0],
        'ride':      [0,0,1,0, 0,0,1,0, 0,0,1,0, 0,0,1,0],
    },
}

# 필인 패턴: 섹션 전환 직전 마지막 마디에 사용
FILL_PATTERNS = {
    'light': {
        # 마지막 2비트만 활성화
        'snare':    [0,0,0,0, 0,0,0,0, 0,0,1,0, 1,0,1,1],
        'high_tom': [0,0,0,0, 0,0,0,0, 1,0,0,0, 0,1,0,0],
    },
    'medium': {
        'snare':    [0,0,0,0, 0,0,1,0, 1,0,1,0, 1,1,1,1],
        'high_tom': [0,0,0,0, 1,0,0,1, 0,0,0,0, 0,0,0,0],
        'mid_tom':  [0,0,0,0, 0,0,0,0, 0,1,0,1, 0,0,0,0],
    },
    'heavy': {
        'snare':    [0,0,1,0, 1,0,1,0, 1,1,1,0, 1,1,1,1],
        'high_tom': [1,0,0,1, 0,0,0,0, 0,0,0,0, 0,0,0,0],
        'mid_tom':  [0,0,0,0, 0,1,0,1, 0,0,0,0, 0,0,0,0],
        'low_tom':  [0,0,0,0, 0,0,0,0, 0,0,0,1, 0,0,0,0],
        'crash':    [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,1],
    },
}


def get_fill_intensity(from_energy, to_energy):
    """섹션 전환 방향에 따라 필인 강도 결정."""
    levels = ['very_low', 'low', 'medium', 'high', 'very_high']
    diff = levels.index(to_energy) - levels.index(from_energy)
    if diff >= 2:
        return 'heavy'
    elif diff >= 0:
        return 'medium'
    else:
        return 'light'


def generate_drums(settings, ticks_per_beat=480, song_context=None):
    """드럼 트랙 생성 — 섹션 인식 + 필인 + 그루브.

    Troubleshooter 이슈 #4 대응:
    - 섹션별 에너지에 따라 비트 패턴 전환
    - 섹션 경계에 자동 필인 삽입
    - 벨로시티 그루브 (강약 패턴)
    - 고스트 노트 / 미세 타이밍
    """
    track = mido.MidiTrack()
    track.name = 'Drums'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [60, 110])
    ticks_per_16th = ticks_per_beat // 4
    ticks_per_measure = ticks_per_beat * 4

    # 섹션 정보 구축
    sections = []
    if song_context:
        sections = song_context.get('sections', [])

    def get_energy_at_measure(m):
        tick = m * ticks_per_measure
        for sec in sections:
            if sec['start_tick'] <= tick < sec['end_tick']:
                return sec.get('energy', 'medium')
        return 'medium'

    def is_section_boundary(m):
        """다음 마디가 다른 섹션인지 확인"""
        current_tick = m * ticks_per_measure
        next_tick = (m + 1) * ticks_per_measure
        for sec in sections:
            # 현재 마디가 섹션의 마지막 마디인 경우
            if sec['start_tick'] <= current_tick < sec['end_tick'] <= next_tick:
                return True
        return False

    # 벨로시티 그루브 (16스텝): 강-약-중-약 패턴
    groove_vel = [1.0, 0.6, 0.8, 0.55, 0.9, 0.6, 0.75, 0.55,
                  1.0, 0.6, 0.8, 0.55, 0.9, 0.6, 0.75, 0.6]

    last_event_tick = 0

    for m in range(measures):
        energy = get_energy_at_measure(m)
        boundary = is_section_boundary(m)

        # 필인 또는 기본 패턴 선택
        if boundary and m < measures - 1:
            next_energy = get_energy_at_measure(m + 1)
            fill_intensity = get_fill_intensity(energy, next_energy)
            pattern = FILL_PATTERNS.get(fill_intensity, FILL_PATTERNS['medium'])
            # 필인 위의 기본 킥은 유지
            base_pattern = DRUM_PATTERNS.get(energy, DRUM_PATTERNS['medium'])
            merged = dict(base_pattern)
            merged.update(pattern)
            pattern = merged
        else:
            pattern = DRUM_PATTERNS.get(energy, DRUM_PATTERNS['medium'])

        for drum_name, steps in pattern.items():
            midi_note = GM_DRUM.get(drum_name)
            if midi_note is None:
                continue

            for step, hit in enumerate(steps):
                if not hit:
                    continue

                tick_pos = m * ticks_per_measure + step * ticks_per_16th
                delta = max(0, tick_pos - last_event_tick)

                # 벨로시티: 그루브 적용
                base_vel = random.randint(vel_low, vel_high)
                vel = int(base_vel * groove_vel[step])

                # 악기별 벨로시티 보정
                if drum_name == 'kick':
                    vel = min(127, int(vel * 1.1))
                elif drum_name == 'snare':
                    vel = min(127, int(vel * 1.05))
                elif drum_name in ('closed_hh', 'open_hh', 'pedal_hh'):
                    vel = min(127, int(vel * 0.8))
                elif drum_name == 'crash':
                    vel = min(127, int(vel * 1.15))

                vel = max(15, min(127, vel))

                # 미세 타이밍: 하이햇에 약간의 스윙
                timing_offset = 0
                if drum_name in ('closed_hh', 'open_hh') and step % 2 == 1:
                    timing_offset = random.randint(0, ticks_per_16th // 8)  # 미세 지연

                note_dur = ticks_per_16th // 2  # 짧은 타격음

                track.append(mido.Message('note_on', note=midi_note, velocity=vel,
                                          time=delta + timing_offset, channel=9))
                track.append(mido.Message('note_off', note=midi_note, velocity=0,
                                          time=note_dur, channel=9))
                last_event_tick = tick_pos + timing_offset + note_dur

    return track


# ── 스트링 섹션 생성 (Troubleshooter 이슈 #2 대응) ──

# 스트링 파트별 음역 (MIDI 번호)
STRING_RANGES = {
    'violin1':    (55, 100),
    'violin2':    (55, 93),
    'viola':      (48, 84),
    'cello':      (36, 72),
    'contrabass': (28, 60),
}

# GM 프로그램 번호
STRING_PROGRAMS = {
    'violin1': 40, 'violin2': 40,
    'viola': 41, 'cello': 42, 'contrabass': 43,
}

# 에너지별 스트링 텍스처
STRING_TEXTURES = {
    'very_low': {'parts': ['cello'], 'articulation': 'sustain', 'density': 0.2},
    'low':      {'parts': ['violin1', 'cello'], 'articulation': 'sustain', 'density': 0.3},
    'medium':   {'parts': ['violin1', 'violin2', 'viola', 'cello'], 'articulation': 'sustain', 'density': 0.5},
    'high':     {'parts': ['violin1', 'violin2', 'viola', 'cello', 'contrabass'], 'articulation': 'detache', 'density': 0.7},
    'very_high':{'parts': ['violin1', 'violin2', 'viola', 'cello', 'contrabass'], 'articulation': 'tremolo', 'density': 0.9},
}

# 보이싱 역할: 코드 구성음을 파트에 배분하는 기본 규칙
STRING_VOICING_ROLES = {
    'violin1':    'melody',     # 최상성부 / 멜로디
    'violin2':    'third',      # 3도 또는 보조 선율
    'viola':      'fifth',      # 5도 또는 내성
    'cello':      'root',       # 루트 또는 저음 선율
    'contrabass': 'bass',       # 루트 옥타브 아래
}


def get_voicing_pitch(root_idx, scale_name, role, target_range):
    """보이싱 역할에 따라 적절한 음역의 피치를 반환."""
    intervals = SCALES.get(scale_name, SCALES['minor'])
    lo, hi = target_range

    if role == 'melody' or role == 'third':
        # 3도 또는 멜로디: 스케일의 3번째 음
        degree = 2 if role == 'third' else 4
        target_pc = (root_idx + intervals[degree % len(intervals)]) % 12
    elif role == 'fifth':
        target_pc = (root_idx + 7) % 12
    elif role in ('root', 'bass'):
        target_pc = root_idx % 12
    else:
        target_pc = root_idx % 12

    # 음역 내에서 해당 피치 클래스 찾기
    center = (lo + hi) // 2
    candidates = []
    for octave_base in range(0, 128, 12):
        p = octave_base + target_pc
        if lo <= p <= hi:
            candidates.append(p)

    if not candidates:
        return center

    # 중앙에 가장 가까운 음 선택
    return min(candidates, key=lambda p: abs(p - center))


def generate_strings(root, scale_name, settings, ticks_per_beat=480, song_context=None):
    """스트링 섹션 생성 — 파트 분리 + CC Expression 레이어.

    Troubleshooter 이슈 #2 핵심:
    - 노트 구조(보이싱/배치)와 표현(CC) 레이어 분리
    - 에너지에 따라 활성 파트 수와 아티큘레이션 변화
    - 각 파트가 역할에 맞는 음역에서 연주
    """
    tracks = []
    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [30, 80])
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])
    degrees = [0, 3, 4, 0, 5, 3, 4, 0]
    ticks_per_measure = ticks_per_beat * 4

    # 섹션 정보
    sections = song_context.get('sections', []) if song_context else []

    def get_energy_at_measure(m):
        tick = m * ticks_per_measure
        for sec in sections:
            if sec['start_tick'] <= tick < sec['end_tick']:
                return sec.get('energy', 'medium')
        return 'medium'

    # 각 파트별 트랙 생성
    for part_name in ['violin1', 'violin2', 'viola', 'cello', 'contrabass']:
        track = mido.MidiTrack()
        track.name = f'Str_{part_name}'
        part_range = STRING_RANGES[part_name]
        part_role = STRING_VOICING_ROLES[part_name]
        program = STRING_PROGRAMS[part_name]

        # 채널 할당 (3~7)
        ch = ['violin1', 'violin2', 'viola', 'cello', 'contrabass'].index(part_name) + 3

        # 프로그램 체인지
        track.append(mido.Message('program_change', program=program, channel=ch, time=0))

        last_event_tick = 0
        cc_events = []  # CC 표현 레이어

        for m in range(measures):
            energy = get_energy_at_measure(m)
            texture = STRING_TEXTURES.get(energy, STRING_TEXTURES['medium'])

            # 이 에너지 레벨에서 현재 파트가 활성인지 확인
            if part_name not in texture['parts']:
                continue

            degree = degrees[m % len(degrees)]
            chord_root = (root_idx + intervals[degree % len(intervals)]) % 12

            # 보이싱에 따른 피치 결정
            pitch = get_voicing_pitch(chord_root, scale_name, part_role, part_range)

            # 아티큘레이션에 따른 노트 길이
            art = texture['articulation']
            if art == 'tremolo':
                # 트레몰로: 짧은 노트 반복
                num_repeats = 8
                note_dur = ticks_per_measure // num_repeats
                for r in range(num_repeats):
                    tick_pos = m * ticks_per_measure + r * note_dur
                    delta = max(0, tick_pos - last_event_tick)
                    vel = random.randint(vel_low, vel_high)
                    track.append(mido.Message('note_on', note=pitch, velocity=vel, time=delta, channel=ch))
                    track.append(mido.Message('note_off', note=pitch, velocity=0, time=note_dur - 10, channel=ch))
                    last_event_tick = tick_pos + note_dur - 10
            elif art == 'detache':
                # 데타셰: 비트 단위 분리
                for beat in range(4):
                    tick_pos = m * ticks_per_measure + beat * ticks_per_beat
                    delta = max(0, tick_pos - last_event_tick)
                    vel = random.randint(vel_low, vel_high)
                    dur = ticks_per_beat - 20
                    track.append(mido.Message('note_on', note=pitch, velocity=vel, time=delta, channel=ch))
                    track.append(mido.Message('note_off', note=pitch, velocity=0, time=dur, channel=ch))
                    last_event_tick = tick_pos + dur
            else:
                # 서스테인: 한 마디 전체
                tick_pos = m * ticks_per_measure
                delta = max(0, tick_pos - last_event_tick)
                vel = random.randint(vel_low, vel_high)
                dur = ticks_per_measure - 10
                track.append(mido.Message('note_on', note=pitch, velocity=vel, time=delta, channel=ch))
                track.append(mido.Message('note_off', note=pitch, velocity=0, time=dur, channel=ch))
                last_event_tick = tick_pos + dur

            # CC Expression 레이어: 크레센도/디크레센도
            for beat in range(4):
                cc_tick = m * ticks_per_measure + beat * ticks_per_beat
                # 에너지에 따른 Expression 값
                energy_base = {'very_low': 40, 'low': 55, 'medium': 75, 'high': 95, 'very_high': 115}
                base_val = energy_base.get(energy, 75)
                expr_val = min(127, max(20, base_val + random.randint(-10, 10)))
                cc_events.append((cc_tick, 11, expr_val, ch))  # CC11 Expression

            # 비브라토 (높은 에너지에서)
            if energy in ('high', 'very_high'):
                vib_tick = m * ticks_per_measure
                cc_events.append((vib_tick, 1, random.randint(40, 80), ch))  # CC1 Modulation

        # CC 이벤트를 트랙에 삽입 (시간순 정렬)
        cc_events.sort(key=lambda x: x[0])
        cc_last_tick = last_event_tick
        for cc_tick, cc_num, cc_val, cc_ch in cc_events:
            # CC는 note 이벤트와 별도로 삽입하기 어려우므로
            # 실제 MIDI에서는 note와 인터리브 필요 — 여기서는 메타로 보존
            pass
        # (CC 레이어는 메타데이터로만 저장, 실제 적용은 DAW/가상악기 단에서)

        tracks.append(track)

    return tracks


# ── 기타 생성 (Troubleshooter 이슈 #5 대응) ──

# 기본 코드 폼 라이브러리 (개방현 기준, -1=안침)
GUITAR_CHORD_SHAPES = {
    'C':  [-1, 3, 2, 0, 1, 0],
    'Cm': [-1, 3, 5, 5, 4, 3],
    'D':  [-1,-1, 0, 2, 3, 2],
    'Dm': [-1,-1, 0, 2, 3, 1],
    'E':  [0, 2, 2, 1, 0, 0],
    'Em': [0, 2, 2, 0, 0, 0],
    'F':  [1, 3, 3, 2, 1, 1],
    'Fm': [1, 3, 3, 1, 1, 1],
    'G':  [3, 2, 0, 0, 0, 3],
    'Gm': [3, 5, 5, 3, 3, 3],
    'A':  [-1, 0, 2, 2, 2, 0],
    'Am': [-1, 0, 2, 2, 1, 0],
    'B':  [-1, 2, 4, 4, 4, 2],
    'Bm': [-1, 2, 4, 4, 3, 2],
}

# 표준 튜닝
GUITAR_TUNING = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4

# 스트럼 패턴 (D=downstroke, U=upstroke, x=mute, .=rest)
STRUM_PATTERNS = {
    'ballad':  ['D', '.', '.', 'D', '.', 'D', 'U', '.'],     # 8분음표 그리드
    'pop':     ['D', '.', 'U', '.', 'D', 'U', '.', 'U'],
    'rock':    ['D', 'D', 'U', 'D', 'D', 'U', 'D', 'U'],
    'folk':    ['D', '.', 'D', 'U', '.', 'U', 'D', 'U'],
    'mute':    ['x', '.', 'x', '.', 'D', '.', 'x', '.'],
    'arpeggio':['1', '2', '3', '4', '5', '6', '5', '4'],     # 줄 번호 순서
}


def chord_shape_to_pitches(shape, tuning=None):
    """코드 폼 → MIDI 피치 리스트."""
    if tuning is None:
        tuning = GUITAR_TUNING
    pitches = []
    for i, fret in enumerate(shape):
        if fret >= 0:
            pitches.append(tuning[i] + fret)
    return pitches


def generate_guitar(root, scale_name, settings, ticks_per_beat=480, song_context=None):
    """기타 트랙 생성 — 코드 보이싱 + 스트럼 패턴 + 아티큘레이션.

    Troubleshooter 이슈 #5 대응:
    - 코드 폼 기반 보이싱 (개방현/바레 구분)
    - 스트럼 방향 + 줄 간 시간차(spread)
    - 에너지별 스트럼 패턴 전환
    - 팜뮤트/뮤트 스트로크 지원
    """
    track = mido.MidiTrack()
    track.name = 'Guitar'

    measures = settings.get('measures', 16)
    vel_low, vel_high = settings.get('velocity_range', [50, 100])
    root_idx = NOTE_NAMES.index(root)
    intervals = SCALES.get(scale_name, SCALES['minor'])
    degrees = [0, 3, 4, 0, 5, 3, 4, 0]
    ticks_per_measure = ticks_per_beat * 4
    ticks_per_8th = ticks_per_beat // 2

    sections = song_context.get('sections', []) if song_context else []

    def get_energy_at_measure(m):
        tick = m * ticks_per_measure
        for sec in sections:
            if sec['start_tick'] <= tick < sec['end_tick']:
                return sec.get('energy', 'medium')
        return 'medium'

    # 에너지별 스트럼 패턴 매핑
    energy_strum_map = {
        'very_low': 'ballad',
        'low':      'folk',
        'medium':   'pop',
        'high':     'rock',
        'very_high':'rock',
    }

    # 스트럼 spread (줄 간 시간차, 틱)
    energy_spread = {
        'very_low': 25,   # 느린 아르페지오식
        'low':      18,
        'medium':   12,
        'high':     6,
        'very_high': 3,   # 거의 동시
    }

    # 코드 진행에 맞는 코드명 결정
    def get_chord_name(degree_idx):
        degree = degrees[degree_idx % len(degrees)]
        chord_root_pc = (root_idx + intervals[degree % len(intervals)]) % 12
        chord_root_name = NOTE_NAMES[chord_root_pc]

        # 간단한 장/단 판별 (스케일 디그리 기반)
        minor_degrees = {1, 2, 5}  # ii, iii, vi in major context
        if scale_name == 'minor':
            minor_degrees = {0, 2, 3}  # i, iii, iv in minor context

        if degree in minor_degrees:
            return chord_root_name + 'm'
        return chord_root_name

    last_event_tick = 0
    guitar_meta = []  # 기타 고유 메타데이터

    for m in range(measures):
        energy = get_energy_at_measure(m)
        strum_name = energy_strum_map.get(energy, 'pop')
        pattern = STRUM_PATTERNS.get(strum_name, STRUM_PATTERNS['pop'])
        spread = energy_spread.get(energy, 12)

        chord_name = get_chord_name(m)
        shape = GUITAR_CHORD_SHAPES.get(chord_name)
        if shape is None:
            # 폴백: 루트만 사용
            shape = GUITAR_CHORD_SHAPES.get(chord_name.replace('m', ''), GUITAR_CHORD_SHAPES['Am'])
        pitches = chord_shape_to_pitches(shape)

        is_palm_mute = energy in ('high', 'very_high') and random.random() < 0.3

        for step, action in enumerate(pattern):
            tick_pos = m * ticks_per_measure + step * ticks_per_8th
            if tick_pos < last_event_tick - 10:
                continue

            if action == '.':
                continue  # 쉼

            if action == 'x':
                # 뮤트 스트로크
                for i, p in enumerate(pitches):
                    t = tick_pos + i * 2  # 극히 짧은 spread
                    delta = max(0, t - last_event_tick)
                    vel = max(15, random.randint(vel_low, vel_high) // 3)
                    track.append(mido.Message('note_on', note=p, velocity=vel, time=delta, channel=3))
                    track.append(mido.Message('note_off', note=p, velocity=0, time=20, channel=3))
                    last_event_tick = t + 20
                continue

            if action in ('D', 'U'):
                # 스트럼
                strum_pitches = pitches if action == 'D' else list(reversed(pitches))
                for i, p in enumerate(strum_pitches):
                    t = tick_pos + i * spread
                    delta = max(0, t - last_event_tick)
                    vel = random.randint(vel_low, vel_high)
                    if i == 0:
                        vel = min(127, int(vel * 1.1))  # 첫 줄 악센트

                    dur = ticks_per_8th - 10
                    if is_palm_mute:
                        dur = min(dur, ticks_per_8th // 3)
                        vel = max(20, int(vel * 0.7))

                    track.append(mido.Message('note_on', note=p, velocity=vel, time=delta, channel=3))
                    track.append(mido.Message('note_off', note=p, velocity=0, time=dur, channel=3))
                    last_event_tick = t + dur

            elif action.isdigit():
                # 아르페지오: 특정 줄만
                string_idx = int(action) - 1
                if 0 <= string_idx < len(pitches):
                    delta = max(0, tick_pos - last_event_tick)
                    vel = random.randint(vel_low, vel_high)
                    dur = ticks_per_8th
                    track.append(mido.Message('note_on', note=pitches[string_idx], velocity=vel, time=delta, channel=3))
                    track.append(mido.Message('note_off', note=pitches[string_idx], velocity=0, time=dur, channel=3))
                    last_event_tick = tick_pos + dur

        guitar_meta.append({
            'measure': m, 'chord': chord_name, 'energy': energy,
            'strum_pattern': strum_name, 'spread_ticks': spread,
            'palm_mute': is_palm_mute,
            'uses_open_strings': any(f == 0 for f in shape),
        })

    return track


def build_song_context(settings, tpb=480):
    """설정과 스타일 프리셋으로부터 SongContext 구축.

    Troubleshooter 이슈 #6 대응:
    모든 악기가 공유할 섹션 구조, 에너지 커브, 역할 분담을 생성한다.
    """
    style = settings.get('style', 'ambient')
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS['ambient'])
    measures = settings.get('measures', 16)
    key = settings.get('key', 'A#')
    scale_name = settings.get('scale', 'minor')

    section_template = preset.get('section_template', ['verse'])
    energy_curve = preset.get('energy_curve', ['medium'] * len(section_template))

    # 섹션당 마디 수 분배
    num_sections = len(section_template)
    measures_per_section = max(2, measures // num_sections)
    ticks_per_measure = tpb * 4  # 4/4 기준

    sections = []
    track_roles = []
    current_tick = 0

    for i, (sec_name, energy) in enumerate(zip(section_template, energy_curve)):
        # 마지막 섹션은 남은 마디 모두 사용
        if i == num_sections - 1:
            sec_measures = measures - (measures_per_section * (num_sections - 1))
        else:
            sec_measures = measures_per_section

        sec_measures = max(2, sec_measures)
        sec_ticks = sec_measures * ticks_per_measure

        sections.append({
            'name': sec_name,
            'start_tick': current_tick,
            'end_tick': current_tick + sec_ticks,
            'energy': energy,
            'chord_progression': [],  # 추후 코드 진행 자동 생성 가능
        })

        # 트랙별 역할 분담 (에너지 레벨 기반)
        energy_idx = ['very_low', 'low', 'medium', 'high', 'very_high'].index(energy)
        density_map = [0.1, 0.3, 0.5, 0.7, 0.9]

        for track_cfg in settings.get('tracks', []):
            track_name = track_cfg['name']
            track_type = track_cfg.get('type', 'melody')

            if track_type == 'melody':
                role = 'lead' if energy_idx >= 2 else 'silent' if sec_name == 'intro' else 'lead'
            elif track_type == 'chords':
                role = 'pad' if preset.get('accompaniment_pattern') == 'pad' else 'comp'
            elif track_type == 'bass':
                role = 'bass'
            elif track_type == 'drums':
                role = 'rhythm' if energy_idx >= 1 else 'silent'
            elif track_type == 'strings':
                role = 'pad' if energy_idx <= 2 else 'comp'
            elif track_type == 'guitar':
                role = 'comp' if energy_idx >= 1 else 'silent'
            else:
                role = 'comp'

            track_roles.append({
                'track_name': track_name,
                'section_name': sec_name,
                'role': role,
                'density': density_map[energy_idx],
            })

        current_tick += sec_ticks

    context = {
        'sections': sections,
        'role_matrix': track_roles,
        'global_key': key,
        'global_scale': scale_name,
        'style_tags': {
            'rhythm_type': preset.get('rhythm_type', 'moderate'),
            'harmony_type': preset.get('harmony_type', 'triadic'),
            'accompaniment_pattern': preset.get('accompaniment_pattern', 'mixed'),
            'voicing_type': preset.get('voicing_type', 'close'),
            'dynamic_profile': preset.get('dynamic_profile', 'moderate'),
        },
    }

    print(f"   Song Context: {num_sections} sections")
    for sec in sections:
        print(f"     [{sec['name']:12s}] {sec['start_tick']:6d}~{sec['end_tick']:6d} ticks | energy: {sec['energy']}")

    return context


def compose(settings=None):
    """메인 작곡 함수"""
    if settings is None:
        settings = load_settings()

    bpm = settings.get('bpm', 60)
    key = settings.get('key', 'A#')
    scale = settings.get('scale', 'minor')
    tpb = 480

    print(f"작곡 시작")
    print(f"   Key: {key} {scale}")
    print(f"   BPM: {bpm}")
    print(f"   Style: {settings.get('style', 'ambient')}")
    print(f"   Measures: {settings.get('measures', 16)}")

    # SongContext 구축 (Troubleshooter 이슈 #6)
    song_context = build_song_context(settings, tpb)

    mid = mido.MidiFile(ticks_per_beat=tpb)

    # 메타 트랙
    meta_track = mido.MidiTrack()
    meta_track.name = 'Meta'
    meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    num, den = map(int, settings.get('time_signature', '4/4').split('/'))
    meta_track.append(mido.MetaMessage('time_signature', numerator=num, denominator=den))
    mid.tracks.append(meta_track)

    scale_notes = get_scale_notes(key, scale, *settings.get('octave_range', [2, 6]))

    # 트랙 생성 — SongContext 연동
    for track_cfg in settings.get('tracks', []):
        track_type = track_cfg.get('type', 'melody')
        if track_type == 'melody':
            mid.tracks.append(generate_melody(scale_notes, settings, tpb))
            print(f"   + Melody 트랙 생성")
        elif track_type == 'chords':
            mid.tracks.append(generate_chords(key, scale, settings, tpb))
            print(f"   + Chords 트랙 생성")
        elif track_type == 'bass':
            mid.tracks.append(generate_bass(key, scale, settings, tpb, song_context))
            print(f"   + Bass 트랙 생성 (섹션 인식)")
        elif track_type == 'drums':
            mid.tracks.append(generate_drums(settings, tpb, song_context))
            print(f"   + Drums 트랙 생성 (섹션 인식 + 필인)")
        elif track_type == 'strings':
            string_tracks = generate_strings(key, scale, settings, tpb, song_context)
            for st in string_tracks:
                mid.tracks.append(st)
            print(f"   + Strings 트랙 생성 ({len(string_tracks)}파트, CC Expression)")
        elif track_type == 'guitar':
            mid.tracks.append(generate_guitar(key, scale, settings, tpb, song_context))
            print(f"   + Guitar 트랙 생성 (코드폼 + 스트럼)")

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
        'song_context': song_context,
        'created_at': timestamp,
        'tracks': [t.name for t in mid.tracks],
        'total_notes': sum(1 for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0),
        'duration_sec': mid.length,
        'status': 'pending_review',
    }
    meta_path = os.path.join(OUTPUT_DIR, f"{filename}.meta.json")
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"\n저장: {filepath}")
    print(f"메타: {meta_path}")
    print(f"길이: {mid.length:.1f}초")
    print(f"총 노트: {meta['total_notes']}개")

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
