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
        with open(SETTINGS_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {}


def midi_to_name(n):
    return f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"


# ─── 분석 함수들 ───

# 2026-04-21 결함리스트 #10 대응 — Reviewer 계층 확장. 기존 scale/velocity/
# rhythm/distribution 체크 외에 "실제 코드 진행을 따르는가" + "트랙끼리
# 충돌하는가" 를 판정. 출력은 기존 체크들과 같은 dict 형식.
_CHORD_TONE_INTERVALS = {
    # triad + 7th (engine.py _CHORD_TONE_INTERVALS 와 동일 의도, reviewer
    # 는 순수 분석 path 라 별도 정의해 의존성 방향 단순화).
    "maj":  [0, 4, 7],       "maj7": [0, 4, 7, 11],
    "min":  [0, 3, 7],       "m7":   [0, 3, 7, 10],
    "7":    [0, 4, 7, 10],
    "dim":  [0, 3, 6],       "aug":  [0, 4, 8],
    "sus4": [0, 5, 7],       "sus2": [0, 2, 7],
}


def check_chord_adherence(notes_with_beat, chord_progression, bar_duration_beats=4.0):
    """노트가 주어진 코드 진행을 얼마나 잘 따르는가.

    Args:
        notes_with_beat: list of (pitch_int, start_beat_float) tuples.
        chord_progression: list of (root_name, quality, start_beat, length_beats).
        bar_duration_beats: 4 (4/4) default.

    Returns dict with keys:
        downbeat_chord_tone_ratio  — 강박(beat 0/2)에서 chord tone 비율 (%)
        per_bar_adherence          — 각 bar 별 chord tone 비율
        average_adherence          — 전체 bar 평균
    """
    if not notes_with_beat or not chord_progression:
        return {"status": "no_data"}

    # Map from absolute beat → (root_pc, quality) lookup
    def chord_at(beat):
        for root_name, quality, start, length in chord_progression:
            if start <= beat < start + length:
                try:
                    root_pc = NOTE_NAMES.index(root_name)
                except ValueError:
                    return None
                return (root_pc, quality)
        return None

    def is_chord_tone(pitch, chord):
        if chord is None:
            return None
        root_pc, quality = chord
        intervals = _CHORD_TONE_INTERVALS.get(quality, [0, 4, 7])
        allowed = {(root_pc + iv) % 12 for iv in intervals}
        return (pitch % 12) in allowed

    # Bar-level aggregation
    per_bar = {}
    downbeat_hits = 0
    downbeat_total = 0
    for pitch, beat in notes_with_beat:
        bar_idx = int(beat / bar_duration_beats)
        chord = chord_at(beat)
        ct = is_chord_tone(pitch, chord)
        if ct is None:
            continue
        per_bar.setdefault(bar_idx, [0, 0])  # [chord_tone, total]
        per_bar[bar_idx][1] += 1
        if ct:
            per_bar[bar_idx][0] += 1

        # Downbeat = 박자 정수 또는 0.5 이하
        beat_in_bar = beat - bar_idx * bar_duration_beats
        if abs(beat_in_bar - round(beat_in_bar)) < 0.05 and int(round(beat_in_bar)) in (0, 2):
            downbeat_total += 1
            if ct:
                downbeat_hits += 1

    adherence = {b: (ct / total * 100) if total > 0 else 0
                 for b, (ct, total) in per_bar.items()}
    avg = (sum(adherence.values()) / len(adherence)) if adherence else 0
    downbeat_ratio = (downbeat_hits / downbeat_total * 100) if downbeat_total > 0 else 0

    return {
        "downbeat_chord_tone_ratio": round(downbeat_ratio, 1),
        "per_bar_adherence":         {b: round(v, 1) for b, v in adherence.items()},
        "average_adherence":         round(avg, 1),
        "bars_checked":              len(per_bar),
    }


def check_track_conflicts(tracks, window_seconds=0.1, min_pitch_sep=2):
    """여러 트랙이 동시 타이밍에 충돌(너무 가까운 피치 중복) 여부 검증.

    Args:
        tracks: list of dicts {"name": str, "notes": [(pitch, start_sec), ...]}.
        window_seconds: same-time 판정 창.
        min_pitch_sep: 최소 허용 반음 간격. 미만은 충돌로 계수.

    Returns dict with:
        conflict_count — 시간-피치 근접 중복 수
        worst_pair     — (track_a, track_b, count) 가장 자주 충돌한 쌍
    """
    if len(tracks) < 2:
        return {"status": "single_track"}

    pairs_count = {}
    total = 0
    for i in range(len(tracks)):
        for j in range(i + 1, len(tracks)):
            na, nb = tracks[i]["notes"], tracks[j]["notes"]
            conflicts = 0
            for (pa, ta) in na:
                for (pb, tb) in nb:
                    if abs(ta - tb) <= window_seconds and abs(pa - pb) < min_pitch_sep:
                        conflicts += 1
            pairs_count[(tracks[i]["name"], tracks[j]["name"])] = conflicts
            total += conflicts

    worst = max(pairs_count.items(), key=lambda kv: kv[1]) if pairs_count else (("", ""), 0)
    return {
        "conflict_count": total,
        "worst_pair":     (worst[0][0], worst[0][1], worst[1]),
        "pairs":          {f"{a}|{b}": c for (a, b), c in pairs_count.items()},
    }


def check_bar_density(notes_with_beat, start_bar: int = 0,
                      end_bar: int | None = None,
                      beats_per_bar: float = 4.0,
                      min_notes_per_bar: int = 1):
    """Sprint VVV — empty-bar / sparse-output guard (종합리뷰 §6-2, §20-4).

    The "긴 파일인데 중간 마디가 비는" symptom (9차까지 반복 확인) needs a
    detector at the reviewer level so the generation loop can reject or
    regenerate. This walks the target bar range and counts note-ons per bar.

    Args:
        notes_with_beat: list of (pitch, start_beat, ...). Only start_beat is used.
        start_bar:       inclusive. Defaults to 0.
        end_bar:         exclusive. Defaults to max bar seen in the input.
        beats_per_bar:   1.0 = quarter, 4.0 = 4/4 default.
        min_notes_per_bar: a bar with fewer note-ons than this is flagged.

    Returns dict with:
        total_bars          — end_bar - start_bar
        empty_bars          — count where note-count == 0
        sparse_bars         — count where 0 < count < min_notes_per_bar
        density             — notes per bar overall
        longest_empty_run   — longest consecutive-empty-bar stretch
        pass                — True iff no empty bars AND no run > 1 sparse
        histogram           — list[int] per-bar note count (length total_bars)
    """
    if beats_per_bar <= 0:
        beats_per_bar = 4.0

    max_beat = 0.0
    for ev in notes_with_beat:
        # Support both (pitch, beat) pairs and full tuples.
        b = ev[1] if len(ev) >= 2 else 0.0
        if b > max_beat:
            max_beat = b
    if end_bar is None:
        end_bar = int(max_beat / beats_per_bar) + 1
    if end_bar <= start_bar:
        return {"status": "empty_range", "pass": False}

    total = end_bar - start_bar
    histogram = [0] * total
    for ev in notes_with_beat:
        b = ev[1] if len(ev) >= 2 else 0.0
        bar_idx = int(b / beats_per_bar) - start_bar
        if 0 <= bar_idx < total:
            histogram[bar_idx] += 1

    empty_bars = sum(1 for c in histogram if c == 0)
    sparse_bars = sum(1 for c in histogram
                      if 0 < c < min_notes_per_bar)
    total_notes = sum(histogram)
    density = total_notes / total if total else 0.0

    run = longest = 0
    for c in histogram:
        if c == 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0

    return {
        "total_bars":        total,
        "empty_bars":        empty_bars,
        "sparse_bars":       sparse_bars,
        "density":           density,
        "longest_empty_run": longest,
        "pass":              empty_bars == 0 and longest <= 0,
        "histogram":         histogram,
    }


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
    # encoding='utf-8' is required: on Korean Windows the default text-mode
    # encoding is CP949, which then causes UnicodeDecodeError downstream when
    # build_dpo_pairs.py reads these files with encoding='utf-8'.
    with open(review_path, 'w', encoding='utf-8') as f:
        json.dump(review, f, indent=2, ensure_ascii=False)
    print(f"\n💾 리뷰 저장: {review_path}")

    # 메타데이터 업데이트
    meta_path = filepath + '.meta.json'
    if os.path.exists(meta_path):
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)
        meta['status'] = 'approved' if not issues else 'needs_revision'
        meta['review'] = review
        with open(meta_path, 'w', encoding='utf-8') as f:
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
            with open(meta_path, encoding='utf-8') as f:
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
