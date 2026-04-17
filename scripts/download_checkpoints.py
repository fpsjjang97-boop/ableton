"""Download Tier 1 Audio2MIDI checkpoints (Onsets & Frames + ADTOF).

Sprint 37 이슈3. Both are optional accuracy upgrades — the plugin works
without them (falls back to Basic Pitch / librosa). This script pulls the
official public checkpoints and places them where convert.py expects.

Layout after running:
    checkpoints/onsets_frames/   — Magenta Onsets&Frames (MAPS 9 변형)
    checkpoints/adtof/           — ADTOF pretrained drum classifier

Usage:
    python scripts/download_checkpoints.py           # both
    python scripts/download_checkpoints.py --oaf     # piano O&F only
    python scripts/download_checkpoints.py --adtof   # drums ADTOF only

Size (approximate):
    O&F:   ~180 MB  (.zip → extracted)
    ADTOF:  ~20 MB

Sources are official first-party releases. See
docs/business/10_audio2midi_roadmap.md for references.
"""
from __future__ import annotations

import argparse
import io
import sys
import zipfile
from pathlib import Path
from urllib.request import urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Source catalogue (public URLs — verify before changing)
# ---------------------------------------------------------------------------
OAF_URL = (
    "https://storage.googleapis.com/magentadata/models/"
    "onsets_frames_transcription/maps_checkpoint.zip"
)
OAF_DEST = REPO_ROOT / "checkpoints" / "onsets_frames"

# ADTOF pretrained bundle. Repo releases: https://github.com/MZehren/ADTOF/releases
# The exact URL changes per release; users may want to override via --adtof-url.
ADTOF_URL = (
    "https://github.com/MZehren/ADTOF/releases/latest/download/pretrained.zip"
)
ADTOF_DEST = REPO_ROOT / "checkpoints" / "adtof"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _download(url: str, dest_dir: Path, label: str) -> bool:
    """Download ``url`` (must be a .zip) and extract into ``dest_dir``.

    Returns True on success. Prints friendly progress + failure hints on
    the common error modes (network down, dead URL, etc.) rather than
    letting a raw Python traceback scroll past.
    """
    if dest_dir.exists() and any(dest_dir.iterdir()):
        print(f"[{label}] 이미 존재 ({dest_dir}) — skip")
        return True

    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{label}] 다운로드: {url}")
    try:
        with urlopen(url, timeout=30) as r:
            data = r.read()
    except Exception as e:
        print(f"[{label}] 다운로드 실패: {e}")
        print(f"         브라우저에서 직접 받아 {dest_dir} 에 수동 설치 가능.")
        return False

    print(f"[{label}] {len(data)/1e6:.1f} MB 받음 — 압축 해제 중...")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extractall(dest_dir)
    except zipfile.BadZipFile:
        print(f"[{label}] .zip 아님 — URL 확인 필요.")
        return False
    except Exception as e:
        print(f"[{label}] 압축 해제 실패: {e}")
        return False

    print(f"[{label}] 완료 → {dest_dir}")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oaf",    action="store_true", help="Onsets & Frames 만")
    parser.add_argument("--adtof",  action="store_true", help="ADTOF 만")
    parser.add_argument("--oaf-url",   default=OAF_URL,   help="override O&F URL")
    parser.add_argument("--adtof-url", default=ADTOF_URL, help="override ADTOF URL")
    args = parser.parse_args()

    # Default: both
    do_oaf   = args.oaf   or not (args.oaf or args.adtof)
    do_adtof = args.adtof or not (args.oaf or args.adtof)

    results = []
    if do_oaf:
        results.append(("O&F",   _download(args.oaf_url,   OAF_DEST,   "O&F")))
    if do_adtof:
        results.append(("ADTOF", _download(args.adtof_url, ADTOF_DEST, "ADTOF")))

    print()
    print("=== 요약 ===")
    all_ok = True
    for label, ok in results:
        print(f"  {label}: {'✅ OK' if ok else '❌ 실패'}")
        all_ok = all_ok and ok

    print()
    if all_ok:
        print("다음 단계: python scripts/doctor.py 로 전체 준비 상태 확인.")
    else:
        print("일부 실패. 수동 설치 방법은 docs/business/10_audio2midi_roadmap.md 참고.")
        sys.exit(1)


if __name__ == "__main__":
    main()
