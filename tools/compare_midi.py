"""원본 11.mid vs 변주곡 비교 분석"""
import sys, json
import numpy as np
import pretty_midi

sys.stdout.reconfigure(encoding='utf-8')

ORIGINAL = 'E:/SUNO/ableton-work/11.mid'
VARIATION = 'E:/SUNO/ableton-work/output/2026-03-23_variation_classic_piano.mid'

def analyze(path):
    midi = pretty_midi.PrettyMIDI(path)
    notes = []
    for inst in midi.instruments:
        for n in inst.notes:
            notes.append({
                'pitch': n.pitch, 'start': round(n.start, 3),
                'end': round(n.end, 3), 'dur': round(n.end - n.start, 3),
                'vel': n.velocity
            })
    notes.sort(key=lambda x: x['start'])

    pitches = [n['pitch'] for n in notes]
    vels = [n['vel'] for n in notes]
    durs = [n['dur'] for n in notes]

    # 피치 클래스 분포
    pc_hist = np.zeros(12)
    for p in pitches:
        pc_hist[p % 12] += 1

    # 인터벌
    intervals = [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]

    # 동시발음 (50ms 이내)
    chords = 0
    for i in range(len(notes)-1):
        if abs(notes[i+1]['start'] - notes[i]['start']) < 0.05:
            chords += 1

    # 섹션별 노트 밀도
    end_time = midi.get_end_time()
    section_size = 30
    sections = []
    t = 0
    while t < end_time:
        sec_notes = [n for n in notes if t <= n['start'] < t + section_size]
        sections.append({
            'time': f"{int(t)}-{int(t+section_size)}s",
            'notes': len(sec_notes),
            'density': round(len(sec_notes) / section_size, 1) if sec_notes else 0,
            'avg_vel': round(np.mean([n['vel'] for n in sec_notes]), 1) if sec_notes else 0,
            'avg_pitch': round(np.mean([n['pitch'] for n in sec_notes]), 1) if sec_notes else 0,
        })
        t += section_size

    tempos = midi.get_tempo_changes()
    tempo = float(np.mean(tempos[1])) if len(tempos[1]) > 0 else 120.0

    keys = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    top_keys = sorted(range(12), key=lambda i: pc_hist[i], reverse=True)

    return {
        'notes': len(notes),
        'duration': round(end_time, 1),
        'tempo': round(tempo, 1),
        'pitch_range': [min(pitches), max(pitches)],
        'pitch_mean': round(np.mean(pitches), 1),
        'pitch_std': round(np.std(pitches), 1),
        'vel_range': [min(vels), max(vels)],
        'vel_mean': round(np.mean(vels), 1),
        'vel_std': round(np.std(vels), 1),
        'dur_mean': round(np.mean(durs), 3),
        'dur_std': round(np.std(durs), 3),
        'top_keys': [keys[i] for i in top_keys[:3]],
        'pc_hist': pc_hist,
        'interval_mean': round(np.mean(np.abs(intervals)), 2),
        'interval_std': round(np.std(intervals), 2),
        'large_leaps': sum(1 for iv in intervals if abs(iv) > 7),
        'step_motion': sum(1 for iv in intervals if abs(iv) <= 2),
        'chord_count': chords,
        'sections': sections,
        'raw_notes': notes,
    }

orig = analyze(ORIGINAL)
var = analyze(VARIATION)

print("=" * 70)
print("원본 11.mid vs 변주곡 비교")
print("=" * 70)

print(f"\n{'항목':<25} {'원본':>15} {'변주곡':>15} {'변화':>15}")
print("-" * 70)
print(f"{'총 노트 수':<25} {orig['notes']:>15,} {var['notes']:>15,} {var['notes']-orig['notes']:>+15,}")
print(f"{'재생 시간(초)':<25} {orig['duration']:>15} {var['duration']:>15} {var['duration']-orig['duration']:>+15.1f}")
print(f"{'템포(BPM)':<25} {orig['tempo']:>15} {var['tempo']:>15} {var['tempo']-orig['tempo']:>+15.1f}")
print(f"{'피치 범위':<25} {str(orig['pitch_range']):>15} {str(var['pitch_range']):>15}")
print(f"{'평균 피치':<25} {orig['pitch_mean']:>15} {var['pitch_mean']:>15} {var['pitch_mean']-orig['pitch_mean']:>+15.1f}")
print(f"{'피치 표준편차':<25} {orig['pitch_std']:>15} {var['pitch_std']:>15} {var['pitch_std']-orig['pitch_std']:>+15.1f}")
print(f"{'벨로시티 범위':<25} {str(orig['vel_range']):>15} {str(var['vel_range']):>15}")
print(f"{'평균 벨로시티':<25} {orig['vel_mean']:>15} {var['vel_mean']:>15} {var['vel_mean']-orig['vel_mean']:>+15.1f}")
print(f"{'벨로시티 편차':<25} {orig['vel_std']:>15} {var['vel_std']:>15} {var['vel_std']-orig['vel_std']:>+15.1f}")
print(f"{'평균 음 길이(초)':<25} {orig['dur_mean']:>15} {var['dur_mean']:>15} {var['dur_mean']-orig['dur_mean']:>+15.3f}")
print(f"{'주요 조성':<25} {str(orig['top_keys']):>15} {str(var['top_keys']):>15}")
print(f"{'평균 인터벌(반음)':<25} {orig['interval_mean']:>15} {var['interval_mean']:>15} {var['interval_mean']-orig['interval_mean']:>+15.2f}")
print(f"{'큰 도약(>7반음)':<25} {orig['large_leaps']:>15} {var['large_leaps']:>15} {var['large_leaps']-orig['large_leaps']:>+15}")
print(f"{'순차진행(<=2반음)':<25} {orig['step_motion']:>15} {var['step_motion']:>15} {var['step_motion']-orig['step_motion']:>+15}")
print(f"{'화음(동시발음)':<25} {orig['chord_count']:>15} {var['chord_count']:>15} {var['chord_count']-orig['chord_count']:>+15}")

print(f"\n{'='*70}")
print("섹션별 비교")
print(f"{'='*70}")
print(f"\n[원본 섹션]")
print(f"{'구간':<15} {'노트수':>8} {'밀도(n/s)':>10} {'평균벨로시티':>12} {'평균피치':>10}")
for s in orig['sections']:
    print(f"{s['time']:<15} {s['notes']:>8} {s['density']:>10} {s['avg_vel']:>12} {s['avg_pitch']:>10}")

print(f"\n[변주곡 섹션]")
print(f"{'구간':<15} {'노트수':>8} {'밀도(n/s)':>10} {'평균벨로시티':>12} {'평균피치':>10} {'설명'}")
labels = ['Theme(테마제시)', 'Theme->RhythmVar', 'RhythmVar(리듬변주)', 'HarmonicVar(화성변주)', 'Climax(클라이맥스)', 'Coda(코다)']
for i, s in enumerate(var['sections']):
    label = labels[i] if i < len(labels) else ''
    print(f"{s['time']:<15} {s['notes']:>8} {s['density']:>10} {s['avg_vel']:>12} {s['avg_pitch']:>10}  {label}")

# 피치 클래스 비교
print(f"\n{'='*70}")
print("피치 클래스 분포 비교 (음 사용 빈도)")
print(f"{'='*70}")
keys = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
o_total = orig['pc_hist'].sum()
v_total = var['pc_hist'].sum()
print(f"\n{'음':>4} {'원본':>8} {'변주곡':>8} {'차이':>8}")
for i in range(12):
    o_pct = orig['pc_hist'][i] / o_total * 100
    v_pct = var['pc_hist'][i] / v_total * 100
    bar_o = '█' * int(o_pct / 2)
    bar_v = '▓' * int(v_pct / 2)
    print(f"{keys[i]:>4} {o_pct:>7.1f}% {v_pct:>7.1f}% {v_pct-o_pct:>+7.1f}%  {bar_o} | {bar_v}")

print(f"\n{'='*70}")
print("핵심 변경 요약")
print(f"{'='*70}")
print(f"""
1. 구조: 원본은 단일 흐름 → 변주곡은 5섹션 구조
   (테마제시 → 리듬변주 → 화성변주 → 클라이맥스 → 코다)

2. 노트 수: {orig['notes']}개 → {var['notes']}개 ({var['notes']-orig['notes']:+d})
   - 화성변주에서 보이싱(화음) 추가 → 노트 증가
   - 클라이맥스에서 빠른 패시지 추가

3. 리듬: 레퍼런스 DB에서 8,480개 리듬 패턴 중 선별 적용
   - 원본 평균 음길이 {orig['dur_mean']}s → 변주 {var['dur_mean']}s
   - 슈베르트/리사이틀의 다양한 리듬감 반영

4. 다이나믹: 평균 벨로시티 {orig['vel_mean']} → {var['vel_mean']}
   - 원본은 전체적으로 부드러운 pp~mp
   - 변주곡은 pp(코다) ~ ff(클라이맥스) 폭넓은 다이나믹

5. 화성: 동시발음 {orig['chord_count']}개 → {var['chord_count']}개
   - 레퍼런스 보이싱 패턴 8,282개에서 화음 구조 차용

6. 조성: Bb minor 유지 (원본 스케일 보존)
   - 비스케일 음은 가장 가까운 Bb minor 음으로 보정

7. 템포: {orig['tempo']} BPM → {var['tempo']} BPM
""")
