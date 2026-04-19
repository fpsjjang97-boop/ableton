"""Audio2MIDI source-filter refine 스모크 테스트 (Sprint 43 GGG6 후반).

합성 오디오(사인파) + 의도적 "유령 노트" 를 포함한 MIDI → refine 이
유령을 제거하거나 diff 를 줄이는지 검증. fluidsynth 없어도 sine fallback
으로 파이프라인이 깨지지 않아야 한다.

검사:
    1. refine_midi 호출 시 예외 없이 report 반환
    2. fluidsynth_used 필드 존재 (True/False 상관없이 pipeline 동작)
    3. 유령 노트(velocity 낮은 + hot frame 내) 는 제거 또는 유지, 다만 전체
       노트 수 before/after 가 합리적 (before >= after)
    4. final_diff_l1 이 initial 보다 작거나 같음 (monotonic improvement)

사용:
    python scripts/regress_audio2midi_refine.py
종료 0 = PASS.
"""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _write_sine_wav(path: Path, duration: float = 4.0, sr: int = 22050,
                    freq: float = 440.0):
    n = int(duration * sr)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(n):
            v = int(0.3 * 32767 * math.sin(2 * math.pi * freq * i / sr))
            w.writeframes(struct.pack("<h", v))


def _build_midi_with_ghost(path: Path):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0)
    # Real note — A4 (440Hz, pitch=69), 80 velocity, 2s
    inst.notes.append(pretty_midi.Note(velocity=80, pitch=69, start=0.0, end=2.0))
    # Ghost notes — very low velocity, not in original audio
    inst.notes.append(pretty_midi.Note(velocity=20, pitch=50, start=0.5, end=1.0))
    inst.notes.append(pretty_midi.Note(velocity=25, pitch=75, start=1.2, end=1.8))
    inst.notes.append(pretty_midi.Note(velocity=15, pitch=40, start=2.5, end=3.5))
    pm.instruments.append(inst)
    pm.write(str(path))


def main():
    import argparse
    argparse.ArgumentParser(
        description="Audio2MIDI source-filter refine 회귀 스모크. 인자 없음."
    ).parse_args()

    from refine import refine_midi

    print("=" * 60)
    print("  Audio2MIDI refine 스모크 (Sprint 43 GGG6)")
    print("=" * 60)

    tmp = Path(tempfile.mkdtemp(prefix="refine_smoke_"))
    try:
        audio = tmp / "sine.wav"
        midi_in = tmp / "input.mid"
        midi_out = tmp / "refined.mid"

        _write_sine_wav(audio, duration=4.0, freq=440.0)
        _build_midi_with_ghost(midi_in)

        fails = 0
        try:
            report = refine_midi(audio, midi_in, midi_out, max_iters=2)
        except Exception as e:
            print(f"  [FAIL] refine_midi 예외: {type(e).__name__}: {e}")
            return 1

        rd = report.to_dict()
        print(f"  report: {rd}")

        # 1. 필드 체크
        for k in ("iters", "initial_diff_l1", "final_diff_l1",
                  "fluidsynth_used", "notes_before", "notes_after"):
            if k not in rd:
                print(f"  [FAIL] field 누락: {k}")
                fails += 1
        if fails == 0:
            print(f"  [OK] 필수 필드 존재 ({len(rd)} keys)")

        # 2. monotonic diff
        if rd["final_diff_l1"] <= rd["initial_diff_l1"] * 1.01:
            print(f"  [OK] final_diff ({rd['final_diff_l1']:.2f}) "
                  f"<= initial_diff ({rd['initial_diff_l1']:.2f}) + ε")
        else:
            print(f"  [FAIL] diff 악화: {rd['initial_diff_l1']:.2f} → {rd['final_diff_l1']:.2f}")
            fails += 1

        # 3. note 수 불변량 (Sprint 44 HHH1 이후: before - removed + added == after)
        expected = rd["notes_before"] - rd["notes_removed"] + rd["notes_added"]
        if rd["notes_after"] == expected:
            print(f"  [OK] note 회계: {rd['notes_before']} - {rd['notes_removed']} "
                  f"+ {rd['notes_added']} = {rd['notes_after']}")
        else:
            print(f"  [FAIL] 회계 불일치: expected {expected}, got {rd['notes_after']}")
            fails += 1

        # 4. 출력 파일 존재 + 읽기 가능
        if midi_out.exists():
            try:
                import pretty_midi
                pm = pretty_midi.PrettyMIDI(str(midi_out))
                n = sum(len(i.notes) for i in pm.instruments)
                print(f"  [OK] refined MIDI 재파싱: {n} notes")
            except Exception as e:
                print(f"  [FAIL] refined MIDI 파싱: {e}")
                fails += 1
        else:
            print(f"  [FAIL] refined MIDI 미생성")
            fails += 1

    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("=" * 60)
    if fails == 0:
        print("  ALL PASS")
    else:
        print(f"  FAIL {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
