"""
MIDI 변주 파이프라인 — 전체 과정 자동화
1. 원본 MIDI 임베딩
2. DB에서 유사곡 검색 (코사인 유사도)
3. 유사곡에서 프레이즈 단위 패턴 추출
4. 변주 생성 (멜로디/리듬/화성/다이나믹)
5. 결과 분석 + 메타데이터 JSON 생성
6. reviewed/ 구조에 맞게 저장
"""

import os, sys, json, random, math, datetime
import numpy as np
import pretty_midi

sys.stdout.reconfigure(encoding='utf-8')
np.random.seed(42)
random.seed(42)

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
EMBED_DIR = os.path.join(BASE_DIR, 'embeddings')
SOURCE_MIDI = os.path.join(BASE_DIR, '11.mid')
TODAY = datetime.date.today().isoformat()


# ============================================================
# Step 1: 원본 MIDI 임베딩
# ============================================================
def embed_midi(filepath):
    """원본 MIDI를 128차원 벡터로 임베딩"""
    midi = pretty_midi.PrettyMIDI(filepath)
    notes = []
    for inst in midi.instruments:
        for n in inst.notes:
            notes.append({
                'pitch': n.pitch, 'start': n.start, 'end': n.end,
                'duration': n.end - n.start, 'velocity': n.velocity,
                'instrument': inst.program, 'is_drum': inst.is_drum
            })
    notes.sort(key=lambda x: x['start'])

    pitches = [n['pitch'] for n in notes]
    velocities = [n['velocity'] for n in notes]
    durations = [n['duration'] for n in notes]

    # 피치 히스토그램
    pitch_hist = np.zeros(128)
    for p in pitches: pitch_hist[p] += 1
    if pitch_hist.sum() > 0: pitch_hist /= pitch_hist.sum()

    # 피치 클래스 히스토그램
    pc_hist = np.zeros(12)
    for p in pitches: pc_hist[p % 12] += 1
    if pc_hist.sum() > 0: pc_hist /= pc_hist.sum()

    # 인터벌 히스토그램
    intervals = [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]
    iv_hist = np.zeros(25)
    for iv in intervals: iv_hist[max(0, min(24, iv + 12))] += 1
    if iv_hist.sum() > 0: iv_hist /= iv_hist.sum()

    # 벨로시티 히스토그램
    vel_hist = np.zeros(8)
    for v in velocities: vel_hist[min(7, v // 16)] += 1
    if vel_hist.sum() > 0: vel_hist /= vel_hist.sum()

    # 듀레이션 히스토그램
    dur_bins = [0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, float('inf')]
    dur_hist = np.zeros(10)
    for d in durations:
        for i in range(10):
            if dur_bins[i] <= d < dur_bins[i+1]:
                dur_hist[i] += 1; break
    if dur_hist.sum() > 0: dur_hist /= dur_hist.sum()

    # 128차원 벡터
    emb = np.zeros(128)
    emb[0:12] = pc_hist
    emb[12:37] = iv_hist
    emb[37:45] = vel_hist
    emb[45:55] = dur_hist
    emb[55] = np.mean(pitches) / 127.0
    emb[56] = np.std(pitches) / 40.0
    emb[57] = np.mean(velocities) / 127.0
    emb[58] = np.std(velocities) / 40.0
    emb[59] = np.mean(durations) / 10.0
    emb[60] = np.std(durations) / 10.0
    tempos = midi.get_tempo_changes()
    avg_tempo = float(np.mean(tempos[1])) if len(tempos[1]) > 0 else 120.0
    emb[61] = avg_tempo / 200.0
    emb[62] = midi.get_end_time() / 600.0
    emb[63] = len(notes) / 10000.0
    sorted_p = np.argsort(pitch_hist)[::-1][:65]
    for i, p in enumerate(sorted_p): emb[63+i] = pitch_hist[p]

    key_names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    est_key = key_names[int(np.argmax(pc_hist))]

    return {
        'embedding': emb,
        'notes': notes,
        'stats': {
            'total_notes': len(notes),
            'duration_sec': round(midi.get_end_time(), 2),
            'avg_tempo': round(avg_tempo, 1),
            'estimated_key': est_key,
            'pitch_range': [int(min(pitches)), int(max(pitches))],
            'pitch_mean': round(float(np.mean(pitches)), 1),
            'velocity_range': [int(min(velocities)), int(max(velocities))],
            'velocity_mean': round(float(np.mean(velocities)), 1),
            'duration_mean': round(float(np.mean(durations)), 4),
        },
        'pc_hist': pc_hist,
    }


# ============================================================
# Step 2: DB에서 유사곡 검색
# ============================================================
def find_similar(query_emb, top_k=10):
    """코사인 유사도로 Top-K 유사곡 검색"""
    matrix = np.load(os.path.join(EMBED_DIR, 'embedding_matrix.npy'))
    meta = json.load(open(os.path.join(EMBED_DIR, 'metadata.json'), 'r', encoding='utf-8'))

    # 코사인 유사도
    norms = np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_emb)
    norms[norms == 0] = 1e-10
    sims = matrix @ query_emb / norms

    top_idx = np.argsort(sims)[::-1][:top_k]
    results = []
    for idx in top_idx:
        results.append({
            'index': int(idx),
            'filename': meta['files'][idx],
            'similarity': round(float(sims[idx]), 4),
        })
    return results


# ============================================================
# Step 3: 유사곡에서 프레이즈 단위 패턴 추출
# ============================================================
def load_reference_data(filename):
    """개별 JSON에서 노트 데이터 로드"""
    # 카테고리 디렉토리 탐색
    for cat in ['chamber', 'recital', 'schubert']:
        path = os.path.join(EMBED_DIR, 'individual', cat, filename.replace('.midi', '.json').replace('.mid', '.json'))
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None


def extract_phrase_patterns(ref_data, phrase_bars=8, beats_per_bar=4, tempo=120):
    """프레이즈(8마디) 단위로 패턴 추출 — 4초 윈도우보다 긴 문맥"""
    notes = ref_data['notes']
    if not notes:
        return []

    sec_per_beat = 60.0 / tempo
    phrase_sec = phrase_bars * beats_per_bar * sec_per_beat

    patterns = []
    t = 0
    max_t = notes[-1]['end']

    while t < max_t:
        phrase_notes = [n for n in notes if t <= n['start'] < t + phrase_sec]
        if len(phrase_notes) >= 8:
            t0 = phrase_notes[0]['start']
            pattern = {
                'notes': [{
                    'rel_start': round(n['start'] - t0, 4),
                    'rel_end': round(n['end'] - t0, 4),
                    'duration': round(n['duration'], 4),
                    'pitch': n['pitch'],
                    'velocity': n['velocity'],
                } for n in phrase_notes],
                'note_count': len(phrase_notes),
                'density': round(len(phrase_notes) / phrase_sec, 2),
                'avg_velocity': round(np.mean([n['velocity'] for n in phrase_notes]), 1),
                'pitch_range': [min(n['pitch'] for n in phrase_notes), max(n['pitch'] for n in phrase_notes)],
            }
            patterns.append(pattern)
        t += phrase_sec

    return patterns


# ============================================================
# Step 4: 변주 생성
# ============================================================
def snap_to_scale(pitch, scale):
    """피치를 스케일에 맞게 보정"""
    pc = pitch % 12
    if pc in scale:
        return pitch
    dists = [min(abs(pc - s), 12 - abs(pc - s)) for s in scale]
    closest = scale[int(np.argmin(dists))]
    return (pitch // 12) * 12 + closest


def generate_variation_v2(source_notes, source_stats, similar_songs, all_patterns):
    """
    변주 생성 v2 — 프레이즈 단위, 5섹션 구조
    원본 멜로디/조성 유지 + 레퍼런스 리듬/다이나믹/보이싱 적용
    """
    # Bb minor: Bb(10), C(0), Db(1), Eb(3), F(5), Gb(6), Ab(8)
    scale = [10, 0, 1, 3, 5, 6, 8]
    tempo = 66  # 원본(50.6)보다 약간 빠르게, 하지만 여전히 느린 클래식

    new_midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano = pretty_midi.Instrument(program=0, name='Variation on 11.mid')

    sections = []
    source_dur = source_stats['duration_sec']

    # 원본 프레이즈 분리 (30초 단위)
    src_phrases = []
    t = 0
    while t < source_dur:
        phrase = [n for n in source_notes if t <= n['start'] < t + 30]
        if phrase:
            src_phrases.append(phrase)
        t += 30

    # 레퍼런스에서 밀도/다이나믹별로 패턴 분류
    soft_patterns = [p for p in all_patterns if p['avg_velocity'] < 60]
    medium_patterns = [p for p in all_patterns if 60 <= p['avg_velocity'] < 90]
    loud_patterns = [p for p in all_patterns if p['avg_velocity'] >= 90]
    dense_patterns = [p for p in all_patterns if p['density'] > 6]
    sparse_patterns = [p for p in all_patterns if p['density'] <= 3]

    print(f"    Patterns: soft={len(soft_patterns)}, medium={len(medium_patterns)}, loud={len(loud_patterns)}")
    print(f"    Patterns: dense={len(dense_patterns)}, sparse={len(sparse_patterns)}")

    # ── Section 1: 테마 제시 (원본 충실 재현) ──
    sec_start = 0
    sec_name = "Theme"
    note_count = 0
    if len(src_phrases) > 0:
        for n in src_phrases[0]:
            pitch = snap_to_scale(n['pitch'], scale)
            vel = max(20, min(80, n['velocity'] + random.randint(-5, 5)))
            dur = n['duration'] * random.uniform(0.95, 1.05)
            piano.notes.append(pretty_midi.Note(
                velocity=vel, pitch=pitch,
                start=n['start'], end=n['start'] + dur
            ))
            note_count += 1
    sections.append({'name': sec_name, 'start': 0, 'end': 30, 'notes': note_count})
    print(f"    [Section 1] {sec_name}: {note_count} notes (0-30s)")

    # ── Section 2: 리듬 변주 — 레퍼런스 리듬으로 원본 피치 연주 ──
    sec_start = 30
    sec_name = "Rhythm Variation"
    note_count = 0
    src_pitches = [n['pitch'] for phrase in src_phrases for n in phrase]
    ref_patterns = random.sample(medium_patterns, min(8, len(medium_patterns))) if medium_patterns else all_patterns[:8]

    for i, pat in enumerate(ref_patterns):
        base_t = sec_start + i * 5.0
        if base_t >= 65:
            break
        for j, rn in enumerate(pat['notes'][:15]):
            # 원본 피치 순환 사용 + 스케일 보정
            src_pitch = src_pitches[(i * 15 + j) % len(src_pitches)]
            pitch = snap_to_scale(src_pitch + random.choice([0, 0, -12, 12]), scale)
            pitch = max(28, min(96, pitch))

            vel = max(25, min(100, rn['velocity'] + random.randint(-10, 10)))
            start = base_t + rn['rel_start'] * 0.8
            dur = rn['duration'] * random.uniform(0.6, 1.2)

            piano.notes.append(pretty_midi.Note(
                velocity=vel, pitch=pitch,
                start=start, end=start + dur
            ))
            note_count += 1
    sections.append({'name': sec_name, 'start': 30, 'end': 65, 'notes': note_count})
    print(f"    [Section 2] {sec_name}: {note_count} notes (30-65s)")

    # ── Section 3: 화성 변주 — 원본 멜로디 + 레퍼런스 보이싱 ──
    sec_start = 65
    sec_name = "Harmonic Variation"
    note_count = 0

    # 레퍼런스에서 동시발음 인터벌 추출
    voicing_intervals = []
    for pat in all_patterns:
        for k, n1 in enumerate(pat['notes']):
            for n2 in pat['notes'][k+1:]:
                if abs(n1['rel_start'] - n2['rel_start']) < 0.05:
                    iv = n2['pitch'] - n1['pitch']
                    if -24 <= iv <= 24 and iv != 0:
                        voicing_intervals.append(iv)
    voicing_intervals = voicing_intervals or [3, 7, 12, -12]

    src_phrase2 = src_phrases[1] if len(src_phrases) > 1 else src_phrases[0]
    for i, n in enumerate(src_phrase2):
        t = sec_start + (n['start'] - src_phrase2[0]['start']) * 1.2
        if t >= 100:
            break
        pitch = snap_to_scale(n['pitch'], scale)
        vel = max(30, min(95, n['velocity'] + 15))
        dur = n['duration'] * random.uniform(1.0, 1.8)

        # 멜로디 음
        piano.notes.append(pretty_midi.Note(velocity=vel, pitch=pitch, start=t, end=t + dur))
        note_count += 1

        # 보이싱 추가 (2~3개 음)
        if i % 2 == 0:
            n_voices = random.randint(2, 3)
            chosen_ivs = random.sample(voicing_intervals, min(n_voices, len(voicing_intervals)))
            for iv in chosen_ivs:
                hp = snap_to_scale(pitch + iv, scale)
                hp = max(28, min(96, hp))
                hv = max(20, vel - random.randint(10, 25))
                piano.notes.append(pretty_midi.Note(
                    velocity=hv, pitch=hp,
                    start=t + random.uniform(0, 0.03),
                    end=t + dur * random.uniform(0.8, 1.0)
                ))
                note_count += 1
    sections.append({'name': sec_name, 'start': 65, 'end': 100, 'notes': note_count})
    print(f"    [Section 3] {sec_name}: {note_count} notes (65-100s)")

    # ── Section 4: 클라이맥스 — 빠른 패시지 + 풀 다이나믹 ──
    sec_start = 100
    sec_name = "Climax"
    note_count = 0
    climax_pats = random.sample(dense_patterns or loud_patterns or all_patterns, min(6, len(all_patterns)))

    for i, pat in enumerate(climax_pats):
        base_t = sec_start + i * 5.5
        if base_t >= 130:
            break
        for j, rn in enumerate(pat['notes'][:20]):
            pitch = snap_to_scale(rn['pitch'], scale)
            pitch = max(36, min(96, pitch))
            vel = max(60, min(127, rn['velocity'] + random.randint(10, 30)))
            start = base_t + rn['rel_start'] * 0.6
            dur = rn['duration'] * 0.5

            piano.notes.append(pretty_midi.Note(
                velocity=vel, pitch=pitch,
                start=start, end=start + dur
            ))
            note_count += 1
    sections.append({'name': sec_name, 'start': 100, 'end': 130, 'notes': note_count})
    print(f"    [Section 4] {sec_name}: {note_count} notes (100-130s)")

    # ── Section 5: 코다 — 원본 테마 회귀 + 페이드아웃 ──
    sec_start = 130
    sec_name = "Coda"
    note_count = 0
    coda_src = src_phrases[0][:30] if src_phrases else source_notes[:30]

    for i, n in enumerate(coda_src):
        progress = i / max(len(coda_src), 1)
        t = sec_start + n['start'] * 1.5
        if t >= 170:
            break
        pitch = snap_to_scale(n['pitch'], scale)
        vel = max(10, int(n['velocity'] * (1 - progress * 0.8)))
        dur = n['duration'] * random.uniform(1.2, 2.0)

        piano.notes.append(pretty_midi.Note(
            velocity=vel, pitch=pitch,
            start=t, end=t + dur
        ))
        note_count += 1
    sections.append({'name': sec_name, 'start': 130, 'end': 170, 'notes': note_count})
    print(f"    [Section 5] {sec_name}: {note_count} notes (130-170s)")

    # 서스테인 페달
    for t in np.arange(0, 170, 2.5):
        piano.control_changes.append(pretty_midi.ControlChange(64, 127, t))
        piano.control_changes.append(pretty_midi.ControlChange(64, 0, t + 2.2))

    new_midi.instruments.append(piano)
    total_notes = sum(len(inst.notes) for inst in new_midi.instruments)

    return new_midi, sections, total_notes


# ============================================================
# Step 5: 결과 분석 + 메타데이터 생성
# ============================================================
def analyze_result(midi_obj):
    """생성된 MIDI 분석"""
    notes = []
    for inst in midi_obj.instruments:
        for n in inst.notes:
            notes.append({'pitch': n.pitch, 'velocity': n.velocity,
                          'start': n.start, 'end': n.end, 'duration': n.end - n.start})

    pitches = [n['pitch'] for n in notes]
    vels = [n['velocity'] for n in notes]
    durs = [n['duration'] for n in notes]

    pc_hist = np.zeros(12)
    for p in pitches: pc_hist[p % 12] += 1
    key_names = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']

    return {
        'total_notes': len(notes),
        'duration_sec': round(midi_obj.get_end_time(), 2),
        'pitch_range': [int(min(pitches)), int(max(pitches))],
        'pitch_mean': round(float(np.mean(pitches)), 1),
        'velocity_range': [int(min(vels)), int(max(vels))],
        'velocity_mean': round(float(np.mean(vels)), 1),
        'duration_mean': round(float(np.mean(durs)), 4),
        'estimated_key': key_names[int(np.argmax(pc_hist))],
        'top_pitch_classes': [key_names[i] for i in np.argsort(pc_hist)[::-1][:3]],
    }


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 70)
    print(f"MIDI Variation Pipeline v2 — {TODAY}")
    print("=" * 70)

    # Step 1
    print(f"\n[Step 1] 원본 임베딩: {SOURCE_MIDI}")
    source = embed_midi(SOURCE_MIDI)
    s = source['stats']
    print(f"    Notes: {s['total_notes']}, Duration: {s['duration_sec']}s")
    print(f"    Key: {s['estimated_key']}, Tempo: {s['avg_tempo']} BPM")
    print(f"    Pitch: {s['pitch_range']}, Velocity: {s['velocity_range']}")

    # Step 2
    print(f"\n[Step 2] DB에서 유사곡 검색 (Top 10)")
    similar = find_similar(source['embedding'], top_k=10)
    for i, sim in enumerate(similar):
        print(f"    {i+1}. {sim['filename'][:55]}  (sim: {sim['similarity']})")

    # Step 3
    print(f"\n[Step 3] 유사곡에서 프레이즈 패턴 추출")
    all_patterns = []
    loaded_refs = []
    for sim in similar:
        ref = load_reference_data(sim['filename'])
        if ref:
            patterns = extract_phrase_patterns(ref, phrase_bars=8)
            all_patterns.extend(patterns)
            loaded_refs.append({
                'filename': sim['filename'],
                'similarity': sim['similarity'],
                'patterns_extracted': len(patterns),
                'total_notes': ref['stats']['total_notes'],
            })
            print(f"    {sim['filename'][:50]}: {len(patterns)} phrases")
    print(f"    Total patterns: {len(all_patterns)}")

    # Step 4
    print(f"\n[Step 4] 변주 생성")
    variation, sections, total_notes = generate_variation_v2(
        source['notes'], source['stats'], similar, all_patterns
    )

    # 저장
    output_midi = os.path.join(BASE_DIR, 'output', f'{TODAY}_variation_v2_classic_piano.mid')
    os.makedirs(os.path.dirname(output_midi), exist_ok=True)
    variation.write(output_midi)

    # reviewed/ 에도 저장
    reviewed_dir = os.path.join(BASE_DIR, 'reviewed')
    os.makedirs(os.path.join(reviewed_dir, 'originals'), exist_ok=True)
    os.makedirs(os.path.join(reviewed_dir, 'variations'), exist_ok=True)
    os.makedirs(os.path.join(reviewed_dir, 'metadata'), exist_ok=True)

    # 원본 프레이즈 복사
    orig_midi = pretty_midi.PrettyMIDI(SOURCE_MIDI)
    orig_path = os.path.join(reviewed_dir, 'originals', '11_full.mid')
    orig_midi.write(orig_path)

    # 변주 복사
    var_path = os.path.join(reviewed_dir, 'variations', f'11_var_v2_{TODAY}.mid')
    variation.write(var_path)

    # Step 5
    print(f"\n[Step 5] 결과 분석 + 메타데이터 생성")
    result_stats = analyze_result(variation)

    metadata = {
        'id': f'pair_{TODAY}_001',
        'created_by': 'pipeline_variation.py (auto)',
        'created_date': TODAY,
        'pipeline_version': 'v2',

        'original': {
            'midi_file': 'originals/11_full.mid',
            'source': '11.mid (Omnisphere, ambient/cinematic)',
            'key': source['stats']['estimated_key'],
            'tempo': source['stats']['avg_tempo'],
            'time_signature': '4/4',
            'total_notes': source['stats']['total_notes'],
            'duration_sec': source['stats']['duration_sec'],
            'pitch_range': source['stats']['pitch_range'],
            'velocity_range': source['stats']['velocity_range'],
            'style_tags': ['앰비언트', '시네마틱', '서정적', 'pp~mp', '레가토'],
            'quality_score': None,
            'notes': '11.mid - Bb minor, Omnisphere synth, 앰비언트/시네마틱 스타일'
        },

        'variation': {
            'midi_file': f'variations/11_var_v2_{TODAY}.mid',
            'variation_type': 'mixed',
            'variation_types_used': ['rhythm', 'harmony', 'dynamics', 'structure'],
            'description': (
                f'11.mid를 베이스로 MAESTRO DB Top-10 유사곡에서 '
                f'{len(all_patterns)}개 프레이즈 패턴 추출 후 적용. '
                f'5섹션 구조 (Theme→Rhythm Var→Harmonic Var→Climax→Coda).'
            ),
            'sections': sections,
            'total_notes': result_stats['total_notes'],
            'duration_sec': result_stats['duration_sec'],
            'key': result_stats['estimated_key'],
            'top_pitch_classes': result_stats['top_pitch_classes'],
            'tempo': 66,
            'pitch_range': result_stats['pitch_range'],
            'velocity_range': result_stats['velocity_range'],
            'style_tags': ['클래식', '피아노솔로', '변주곡', 'pp~ff'],
            'quality_score': None,
            'reviewer': None,
            'review_date': None,
        },

        'reference_songs': loaded_refs,

        'pipeline_log': {
            'step1_embedding_dim': 128,
            'step2_similar_songs': len(similar),
            'step3_total_patterns': len(all_patterns),
            'step4_sections': len(sections),
            'step5_output_notes': result_stats['total_notes'],
        }
    }

    meta_path = os.path.join(reviewed_dir, 'metadata', f'11_var_v2_{TODAY}_meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    # 요약 출력
    print(f"\n{'=' * 70}")
    print(f"Pipeline Complete")
    print(f"{'=' * 70}")
    print(f"  원본:     {s['total_notes']} notes, {s['duration_sec']}s, {s['estimated_key']}")
    print(f"  변주:     {result_stats['total_notes']} notes, {result_stats['duration_sec']}s, {result_stats['estimated_key']}")
    print(f"  유사곡:   {len(similar)}곡 참조, {len(all_patterns)}개 패턴 사용")
    print(f"  섹션:     {' → '.join(sec['name'] for sec in sections)}")
    print(f"  출력:     {output_midi}")
    print(f"  메타:     {meta_path}")
    print(f"  검수필요: quality_score 미입력 (사람 검수 대기)")
    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
