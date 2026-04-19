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

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


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
    """ADTOF 드럼 채보 자동 설치 — git clone + pip install -e . 까지.

    공식 repo (MZehren/ADTOF) 는 `adtof/models/` 디렉토리에 pretrained
    weights 를 포함해 배포. 따라서 clone 만 하면 weight 도 같이 온다.
    pip install -e . 로 개발 모드 설치하면 `adtof` 모듈이 import 가능.

    실패 경로별 처리:
      • git clone 실패 (네트워크/404): 수동 안내 출력, False 반환
      • pip install 실패 (컴파일 의존성): repo 는 남기고 안내
      • 모든 성공: ADTOF_MODEL 환경변수 권장 경로 안내
    """
    target = REPO_ROOT / "checkpoints" / "adtof"
    target.mkdir(parents=True, exist_ok=True)
    repo_dir = REPO_ROOT / "third_party" / "ADTOF"

    # 이미 import 가능하면 건너뜀
    try:
        import adtof  # type: ignore  # noqa: F401
        print(f"[drums] adtof 이미 import 가능 — skip install")
        print(f"[drums] 체크포인트 디렉토리: {target}")
        return True
    except ImportError:
        pass

    # 1) Clone
    if not repo_dir.exists():
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        print(f"[drums] cloning ADTOF into {repo_dir} ...")
        res = subprocess.run(
            ["git", "clone", "--depth", "1",
             "https://github.com/MZehren/ADTOF", str(repo_dir)],
            capture_output=True, text=True,
        )
        if res.returncode != 0:
            print(f"[drums] git clone FAILED:\n{res.stderr[-400:]}")
            print("[drums] 수동 설치: "
                  "git clone https://github.com/MZehren/ADTOF && "
                  "cd ADTOF && pip install -e .")
            return False
        print(f"[drums] clone OK ({repo_dir})")
    else:
        print(f"[drums] repo 이미 존재: {repo_dir} — clone skip")

    # 2) Pretrained weight 탐지 — clone 만 되어도 TF checkpoint 는 함께 옴
    # ADTOF repo 는 `adtof/models/Frame_RNN_adtofAll_0.{data-..., index}` 형태로
    # TF2 체크포인트를 repo 안에 배포 (setup.py package_data 참조).
    weight_files = list((repo_dir / "adtof" / "models").glob("*")) \
        if (repo_dir / "adtof" / "models").exists() else []
    has_weights = any(
        f.suffix == ".index" or f.name.endswith("data-00000-of-00001")
        for f in weight_files
    )

    if has_weights:
        weight_dir = repo_dir / "adtof" / "models"
        print(f"[drums] pretrained TF checkpoint 발견: {weight_dir}")
        for f in sorted(weight_files)[:4]:
            print(f"    {f.name}  ({f.stat().st_size/1e6:.1f} MB)")

        # 디폴트 심볼릭/복사 위치로도 연결
        try:
            import shutil
            if not any(target.iterdir()):
                for f in weight_files:
                    shutil.copy2(f, target / f.name)
                print(f"[drums] 체크포인트 복사: -> {target}")
        except (OSError, PermissionError) as e:
            print(f"[drums] 체크포인트 복사 skip: {e}")
    else:
        print(f"[drums] pretrained weight 자동 탐지 실패 — {repo_dir} 내부 확인 필요")

    # 3) pip install -e . — deps 가 무거워 실패해도 repo/weight 는 유효
    print(f"[drums] pip install -e . 시도 (실패해도 weight 는 사용 가능)...")
    res = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        print(f"[drums] pip install -e 실패 — 주요 dep (tensorflow, madmom "
              f"git-install 등) 설치 이슈로 추정. 수동 안내:")
        print(f"    pip install tensorflow>=2.13 cython")
        print(f"    pip install 'madmom @ git+https://github.com/CPJKU/madmom'")
        print(f"    pip install -e {repo_dir}")
        print(f"[drums] 그러나 체크포인트 파일은 이미 확보됨 — "
              f"audio2midi 파이프라인이 ADTOF_MODEL env 로 경로를 참조하면 동작")
    else:
        print("[drums] pip install -e OK — adtof 모듈 import 가능")

    # 4) 환경변수 권장
    env_target = target if any(target.iterdir()) else (repo_dir / "adtof" / "models")
    print(f"[drums] 환경변수 설정 권장:")
    if sys.platform == "win32":
        print(f'    setx ADTOF_MODEL "{env_target}"')
    else:
        print(f"    export ADTOF_MODEL={env_target}")
    return has_weights


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
