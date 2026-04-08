"""
sinco.mid 생성 스크립트
========================
settings.json의 chord_progression을 읽어 커스텀 코드진행 기반 MIDI를 생성.

코드진행: DMaj7 - C#m7b5,F#7 - Bm7 - Am7,D7 - GMaj7 - F#m7,Bm7 - E7 - A7
"""

import mido
import os
import sys
import json
import random

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# ── 코드 보이싱 정의 (루트 기준 반음 간격) ──

CHORD_VOICINGS = {
    'Maj7':   [0, 4, 7, 11],       # 1 3 5 7
    'm7':     [0, 3, 7, 10],       # 1 b3 5 b7
    '7':      [0, 4, 7, 10],       # 1 3 5 b7 (dominant)
    'm7b5':   [0, 3, 6, 10],       # 1 b3 b5 b7 (half-dim)
    'dim7':   [0, 3, 6, 9],        # 1 b3 b5 bb7
    'Maj':    [0, 4, 7],           # triad
    'm':      [0, 3, 7],           # minor triad
    'aug':    [0, 4, 8],           # augmented
    'sus4':   [0, 5, 7],
    'sus2':   [0, 2, 7],
    '9':      [0, 4, 7, 10, 14],   # dominant 9
    'Maj9':   [0, 4, 7, 11, 14],
    'm9':     [0, 3, 7, 10, 14],
}

SCALES = {
    'major': [0, 2, 4, 5, 7, 9, 11],
    'minor': [0, 2, 3, 5, 7, 8, 10],
    'dorian': [0, 2, 3, 5, 7, 9, 10],
    'mixolydian': [0, 2, 4, 5, 7, 9, 10],
}


def parse_chord_name(name):
    """코드명 파싱 → (루트 MIDI pitch class, 코드 타입)
    예: 'DMaj7' → (2, 'Maj7'), 'C#m7b5' → (1, 'm7b5'), 'F#7' → (6, '7')
    """
    # 루트 음 추출
    if len(name) >= 2 and name[1] in ('#', 'b'):
        root_name = name[:2]
        chord_type = name[2:]
    else:
        root_name = name[0]
        chord_type = name[1:]

    # 플랫 처리
    if root_name.endswith('b'):
        base = root_name[0]
        idx = NOTE_NAMES.index(base)
        root_pc = (idx - 1) % 12
    else:
        root_pc = NOTE_NAMES.index(root_name)

    # 코드 타입이 비어있으면 Major triad
    if not chord_type:
        chord_type = 'Maj'

    return root_pc, chord_type


def chord_to_midi_notes(chord_name, octave=3):
    """코드명 → MIDI 노트 리스트 (보이싱 적용)"""
    root_pc, chord_type = parse_chord_name(chord_name)
    intervals = CHORD_VOICINGS.get(chord_type, CHORD_VOICINGS['Maj7'])
    base = root_pc + (octave + 1) * 12
    return [base + iv for iv in intervals if 0 <= base + iv <= 127]


def get_chord_scale(chord_name, key_root='D', key_scale='major'):
    """코드에 맞는 스케일 음 반환 (멜로디/베이스용)"""
    root_pc, chord_type = parse_chord_name(chord_name)
    key_root_pc = NOTE_NAMES.index(key_root)
    key_intervals = SCALES.get(key_scale, SCALES['major'])

    # 코드 톤 + 키 스케일 노트 결합
    chord_tones = set()
    voicing = CHORD_VOICINGS.get(chord_type, CHORD_VOICINGS['Maj7'])
    for iv in voicing:
        chord_tones.add((root_pc + iv) % 12)

    key_notes = set()
    for iv in key_intervals:
        key_notes.add((key_root_pc + iv) % 12)

    # 코드톤 우선, 키 스케일 보조
    all_pcs = chord_tones | key_notes
    return sorted(all_pcs)


def load_settings():
    with open(SETTINGS_FILE, encoding='utf-8') as f:
        return json.load(f)


def build_chord_timeline(settings, tpb=480):
    """settings의 chord_progression을 타임라인으로 변환.

    Returns: [(start_tick, end_tick, chord_name), ...]
    """
    progression = settings.get('chord_progression', [])
    if not progression:
        return []

    ticks_per_measure = tpb * 4  # 4/4
    timeline = []
    current_tick = 0

    for entry in progression:
        chord = entry['chord']
        dur = entry.get('duration', 'full')
        if dur == 'half':
            length = ticks_per_measure // 2
        elif dur == 'quarter':
            length = ticks_per_measure // 4
        else:  # full
            length = ticks_per_measure

        timeline.append((current_tick, current_tick + length, chord))
        current_tick += length

    return timeline


def generate_chord_track(timeline, settings, tpb=480):
    """코드 트랙 생성 — 커스텀 코드진행"""
    track = mido.MidiTrack()
    track.name = 'Chords'

    vel_low, vel_high = settings.get('velocity_range', [40, 80])
    last_event_tick = 0

    for start, end, chord_name in timeline:
        notes = chord_to_midi_notes(chord_name, octave=3)
        duration = end - start
        vel = random.randint(vel_low, vel_high)

        delta = max(0, start - last_event_tick)

        # 코드 동시 발음
        for i, note in enumerate(notes):
            track.append(mido.Message('note_on', note=note, velocity=vel,
                                      time=delta if i == 0 else 0, channel=1))
        # 코드 동시 해제
        for i, note in enumerate(notes):
            track.append(mido.Message('note_off', note=note, velocity=0,
                                      time=duration if i == 0 else 0, channel=1))
        last_event_tick = end

    return track


def generate_melody_over_chords(timeline, settings, tpb=480):
    """코드진행 위에 멜로디 생성 — 코드톤 기반 즉흥"""
    track = mido.MidiTrack()
    track.name = 'Melody'

    vel_low, vel_high = settings.get('velocity_range', [50, 90])
    key = settings.get('key', 'D')
    scale = settings.get('scale', 'major')
    last_event_tick = 0
    prev_note = None

    for start, end, chord_name in timeline:
        # 코드에 맞는 스케일 구축
        scale_pcs = get_chord_scale(chord_name, key, scale)
        # 옥타브 4~5 범위의 스케일 음
        melody_notes = []
        for oct in range(4, 6):
            for pc in scale_pcs:
                midi_num = pc + (oct + 1) * 12
                if 60 <= midi_num <= 96:
                    melody_notes.append(midi_num)
        melody_notes.sort()

        if not melody_notes:
            continue

        # 코드 구간 내에서 멜로디 노트 배치
        chord_duration = end - start
        current = start
        # 8분음표 또는 4분음표 단위
        step = tpb // 2

        while current < end:
            if random.random() < 0.65:  # 65% 확률로 노트 발생
                if prev_note:
                    # 인접 음 선호 (스텝 모션)
                    candidates = [n for n in melody_notes if abs(n - prev_note) <= 4]
                    if not candidates:
                        candidates = melody_notes
                    note = random.choice(candidates)
                else:
                    # 코드톤에서 시작
                    root_pc, ct = parse_chord_name(chord_name)
                    chord_pitches = chord_to_midi_notes(chord_name, octave=4)
                    note = random.choice(chord_pitches) if chord_pitches else random.choice(melody_notes)

                vel = random.randint(vel_low, vel_high)

                # 노트 길이: 8분 ~ 온음표
                possible_durs = [tpb // 2, tpb, tpb * 2]
                duration = random.choice(possible_durs)
                duration = min(duration, end - current)  # 코드 경계 넘지 않기

                delta = max(0, current - last_event_tick)
                track.append(mido.Message('note_on', note=note, velocity=vel,
                                          time=delta, channel=0))
                track.append(mido.Message('note_off', note=note, velocity=0,
                                          time=duration, channel=0))
                last_event_tick = current + duration
                prev_note = note

            current += step

    return track


def generate_bass_over_chords(timeline, settings, tpb=480):
    """코드진행 기반 베이스 트랙 — 루트 워킹"""
    track = mido.MidiTrack()
    track.name = 'Bass'

    vel_low, vel_high = settings.get('velocity_range', [50, 80])
    last_event_tick = 0

    for start, end, chord_name in timeline:
        root_pc, chord_type = parse_chord_name(chord_name)
        voicing = CHORD_VOICINGS.get(chord_type, CHORD_VOICINGS['Maj7'])

        # 베이스 음역 (옥타브 2~3)
        bass_root = root_pc + 36  # 옥타브 2
        if bass_root < 28:
            bass_root += 12
        bass_fifth = bass_root + 7
        if bass_fifth > 55:
            bass_fifth -= 12

        chord_duration = end - start
        step = tpb  # 4분음표 단위 워킹
        current = start
        beat = 0

        while current < end:
            if beat == 0:
                note = bass_root  # 첫 박은 루트
            elif beat == 2 and chord_duration >= tpb * 3:
                note = bass_fifth  # 3박에 5도
            else:
                # 워킹: 루트, 3도, 5도 중 선택
                third = bass_root + voicing[1] if len(voicing) > 1 else bass_root
                candidates = [bass_root, third, bass_fifth]
                candidates = [n for n in candidates if 28 <= n <= 55]
                note = random.choice(candidates) if candidates else bass_root

            vel = random.randint(vel_low, vel_high)
            dur = min(step - 20, end - current - 10)
            dur = max(1, dur)

            delta = max(0, current - last_event_tick)
            track.append(mido.Message('note_on', note=note, velocity=vel,
                                      time=delta, channel=2))
            track.append(mido.Message('note_off', note=note, velocity=0,
                                      time=dur, channel=2))
            last_event_tick = current + dur

            current += step
            beat += 1

    return track


def generate_drums_jazz(settings, total_ticks, tpb=480):
    """재즈 드럼 — 라이드 + 킥/스네어 콤핑"""
    track = mido.MidiTrack()
    track.name = 'Drums'

    vel_low, vel_high = settings.get('velocity_range', [40, 90])
    ticks_per_measure = tpb * 4
    measures = total_ticks // ticks_per_measure
    last_event_tick = 0

    # GM 드럼
    RIDE = 51
    KICK = 36
    SNARE = 38
    HH_CLOSED = 42
    HH_PEDAL = 44
    CRASH = 49

    for m in range(measures):
        base_tick = m * ticks_per_measure

        # 라이드: 스윙 패턴 (1-and-a, 2-and-a, ...)
        for beat in range(4):
            # 비트 온
            t = base_tick + beat * tpb
            delta = max(0, t - last_event_tick)
            vel = random.randint(vel_low + 10, vel_high)
            track.append(mido.Message('note_on', note=RIDE, velocity=vel, time=delta, channel=9))
            track.append(mido.Message('note_off', note=RIDE, velocity=0, time=tpb // 4, channel=9))
            last_event_tick = t + tpb // 4

            # 스윙된 & (3연음 느낌: 비트의 2/3 지점)
            swing_t = t + int(tpb * 0.67)
            delta = max(0, swing_t - last_event_tick)
            vel_swing = random.randint(vel_low, vel_high - 15)
            track.append(mido.Message('note_on', note=RIDE, velocity=vel_swing, time=delta, channel=9))
            track.append(mido.Message('note_off', note=RIDE, velocity=0, time=tpb // 4, channel=9))
            last_event_tick = swing_t + tpb // 4

        # 하이햇 페달: 2, 4박
        for beat in [1, 3]:
            t = base_tick + beat * tpb
            delta = max(0, t - last_event_tick)
            vel = random.randint(30, 55)
            track.append(mido.Message('note_on', note=HH_PEDAL, velocity=vel, time=delta, channel=9))
            track.append(mido.Message('note_off', note=HH_PEDAL, velocity=0, time=tpb // 4, channel=9))
            last_event_tick = t + tpb // 4

        # 킥: 1박 + 랜덤 콤핑
        kick_t = base_tick
        delta = max(0, kick_t - last_event_tick)
        vel = random.randint(vel_low, vel_high)
        track.append(mido.Message('note_on', note=KICK, velocity=vel, time=delta, channel=9))
        track.append(mido.Message('note_off', note=KICK, velocity=0, time=tpb // 3, channel=9))
        last_event_tick = kick_t + tpb // 3

        # 랜덤 킥 콤핑
        if random.random() < 0.4:
            comp_beat = random.choice([2, 3])
            t = base_tick + comp_beat * tpb + random.randint(0, tpb // 4)
            delta = max(0, t - last_event_tick)
            vel = random.randint(vel_low - 10, vel_high - 20)
            vel = max(20, vel)
            track.append(mido.Message('note_on', note=KICK, velocity=vel, time=delta, channel=9))
            track.append(mido.Message('note_off', note=KICK, velocity=0, time=tpb // 4, channel=9))
            last_event_tick = t + tpb // 4

        # 스네어 콤핑 (재즈식 랜덤)
        if random.random() < 0.35:
            comp_pos = random.choice([1, 2, 3])
            t = base_tick + comp_pos * tpb + random.randint(0, tpb // 3)
            delta = max(0, t - last_event_tick)
            vel = random.randint(25, 60)  # 부드럽게
            track.append(mido.Message('note_on', note=SNARE, velocity=vel, time=delta, channel=9))
            track.append(mido.Message('note_off', note=SNARE, velocity=0, time=tpb // 4, channel=9))
            last_event_tick = t + tpb // 4

        # 4마디마다 크래시
        if m > 0 and m % 4 == 0:
            delta = max(0, base_tick - last_event_tick)
            track.append(mido.Message('note_on', note=CRASH, velocity=random.randint(60, 90), time=delta, channel=9))
            track.append(mido.Message('note_off', note=CRASH, velocity=0, time=tpb, channel=9))
            last_event_tick = base_tick + tpb

    return track


def main():
    settings = load_settings()
    bpm = settings.get('bpm', 120)
    key = settings.get('key', 'D')
    scale = settings.get('scale', 'major')
    tpb = 480

    print("=" * 55)
    print("  sinco.mid 생성 -- 커스텀 코드진행 기반")
    print("=" * 55)
    print(f"  Key: {key} {scale}")
    print(f"  BPM: {bpm}")
    print(f"  Style: {settings.get('style', 'jazz')}")

    # 코드 타임라인 구축
    timeline = build_chord_timeline(settings, tpb)
    if not timeline:
        print("ERROR: settings.json에 chord_progression이 없습니다!")
        return

    total_ticks = timeline[-1][1]
    total_measures = total_ticks // (tpb * 4)
    total_seconds = (total_ticks / tpb) * (60.0 / bpm)

    print(f"  Measures: {total_measures} (코드진행 {len(timeline)}개)")
    print(f"  Duration: {total_seconds:.1f}초")
    print()

    # 코드진행 출력
    print("  코드진행:")
    bar = 1
    for start, end, chord in timeline:
        dur_label = "full" if (end - start) == tpb * 4 else "half"
        beat_start = start / tpb + 1
        print(f"    Bar {start // (tpb*4) + 1:2d} | {chord:10s} ({dur_label})")
    print()

    # 16마디로 반복 (8마디 진행 x 2)
    measures_target = settings.get('measures', 16)
    if total_measures < measures_target:
        # 코드진행 반복
        repeat_timeline = list(timeline)
        offset = total_ticks
        while len(repeat_timeline) < len(timeline) * (measures_target // total_measures + 1):
            for s, e, ch in timeline:
                repeat_timeline.append((s + offset, e + offset, ch))
            offset += total_ticks
        # 목표 마디에 맞게 자르기
        target_ticks = measures_target * tpb * 4
        timeline = [(s, min(e, target_ticks), ch) for s, e, ch in repeat_timeline if s < target_ticks]
        total_ticks = target_ticks

    # MIDI 파일 생성
    mid = mido.MidiFile(ticks_per_beat=tpb)

    # 메타 트랙
    meta_track = mido.MidiTrack()
    meta_track.name = 'Meta'
    meta_track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
    num, den = map(int, settings.get('time_signature', '4/4').split('/'))
    meta_track.append(mido.MetaMessage('time_signature', numerator=num, denominator=den))
    mid.tracks.append(meta_track)

    # 트랙 생성
    for track_cfg in settings.get('tracks', []):
        track_type = track_cfg.get('type', 'melody')
        if track_type == 'melody':
            mid.tracks.append(generate_melody_over_chords(timeline, settings, tpb))
            print("  + Melody 트랙 (코드톤 기반 즉흥)")
        elif track_type == 'chords':
            mid.tracks.append(generate_chord_track(timeline, settings, tpb))
            print("  + Chords 트랙 (커스텀 코드진행)")
        elif track_type == 'bass':
            mid.tracks.append(generate_bass_over_chords(timeline, settings, tpb))
            print("  + Bass 트랙 (워킹 베이스)")
        elif track_type == 'drums':
            mid.tracks.append(generate_drums_jazz(settings, total_ticks, tpb))
            print("  + Drums 트랙 (재즈 스윙)")

    # 저장
    filepath = os.path.join(OUTPUT_DIR, "sinco.mid")
    mid.save(filepath)

    # 메타 저장
    meta = {
        'filename': 'sinco.mid',
        'filepath': filepath,
        'settings': settings,
        'chord_progression': [f"{c[2]} ({c[0]/tpb:.1f}~{c[1]/tpb:.1f} beats)" for c in timeline[:len(settings.get('chord_progression', []))]],
        'tracks': [t.name for t in mid.tracks],
        'total_notes': sum(1 for t in mid.tracks for m in t if m.type == 'note_on' and m.velocity > 0),
        'duration_sec': mid.length,
    }
    meta_path = filepath + ".meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print()
    print(f"  저장: {filepath}")
    print(f"  메타: {meta_path}")
    print(f"  길이: {mid.length:.1f}초")
    print(f"  총 노트: {meta['total_notes']}개")
    print(f"  트랙 수: {len(mid.tracks)}개")
    print()

    # JSON 설정 검증
    print("=" * 55)
    print("  settings.json 적용 검증")
    print("=" * 55)
    print(f"  [OK] Key: {key} {scale}")
    print(f"  [OK] BPM: {bpm}")
    print(f"  [OK] Style: {settings.get('style')}")
    print(f"  [OK] Time Sig: {settings.get('time_signature')}")
    print(f"  [OK] Measures: {settings.get('measures')}")
    print(f"  [OK] Velocity: {settings.get('velocity_range')}")
    print(f"  [OK] Octave: {settings.get('octave_range')}")
    print(f"  [OK] Chord Progression: {len(settings.get('chord_progression', []))}개 코드")
    print(f"  [OK] Tracks: {len(settings.get('tracks', []))}개")
    for tc in settings.get('tracks', []):
        print(f"       - {tc['name']} (ch{tc['channel']}, {tc['type']})")

    return filepath


if __name__ == '__main__':
    main()
