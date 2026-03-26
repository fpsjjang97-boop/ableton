"""
MIDI 카탈로그 생성 — 카테고리/조성/템포/난이도별 분류 인덱스
embeddings/catalog.json 생성
"""

import os, sys, json, glob

sys.stdout.reconfigure(encoding='utf-8')

EMBED_DIR = os.path.join(os.path.dirname(__file__), '..', 'embeddings')
CATEGORIES = ['chamber', 'recital', 'schubert', 'pop909']

KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def classify_tempo(bpm):
    if bpm < 60: return 'Largo'
    if bpm < 80: return 'Adagio'
    if bpm < 100: return 'Andante'
    if bpm < 120: return 'Moderato'
    if bpm < 140: return 'Allegro'
    if bpm < 170: return 'Vivace'
    return 'Presto'


def classify_complexity(notes, duration):
    """노트 밀도(notes/sec)로 난이도 추정"""
    if duration == 0: return 'unknown'
    density = notes / duration
    if density < 3: return 'easy'
    if density < 7: return 'intermediate'
    if density < 12: return 'advanced'
    return 'virtuoso'


def classify_dynamics(vel_mean, vel_std):
    """다이나믹 스타일 분류"""
    if vel_mean < 40: return 'pianissimo'
    if vel_mean < 60: return 'piano'
    if vel_mean < 80: return 'mezzo-forte'
    if vel_mean < 100: return 'forte'
    return 'fortissimo'


def classify_register(pitch_mean):
    """음역대 분류"""
    if pitch_mean < 48: return 'bass'
    if pitch_mean < 60: return 'tenor'
    if pitch_mean < 72: return 'alto'
    if pitch_mean < 84: return 'soprano'
    return 'high'


def main():
    catalog = []
    by_category = {c: [] for c in CATEGORIES}
    by_key = {k: [] for k in KEY_NAMES}
    by_tempo = {}
    by_complexity = {}
    by_dynamics = {}
    by_register = {}
    # 작곡가 관점 태그 인덱스
    by_rhythm_type = {}
    by_harmony_type = {}
    by_accompaniment = {}
    by_voicing_type = {}
    by_dynamic_profile = {}

    for cat in CATEGORIES:
        cat_dir = os.path.join(EMBED_DIR, 'individual', cat)
        files = sorted(glob.glob(os.path.join(cat_dir, '*.json')))

        for filepath in files:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            stats = data['stats']
            fname = stats['filename']

            tempo_class = classify_tempo(stats.get('avg_tempo', 120))
            complexity = classify_complexity(stats['total_notes'], stats['total_duration_sec'])
            dynamics = classify_dynamics(stats.get('velocity_mean', 64), stats.get('velocity_std', 20))
            register = classify_register(stats.get('pitch_mean', 60))

            # 작곡가 관점 태그 (있으면 사용)
            ctags = data.get('composer_tags', {})

            entry = {
                'filename': fname,
                'category': cat,
                'estimated_key': stats.get('estimated_key', '?'),
                'tempo_bpm': stats.get('avg_tempo', 120),
                'tempo_class': tempo_class,
                'total_notes': stats['total_notes'],
                'duration_sec': stats['total_duration_sec'],
                'duration_min': round(stats['total_duration_sec'] / 60, 1),
                'notes_per_sec': round(stats['total_notes'] / max(stats['total_duration_sec'], 1), 1),
                'complexity': complexity,
                'dynamics': dynamics,
                'dynamics_detail': {
                    'velocity_mean': stats.get('velocity_mean'),
                    'velocity_std': stats.get('velocity_std'),
                    'velocity_range': stats.get('velocity_range'),
                },
                'register': register,
                'pitch_range': stats.get('pitch_range'),
                'pitch_mean': stats.get('pitch_mean'),
                'time_signatures': stats.get('time_signatures', []),
                'embedding_file': f'individual/{cat}/{fname.replace(".midi", ".json").replace(".mid", ".json")}',
                'midi_file': f'Ableton/midi_raw/{cat}/{fname}',
                # 작곡가 관점 태그
                'composer_tags': ctags,
            }

            catalog.append(entry)
            by_category[cat].append(fname)

            # 작곡가 태그별 인덱스 구축
            if ctags:
                by_rhythm_type.setdefault(ctags.get('rhythm_type', 'unknown'), []).append(fname)
                by_harmony_type.setdefault(ctags.get('harmony_type', 'unknown'), []).append(fname)
                by_accompaniment.setdefault(ctags.get('accompaniment_pattern', 'unknown'), []).append(fname)
                by_voicing_type.setdefault(ctags.get('voicing_type', 'unknown'), []).append(fname)
                by_dynamic_profile.setdefault(ctags.get('dynamic_profile', 'unknown'), []).append(fname)

            key = stats.get('estimated_key', '?')
            if key in by_key:
                by_key[key].append(fname)

            by_tempo.setdefault(tempo_class, []).append(fname)
            by_complexity.setdefault(complexity, []).append(fname)
            by_dynamics.setdefault(dynamics, []).append(fname)
            by_register.setdefault(register, []).append(fname)

    # 카탈로그 저장
    output = {
        'generated': '2026-03-23',
        'total_files': len(catalog),
        'classification_summary': {
            'by_category': {k: len(v) for k, v in by_category.items()},
            'by_key': {k: len(v) for k, v in by_key.items() if v},
            'by_tempo': {k: len(v) for k, v in by_tempo.items()},
            'by_complexity': {k: len(v) for k, v in by_complexity.items()},
            'by_dynamics': {k: len(v) for k, v in by_dynamics.items()},
            'by_register': {k: len(v) for k, v in by_register.items()},
            # 작곡가 관점 분류
            'by_rhythm_type': {k: len(v) for k, v in by_rhythm_type.items()},
            'by_harmony_type': {k: len(v) for k, v in by_harmony_type.items()},
            'by_accompaniment': {k: len(v) for k, v in by_accompaniment.items()},
            'by_voicing_type': {k: len(v) for k, v in by_voicing_type.items()},
            'by_dynamic_profile': {k: len(v) for k, v in by_dynamic_profile.items()},
        },
        'index': {
            'by_category': by_category,
            'by_key': {k: v for k, v in by_key.items() if v},
            'by_tempo': by_tempo,
            'by_complexity': by_complexity,
            'by_dynamics': by_dynamics,
            'by_register': by_register,
            # 작곡가 관점 인덱스
            'by_rhythm_type': by_rhythm_type,
            'by_harmony_type': by_harmony_type,
            'by_accompaniment': by_accompaniment,
            'by_voicing_type': by_voicing_type,
            'by_dynamic_profile': by_dynamic_profile,
        },
        'catalog': catalog,
    }

    outpath = os.path.join(EMBED_DIR, 'catalog.json')
    with open(outpath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 사람이 읽을 수 있는 요약 테이블 생성
    lines = ['# MIDI 카탈로그 — 분류 요약\n']
    lines.append(f'총 {len(catalog)}개 파일 | 생성: 2026-03-23\n')

    lines.append('\n## 카테고리별')
    lines.append('| 카테고리 | 파일 수 | 설명 |')
    lines.append('|----------|---------|------|')
    lines.append(f'| chamber | {len(by_category["chamber"])} | 실내악 피아노 |')
    lines.append(f'| recital | {len(by_category["recital"])} | 독주회 피아노 |')
    lines.append(f'| schubert | {len(by_category["schubert"])} | 슈베르트 소나타 |')

    lines.append('\n## 조성별')
    lines.append('| 조성 | 파일 수 |')
    lines.append('|------|---------|')
    for k in KEY_NAMES:
        if by_key[k]:
            lines.append(f'| {k} | {len(by_key[k])} |')

    lines.append('\n## 템포별')
    lines.append('| 템포 | 파일 수 | BPM 범위 |')
    lines.append('|------|---------|----------|')
    tempo_order = ['Largo', 'Adagio', 'Andante', 'Moderato', 'Allegro', 'Vivace', 'Presto']
    bpm_ranges = {'Largo': '<60', 'Adagio': '60-79', 'Andante': '80-99', 'Moderato': '100-119', 'Allegro': '120-139', 'Vivace': '140-169', 'Presto': '170+'}
    for t in tempo_order:
        if t in by_tempo:
            lines.append(f'| {t} | {len(by_tempo[t])} | {bpm_ranges[t]} |')

    lines.append('\n## 난이도별')
    lines.append('| 난이도 | 파일 수 | 노트 밀도 (notes/sec) |')
    lines.append('|--------|---------|----------------------|')
    comp_desc = {'easy': '<3', 'intermediate': '3-6', 'advanced': '7-11', 'virtuoso': '12+'}
    for c in ['easy', 'intermediate', 'advanced', 'virtuoso']:
        if c in by_complexity:
            lines.append(f'| {c} | {len(by_complexity[c])} | {comp_desc[c]} |')

    lines.append('\n## 다이나믹별')
    lines.append('| 다이나믹 | 파일 수 |')
    lines.append('|----------|---------|')
    for d in ['pianissimo', 'piano', 'mezzo-forte', 'forte', 'fortissimo']:
        if d in by_dynamics:
            lines.append(f'| {d} | {len(by_dynamics[d])} |')

    lines.append('\n## 전체 목록')
    lines.append('| # | 파일명 | 카테고리 | 키 | 템포 | 노트 | 시간 | 난이도 | 다이나믹 |')
    lines.append('|---|--------|----------|-----|------|------|------|--------|----------|')
    for i, e in enumerate(catalog):
        lines.append(f'| {i+1} | {e["filename"][:50]} | {e["category"]} | {e["estimated_key"]} | {e["tempo_class"]} ({e["tempo_bpm"]:.0f}) | {e["total_notes"]:,} | {e["duration_min"]}min | {e["complexity"]} | {e["dynamics"]} |')

    lines.append('')
    md_path = os.path.join(EMBED_DIR, 'CATALOG.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"Catalog: {outpath}")
    print(f"Summary: {md_path}")
    print(f"\nClassification:")
    for key, counts in output['classification_summary'].items():
        print(f"  {key}: {counts}")


if __name__ == '__main__':
    main()
