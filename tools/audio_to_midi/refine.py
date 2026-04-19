"""Source-filter 반복 정제 — Audio2MIDI Tier 2 진입 (Sprint 43 GGG4).

설계: docs/business/16_sprint_43_design.md §B.2

파이프라인:
    1. synth(mid) — 현재 전사된 MIDI 를 간이 합성 (fluidsynth OR 사인파)
    2. mel_spec(original) vs mel_spec(synth) — L1 프레임별 diff
    3. hot frames = 상위 5% diff
    4. hot frame 내 노트 조정:
         - 원본 노트 없음 → 미검출 → basic_pitch threshold 낮춰 재채보
         - 원본 노트 있음 → threshold 높여 유령 제거
    5. 최대 2회 반복 수렴

의존:
    - librosa, numpy, pretty_midi — 필수 (이미 설치)
    - basic_pitch — 재채보용 (옵션: 없으면 librosa pyin fallback)
    - pyfluidsynth — 합성 (옵션: 없으면 사인파 대체)

API:
    refine_midi(audio_path, midi_path, output_path, max_iters=2)
      → 반환: (refined_path, diff_report)
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


@dataclass
class RefineReport:
    input_audio: str
    input_midi: str
    output_midi: str
    iters: int = 0
    initial_diff_l1: float = 0.0
    final_diff_l1: float = 0.0
    hot_frames_count: list[int] = field(default_factory=list)
    fluidsynth_used: bool = False
    notes_added: int = 0
    notes_removed: int = 0
    notes: dict = field(default_factory=dict)   # {before, after}

    def to_dict(self) -> dict:
        return {
            "input_audio": self.input_audio,
            "input_midi": self.input_midi,
            "output_midi": self.output_midi,
            "iters": self.iters,
            "initial_diff_l1": self.initial_diff_l1,
            "final_diff_l1": self.final_diff_l1,
            "hot_frames_per_iter": self.hot_frames_count,
            "fluidsynth_used": self.fluidsynth_used,
            "notes_before": self.notes.get("before"),
            "notes_after": self.notes.get("after"),
            "notes_added": self.notes_added,
            "notes_removed": self.notes_removed,
        }


def _try_synth_fluidsynth(pm, sr: int):
    """pretty_midi.fluidsynth — libfluidsynth 필요."""
    try:
        import pretty_midi  # noqa
        return pm.fluidsynth(fs=sr), True
    except (ImportError, OSError, FileNotFoundError, Exception) as e:
        # FluidSynth 바인딩 없으면 PrettyMIDI.fluidsynth() 는 raise 한다.
        return None, False


def _synth_sine(pm, sr: int):
    """fluidsynth 없을 때 fallback — 각 노트를 사인파로 합성.

    정확한 스펙트럼 비교는 아니지만 onset/offset 타이밍 추정에는 사용 가능.
    드럼 / 넓은 대역 악기는 이 fallback 으로는 diff 품질 낮음.
    """
    import numpy as np
    total_dur = max(pm.get_end_time(), 0.5)
    t = np.arange(int(total_dur * sr)) / sr
    out = np.zeros_like(t, dtype=np.float32)
    for inst in pm.instruments:
        for note in inst.notes:
            freq = 440.0 * (2 ** ((note.pitch - 69) / 12.0))
            i0 = int(note.start * sr)
            i1 = int(note.end * sr)
            if i1 <= i0 or i0 >= len(t):
                continue
            i1 = min(i1, len(t))
            seg = t[i0:i1] - t[i0]
            # ADSR 간이: 10ms 페이드 인/아웃
            env = np.ones_like(seg)
            fade = int(0.01 * sr)
            if len(env) > 2 * fade:
                env[:fade] = np.linspace(0, 1, fade)
                env[-fade:] = np.linspace(1, 0, fade)
            amp = (note.velocity / 127.0) * 0.2
            out[i0:i1] += amp * env * np.sin(2 * np.pi * freq * seg)
    # Clip
    out = np.clip(out, -1.0, 1.0).astype(np.float32)
    return out


def _mel_diff_l1(y1, y2, sr: int = 22050, n_mels: int = 64):
    """L1 mel-spectrogram diff per frame. 반환: (diff per frame, avg)."""
    import librosa
    import numpy as np
    # 두 신호 길이 맞춤
    n = min(len(y1), len(y2))
    if n == 0:
        return np.array([]), 0.0
    y1 = y1[:n]
    y2 = y2[:n]
    S1 = librosa.feature.melspectrogram(y=y1, sr=sr, n_mels=n_mels)
    S2 = librosa.feature.melspectrogram(y=y2, sr=sr, n_mels=n_mels)
    # log-mel 로 gain 차이 완화
    L1 = librosa.power_to_db(S1 + 1e-9)
    L2 = librosa.power_to_db(S2 + 1e-9)
    per_frame = np.mean(np.abs(L1 - L2), axis=0)
    return per_frame, float(per_frame.mean())


def _hot_frame_intervals(diff_per_frame, sr: int, hop: int, top_frac: float = 0.05):
    """Top N% diff 프레임을 연속 구간으로 그룹화 → [(t_start, t_end), ...]."""
    import numpy as np
    if len(diff_per_frame) == 0:
        return []
    threshold = np.quantile(diff_per_frame, 1.0 - top_frac)
    mask = diff_per_frame >= threshold
    intervals = []
    in_seg = False
    seg_start = 0
    for i, m in enumerate(mask):
        if m and not in_seg:
            seg_start = i
            in_seg = True
        elif not m and in_seg:
            t0 = seg_start * hop / sr
            t1 = i * hop / sr
            intervals.append((t0, t1))
            in_seg = False
    if in_seg:
        t0 = seg_start * hop / sr
        t1 = len(mask) * hop / sr
        intervals.append((t0, t1))
    return intervals


def _remove_ghost_notes(pm, intervals, min_velocity: int = 30):
    """Hot interval 내 원본 노트가 존재하면서 velocity 낮은(<30) 것을 유령으로 제거.

    반환: 제거된 노트 수.
    """
    removed = 0
    for inst in pm.instruments:
        kept = []
        for n in inst.notes:
            in_hot = any(t0 <= n.start < t1 or t0 < n.end <= t1
                         for t0, t1 in intervals)
            if in_hot and n.velocity < min_velocity:
                removed += 1
                continue
            kept.append(n)
        inst.notes = kept
    return removed


def _fill_missed_notes(pm, audio_path, intervals, sr: int = 22050):
    """Sprint 44 HHH1 — hot frame 내 원본 노트가 "없거나 매우 적은" 구간을
    basic_pitch (낮은 threshold) 로 재채보해 놓친 노트를 채운다.

    basic_pitch 없거나 오디오 crop 이 실패하면 silent skip.
    반환: 추가된 노트 수.
    """
    try:
        from basic_pitch.inference import predict as bp_predict
    except ImportError:
        return 0

    import numpy as np
    import pretty_midi
    import librosa

    # 후보 구간: hot interval 중 기존 노트가 0개인 (= 완전 미검출) 구간
    def _notes_in(t0: float, t1: float) -> int:
        return sum(
            1
            for inst in pm.instruments
            for n in inst.notes
            if (t0 <= n.start < t1) or (t0 < n.end <= t1)
        )

    missed = [(t0, t1) for t0, t1 in intervals
              if (t1 - t0) >= 0.2 and _notes_in(t0, t1) == 0]
    if not missed:
        return 0

    # 짧은 구간만 한 번에 묶어 재채보 — 전체 오디오 재채보는 비용 큼
    try:
        y, _ = librosa.load(str(audio_path), sr=sr, mono=True)
    except Exception:
        return 0

    added = 0
    for t0, t1 in missed[:10]:  # 과도한 반복 방지 — 최대 10 구간
        i0, i1 = int(t0 * sr), min(int(t1 * sr), len(y))
        if i1 - i0 < int(0.2 * sr):
            continue
        import tempfile
        import soundfile as sf  # librosa 의존성에 포함
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            wav_path = tf.name
        try:
            sf.write(wav_path, y[i0:i1], sr)
            _, pm_new, _ = bp_predict(wav_path, onset_threshold=0.3)
            for inst in pm_new.instruments:
                for n in inst.notes:
                    # 구간 시작 기준으로 시프트
                    shifted = pretty_midi.Note(
                        velocity=max(1, min(127, int(n.velocity))),
                        pitch=n.pitch,
                        start=t0 + n.start,
                        end=t0 + n.end,
                    )
                    if not pm.instruments:
                        pm.instruments.append(pretty_midi.Instrument(program=0))
                    pm.instruments[0].notes.append(shifted)
                    added += 1
        except Exception:
            continue
        finally:
            try:
                Path(wav_path).unlink(missing_ok=True)
            except Exception:
                pass

    return added


def refine_midi(
    audio_path: str | Path,
    midi_path: str | Path,
    output_path: str | Path,
    max_iters: int = 2,
    sr: int = 22050,
    hop_length: int = 512,
) -> RefineReport:
    """메인 진입점 — Tier 2 source-filter 반복 정제 1~2회 수행.

    실제 재채보(basic_pitch 재실행)는 과도한 비용이라 Sprint 43 GGG4 범위에서는
    **유령 노트 제거** 만 활성화. 재채보 경로는 Sprint 44+ 에 추가 (GGG4.2).
    """
    import numpy as np
    import librosa
    import pretty_midi

    audio_path = Path(audio_path)
    midi_path = Path(midi_path)
    output_path = Path(output_path)

    y_orig, _ = librosa.load(str(audio_path), sr=sr, mono=True)
    pm = pretty_midi.PrettyMIDI(str(midi_path))

    report = RefineReport(
        input_audio=str(audio_path),
        input_midi=str(midi_path),
        output_midi=str(output_path),
    )
    notes_before = sum(len(i.notes) for i in pm.instruments)
    report.notes = {"before": notes_before}

    for it in range(max_iters):
        # Synth 현재 MIDI
        y_synth, used_fs = _try_synth_fluidsynth(pm, sr)
        if not used_fs:
            y_synth = _synth_sine(pm, sr)
            report.fluidsynth_used = False
        else:
            report.fluidsynth_used = True

        diff_frames, avg = _mel_diff_l1(y_orig, y_synth, sr=sr)
        if it == 0:
            report.initial_diff_l1 = avg

        intervals = _hot_frame_intervals(diff_frames, sr, hop_length, top_frac=0.05)
        report.hot_frames_count.append(len(intervals))

        if not intervals:
            break

        removed = _remove_ghost_notes(pm, intervals)
        report.notes_removed += removed

        # Sprint 44 HHH1 — 미검출 영역 재채보 (basic_pitch 있을 때만)
        added = _fill_missed_notes(pm, audio_path, intervals, sr=sr)
        report.notes_added += added

        if removed == 0 and added == 0:
            # 더 이상 변경 없음 — 조기 수렴
            break

        report.iters = it + 1

    # 최종 diff 재측정
    y_synth_final, _ = _try_synth_fluidsynth(pm, sr)
    if y_synth_final is None:
        y_synth_final = _synth_sine(pm, sr)
    _, final_avg = _mel_diff_l1(y_orig, y_synth_final, sr=sr)
    report.final_diff_l1 = final_avg

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pm.write(str(output_path))
    report.notes["after"] = sum(len(i.notes) for i in pm.instruments)

    return report


def main():
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Audio2MIDI source-filter 반복 정제")
    ap.add_argument("--audio", required=True, help="원본 오디오 (wav/mp3)")
    ap.add_argument("--midi", required=True, help="전사된 MIDI (Tier 1 결과)")
    ap.add_argument("--out", required=True, help="정제된 MIDI 저장 경로")
    ap.add_argument("--iters", type=int, default=2)
    args = ap.parse_args()

    report = refine_midi(args.audio, args.midi, args.out, max_iters=args.iters)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
