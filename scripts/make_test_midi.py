"""테스트용 합성 MIDI 생성기 (Sprint 46 JJJ1).

회귀 테스트 / 데모 / CI 에서 외부 .mid 파일 의존 없이 돌릴 수 있도록
결정성 있는 fixture 를 생성. 4 종 preset:

    simple_chord — C-F-G-C 4/4 화성 진행 (8 bars)
    melody       — C 장조 simple melody (16 bars)
    arp          — Am7-F-C-G arpeggio 16th (8 bars)
    drum         — 4/4 rock 드럼 패턴 (8 bars)

사용:
    python scripts/make_test_midi.py --preset melody --out fixture.mid
    python scripts/make_test_midi.py --all --out_dir ./fixtures/   # 4종 모두
    python scripts/make_test_midi.py --preset simple_chord --tempo 140 --seed 7

의존: pretty_midi (이미 설치).
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


CHORDS_I_IV_V_I = [
    [60, 64, 67],        # C major
    [65, 69, 72],        # F major
    [67, 71, 74],        # G major
    [60, 64, 67],        # C major
]

C_MAJOR_SCALE = [60, 62, 64, 65, 67, 69, 71, 72]  # C-D-E-F-G-A-B-C

AM7_ARP = [57, 60, 64, 67]  # A-C-E-G
F_ARP = [53, 57, 60, 65]
C_ARP = [48, 52, 55, 60]
G_ARP = [55, 59, 62, 67]
ARP_SEQUENCE = [AM7_ARP, F_ARP, C_ARP, G_ARP]

# GM drums (channel 9 기본)
KICK, SNARE, HH_CLOSED, HH_OPEN = 36, 38, 42, 46


def _beat_to_sec(beat: float, tempo: float) -> float:
    return beat * 60.0 / tempo


def make_simple_chord(tempo: float, seed: int):
    import pretty_midi
    rng = random.Random(seed)
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, name="Piano")
    # 8 bars, 1 chord per bar
    for bar in range(8):
        chord = CHORDS_I_IV_V_I[bar % 4]
        bar_start = _beat_to_sec(bar * 4, tempo)
        bar_end = _beat_to_sec((bar + 1) * 4, tempo)
        for pitch in chord:
            inst.notes.append(pretty_midi.Note(
                velocity=70 + rng.randint(-5, 5),
                pitch=pitch, start=bar_start, end=bar_end - 0.02,
            ))
    pm.instruments.append(inst)
    return pm


def make_melody(tempo: float, seed: int):
    import pretty_midi
    rng = random.Random(seed)
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, name="Melody")
    # 16 bars, 2 notes per beat (eighth note)
    for bar in range(16):
        for beat in range(4):
            for half in range(2):
                step = bar * 8 + beat * 2 + half
                pitch = C_MAJOR_SCALE[(step + rng.randint(0, 7)) % 8]
                start = _beat_to_sec(bar * 4 + beat + half * 0.5, tempo)
                end = start + _beat_to_sec(0.45, tempo)
                inst.notes.append(pretty_midi.Note(
                    velocity=80 + rng.randint(-8, 8),
                    pitch=pitch, start=start, end=end,
                ))
    pm.instruments.append(inst)
    return pm


def make_arp(tempo: float, seed: int):
    import pretty_midi
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, name="Arp")
    rng = random.Random(seed)
    # 8 bars, 16 sixteenth notes per bar
    for bar in range(8):
        chord = ARP_SEQUENCE[bar % 4]
        for step in range(16):
            pitch = chord[step % 4] + 12 * (step // 4 % 2)  # 옥타브 교차
            start = _beat_to_sec(bar * 4 + step * 0.25, tempo)
            end = start + _beat_to_sec(0.22, tempo)
            inst.notes.append(pretty_midi.Note(
                velocity=65 + rng.randint(-5, 5),
                pitch=pitch, start=start, end=end,
            ))
    pm.instruments.append(inst)
    return pm


def make_drum(tempo: float, seed: int):
    import pretty_midi
    rng = random.Random(seed)
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=0, is_drum=True, name="Drums")
    # 8 bars 4/4, rock pattern
    for bar in range(8):
        for beat in range(4):
            t = _beat_to_sec(bar * 4 + beat, tempo)
            if beat % 2 == 0:
                inst.notes.append(pretty_midi.Note(100, KICK, t, t + 0.1))
            else:
                inst.notes.append(pretty_midi.Note(90, SNARE, t, t + 0.1))
            # 8th HH
            inst.notes.append(pretty_midi.Note(70 + rng.randint(-5, 5),
                                               HH_CLOSED, t, t + 0.05))
            t2 = t + _beat_to_sec(0.5, tempo)
            inst.notes.append(pretty_midi.Note(60 + rng.randint(-5, 5),
                                               HH_CLOSED, t2, t2 + 0.05))
    pm.instruments.append(inst)
    return pm


PRESETS = {
    "simple_chord": make_simple_chord,
    "melody": make_melody,
    "arp": make_arp,
    "drum": make_drum,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--preset", choices=list(PRESETS.keys()), default="simple_chord")
    ap.add_argument("--tempo", type=float, default=120.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="fixture.mid")
    ap.add_argument("--all", action="store_true",
                    help="4 preset 모두 생성 (--out_dir 로)")
    ap.add_argument("--out_dir", default="./fixtures",
                    help="--all 사용 시 저장 디렉토리")
    args = ap.parse_args()

    def _save(pm, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        pm.write(str(path))
        n = sum(len(i.notes) for i in pm.instruments)
        print(f"  [OK] {path}  notes={n}  dur={pm.get_end_time():.1f}s")

    if args.all:
        out_dir = Path(args.out_dir)
        for name, fn in PRESETS.items():
            pm = fn(args.tempo, args.seed)
            _save(pm, out_dir / f"{name}.mid")
    else:
        fn = PRESETS[args.preset]
        pm = fn(args.tempo, args.seed)
        _save(pm, Path(args.out))


if __name__ == "__main__":
    main()
