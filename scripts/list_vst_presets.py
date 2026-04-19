"""VST3 플러그인 preset 디렉토리 스캔 (Sprint 46 JJJ5).

JUCE plugin preset save/load (Sprint 36 AAA4 / BB4) 는 OS 별 표준 위치에
.preset 파일을 저장한다. 본 유틸은 해당 위치를 스캔하고 플러그인별로
preset 개수를 출력.

OS 별 기본 경로:
    Windows:  %APPDATA%\MidiGPT\presets\<plugin_name>\
    macOS:    ~/Library/Application Support/MidiGPT/presets/<plugin_name>/
    Linux:    ~/.config/MidiGPT/presets/<plugin_name>/

사용:
    python scripts/list_vst_presets.py
    python scripts/list_vst_presets.py --plugin MidiGPT
    python scripts/list_vst_presets.py --path /custom/presets/
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _default_preset_root() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", "")) / "MidiGPT" / "presets"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "MidiGPT" / "presets"
    return Path.home() / ".config" / "MidiGPT" / "presets"


def scan(root: Path, plugin_filter: str | None) -> int:
    if not root.exists():
        print(f"Preset 디렉토리 없음: {root}")
        print("플러그인이 아직 preset 을 저장하지 않았거나, 경로가 다릅니다.")
        return 1

    print(f"Preset root: {root}")
    print("=" * 60)

    plugins = [p for p in root.iterdir() if p.is_dir()]
    if plugin_filter:
        plugins = [p for p in plugins if p.name == plugin_filter]

    if not plugins:
        print("플러그인 디렉토리 0개")
        return 0

    total = 0
    for plugin_dir in sorted(plugins):
        files = sorted(plugin_dir.glob("*.preset")) + \
                sorted(plugin_dir.glob("*.json"))
        print(f"\n[{plugin_dir.name}]  {len(files)}개")
        for f in files[:20]:
            sz = f.stat().st_size
            print(f"    {f.name}  ({sz:,} bytes)")
        if len(files) > 20:
            print(f"    ... (+{len(files) - 20}개)")
        total += len(files)

    print("=" * 60)
    print(f"총 {total} presets")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--path", default=None,
                    help="preset 루트 (기본: OS 표준 위치)")
    ap.add_argument("--plugin", default=None,
                    help="특정 플러그인 이름만 (예: MidiGPT)")
    args = ap.parse_args()

    root = Path(args.path) if args.path else _default_preset_root()
    sys.exit(scan(root, args.plugin))


if __name__ == "__main__":
    main()
