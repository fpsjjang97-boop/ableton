"""
리뷰어 (Reviewer) 에이전트
=========================
역할: 생성된 MIDI 결과물 확인, 품질 평가, 피드백 제공
- 노트 분포/음역/벨로시티 분석
- 스케일 일관성 검증
- 리듬 패턴 평가
- 설정 대비 결과 검증
- 승인/반려/수정요청
"""

import os
import sys
import json
import glob
import mido
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
SETTINGS_FILE = os.path.join(PROJECT_DIR, "settings.json")
REVIEW_DIR = os.path.join(PROJECT_DIR, "reviews")

os.makedirs(REVIEW_DIR, exist_ok=True)

NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

SCALES = {
    'major':       [0, 2, 4, 5, 7, 9, 11],
    'minor':       [0, 2, 3, 5, 7, 8, 10],
    'dorian':      [0, 2, 3, 5, 7, 9, 10],
    'mixolydian':  [0, 2, 4, 5, 7, 9, 10],
    'pentatonic':  [0, 2, 4, 7, 9],
    'minor_penta': [0, 3, 5, 7, 10],
    'blues':       [0, 3, 5, 6, 7, 10],
    'chromatic':   list(range(12)),
}


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE) as f:
            return json.load(f)
    return {}


def midi_to_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


# ─── 분석 함수들 ───

def check_scale_consistency(notes, root, scale_name):
    """스케일 일관성 검증"""
    root_idx = NOTE_NAMES.index(root)
    scale_intervals = set(SCALES.get(scale_name, SCALES['chromatic']))
    scale_pcs = set((root_idx + i) % 12 for i in scale_intervals)

    in_scale = 0
    out_scale = 0
    out_notes = []

    for n in notes:
        pc = n % 12
        if pc in scale_pcs:
            in_scale += 1
        else:
            out_scale += 1
            out_notes.append(midi_to_name(n))

    total = in_scale + out_scale
    ratio = (in_scale / total * 100) if total > 0 else 0

    return {
        'in_scale': in_scale,
        'out_scale': out_scale,
        'ratio': ratio,
        'out_notes_sample': list(set(out_notes))[:10],
    }


def check_velocity_dynamics(velocities, expected_range):
    """벨로시티 다이내믹 검증"""
    if not velocities:
        return {'status': 'no_data'}

    vel_min = min(velocities)
    vel_max = max(velocities)
    vel_avg = sum(velocities) / len(velocities)
    vel_std = (sum((v - vel_avg)**2 for v in velocities) / len(velocities)) ** 0.5

    exp_min, exp_max = expected_range
    in_range = sum(1 for v in velocities if exp_min <= v <= exp_max)
    range_ratio = in_range / len(velocities) * 100

    return {
        'min': vel_min,
        'max': vel_max,
        'avg': round(vel_avg, 1),
        'std': round(vel_std, 1),
        'expected_range': expected_range,
        'in_range_ratio': round(range_ratio, 1),
        'dynamic_range': vel_max - vel_min,
    }


def check_rhythm_pattern(track, ticks_per_beat):
    """리듬 패턴 분석"""
    intervals = []
    abs_time = 0

    note_times = []
    for msg in track:
        abs_time += msg.time
        if msg.type == 'note_on' and msg.velocity > 0:
            note_times.append(abs_time)

    for i in range(1, len(note_times)):
        intervals.append(note_times[i] - note_times[i-1])

    if not intervals:
        return {'status': 'no_notes'}

    # 비트 단위로 변환
    beat_intervals = [i / ticks_per_beat for i in intervals]

    # 가장 흔한 간격
    from collections import Counter
    rounded = [round(b * 4) / 4 for b in beat_intervals]  # 16분음표 단위로 반올림
    counter = Counter(rounded)
    common = counter.most_common(5)

    return {
        'total_notes': len(note_times),
        'avg_interval_beats': round(sum(beat_intervals) / len(beat_intervals), 2),
        'common_intervals': [(f"{v}beat", c) for v, c in common],
        'regularity': round(counter.most_common(1)[0][1] / len(rounded) * 100, 1) if rounded else 0,
    }


def check_note_distribution(notes):
    """음 분포 분석"""
    if not notes:
        return {}

    dist = {}
    for n in notes:
        name = NOTE_NAMES[n % 12]
        dist[name] = dist.get(name, 0) + 1

    total = sum(dist.values())
    max_count = max(dist.values())

    # 엔트로피 계산 (다양성 지표)
    import math
    entropy = -sum((c/total) * math.log2(c/total) for c in dist.values() if c > 0)
    max_entropy = math.log2(len(dist)) if len(dist) > 1 else 1

    return {
        'distribution': dist,
        'unique_notes': len(dist),
        'dominant_note': max(dist, key=dist.get),
        'entropy': round(entropy, 2),
        'normalized_entropy': round(entropy / max_entropy, 2) if max_entropy > 0 else 0,
        'balance': '균형' if entropy / max_entropy > 0.8 else '편중' if entropy / max_entropy < 0.5 else '보통',
    }


# ─── 리뷰 실행 ───

def review_midi(filepath):
    """MIDI 파일 종합 리뷰"""
    mid = mido.MidiFile(filepath)
    settings = load_settings()
    basename = os.path.basename(filepath)

    print(f"\n{'='*60}")
    print(f"🔍 리뷰: {basename}")
    print(f"{'='*60}")

    # 기본 정보
    print(f"\n[기본 정보]")
    print(f"  트랙: {len(mid.tracks)}개")
    print(f"  길이: {mid.length:.1f}초 ({mid.length/60:.1f}분)")
    print(f"  Ticks/beat: {mid.ticks_per_beat}")

    all_notes = []
    all_velocities = []
    issues = []
    scores = {}

    for i, track in enumerate(mid.tracks):
        track_notes = []
        track_velocities = []

        for msg in track:
            if msg.type == 'note_on' and msg.velocity > 0:
                track_notes.append(msg.note)
                track_velocities.append(msg.velocity)

        if not track_notes:
            continue

        all_notes.extend(track_notes)
        all_velocities.extend(track_velocities)

        print(f"\n[트랙 {i}: {track.name or '(이름 없음)'}]")
        print(f"  노트: {len(track_notes)}개")
        print(f"  음역: {midi_to_name(min(track_notes))} ~ {midi_to_name(max(track_notes))}")

        # 스케일 일관성
        if settings.get('key') and settings.get('scale'):
            sc = check_scale_consistency(track_notes, settings['key'], settings['scale'])
            print(f"  스케일 일관성: {sc['ratio']:.1f}% ({settings['key']} {settings['scale']})")
            if sc['out_scale'] > 0:
                print(f"    스케일 밖 노트: {', '.join(sc['out_notes_sample'])}")
            if sc['ratio'] < 80:
                issues.append(f"트랙 {i} 스케일 일관성 낮음 ({sc['ratio']:.0f}%)")
            scores[f'track_{i}_scale'] = sc['ratio']

        # 벨로시티
        vel_range = settings.get('velocity_range', [0, 127])
        vc = check_velocity_dynamics(track_velocities, vel_range)
        print(f"  벨로시티: {vc['min']}~{vc['max']} (평균 {vc['avg']}, 범위내 {vc['in_range_ratio']}%)")
        if vc['in_range_ratio'] < 70:
            issues.append(f"트랙 {i} 벨로시티 범위 이탈 ({vc['in_range_ratio']:.0f}%)")
        scores[f'track_{i}_velocity'] = vc['in_range_ratio']

        # 리듬
        rc = check_rhythm_pattern(track, mid.ticks_per_beat)
        if rc.get('total_notes'):
            print(f"  리듬: 평균간격 {rc['avg_interval_beats']}beat, 규칙성 {rc['regularity']}%")
            common_str = ', '.join(f"{v}({c})" for v, c in rc['common_intervals'][:3])
            print(f"    주요 간격: {common_str}")
            scores[f'track_{i}_rhythm'] = rc['regularity']

    # 전체 음 분포
    if all_notes:
        nd = check_note_distribution(all_notes)
        print(f"\n[전체 음 분포]")
        print(f"  고유 음: {nd['unique_notes']}개")
        print(f"  지배적 음: {nd['dominant_note']}")
        print(f"  다양성: {nd['normalized_entropy']:.2f} ({nd['balance']})")

        max_c = max(nd['distribution'].values())
        for name in NOTE_NAMES:
            c = nd['distribution'].get(name, 0)
            if c > 0:
                bar = '█' * int(c / max_c * 20)
                print(f"    {name:2s} | {bar} {c}")

        scores['note_diversity'] = nd['normalized_entropy'] * 100

    # 종합 평가
    print(f"\n{'='*60}")
    print(f"📋 종합 평가")
    print(f"{'='*60}")

    if scores:
        avg_score = sum(scores.values()) / len(scores)
        print(f"  평균 점수: {avg_score:.1f}/100")

        if avg_score >= 80:
            grade = 'A (우수)'
        elif avg_score >= 60:
            grade = 'B (양호)'
        elif avg_score >= 40:
            grade = 'C (보통)'
        else:
            grade = 'D (개선 필요)'
        print(f"  등급: {grade}")

    if issues:
        print(f"\n  [이슈]")
        for iss in issues:
            print(f"  ⚠ {iss}")
    else:
        print(f"\n  ✓ 특이 이슈 없음")

    # 리뷰 결과 저장
    review = {
        'file': basename,
        'reviewed_at': datetime.now().isoformat(),
        'scores': scores,
        'avg_score': round(avg_score, 1) if scores else 0,
        'issues': issues,
        'total_notes': len(all_notes),
        'duration': mid.length,
    }

    review_path = os.path.join(REVIEW_DIR, f"review_{basename}.json")
    with open(review_path, 'w') as f:
        json.dump(review, f, indent=2, ensure_ascii=False)
    print(f"\n💾 리뷰 저장: {review_path}")

    # 메타데이터 업데이트
    meta_path = filepath + '.meta.json'
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)
        meta['status'] = 'approved' if not issues else 'needs_revision'
        meta['review'] = review
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

    return review


def list_pending():
    """리뷰 대기 파일 목록"""
    midi_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, '*.mid')))
    pending = []

    print(f"\n[리뷰 대기 목록]")
    for mf in midi_files:
        meta_path = mf + '.meta.json'
        status = 'unknown'
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
                status = meta.get('status', 'unknown')

        icon = '⏳' if status == 'pending_review' else '✓' if status == 'approved' else '⚠' if status == 'needs_revision' else '?'
        print(f"  {icon} {os.path.basename(mf)} [{status}]")

        if status == 'pending_review':
            pending.append(mf)

    if not midi_files:
        print("  (결과물 없음)")

    return pending


def review_all_pending():
    """모든 대기 파일 리뷰"""
    pending = list_pending()
    for fp in pending:
        review_midi(fp)


# ─── DPO 연동 ───

def export_for_dpo():
    """리뷰 결과를 읽어 DPO 학습 페어(chosen/rejected)를 자동 생성한다.

    1. reviews/ 디렉토리의 모든 리뷰 JSON 로드
    2. avg_score 기준으로 chosen(>=80) / rejected(<60) 분류
    3. midigpt.build_dpo_pairs 호출로 페어링 + 토크나이징 + 저장
    4. 생성된 페어 수 반환

    Returns:
        int: 생성된 DPO 페어 수 (오류 시 0)
    """
    try:
        sys.path.insert(0, PROJECT_DIR)
        from midigpt.build_dpo_pairs import collect_reviews, build_pairs, save_dpo_pairs, print_summary
    except ImportError as exc:
        print(f"[ERR] DPO 모듈 임포트 실패: {exc}")
        print("      midigpt/build_dpo_pairs.py 가 프로젝트 루트에 있는지 확인하세요.")
        return 0

    print(f"\n{'='*60}")
    print("📦 DPO 페어 생성 (export_for_dpo)")
    print(f"{'='*60}")

    # Step 1: 리뷰 수집
    print("\n[1/3] 리뷰 수집 중...")
    items = collect_reviews()
    if not items:
        print("  리뷰 데이터 없음. 먼저 MIDI 리뷰를 실행하세요.")
        return 0

    chosen = [r for r in items if r.category == "chosen"]
    rejected = [r for r in items if r.category == "rejected"]
    neutral = [r for r in items if r.category == "neutral"]

    print(f"  총 리뷰: {len(items)}건")
    print(f"    Chosen  (score >= 80): {len(chosen)}건")
    print(f"    Rejected (score < 60): {len(rejected)}건")
    print(f"    Neutral (60~79):       {len(neutral)}건")

    if not chosen or not rejected:
        lack = "chosen (우수)" if not chosen else "rejected (저평가)"
        print(f"\n  ⚠ {lack} 샘플이 없어 DPO 페어를 만들 수 없습니다.")
        print("    더 많은 MIDI를 생성/리뷰하여 양쪽 분포를 확보하세요.")
        return 0

    # Step 2: 페어링
    print("\n[2/3] 페어 매칭 중...")
    pairs = build_pairs(items)
    if not pairs:
        print("  매칭된 페어가 없습니다 (키/템포 조건 불일치 또는 MIDI 파일 누락).")
        return 0

    print(f"  매칭 완료: {len(pairs)}쌍")

    # Step 3: 토크나이징 + 저장
    print("\n[3/3] 토크나이징 & 저장 중...")
    saved = save_dpo_pairs(pairs, dry_run=False)

    # 요약
    print_summary(items, pairs, saved)

    print(f"\n✅ DPO 페어 {saved}쌍 생성 완료!")
    return saved


# ─── CLI ───

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'review' and len(sys.argv) > 2:
            review_midi(sys.argv[2])
        elif cmd == 'pending':
            list_pending()
        elif cmd == 'all':
            review_all_pending()
        elif cmd == 'dpo':
            export_for_dpo()
        else:
            print("사용법: python reviewer.py [review <file>|pending|all|dpo]")
    else:
        print("="*50)
        print("🔍 리뷰어 에이전트 (Reviewer)")
        print("="*50)
        print("명령어:")
        print("  review <file> - MIDI 파일 리뷰")
        print("  pending       - 대기 목록 확인")
        print("  all           - 대기 파일 전부 리뷰")
        print("  dpo           - DPO 학습 페어 생성")
        print("  quit          - 종료")
        print()

        while True:
            try:
                cmd = input("reviewer> ").strip()
                if not cmd:
                    continue
                elif cmd == 'quit':
                    break
                elif cmd.startswith('review '):
                    filepath = cmd.split(maxsplit=1)[1]
                    if not os.path.isabs(filepath):
                        filepath = os.path.join(OUTPUT_DIR, filepath)
                    if os.path.exists(filepath):
                        review_midi(filepath)
                    else:
                        print(f"파일 없음: {filepath}")
                elif cmd == 'pending':
                    list_pending()
                elif cmd == 'all':
                    review_all_pending()
                elif cmd == 'dpo':
                    export_for_dpo()
                else:
                    print(f"알 수 없는 명령: {cmd}")
            except (EOFError, KeyboardInterrupt):
                print()
                break
