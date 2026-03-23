"""
MIDI 변주 생성기
- 원본 11.mid (Bb minor, 앰비언트) 를 베이스로
- MAESTRO 2018 레퍼런스 DB에서 유사 패턴을 학습
- 클래식 피아노 솔로 변주곡 생성
"""

import os, sys, json, random
import numpy as np
import pretty_midi

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
EMBED_DIR = os.path.join(BASE_DIR, 'embeddings')
MIDI_RAW = os.path.join(BASE_DIR, 'Ableton', 'midi_raw')
SOURCE_MIDI = os.path.join(BASE_DIR, '11.mid')
OUTPUT_PATH = os.path.join(BASE_DIR, 'output', '2026-03-23_variation_classic_piano.mid')

random.seed(42)
np.random.seed(42)


def load_reference_notes(category='schubert', max_files=12):
    """레퍼런스 DB에서 노트 패턴 수집"""
    ref_notes = []
    cat_dir = os.path.join(EMBED_DIR, 'individual', category)
    files = sorted([f for f in os.listdir(cat_dir) if f.endswith('.json')])[:max_files]
    for fname in files:
        with open(os.path.join(cat_dir, fname), 'r', encoding='utf-8') as f:
            data = json.load(f)
        ref_notes.append(data)
        print(f"  Loaded ref: {fname} ({data['stats']['total_notes']} notes, key={data['stats'].get('estimated_key', '?')})")
    return ref_notes


def extract_patterns(ref_data_list, window_sec=4.0):
    """레퍼런스에서 리듬/벨로시티/보이싱 패턴 추출"""
    rhythm_patterns = []
    velocity_curves = []
    voicing_patterns = []

    for ref in ref_data_list:
        notes = ref['notes']
        if not notes:
            continue

        # 4초 윈도우 단위로 패턴 추출
        t = 0
        max_t = notes[-1]['end']
        while t < max_t:
            window = [n for n in notes if t <= n['start'] < t + window_sec]
            if len(window) >= 3:
                # 리듬 패턴: 상대적 시작 시간
                t0 = window[0]['start']
                rhythm = [(n['start'] - t0, n['duration']) for n in window]
                rhythm_patterns.append(rhythm)

                # 벨로시티 커브
                vels = [n['velocity'] for n in window]
                velocity_curves.append(vels)

                # 보이싱: 동시에 울리는 음들의 인터벌
                simultaneous = []
                for i, n1 in enumerate(window):
                    for n2 in window[i+1:]:
                        if abs(n1['start'] - n2['start']) < 0.05:
                            simultaneous.append(n2['pitch'] - n1['pitch'])
                if simultaneous:
                    voicing_patterns.append(simultaneous)

            t += window_sec

    return rhythm_patterns, velocity_curves, voicing_patterns


def analyze_source(midi_path):
    """원본 MIDI 분석"""
    midi = pretty_midi.PrettyMIDI(midi_path)
    notes = []
    for inst in midi.instruments:
        for note in inst.notes:
            notes.append({
                'pitch': note.pitch,
                'start': note.start,
                'end': note.end,
                'duration': note.end - note.start,
                'velocity': note.velocity,
            })
    notes.sort(key=lambda x: x['start'])

    pitches = [n['pitch'] for n in notes]
    pitch_classes = [p % 12 for p in pitches]

    # Bb minor scale: Bb(10), C(0), Db(1), Eb(3), F(5), Gb(6), Ab(8)
    scale = [10, 0, 1, 3, 5, 6, 8]  # Bb minor

    return notes, scale, midi.get_end_time()


def generate_variation(source_notes, scale, source_duration, rhythm_patterns, velocity_curves, voicing_patterns):
    """변주곡 생성 — 원본 멜로디 + 레퍼런스 패턴 믹싱"""
    new_midi = pretty_midi.PrettyMIDI(initial_tempo=72)  # 느린 클래식 템포
    piano = pretty_midi.Instrument(program=0, name='Classical Piano Variation')

    # === 섹션 1: 원본 테마 제시 (0~30초) — 원본을 조금 변형 ===
    print("\n[Section 1] Theme presentation (0-30s)")
    theme_notes = [n for n in source_notes if n['start'] < 30]
    for n in theme_notes:
        # 피치를 스케일에 맞게 미세 조정
        pitch = n['pitch']
        pc = pitch % 12
        if pc not in scale:
            # 가장 가까운 스케일 음으로
            dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
            closest = scale[np.argmin(dists)]
            pitch = (pitch // 12) * 12 + closest

        vel = min(127, max(20, n['velocity'] + random.randint(-10, 5)))
        piano.notes.append(pretty_midi.Note(
            velocity=vel,
            pitch=pitch,
            start=n['start'],
            end=n['start'] + n['duration'] * random.uniform(0.8, 1.2)
        ))

    # === 섹션 2: 리듬 변주 (30~70초) — 레퍼런스 리듬 적용 ===
    print("[Section 2] Rhythm variation (30-70s)")
    section2_notes = [n for n in source_notes if 10 <= n['start'] < 60]
    t_offset = 30
    used_rhythms = random.sample(rhythm_patterns, min(10, len(rhythm_patterns)))

    for i, rhythm in enumerate(used_rhythms):
        base_t = t_offset + i * 4.0
        if base_t > 70:
            break

        # 원본 피치 시퀀스에서 랜덤 선택
        src_idx = random.randint(0, max(0, len(section2_notes) - len(rhythm)))
        for j, (rel_t, dur) in enumerate(rhythm):
            if src_idx + j >= len(section2_notes):
                break
            src = section2_notes[src_idx + j]
            pitch = src['pitch'] + random.choice([0, 0, 0, -12, 12])  # 옥타브 변주
            pc = pitch % 12
            if pc not in scale:
                dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
                closest = scale[np.argmin(dists)]
                pitch = (pitch // 12) * 12 + closest
            pitch = max(21, min(108, pitch))

            vel_curve = random.choice(velocity_curves) if velocity_curves else [64]
            vel_idx = min(j, len(vel_curve) - 1)
            vel = min(127, max(20, vel_curve[vel_idx]))

            piano.notes.append(pretty_midi.Note(
                velocity=vel,
                pitch=pitch,
                start=base_t + rel_t,
                end=base_t + rel_t + dur * random.uniform(0.7, 1.5)
            ))

    # === 섹션 3: 하모닉 변주 (70~110초) — 보이싱 패턴 적용 ===
    print("[Section 3] Harmonic variation (70-110s)")
    section3_notes = [n for n in source_notes if 20 <= n['start'] < 80]
    t_offset = 70

    for i in range(0, min(len(section3_notes), 40), 2):
        base_note = section3_notes[i]
        t = t_offset + (i / 2) * 2.0
        if t > 110:
            break

        # 멜로디 음
        pitch = base_note['pitch']
        pc = pitch % 12
        if pc not in scale:
            dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
            closest = scale[np.argmin(dists)]
            pitch = (pitch // 12) * 12 + closest

        vel = min(100, max(30, base_note['velocity']))
        dur = random.uniform(1.0, 3.0)
        piano.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=t, end=t + dur))

        # 보이싱 추가 (화음)
        if voicing_patterns:
            voicing = random.choice(voicing_patterns)
            for interval in voicing[:3]:
                harm_pitch = pitch + interval
                harm_pc = harm_pitch % 12
                if harm_pc not in scale:
                    dists = [min(abs(harm_pc - s), 12 - abs(harm_pc - s)) for s in scale]
                    closest = scale[np.argmin(dists)]
                    harm_pitch = (harm_pitch // 12) * 12 + closest
                harm_pitch = max(21, min(108, harm_pitch))
                piano.notes.append(pretty_midi.Note(
                    velocity=max(20, vel - random.randint(10, 25)),
                    pitch=harm_pitch,
                    start=t + random.uniform(0, 0.08),
                    end=t + dur * random.uniform(0.8, 1.1)
                ))

    # === 섹션 4: 클라이맥스 (110~140초) — 빠른 패시지 + 풀 다이나믹 ===
    print("[Section 4] Climax (110-140s)")
    fast_rhythms = [r for r in rhythm_patterns if len(r) > 8]
    if not fast_rhythms:
        fast_rhythms = rhythm_patterns

    t_offset = 110
    for i in range(6):
        rhythm = random.choice(fast_rhythms)
        base_t = t_offset + i * 5.0
        if base_t > 140:
            break

        base_pitch = random.choice([58, 65, 70, 77])  # Bb minor 코드 톤
        for j, (rel_t, dur) in enumerate(rhythm[:12]):
            pitch = base_pitch + random.choice(scale) - 5 + random.randint(-3, 15)
            pitch = max(36, min(96, pitch))
            pc = pitch % 12
            if pc not in scale:
                dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
                closest = scale[np.argmin(dists)]
                pitch = (pitch // 12) * 12 + closest

            vel = min(127, 70 + random.randint(0, 50))
            piano.notes.append(pretty_midi.Note(
                velocity=vel, pitch=pitch,
                start=base_t + rel_t * 0.7,
                end=base_t + rel_t * 0.7 + dur * 0.5
            ))

    # === 섹션 5: 코다 (140~165초) — 원본 테마 회귀, 페이드아웃 ===
    print("[Section 5] Coda (140-165s)")
    coda_notes = [n for n in source_notes if n['start'] < 25]
    t_offset = 140
    for i, n in enumerate(coda_notes):
        progress = i / max(len(coda_notes), 1)
        vel = max(15, int(n['velocity'] * (1 - progress * 0.7)))
        pitch = n['pitch']
        pc = pitch % 12
        if pc not in scale:
            dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
            closest = scale[np.argmin(dists)]
            pitch = (pitch // 12) * 12 + closest

        piano.notes.append(pretty_midi.Note(
            velocity=vel, pitch=pitch,
            start=t_offset + n['start'] * 1.3,
            end=t_offset + n['start'] * 1.3 + n['duration'] * 1.5
        ))

    new_midi.instruments.append(piano)

    # 서스테인 페달 추가
    for t in np.arange(0, 165, 2.0):
        piano.control_changes.append(pretty_midi.ControlChange(64, 127, t))
        piano.control_changes.append(pretty_midi.ControlChange(64, 0, t + 1.8))

    return new_midi


def main():
    print("=" * 60)
    print("MIDI Variation Generator — Classical Piano Solo")
    print("=" * 60)

    # 1. 원본 분석
    print(f"\n[1] Analyzing source: {SOURCE_MIDI}")
    source_notes, scale, duration = analyze_source(SOURCE_MIDI)
    print(f"    Notes: {len(source_notes)}, Duration: {duration:.1f}s, Scale: Bb minor")

    # 2. 레퍼런스 로드 (슈베르트 + 리사이틀)
    print(f"\n[2] Loading reference patterns...")
    refs_schubert = load_reference_notes('schubert', max_files=12)
    refs_recital = load_reference_notes('recital', max_files=10)
    all_refs = refs_schubert + refs_recital

    # 3. 패턴 추출
    print(f"\n[3] Extracting patterns from {len(all_refs)} references...")
    rhythm_patterns, velocity_curves, voicing_patterns = extract_patterns(all_refs)
    print(f"    Rhythm patterns: {len(rhythm_patterns)}")
    print(f"    Velocity curves: {len(velocity_curves)}")
    print(f"    Voicing patterns: {len(voicing_patterns)}")

    # 4. 변주 생성
    print(f"\n[4] Generating variation...")
    variation = generate_variation(source_notes, scale, duration,
                                   rhythm_patterns, velocity_curves, voicing_patterns)

    # 5. 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    variation.write(OUTPUT_PATH)

    # 결과 분석
    total_notes = sum(len(inst.notes) for inst in variation.instruments)
    end_time = variation.get_end_time()
    print(f"\n{'=' * 60}")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Total notes: {total_notes}")
    print(f"Duration: {end_time:.1f}s ({end_time/60:.1f}min)")
    print(f"Sections: Theme → Rhythm Var → Harmonic Var → Climax → Coda")
    print(f"Key: Bb minor")
    print(f"Tempo: 72 BPM")
    print(f"Reference: {len(all_refs)} MAESTRO files (Schubert + Recital)")
    print("=" * 60)


if __name__ == '__main__':
    main()
