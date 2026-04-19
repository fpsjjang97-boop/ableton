"""릴리스 아티팩트 SHA256 매니페스트 생성.

make_release.bat 이후 실행되어:
    1. 릴리스 zip 의 SHA256 생성
    2. staging 폴더 내 모든 파일의 SHA256 생성 (변조 탐지용)
    3. MANIFEST.sha256 / RELEASE_INFO.txt 저장
    4. 필수 아티팩트 존재 + 크기 sanity 체크

사용:
    python scripts/make_release_manifest.py --staging build/release/MidiGPT-0.9.0-beta-win64
    python scripts/make_release_manifest.py --zip build/release/MidiGPT-0.9.0-beta-win64.zip

성공 시 같은 폴더에 MANIFEST.sha256 + RELEASE_INFO.txt 생성.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fp:
        for chunk in iter(lambda: fp.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


REQUIRED = [
    "MidiGPT.vst3",
    "MidiGPT-Standalone.exe",
    "scripts/doctor.py",
    "scripts/setup_audio2midi.bat",
    "requirements-audio2midi.txt",
]

SIZE_FLOOR_MB = {
    "MidiGPT-Standalone.exe": 5,
    "MidiGPT.vst3": 1,  # 디렉토리라 bundle 하위 파일 크기 합
}


def _path_size_mb(p: Path) -> float:
    if p.is_file():
        return p.stat().st_size / 1e6
    if p.is_dir():
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6
    return 0.0


def run(staging: Path | None, zip_path: Path | None) -> int:
    if not staging and not zip_path:
        print("[ERROR] --staging 또는 --zip 중 하나는 필요")
        return 2

    target_dir = None
    if staging:
        if not staging.exists():
            print(f"[ERROR] staging 없음: {staging}")
            return 2
        target_dir = staging

        # Preflight: 필수 아티팩트 존재 + 크기
        missing = []
        too_small = []
        for rel in REQUIRED:
            p = staging / rel
            if not p.exists():
                missing.append(rel)
        for rel, floor in SIZE_FLOOR_MB.items():
            p = staging / rel
            if p.exists() and _path_size_mb(p) < floor:
                too_small.append(f"{rel} ({_path_size_mb(p):.1f} MB < {floor} MB 최소치)")

        if missing:
            print(f"[ERROR] 누락 아티팩트: {missing}")
            return 1
        if too_small:
            print(f"[WARN] 크기 이상:")
            for t in too_small:
                print(f"    {t}")

        # staging 내 모든 파일 SHA256
        manifest_lines = [f"# MidiGPT Release Manifest",
                          f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                          f"# Staging:   {staging}",
                          ""]
        files = sorted(p for p in staging.rglob("*") if p.is_file())
        print(f"파일 {len(files)}개 해시 계산 중...")
        for p in files:
            rel = p.relative_to(staging).as_posix()
            h = _sha256(p)
            sz = p.stat().st_size
            manifest_lines.append(f"{h}  {sz:>12}  {rel}")

        manifest = staging / "MANIFEST.sha256"
        manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
        print(f"[OK] MANIFEST.sha256 — {len(files)} 파일")
        print(f"    {manifest}")

    if zip_path:
        if not zip_path.exists():
            print(f"[ERROR] zip 없음: {zip_path}")
            return 2
        zh = _sha256(zip_path)
        zs = zip_path.stat().st_size
        info = zip_path.with_suffix(zip_path.suffix + ".sha256")
        info.write_text(f"{zh}  {zip_path.name}\n", encoding="utf-8")
        print(f"[OK] ZIP SHA256: {zh}")
        print(f"    {info}  ({zs/1e6:.1f} MB)")

        # RELEASE_INFO.txt
        # Sprint 45 III4 — 버전/주요 변경 cross-ref
        version_note = zip_path.stem.replace("MidiGPT-", "").replace("-win64", "")
        rel_info_lines = [
            f"MidiGPT Release — {zip_path.stem}",
            f"Version:   {version_note}",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"ZIP:    {zip_path.name}",
            f"Size:   {zs/1e6:.1f} MB",
            f"SHA256: {zh}",
            f"",
            f"주요 변경 (자세한 내용은 CHANGELOG.md):",
            f"  - 다중 LoRA 핫스왑 + 블렌딩 (Sprint 43~44)",
            f"  - Audio2MIDI source-filter refine (Sprint 43~44)",
            f"  - 톤 분류기 간이 strings/brass/woodwind (Sprint 44)",
            f"  - SFT 페어 정제 도구 + 회귀 테스트 세트 (Sprint 40~44)",
            f"  - 데모 preflight 8 체크 자동화 (Sprint 42~44)",
            f"",
            f"설치:",
            f"  1. zip 압축 해제",
            f"  2. scripts/setup_audio2midi.bat (Windows) 또는 setup_audio2midi.sh (macOS/Linux)",
            f"  3. python scripts/download_checkpoints.py",
            f"  4. python scripts/doctor.py  — 환경 점검",
            f"  5. MidiGPT-Standalone.exe 실행 또는 DAW VST3 스캔",
            f"",
            f"체크섬 검증 (PowerShell):",
            f'  Get-FileHash {zip_path.name} -Algorithm SHA256',
            f"",
            f"검증 (bash):",
            f"  sha256sum {zip_path.name}",
        ]
        rel_info = zip_path.parent / "RELEASE_INFO.txt"
        rel_info.write_text("\n".join(rel_info_lines) + "\n", encoding="utf-8")
        print(f"    {rel_info}")

    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--staging", default=None,
                    help="make_release.bat 의 staging 폴더")
    ap.add_argument("--zip", default=None, help="생성된 릴리스 zip")
    args = ap.parse_args()
    sys.exit(run(
        Path(args.staging) if args.staging else None,
        Path(args.zip) if args.zip else None,
    ))


if __name__ == "__main__":
    main()
