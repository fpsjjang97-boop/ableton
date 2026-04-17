"""Download / install Tier 1 Audio2MIDI backends.

Sprint 37.4 재작성. 원래 Magenta O&F / ADTOF GitHub release URL 은
404 였고 (자주 바뀜), Magenta 는 TF1 의존으로 Python 3.10+ 설치가 까다롭다.
현재 전략:

  piano:  piano_transcription_inference (pip, 자동 weight 다운로드 ~700MB)
          -> PyTorch 포트, F1 96%. 가장 간단.
  drums:  ADTOF (선택). 공식 pre-trained 는 수동 다운로드 필요 —
          https://github.com/MZehren/ADTOF  의 releases 참조. 스크립트가
          설치 디렉터리만 만들고 실제 파일은 사용자가 복사.

Usage:
    python scripts/download_checkpoints.py          # 둘 다 시도
    python scripts/download_checkpoints.py --piano  # piano 만
    python scripts/download_checkpoints.py --drums  # drums 만

출력은 ASCII only (Windows cp949 환경 호환).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def install_pti() -> bool:
    """piano_transcription_inference 를 pip 설치 + checkpoint 선다운로드.

    PTI 가 `PianoTranscription()` 호출 시 auto-download 를 지원한다고 하지만
    Windows 에서는 urllib 다운로드가 종종 멈추거나 `=` 가 들어간 파일명 때문에
    실패한다 (Sprint 37.4 검증 중 재현). 그래서 ~/piano_transcription_inference_data/
    에 미리 받아 둔다.
    """
    try:
        import piano_transcription_inference  # noqa: F401
        print("[piano] piano_transcription_inference already installed")
    except ImportError:
        print("[piano] installing piano_transcription_inference via pip...")
        res = subprocess.run(
            [sys.executable, "-m", "pip", "install", "piano_transcription_inference"],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"[piano] pip install failed:\n{res.stderr[-500:]}")
            return False
        print("[piano] pip install OK")

    # Checkpoint pre-fetch
    import urllib.request, time as _t
    target_dir = Path.home() / "piano_transcription_inference_data"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "note_F1=0.9677_pedal_F1=0.9186.pth"
    if target.exists() and target.stat().st_size > 100_000_000:
        print(f"[piano] checkpoint already present: {target.name} "
              f"({target.stat().st_size/1e6:.0f} MB)")
        return True

    url = ("https://zenodo.org/record/4034264/files/"
           "CRNN_note_F1%3D0.9677_pedal_F1%3D0.9186.pth?download=1")
    print(f"[piano] fetching checkpoint (~180 MB) from Zenodo...")
    t0 = _t.time()
    try:
        urllib.request.urlretrieve(url, str(target))
    except Exception as e:
        print(f"[piano] checkpoint download failed: {type(e).__name__}: {e}")
        return False
    print(f"[piano] checkpoint OK — {target.stat().st_size/1e6:.0f} MB "
          f"in {_t.time()-t0:.1f}s")
    return True


def install_adtof() -> bool:
    """ADTOF is more involved — just prepare the directory and print the
    official install instructions. The package itself is a manual setup
    from source as of 2024.
    """
    target = REPO_ROOT / "checkpoints" / "adtof"
    target.mkdir(parents=True, exist_ok=True)

    # Try a quick pip install — works on some ADTOF forks, fails silently otherwise.
    print("[drums] attempting `pip install adtof`...")
    res = subprocess.run(
        [sys.executable, "-m", "pip", "install", "adtof"],
        capture_output=True, text=True,
    )
    if res.returncode == 0:
        print("[drums] adtof installed. Pre-trained model still needs manual download:")
    else:
        print("[drums] adtof pip install failed (expected — usually source install).")

    print("[drums] Manual install steps (optional, drums F1 55 -> 80%):")
    print("    git clone https://github.com/MZehren/ADTOF")
    print("    cd ADTOF && pip install -e .")
    print(f"    Copy pre-trained model files into: {target}")
    print("    Then set env var: ADTOF_MODEL=<path-to-checkpoint-dir>")
    print("[drums] Without this setup, drum stem uses librosa onset (F1 ~55%).")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--piano", action="store_true", help="piano backend only")
    parser.add_argument("--drums", action="store_true", help="drums backend only")
    args = parser.parse_args()

    do_piano = args.piano or not (args.piano or args.drums)
    do_drums = args.drums or not (args.piano or args.drums)

    results: list[tuple[str, bool]] = []
    if do_piano:
        results.append(("piano", install_pti()))
    if do_drums:
        results.append(("drums", install_adtof()))

    print()
    print("=== summary ===")
    all_ok = True
    for label, ok in results:
        print(f"  {label}: {'OK' if ok else 'FAIL'}")
        all_ok = all_ok and ok

    print()
    if all_ok:
        print("Next: python scripts/doctor.py")
    else:
        print("Some steps failed. See 10_audio2midi_roadmap.md for manual install.")
        sys.exit(1)


if __name__ == "__main__":
    main()
