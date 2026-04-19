"""DAW .mgp v3 프로젝트 파일 스키마 검증 (Sprint 46 JJJ2).

DAW 가 깨진 .mgp 를 로드하면 크래시 — 로드 전 검증으로 사용자 보호.

검사:
    1. JSON 파싱 가능
    2. 최상위 필수 키: version, tracks, tempoMap (optional: tsMap, buses, audioClips)
    3. version >= 3
    4. tracks: list[dict], 각 원소 필수 키 id/name
    5. tempoMap: list of {beat, bpm} 또는 빈 list
    6. audioClips[].path 참조 (로컬 .wav) 이 존재하면 크기 ≥ 1KB
    7. plugins[].state base64 디코드 가능 (있으면)

실패 항목은 path + 이유 출력. errors (치명) vs warnings (권장) 분리.

사용:
    python scripts/validate_mgp_project.py --project foo.mgp
    python scripts/validate_mgp_project.py --project foo.mgp --strict   # warn 도 fail 로

종료 코드:
    0 = 전부 OK (strict 에서는 warn 도 없음)
    1 = errors 있음
    2 = 파일 없음 / JSON parse 실패
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


REQUIRED_TOP = ("version", "tracks")
TRACK_REQUIRED = ("id", "name")


def validate(project_path: Path, strict: bool = False) -> int:
    if not project_path.exists():
        print(f"[ERROR] 파일 없음: {project_path}")
        return 2
    try:
        data = json.loads(project_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse: {e}")
        return 2

    errors: list[str] = []
    warnings: list[str] = []

    # 1. top-level required
    for k in REQUIRED_TOP:
        if k not in data:
            errors.append(f"최상위 필수 키 누락: {k}")

    # 2. version
    v = data.get("version")
    if isinstance(v, (int, float)) and v < 3:
        errors.append(f"version {v} < 3 — v3 이상만 지원")
    elif not isinstance(v, (int, float)):
        errors.append(f"version 이 숫자가 아님: {type(v).__name__}")

    # 3. tracks
    tracks = data.get("tracks")
    if not isinstance(tracks, list):
        errors.append(f"tracks 가 list 아님: {type(tracks).__name__}")
    else:
        for i, tr in enumerate(tracks):
            if not isinstance(tr, dict):
                errors.append(f"tracks[{i}] 가 dict 아님")
                continue
            for k in TRACK_REQUIRED:
                if k not in tr:
                    errors.append(f"tracks[{i}] 필수 키 누락: {k}")

    # 4. tempoMap
    tm = data.get("tempoMap")
    if tm is not None:
        if not isinstance(tm, list):
            errors.append(f"tempoMap 가 list 아님: {type(tm).__name__}")
        else:
            for i, entry in enumerate(tm):
                if not (isinstance(entry, dict) and "beat" in entry and "bpm" in entry):
                    errors.append(f"tempoMap[{i}] 포맷 오류")
                elif not (isinstance(entry["bpm"], (int, float)) and 30 <= entry["bpm"] <= 300):
                    warnings.append(f"tempoMap[{i}].bpm 범위 외: {entry['bpm']}")
    else:
        warnings.append("tempoMap 없음 — DAW 는 기본 120 BPM 사용")

    # 5. audioClips 외부 파일 참조
    clips = data.get("audioClips", [])
    if isinstance(clips, list):
        project_dir = project_path.parent
        for i, c in enumerate(clips):
            if not isinstance(c, dict):
                continue
            p = c.get("path")
            if not p:
                continue
            refp = (project_dir / p).resolve() if not Path(p).is_absolute() else Path(p)
            if not refp.exists():
                warnings.append(f"audioClips[{i}].path 부재: {p}")
            elif refp.stat().st_size < 1024:
                warnings.append(f"audioClips[{i}].path 크기 비정상: {refp.stat().st_size} bytes")

    # 6. plugins[].state base64
    plugins = data.get("plugins", [])
    if isinstance(plugins, list):
        for i, pl in enumerate(plugins):
            if isinstance(pl, dict) and "state" in pl and isinstance(pl["state"], str):
                try:
                    base64.b64decode(pl["state"], validate=True)
                except Exception as e:
                    warnings.append(f"plugins[{i}].state base64 디코드 실패: {e}")

    # Output
    print(f"Project: {project_path}")
    print(f"Version: {v}  tracks={len(tracks) if isinstance(tracks, list) else '?'}  "
          f"clips={len(clips) if isinstance(clips, list) else 0}  "
          f"plugins={len(plugins) if isinstance(plugins, list) else 0}")
    print("=" * 60)
    if not errors and not warnings:
        print("[OK] 검증 통과")
        return 0
    if errors:
        print(f"[ERROR] {len(errors)}:")
        for e in errors:
            print(f"   - {e}")
    if warnings:
        print(f"[WARN] {len(warnings)}:")
        for w in warnings:
            print(f"   - {w}")

    if errors:
        return 1
    if strict and warnings:
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project", required=True, help=".mgp 파일 경로")
    ap.add_argument("--strict", action="store_true", help="warnings 도 fail 로")
    args = ap.parse_args()
    sys.exit(validate(Path(args.project), strict=args.strict))


if __name__ == "__main__":
    main()
