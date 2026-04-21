"""MIDI → 오디오 렌더링 — SF2 기반, pretty_midi.fluidsynth 가능 시 사용.

대상: 3 MIDI
    audio_to_midi_output/Lemon/Lemon_refined.mid      (원곡 전사)
    output/Lemon/Lemon_variation_conservative.mid      (보수적 변주)
    output/Lemon/Lemon_variation_creative.mid          (창의적 변주)

출력: output/Lemon/*.wav (44100 Hz 16-bit)

Fallback: fluidsynth 실패 시 refine.py 의 sine 합성 재사용.
"""
from __future__ import annotations

import sys
import time
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


def _render(midi_path: Path, out_wav: Path, sf2: Path, sr: int = 44100):
    import pretty_midi
    import numpy as np
    import soundfile as sf

    pm = pretty_midi.PrettyMIDI(str(midi_path))
    t0 = time.time()

    # pretty_midi.synthesize() — numpy 만으로 per-note sinusoidal synth (all tracks).
    # fluidsynth 대비 음색은 단순하지만 multi-track mixing 은 지원, SF2/dll 불필요.
    audio = None
    try:
        audio = pm.synthesize(fs=sr)
        print(f"    synthesize OK: {len(audio)/sr:.1f}s audio")
    except Exception as e:
        print(f"    synthesize fail ({type(e).__name__}): {e}")
        from refine import _synth_sine
        audio = _synth_sine(pm, sr=sr)
        print(f"    sine fallback: {len(audio)/sr:.1f}s audio")

    # Normalize + write
    peak = float(np.max(np.abs(audio)) + 1e-9)
    if peak > 0.95:
        audio = audio * (0.95 / peak)
    sf.write(str(out_wav), audio.astype(np.float32), sr, subtype="PCM_16")
    print(f"    → {out_wav}  ({(out_wav.stat().st_size)/1e6:.1f} MB, "
          f"{time.time()-t0:.1f}s)")


def main():
    sf2 = REPO_ROOT / "checkpoints" / "soundfont" / "GeneralUser_GS.sf2"
    if not sf2.exists():
        print(f"[WARN] SF2 없음: {sf2}  — sine fallback 사용")

    targets = [
        (REPO_ROOT / "audio_to_midi_output" / "Lemon" / "Lemon_refined.mid",
         REPO_ROOT / "output" / "Lemon" / "Lemon_refined.wav",
         "원곡 전사 (Tier 1 + refine)"),
        (REPO_ROOT / "output" / "Lemon" / "Lemon_variation_conservative.mid",
         REPO_ROOT / "output" / "Lemon" / "Lemon_variation_conservative.wav",
         "보수적 변주 (T=0.7)"),
        (REPO_ROOT / "output" / "Lemon" / "Lemon_variation_creative.mid",
         REPO_ROOT / "output" / "Lemon" / "Lemon_variation_creative.wav",
         "창의적 변주 (T=1.05)"),
    ]

    print("=" * 60)
    print("  MIDI → Audio 렌더링")
    print("=" * 60)

    for i, (mid, wav, label) in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {label}")
        print(f"    src: {mid.name}")
        if not mid.exists():
            print(f"    [SKIP] 파일 없음")
            continue
        wav.parent.mkdir(parents=True, exist_ok=True)
        _render(mid, wav, sf2)


if __name__ == "__main__":
    main()
