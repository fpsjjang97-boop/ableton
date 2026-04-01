"""
MIDI Embedding Pipeline
- 93개 MAESTRO 2018 피아노 MIDI 파일을 분석/임베딩
- 노트 시퀀스, 통계, 피아노롤 임베딩 생성
- 데이터 누락 없이 전체 파일 처리
"""

import os
import sys
import json
import glob
import numpy as np
import pretty_midi
from collections import Counter

# Windows 콘솔 UTF-8 출력
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)

MIDI_DIR = os.path.join(os.path.dirname(__file__), '..', 'Ableton', 'midi_raw')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'embeddings')
PIANOROLL_RES = 100  # 피아노롤 해상도 (100 steps/beat)
EMBED_DIM = 128      # 임베딩 차원


def analyze_composer_tags(all_notes, midi):
    """작곡가 관점 파라미터 자동 추출 — Troubleshooter 이슈 #1 대응"""
    if not all_notes:
        return {}

    pitches = [n['pitch'] for n in all_notes]
    velocities = [n['velocity'] for n in all_notes]
    durations = [n['duration'] for n in all_notes]
    starts = [n['start'] for n in all_notes]
    total_dur = all_notes[-1]['end'] if all_notes else 1.0

    # ── 1. 리듬 유형 분석 ──
    # IOI (Inter-Onset Interval) 기반
    ioi_list = [starts[i+1] - starts[i] for i in range(len(starts)-1) if starts[i+1] - starts[i] > 0]
    avg_ioi = float(np.mean(ioi_list)) if ioi_list else 1.0
    ioi_std = float(np.std(ioi_list)) if ioi_list else 0.0

    # 리듬 규칙성: std/mean 비율 — 낮을수록 규칙적
    rhythm_regularity = 1.0 - min(1.0, ioi_std / avg_ioi) if avg_ioi > 0 else 0.0

    # 리듬 밀도: 초당 노트 수
    note_density = len(all_notes) / max(total_dur, 0.1)

    # 리듬 유형 분류
    if note_density < 1.5:
        rhythm_type = "sparse"       # 희박 (앰비언트, 패드)
    elif note_density < 4.0:
        rhythm_type = "moderate"     # 보통 (발라드, 반주)
    elif note_density < 8.0:
        rhythm_type = "dense"        # 밀집 (아르페지오, 컴핑)
    else:
        rhythm_type = "virtuosic"    # 고밀도 (빠른 패시지, 트레몰로)

    # ── 2. 화성 성향 분석 ──
    # 동시 발음 그룹 탐지 (50ms 이내 = 동시)
    chord_groups = []
    current_group = [all_notes[0]]
    for i in range(1, len(all_notes)):
        if all_notes[i]['start'] - current_group[0]['start'] < 0.05:
            current_group.append(all_notes[i])
        else:
            if len(current_group) >= 2:
                chord_groups.append(current_group)
            current_group = [all_notes[i]]
    if len(current_group) >= 2:
        chord_groups.append(current_group)

    # 동시 발음 수 통계
    polyphony_values = [len(g) for g in chord_groups]
    avg_polyphony = float(np.mean(polyphony_values)) if polyphony_values else 1.0
    max_polyphony = max(polyphony_values) if polyphony_values else 1

    # 화성 비율 (전체 노트 중 화음에 속하는 비율)
    chordal_notes = sum(len(g) for g in chord_groups)
    harmony_ratio = chordal_notes / max(len(all_notes), 1)

    # 인터벌 분석 — 화음 내 인터벌
    chord_intervals = []
    for g in chord_groups:
        g_pitches = sorted(set(n['pitch'] for n in g))
        for i in range(len(g_pitches) - 1):
            chord_intervals.append(g_pitches[i+1] - g_pitches[i])

    # 장/단 성향: 장3도(4) vs 단3도(3) 비율
    major_thirds = sum(1 for iv in chord_intervals if iv == 4)
    minor_thirds = sum(1 for iv in chord_intervals if iv == 3)
    if major_thirds + minor_thirds > 0:
        harmonic_brightness = major_thirds / (major_thirds + minor_thirds)
    else:
        harmonic_brightness = 0.5

    # 화성 유형 분류
    if harmony_ratio < 0.2:
        harmony_type = "monophonic"   # 단선율
    elif avg_polyphony < 2.5:
        harmony_type = "dyadic"       # 2음 위주
    elif avg_polyphony < 4.0:
        harmony_type = "triadic"      # 3화음 위주
    else:
        harmony_type = "dense_voicing" # 밀집 보이싱

    # ── 3. 반주 구조 분석 ──
    # 아르페지오 감지: 순차적으로 가까운 음이 빠르게 나오는 패턴
    arpeggio_count = 0
    for i in range(len(all_notes) - 3):
        window = all_notes[i:i+4]
        time_span = window[-1]['start'] - window[0]['start']
        if 0.05 < time_span < 0.5:  # 빠른 순차 진행
            pitches_w = [n['pitch'] for n in window]
            intervals_w = [pitches_w[j+1] - pitches_w[j] for j in range(len(pitches_w)-1)]
            # 같은 방향으로 움직이면 아르페지오
            if all(iv > 0 for iv in intervals_w) or all(iv < 0 for iv in intervals_w):
                arpeggio_count += 1

    arpeggio_ratio = arpeggio_count / max(len(all_notes) - 3, 1)

    if arpeggio_ratio > 0.15:
        accompaniment_pattern = "arpeggio"
    elif harmony_ratio > 0.6:
        accompaniment_pattern = "block_chord"
    elif rhythm_regularity > 0.7 and note_density > 3.0:
        accompaniment_pattern = "comping"
    elif note_density < 2.0 and harmony_ratio > 0.3:
        accompaniment_pattern = "pad"
    else:
        accompaniment_pattern = "mixed"

    # ── 4. 보이싱 밀도 & 음역 분석 ──
    pitch_range = max(pitches) - min(pitches)
    register_center = float(np.mean(pitches))

    if register_center < 48:
        register = "bass"
    elif register_center < 60:
        register = "tenor"
    elif register_center < 72:
        register = "alto"
    else:
        register = "soprano"

    # 보이싱 스프레드 (화음 내 음역 폭)
    voicing_spreads = []
    for g in chord_groups:
        g_pitches = [n['pitch'] for n in g]
        voicing_spreads.append(max(g_pitches) - min(g_pitches))
    avg_voicing_spread = float(np.mean(voicing_spreads)) if voicing_spreads else 0.0

    if avg_voicing_spread < 7:
        voicing_type = "close"        # 밀집 보이싱
    elif avg_voicing_spread < 14:
        voicing_type = "semi_open"    # 반개방
    else:
        voicing_type = "open"         # 개방 보이싱

    # ── 5. 다이나믹 프로파일 ──
    vel_range = max(velocities) - min(velocities)
    vel_mean = float(np.mean(velocities))

    if vel_range < 30:
        dynamic_profile = "flat"       # 일정한 다이나믹
    elif vel_range < 60:
        dynamic_profile = "moderate"   # 보통 변화
    else:
        dynamic_profile = "expressive" # 극적인 다이나믹

    if vel_mean < 50:
        dynamic_level = "piano"
    elif vel_mean < 80:
        dynamic_level = "mezzo-forte"
    elif vel_mean < 105:
        dynamic_level = "forte"
    else:
        dynamic_level = "fortissimo"

    # ── 6. 템포 & BPM ──
    tempos = midi.get_tempo_changes()
    avg_tempo = float(np.mean(tempos[1])) if len(tempos[1]) > 0 else 120.0

    if avg_tempo < 60:
        tempo_category = "largo"
    elif avg_tempo < 80:
        tempo_category = "adagio"
    elif avg_tempo < 100:
        tempo_category = "andante"
    elif avg_tempo < 120:
        tempo_category = "moderato"
    elif avg_tempo < 140:
        tempo_category = "allegro"
    elif avg_tempo < 170:
        tempo_category = "vivace"
    else:
        tempo_category = "presto"

    return {
        # 리듬
        'rhythm_type': rhythm_type,
        'rhythm_regularity': round(rhythm_regularity, 3),
        'note_density_per_sec': round(note_density, 2),
        'avg_ioi': round(avg_ioi, 4),
        # 화성
        'harmony_type': harmony_type,
        'harmonic_brightness': round(harmonic_brightness, 3),
        'harmony_ratio': round(harmony_ratio, 3),
        'avg_polyphony': round(avg_polyphony, 2),
        'max_polyphony': max_polyphony,
        # 반주 구조
        'accompaniment_pattern': accompaniment_pattern,
        'arpeggio_ratio': round(arpeggio_ratio, 3),
        # 보이싱
        'voicing_type': voicing_type,
        'avg_voicing_spread': round(avg_voicing_spread, 1),
        'pitch_range': pitch_range,
        'register': register,
        # 다이나믹
        'dynamic_profile': dynamic_profile,
        'dynamic_level': dynamic_level,
        'velocity_range': vel_range,
        # 템포
        'tempo_bpm': round(avg_tempo, 1),
        'tempo_category': tempo_category,
    }


TRACK_EMBED_DIM = 128  # 트랙별 임베딩 차원

# MIDI program → track type 매핑
_PROGRAM_TO_TRACK = {
    # Piano (0-7)
    range(0, 8): "keys",
    # Chromatic Percussion (8-15)
    range(8, 16): "keys",
    # Organ (16-23)
    range(16, 24): "keys",
    # Guitar (24-31)
    range(24, 32): "guitar",
    # Bass (32-39)
    range(32, 40): "bass",
    # Strings (40-47)
    range(40, 48): "strings",
    # Ensemble (48-55)
    range(48, 56): "strings",
    # Brass (56-63)
    range(56, 64): "brass",
    # Reed (64-71)
    range(64, 72): "woodwind",
    # Pipe (72-79)
    range(72, 80): "woodwind",
    # Synth Lead (80-87)
    range(80, 88): "synth_lead",
    # Synth Pad (88-95)
    range(88, 96): "synth_pad",
    # Synth Effects (96-103)
    range(96, 104): "synth_fx",
    # Ethnic (104-111)
    range(104, 112): "ethnic",
    # Percussive (112-119)
    range(112, 120): "percussion",
    # Sound Effects (120-127)
    range(120, 128): "sfx",
}


def _classify_instrument(inst):
    """Classify a pretty_midi Instrument into a track type."""
    if inst.is_drum:
        return "drums"

    # Name-based detection
    name = (inst.name or "").lower()
    if "bass" in name:
        return "bass"
    if "drum" in name or "perc" in name:
        return "drums"
    if "string" in name or "violin" in name or "cello" in name or "viola" in name:
        return "strings"
    if "brass" in name or "trumpet" in name or "trombone" in name or "horn" in name:
        return "brass"
    if "flute" in name or "oboe" in name or "clarinet" in name or "sax" in name:
        return "woodwind"
    if "guitar" in name:
        return "guitar"
    if "pad" in name or "synth" in name:
        return "synth_pad"

    # Program-based detection
    for prog_range, track_type in _PROGRAM_TO_TRACK.items():
        if inst.program in prog_range:
            return track_type

    # Register-based fallback
    if inst.notes:
        avg_pitch = sum(n.pitch for n in inst.notes) / len(inst.notes)
        if avg_pitch < 48:
            return "bass"

    return "keys"


def _compute_track_embedding(notes_list):
    """Compute a 128-dim embedding for a list of note dicts.

    Same structure as global embedding but for a single track.
    """
    emb = np.zeros(TRACK_EMBED_DIM)
    if not notes_list:
        return emb.tolist()

    pitches = [n['pitch'] for n in notes_list]
    velocities = [n['velocity'] for n in notes_list]
    durations = [n['duration'] for n in notes_list]

    # [0:12] Pitch class histogram
    pc_hist = np.zeros(12)
    for p in pitches:
        pc_hist[p % 12] += 1
    if pc_hist.sum() > 0:
        pc_hist /= pc_hist.sum()
    emb[0:12] = pc_hist

    # [12:37] Interval histogram
    intervals = [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]
    iv_hist = np.zeros(25)
    for iv in intervals:
        idx = max(0, min(24, iv + 12))
        iv_hist[idx] += 1
    if iv_hist.sum() > 0:
        iv_hist /= iv_hist.sum()
    emb[12:37] = iv_hist

    # [37:45] Velocity histogram (8 bins)
    vel_hist = np.zeros(8)
    for v in velocities:
        vel_hist[min(7, v // 16)] += 1
    if vel_hist.sum() > 0:
        vel_hist /= vel_hist.sum()
    emb[37:45] = vel_hist

    # [45:55] Duration histogram (10 bins)
    dur_bins = [0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, float('inf')]
    dur_hist = np.zeros(10)
    for d in durations:
        for i in range(10):
            if dur_bins[i] <= d < dur_bins[i+1]:
                dur_hist[i] += 1
                break
    if dur_hist.sum() > 0:
        dur_hist /= dur_hist.sum()
    emb[45:55] = dur_hist

    # [55:63] Summary stats
    emb[55] = np.mean(pitches) / 127.0
    emb[56] = np.std(pitches) / 40.0
    emb[57] = np.mean(velocities) / 127.0
    emb[58] = np.std(velocities) / 40.0
    emb[59] = np.mean(durations) / 10.0
    emb[60] = np.std(durations) / 10.0
    emb[61] = len(notes_list) / 10000.0                # note count (normalized)
    total_dur = max(n['end'] for n in notes_list) - min(n['start'] for n in notes_list)
    emb[62] = total_dur / 600.0

    # [63:128] Top 65 pitch distribution
    pitch_hist = np.zeros(128)
    for p in pitches:
        pitch_hist[p] += 1
    if pitch_hist.sum() > 0:
        pitch_hist /= pitch_hist.sum()
    sorted_p = np.argsort(pitch_hist)[::-1][:65]
    for i, p in enumerate(sorted_p):
        emb[63 + i] = pitch_hist[p]

    return emb.tolist()


def _compute_drum_embedding(notes_list):
    """Compute a 128-dim embedding for drum tracks.

    Drums use GM pitch mapping, not melodic pitch.
    Focus on rhythm patterns and kit distribution.
    """
    emb = np.zeros(TRACK_EMBED_DIM)
    if not notes_list:
        return emb.tolist()

    pitches = [n['pitch'] for n in notes_list]
    velocities = [n['velocity'] for n in notes_list]
    durations = [n['duration'] for n in notes_list]
    starts = [n['start'] for n in notes_list]

    # [0:12] GM drum kit distribution (grouped)
    # 35-36:Kick, 38-40:Snare, 42-46:HiHat, 47-50:Tom, 49-57:Cymbal, other
    drum_groups = np.zeros(12)
    for p in pitches:
        if p in (35, 36):
            drum_groups[0] += 1   # kick
        elif p in (38, 39, 40):
            drum_groups[1] += 1   # snare
        elif p in (42, 44, 46):
            drum_groups[2] += 1   # hi-hat closed
        elif p == 46:
            drum_groups[3] += 1   # hi-hat open
        elif p in (47, 48, 50):
            drum_groups[4] += 1   # tom high
        elif p in (41, 43, 45):
            drum_groups[5] += 1   # tom low
        elif p in (49, 57):
            drum_groups[6] += 1   # crash
        elif p in (51, 53, 59):
            drum_groups[7] += 1   # ride
        elif p in (54, 56):
            drum_groups[8] += 1   # tambourine/cowbell
        elif p in (60, 61, 62, 63, 64):
            drum_groups[9] += 1   # bongo/conga
        elif p in (65, 66, 67, 68):
            drum_groups[10] += 1  # timbale/agogo
        else:
            drum_groups[11] += 1  # other
    if drum_groups.sum() > 0:
        drum_groups /= drum_groups.sum()
    emb[0:12] = drum_groups

    # [12:37] IOI (inter-onset interval) histogram — rhythm pattern
    ioi_hist = np.zeros(25)
    if len(starts) > 1:
        iois = [starts[i+1] - starts[i] for i in range(len(starts)-1) if starts[i+1] > starts[i]]
        # Quantize IOIs to 25 bins (0-2 seconds, 0.08s per bin)
        for ioi in iois:
            idx = min(24, int(ioi / 0.08))
            ioi_hist[idx] += 1
        if ioi_hist.sum() > 0:
            ioi_hist /= ioi_hist.sum()
    emb[12:37] = ioi_hist

    # [37:45] Velocity histogram
    vel_hist = np.zeros(8)
    for v in velocities:
        vel_hist[min(7, v // 16)] += 1
    if vel_hist.sum() > 0:
        vel_hist /= vel_hist.sum()
    emb[37:45] = vel_hist

    # [45:55] Beat position histogram (10 bins within a beat)
    # Estimate beat positions from note starts
    beat_pos_hist = np.zeros(10)
    avg_ioi = np.mean([starts[i+1] - starts[i] for i in range(len(starts)-1)
                       if starts[i+1] - starts[i] > 0.01]) if len(starts) > 1 else 0.5
    est_beat = max(0.1, avg_ioi * 2)  # rough beat estimate
    for s in starts:
        phase = (s % est_beat) / est_beat
        idx = min(9, int(phase * 10))
        beat_pos_hist[idx] += 1
    if beat_pos_hist.sum() > 0:
        beat_pos_hist /= beat_pos_hist.sum()
    emb[45:55] = beat_pos_hist

    # [55:63] Summary stats
    emb[55] = len(notes_list) / 10000.0
    total_dur = max(n['end'] for n in notes_list) - min(n['start'] for n in notes_list)
    emb[56] = total_dur / 600.0
    emb[57] = np.mean(velocities) / 127.0
    emb[58] = np.std(velocities) / 40.0
    # Note density (hits per second)
    emb[59] = min(1.0, (len(notes_list) / max(total_dur, 0.1)) / 20.0)
    # Unique pitches used (kit variety)
    emb[60] = len(set(pitches)) / 47.0  # GM has ~47 drum sounds
    # Kick/Snare ratio
    kicks = sum(1 for p in pitches if p in (35, 36))
    snares = sum(1 for p in pitches if p in (38, 39, 40))
    emb[61] = kicks / max(kicks + snares, 1)
    emb[62] = snares / max(kicks + snares, 1)

    # [63:128] — pad with zeros for drums (no melodic pitch distribution)

    return emb.tolist()


def analyze_tracks_separated(midi):
    """Analyze MIDI with per-track-type separated embeddings.

    Returns dict: {
        "track_types": ["keys", "bass", "drums", ...],
        "tracks": {
            "keys": {"embedding": [...], "stats": {...}, "note_count": N},
            "bass": {...},
            ...
        },
        "interaction": {"density_ratio": {...}, "register_overlap": {...}}
    }
    """
    # Group notes by track type
    track_notes = {}  # track_type → list of note dicts

    for inst in midi.instruments:
        track_type = _classify_instrument(inst)
        if track_type not in track_notes:
            track_notes[track_type] = []

        for note in inst.notes:
            track_notes[track_type].append({
                'pitch': note.pitch,
                'start': round(note.start, 4),
                'end': round(note.end, 4),
                'duration': round(note.end - note.start, 4),
                'velocity': note.velocity,
            })

    # Sort each track's notes by time
    for track_type in track_notes:
        track_notes[track_type].sort(key=lambda n: (n['start'], n['pitch']))

    # Compute per-track embeddings
    tracks_result = {}
    for track_type, notes in track_notes.items():
        if not notes:
            continue

        # Use drum-specific embedding for drums
        if track_type == "drums":
            emb = _compute_drum_embedding(notes)
        else:
            emb = _compute_track_embedding(notes)

        pitches = [n['pitch'] for n in notes]
        velocities = [n['velocity'] for n in notes]
        durations = [n['duration'] for n in notes]

        tracks_result[track_type] = {
            'embedding': emb,
            'note_count': len(notes),
            'stats': {
                'pitch_range': [int(min(pitches)), int(max(pitches))],
                'pitch_mean': round(float(np.mean(pitches)), 1),
                'velocity_mean': round(float(np.mean(velocities)), 1),
                'duration_mean': round(float(np.mean(durations)), 4),
                'total_duration': round(float(notes[-1]['end'] - notes[0]['start']), 2),
            },
        }

    # Interaction analysis (how tracks relate to each other)
    interaction = {}
    track_types_list = list(tracks_result.keys())

    if len(track_types_list) >= 2:
        # Density ratio: note count ratio between tracks
        total_notes = sum(t['note_count'] for t in tracks_result.values())
        interaction['density_ratio'] = {
            tt: round(tracks_result[tt]['note_count'] / max(total_notes, 1), 3)
            for tt in track_types_list
        }

        # Register overlap between melodic tracks
        melodic_tracks = {tt: tracks_result[tt] for tt in track_types_list
                          if tt not in ('drums', 'percussion', 'sfx')}
        if len(melodic_tracks) >= 2:
            overlap = {}
            mt_list = list(melodic_tracks.keys())
            for i in range(len(mt_list)):
                for j in range(i+1, len(mt_list)):
                    t1, t2 = mt_list[i], mt_list[j]
                    r1 = melodic_tracks[t1]['stats']['pitch_range']
                    r2 = melodic_tracks[t2]['stats']['pitch_range']
                    # Overlap = intersection / union of pitch ranges
                    lo = max(r1[0], r2[0])
                    hi = min(r1[1], r2[1])
                    union = max(r1[1], r2[1]) - min(r1[0], r2[0])
                    ov = max(0, hi - lo) / max(union, 1)
                    overlap[f"{t1}_x_{t2}"] = round(ov, 3)
            interaction['register_overlap'] = overlap

    return {
        'track_types': track_types_list,
        'tracks': tracks_result,
        'interaction': interaction,
    }


def analyze_midi(filepath):
    """단일 MIDI 파일 분석 — 모든 노트 데이터 보존 + 작곡가 태그"""
    midi = pretty_midi.PrettyMIDI(filepath)
    filename = os.path.basename(filepath)

    all_notes = []
    for inst in midi.instruments:
        for note in inst.notes:
            all_notes.append({
                'pitch': note.pitch,
                'start': round(note.start, 4),
                'end': round(note.end, 4),
                'duration': round(note.end - note.start, 4),
                'velocity': note.velocity,
                'instrument': inst.program,
                'instrument_name': pretty_midi.program_to_instrument_name(inst.program),
                'is_drum': inst.is_drum
            })

    all_notes.sort(key=lambda x: x['start'])

    # 통계 계산
    if all_notes:
        pitches = [n['pitch'] for n in all_notes]
        velocities = [n['velocity'] for n in all_notes]
        durations = [n['duration'] for n in all_notes]

        # 피치 히스토그램 (128 MIDI pitches)
        pitch_hist = np.zeros(128)
        for p in pitches:
            pitch_hist[p] += 1
        if pitch_hist.sum() > 0:
            pitch_hist = pitch_hist / pitch_hist.sum()

        # 피치 클래스 히스토그램 (12 semitones)
        pitch_class_hist = np.zeros(12)
        for p in pitches:
            pitch_class_hist[p % 12] += 1
        if pitch_class_hist.sum() > 0:
            pitch_class_hist = pitch_class_hist / pitch_class_hist.sum()

        # 인터벌 히스토그램
        intervals = [pitches[i+1] - pitches[i] for i in range(len(pitches)-1)]
        interval_hist = np.zeros(25)  # -12 ~ +12
        for iv in intervals:
            idx = max(0, min(24, iv + 12))
            interval_hist[idx] += 1
        if interval_hist.sum() > 0:
            interval_hist = interval_hist / interval_hist.sum()

        # 벨로시티 히스토그램 (8 bins)
        vel_hist = np.zeros(8)
        for v in velocities:
            vel_hist[min(7, v // 16)] += 1
        if vel_hist.sum() > 0:
            vel_hist = vel_hist / vel_hist.sum()

        # 듀레이션 히스토그램 (10 bins: 0-0.1, 0.1-0.25, 0.25-0.5, 0.5-1, 1-2, 2-4, 4-8, 8-16, 16-32, 32+)
        dur_bins = [0, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0, float('inf')]
        dur_hist = np.zeros(10)
        for d in durations:
            for i in range(10):
                if dur_bins[i] <= d < dur_bins[i+1]:
                    dur_hist[i] += 1
                    break
        if dur_hist.sum() > 0:
            dur_hist = dur_hist / dur_hist.sum()

        # 추정 조성
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        estimated_key_idx = int(np.argmax(pitch_class_hist))
        estimated_key = key_names[estimated_key_idx]

        # 템포
        tempos = midi.get_tempo_changes()
        avg_tempo = float(np.mean(tempos[1])) if len(tempos[1]) > 0 else 120.0

        stats = {
            'filename': filename,
            'total_notes': len(all_notes),
            'total_duration_sec': round(midi.get_end_time(), 2),
            'avg_tempo': round(avg_tempo, 1),
            'pitch_range': [int(min(pitches)), int(max(pitches))],
            'pitch_mean': round(float(np.mean(pitches)), 1),
            'pitch_std': round(float(np.std(pitches)), 1),
            'velocity_range': [int(min(velocities)), int(max(velocities))],
            'velocity_mean': round(float(np.mean(velocities)), 1),
            'velocity_std': round(float(np.std(velocities)), 1),
            'duration_mean': round(float(np.mean(durations)), 4),
            'duration_std': round(float(np.std(durations)), 4),
            'estimated_key': estimated_key,
            'num_instruments': len(midi.instruments),
            'time_signatures': [f"{ts.numerator}/{ts.denominator}" for ts in midi.time_signature_changes],
        }
    else:
        pitch_hist = np.zeros(128)
        pitch_class_hist = np.zeros(12)
        interval_hist = np.zeros(25)
        vel_hist = np.zeros(8)
        dur_hist = np.zeros(10)
        stats = {
            'filename': filename,
            'total_notes': 0,
            'total_duration_sec': round(midi.get_end_time(), 2),
            'error': 'no notes found'
        }

    # 임베딩 벡터 생성 (128차원)
    # [pitch_hist_12 | interval_hist_25 | vel_hist_8 | dur_hist_10 | stats_73]
    embedding = np.zeros(EMBED_DIM)
    embedding[0:12] = pitch_class_hist
    embedding[12:37] = interval_hist
    embedding[37:45] = vel_hist
    embedding[45:55] = dur_hist
    if all_notes:
        embedding[55] = stats['pitch_mean'] / 127.0
        embedding[56] = stats['pitch_std'] / 40.0
        embedding[57] = stats['velocity_mean'] / 127.0
        embedding[58] = stats['velocity_std'] / 40.0
        embedding[59] = stats['duration_mean'] / 10.0
        embedding[60] = stats['duration_std'] / 10.0
        embedding[61] = stats['avg_tempo'] / 200.0
        embedding[62] = stats['total_duration_sec'] / 600.0
        embedding[63] = stats['total_notes'] / 10000.0
        # 나머지는 pitch histogram 상위 65개
        sorted_pitches = np.argsort(pitch_hist)[::-1][:65]
        for i, p in enumerate(sorted_pitches):
            embedding[63 + i] = pitch_hist[p]

    # 작곡가 관점 태그 추출
    composer_tags = analyze_composer_tags(all_notes, midi)

    # ── 트랙별 분리 임베딩 ──
    track_embeddings = analyze_tracks_separated(midi)

    return {
        'stats': stats,
        'composer_tags': composer_tags,
        'notes': all_notes,
        'embedding': embedding.tolist(),
        'track_embeddings': track_embeddings,
        'pitch_histogram': pitch_hist.tolist(),
        'pitch_class_histogram': pitch_class_hist.tolist(),
        'interval_histogram': interval_hist.tolist(),
        'velocity_histogram': vel_hist.tolist(),
        'duration_histogram': dur_hist.tolist(),
    }


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    midi_files = sorted(glob.glob(os.path.join(MIDI_DIR, '**', '*.midi'), recursive=True) +
                        glob.glob(os.path.join(MIDI_DIR, '**', '*.mid'), recursive=True))

    print(f"Found {len(midi_files)} MIDI files")

    all_stats = []
    all_embeddings = []
    failed = []
    total_notes = 0

    for i, filepath in enumerate(midi_files):
        filename = os.path.basename(filepath)
        try:
            result = analyze_midi(filepath)

            # 개별 파일 저장 (노트 데이터 포함 — 누락 없음)
            # 카테고리 폴더 구조 유지 (e.g. individual/recital/xxx.json)
            rel_path = os.path.relpath(filepath, MIDI_DIR)
            individual_path = os.path.join(OUTPUT_DIR, 'individual',
                                           rel_path.replace('.midi', '.json').replace('.mid', '.json'))
            os.makedirs(os.path.dirname(individual_path), exist_ok=True)
            with open(individual_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, cls=NumpyEncoder)

            all_stats.append({**result['stats'], 'composer_tags': result['composer_tags']})
            all_embeddings.append(result['embedding'])
            total_notes += result['stats']['total_notes']

            tags = result['composer_tags']
            print(f"  [{i+1:3d}/{len(midi_files)}] {filename} — "
                  f"{result['stats']['total_notes']} notes, "
                  f"{result['stats']['total_duration_sec']}s | "
                  f"{tags.get('rhythm_type','?')} / {tags.get('harmony_type','?')} / "
                  f"{tags.get('accompaniment_pattern','?')} / {tags.get('tempo_category','?')}")

        except Exception as e:
            failed.append({'file': filename, 'error': str(e)})
            print(f"  [{i+1:3d}/{len(midi_files)}] FAILED: {filename} — {e}")

    # 전체 임베딩 매트릭스 저장 (numpy)
    embedding_matrix = np.array(all_embeddings)
    np.save(os.path.join(OUTPUT_DIR, 'embedding_matrix.npy'), embedding_matrix)

    # 전체 통계 요약 저장
    summary = {
        'total_files': len(midi_files),
        'processed': len(all_stats),
        'failed': len(failed),
        'failed_files': failed,
        'total_notes': total_notes,
        'embedding_shape': list(embedding_matrix.shape),
        'embedding_dim': EMBED_DIM,
        'stats': all_stats,
    }

    with open(os.path.join(OUTPUT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, cls=NumpyEncoder)

    # 임베딩 메타데이터 (파일명 ↔ 인덱스 매핑)
    meta = {
        'files': [s['filename'] for s in all_stats],
        'embedding_file': 'embedding_matrix.npy',
        'embedding_dim': EMBED_DIM,
        'total_files': len(all_stats),
    }
    with open(os.path.join(OUTPUT_DIR, 'metadata.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Complete: {len(all_stats)}/{len(midi_files)} files processed")
    print(f"Total notes: {total_notes:,}")
    print(f"Embedding matrix: {embedding_matrix.shape}")
    print(f"Failed: {len(failed)}")
    if failed:
        for f_info in failed:
            print(f"  - {f_info['file']}: {f_info['error']}")
    print(f"Output: {OUTPUT_DIR}")


if __name__ == '__main__':
    main()
