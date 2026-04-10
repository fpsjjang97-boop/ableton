"""
External MIDI Dataset Downloader — Lakh + GiantMIDI-Piano + Slakh2100

Downloads, extracts, filters, and integrates external MIDI datasets
into the MidiGPT training pipeline.

Usage:
    python scripts/download_datasets.py --datasets lakh giant slakh --output_dir ./midi_data
    python scripts/download_datasets.py --datasets lakh --output_dir ./midi_data  # Lakh만
    python scripts/download_datasets.py --list  # 데이터셋 정보만 출력
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# Optional tqdm — fall back to a simple progress printer
# ---------------------------------------------------------------------------
try:
    from tqdm import tqdm as _tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


# ---------------------------------------------------------------------------
# Dataset catalogue
# ---------------------------------------------------------------------------
DATASETS = {
    "lakh": {
        "name": "Lakh MIDI Dataset (clean_midi)",
        "url": "http://hog.ee.columbia.edu/craffel/lmd/clean_midi.tar.gz",
        "alt_url": "http://hog.ee.columbia.edu/craffel/lmd/lmd_matched.tar.gz",
        "size_approx": "~75 MB (clean) / ~1.6 GB (matched)",
        "songs_approx": "~10,000 (clean) / ~170,000 (matched)",
        "description": (
            "Colin Raffel's Lakh MIDI Dataset.  The *clean_midi* subset is "
            "recommended: smaller download, higher quality."
        ),
        "archive_type": "tar.gz",
    },
    "giant": {
        "name": "GiantMIDI-Piano",
        "url": "https://github.com/bytedance/GiantMIDI-Piano",
        "size_approx": "N/A (must be generated from YouTube audio)",
        "songs_approx": "~10,000 piano performances",
        "description": (
            "ByteDance's GiantMIDI-Piano.  MIDI files are NOT directly "
            "downloadable — they must be transcribed from YouTube using the "
            "project's own scripts.  If you already have transcribed MIDI "
            "files, use  --giant_dir <path>  to point to them."
        ),
        "archive_type": None,
    },
    "slakh": {
        "name": "Slakh2100",
        "url": "https://zenodo.org/records/4599666",
        "size_approx": "~100 GB (full) — script extracts MIDI only",
        "songs_approx": "2,100 multi-stem songs",
        "description": (
            "Slakh2100 from Zenodo.  The full dataset is very large (~100 GB) "
            "because it includes rendered audio stems.  This script extracts "
            "only the 'all_src.mid' MIDI mixdown from each song folder."
        ),
        "archive_type": "tar.gz",
    },
}

# Zenodo file IDs for Slakh2100 MIDI-bearing archives
# Slakh is split into train / validation / test .tar.gz on Zenodo.
SLAKH_ZENODO_FILES = [
    # (filename, Zenodo download URL)
    (
        "slakh2100_flac_redux-train.tar.gz",
        "https://zenodo.org/records/4599666/files/slakh2100_flac_redux-train.tar.gz",
    ),
    (
        "slakh2100_flac_redux-validation.tar.gz",
        "https://zenodo.org/records/4599666/files/slakh2100_flac_redux-validation.tar.gz",
    ),
    (
        "slakh2100_flac_redux-test.tar.gz",
        "https://zenodo.org/records/4599666/files/slakh2100_flac_redux-test.tar.gz",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sizeof_fmt(num: float) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"


class _ProgressHook:
    """urllib reporthook that uses tqdm when available, else plain prints."""

    def __init__(self, filename: str):
        self.filename = filename
        self.bar = None
        self.last_print = 0.0

    def __call__(self, block_num: int, block_size: int, total_size: int):
        downloaded = block_num * block_size

        if HAS_TQDM:
            if self.bar is None and total_size > 0:
                self.bar = _tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    desc=self.filename,
                )
            if self.bar is not None:
                self.bar.update(block_size)
        else:
            now = time.time()
            if now - self.last_print >= 2.0 or downloaded >= total_size:
                if total_size > 0:
                    pct = min(100.0, downloaded / total_size * 100)
                    print(
                        f"\r  {self.filename}: {_sizeof_fmt(downloaded)} / "
                        f"{_sizeof_fmt(total_size)} ({pct:.1f}%)",
                        end="", flush=True,
                    )
                else:
                    print(
                        f"\r  {self.filename}: {_sizeof_fmt(downloaded)}",
                        end="", flush=True,
                    )
                self.last_print = now

    def close(self):
        if HAS_TQDM and self.bar is not None:
            self.bar.close()
        else:
            print()  # newline after carriage-return progress


def download_file(url: str, dest: Path, retries: int = 3) -> Path:
    """Download *url* to *dest*, skipping if already present.  Returns dest."""
    if dest.exists():
        print(f"  [skip] {dest.name} already exists ({_sizeof_fmt(dest.stat().st_size)})")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    hook = _ProgressHook(dest.name)

    for attempt in range(1, retries + 1):
        try:
            urllib.request.urlretrieve(url, str(dest), reporthook=hook)
            hook.close()
            print(f"  Downloaded {dest.name} ({_sizeof_fmt(dest.stat().st_size)})")
            return dest
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            hook.close()
            if attempt < retries:
                wait = 5 * attempt
                print(f"\n  [retry {attempt}/{retries}] {exc} — waiting {wait}s ...")
                time.sleep(wait)
            else:
                print(f"\n  [ERROR] Failed to download {url} after {retries} attempts: {exc}")
                print("  Check your network connection and try again.")
                raise


def extract_archive(archive: Path, dest_dir: Path) -> Path:
    """Extract tar.gz or zip archive into *dest_dir*.  Returns dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"  Extracting {archive.name} -> {dest_dir} ...")

    if archive.suffixes[-2:] == [".tar", ".gz"] or archive.name.endswith(".tar.gz"):
        with tarfile.open(str(archive), "r:gz") as tf:
            tf.extractall(path=str(dest_dir))
    elif archive.suffix == ".zip":
        with zipfile.ZipFile(str(archive), "r") as zf:
            zf.extractall(path=str(dest_dir))
    else:
        raise ValueError(f"Unsupported archive format: {archive.name}")

    print(f"  Extraction complete.")
    return dest_dir


def collect_midi_files(root: Path, pattern: str = "*.mid") -> List[Path]:
    """Recursively gather MIDI files under *root*."""
    files = sorted(list(root.rglob(pattern)) + list(root.rglob("*.midi")))
    return files


# ---------------------------------------------------------------------------
# Import filter function from sibling script
# ---------------------------------------------------------------------------

def _get_check_midi():
    """Import check_midi from filter_midi_dataset.py (same directory)."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from filter_midi_dataset import check_midi, FilterStats
        return check_midi, FilterStats
    except ImportError:
        print(
            "  [WARN] Could not import check_midi from filter_midi_dataset.py.\n"
            "         MIDI files will be copied WITHOUT quality filtering."
        )
        return None, None


# ---------------------------------------------------------------------------
# Per-dataset handlers
# ---------------------------------------------------------------------------

def handle_lakh(
    download_dir: Path,
    output_dir: Path,
    use_full: bool = False,
    filter_fn=None,
    filter_stats_cls=None,
) -> dict:
    """Download and process Lakh MIDI Dataset."""
    info = DATASETS["lakh"]

    if use_full:
        url = info["alt_url"]
        archive_name = "lmd_matched.tar.gz"
    else:
        url = info["url"]
        archive_name = "clean_midi.tar.gz"

    archive_path = download_dir / archive_name
    extract_dir = download_dir / archive_name.replace(".tar.gz", "")

    # Download
    download_file(url, archive_path)

    # Extract (skip if already extracted)
    if not extract_dir.exists() or not any(extract_dir.rglob("*.mid")):
        extract_archive(archive_path, extract_dir)
    else:
        print(f"  [skip] {extract_dir} already extracted")

    # Collect MIDI files
    midi_files = collect_midi_files(extract_dir)
    print(f"  Found {len(midi_files)} MIDI files in {extract_dir}")

    # Filter and copy
    return _filter_and_copy(midi_files, output_dir, "lakh", filter_fn, filter_stats_cls)


def handle_giant(
    download_dir: Path,
    output_dir: Path,
    giant_dir: Optional[Path] = None,
    filter_fn=None,
    filter_stats_cls=None,
) -> dict:
    """Handle GiantMIDI-Piano dataset."""
    info = DATASETS["giant"]

    print()
    print("=" * 64)
    print("  GiantMIDI-Piano")
    print("=" * 64)
    print()
    print("  GiantMIDI-Piano does NOT provide pre-built MIDI files.")
    print("  The dataset requires transcribing piano performances from")
    print("  YouTube using the project's own scripts.")
    print()
    print(f"  GitHub: {info['url']}")
    print()

    if giant_dir is not None:
        giant_path = Path(giant_dir)
        if not giant_path.exists():
            print(f"  [ERROR] --giant_dir path does not exist: {giant_path}")
            return {"dataset": "giant", "total": 0, "passed": 0, "skipped": True, "elapsed": 0.0}

        midi_files = collect_midi_files(giant_path)
        print(f"  Using user-provided directory: {giant_path}")
        print(f"  Found {len(midi_files)} MIDI files")

        if not midi_files:
            print("  [WARN] No MIDI files found in the provided directory.")
            return {"dataset": "giant", "total": 0, "passed": 0, "skipped": True, "elapsed": 0.0}

        return _filter_and_copy(midi_files, output_dir, "giant", filter_fn, filter_stats_cls)

    print("  To use GiantMIDI-Piano MIDI files you already have, re-run with:")
    print()
    print("    python scripts/download_datasets.py --datasets giant \\")
    print("        --giant_dir /path/to/your/giant_midi_piano/midis")
    print()
    print("  Skipping GiantMIDI-Piano for now.")
    print()
    return {"dataset": "giant", "total": 0, "passed": 0, "skipped": True, "elapsed": 0.0}


def handle_slakh(
    download_dir: Path,
    output_dir: Path,
    filter_fn=None,
    filter_stats_cls=None,
) -> dict:
    """Download and process Slakh2100 (MIDI only)."""
    print()
    print("=" * 64)
    print("  Slakh2100")
    print("=" * 64)
    print()
    print("  Slakh2100 archives are very large (~100 GB total with audio).")
    print("  This script will download each split and extract ONLY the")
    print("  'all_src.mid' mixdown MIDI from each song folder.")
    print()

    all_midi: List[Path] = []
    slakh_midi_dir = download_dir / "slakh2100_midi"
    slakh_midi_dir.mkdir(parents=True, exist_ok=True)

    for archive_name, url in SLAKH_ZENODO_FILES:
        archive_path = download_dir / archive_name
        extract_dir = download_dir / archive_name.replace(".tar.gz", "")

        # Download
        try:
            download_file(url, archive_path)
        except Exception as exc:
            print(f"  [ERROR] Could not download {archive_name}: {exc}")
            print("  You can manually download from: https://zenodo.org/records/4599666")
            print("  Skipping this split.")
            continue

        # Extract only MIDI files (all_src.mid) to save disk space
        if not extract_dir.exists() or not any(extract_dir.rglob("all_src.mid")):
            print(f"  Extracting MIDI files from {archive_name} ...")
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with tarfile.open(str(archive_path), "r:gz") as tf:
                    midi_members = [
                        m for m in tf.getmembers()
                        if m.name.endswith("all_src.mid")
                    ]
                    if midi_members:
                        tf.extractall(path=str(extract_dir), members=midi_members)
                        print(f"  Extracted {len(midi_members)} MIDI files from {archive_name}")
                    else:
                        # Fallback: extract everything if selective extraction finds nothing
                        print(f"  No 'all_src.mid' found with selective filter, extracting all ...")
                        tf.extractall(path=str(extract_dir))
            except Exception as exc:
                print(f"  [ERROR] Extraction failed for {archive_name}: {exc}")
                continue
        else:
            existing = list(extract_dir.rglob("all_src.mid"))
            print(f"  [skip] {extract_dir.name} already extracted ({len(existing)} MIDIs)")

        # Collect all_src.mid files
        midis = list(extract_dir.rglob("all_src.mid"))
        if not midis:
            # Fall back to any .mid files
            midis = collect_midi_files(extract_dir)
        all_midi.extend(midis)

    print(f"\n  Total Slakh MIDI files collected: {len(all_midi)}")

    if not all_midi:
        return {"dataset": "slakh", "total": 0, "passed": 0, "skipped": True, "elapsed": 0.0}

    return _filter_and_copy(all_midi, output_dir, "slakh", filter_fn, filter_stats_cls)


# ---------------------------------------------------------------------------
# Shared filter-and-copy logic
# ---------------------------------------------------------------------------

def _filter_and_copy(
    midi_files: List[Path],
    output_dir: Path,
    prefix: str,
    filter_fn,
    filter_stats_cls,
) -> dict:
    """Filter MIDI files and copy passing ones to output_dir.

    Returns a summary dict with keys: dataset, total, passed, skipped, elapsed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    start = time.time()
    passed = 0
    total = len(midi_files)

    if filter_fn is not None and filter_stats_cls is not None:
        stats = filter_stats_cls()

        for i, path in enumerate(midi_files):
            ok = filter_fn(
                path=path,
                min_tracks=1,
                min_notes=50,
                max_notes=50000,
                min_duration=10.0,
                max_duration=600.0,
                min_density=0.5,
                max_density=200.0,
                require_consistent_time_sig=False,
                require_polyphonic=False,
                stats=stats,
            )
            if ok:
                dest_name = f"{prefix}_{path.stem}_{i}.mid"
                dest = output_dir / dest_name
                try:
                    shutil.copy2(str(path), str(dest))
                    passed += 1
                except OSError as exc:
                    print(f"  [WARN] Copy failed for {path.name}: {exc}")

            if (i + 1) % 500 == 0 or (i + 1) == total:
                print(f"  [{i+1}/{total}] passed={passed}")

        elapsed = time.time() - start
        print(f"\n  Filter summary for '{prefix}':")
        print("  " + stats.summary().replace("\n", "\n  "))
    else:
        # No filter available — copy everything
        print(f"  Copying {total} MIDI files without filtering ...")
        for i, path in enumerate(midi_files):
            dest_name = f"{prefix}_{path.stem}_{i}.mid"
            dest = output_dir / dest_name
            try:
                shutil.copy2(str(path), str(dest))
                passed += 1
            except OSError as exc:
                print(f"  [WARN] Copy failed for {path.name}: {exc}")

            if (i + 1) % 500 == 0 or (i + 1) == total:
                print(f"  [{i+1}/{total}] copied={passed}")

        elapsed = time.time() - start

    return {
        "dataset": prefix,
        "total": total,
        "passed": passed,
        "skipped": False,
        "elapsed": elapsed,
    }


# ---------------------------------------------------------------------------
# --list : print dataset catalogue
# ---------------------------------------------------------------------------

def print_dataset_list():
    """Print information about all available datasets."""
    print()
    print("=" * 68)
    print("  Available External MIDI Datasets")
    print("=" * 68)
    for key, info in DATASETS.items():
        print()
        print(f"  [{key}]  {info['name']}")
        print(f"    URL:          {info['url']}")
        if "alt_url" in info:
            print(f"    Alt URL:      {info['alt_url']}")
        print(f"    Size:         {info['size_approx']}")
        print(f"    Songs:        {info['songs_approx']}")
        print(f"    Description:  {info['description']}")
    print()
    print("=" * 68)
    print()
    print("  Recommended quick start:")
    print("    python scripts/download_datasets.py --datasets lakh --output_dir ./midi_data")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Download, filter, and integrate external MIDI datasets "
            "(Lakh, GiantMIDI-Piano, Slakh2100) into the MidiGPT training pipeline."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/download_datasets.py --list\n"
            "  python scripts/download_datasets.py --datasets lakh --output_dir ./midi_data\n"
            "  python scripts/download_datasets.py --datasets lakh giant slakh --output_dir ./midi_data\n"
            "  python scripts/download_datasets.py --datasets giant --giant_dir /path/to/midis\n"
            "  python scripts/download_datasets.py --datasets lakh --lakh_full  # full 170K matched set\n"
        ),
    )

    parser.add_argument(
        "--list", action="store_true", default=False,
        help="Print dataset catalogue and exit",
    )
    parser.add_argument(
        "--datasets", nargs="+", choices=["lakh", "giant", "slakh"],
        default=None,
        help="Which datasets to download (default: all)",
    )
    parser.add_argument(
        "--download_dir", type=str, default="./downloads",
        help="Temporary download / extraction directory (default: ./downloads)",
    )
    parser.add_argument(
        "--output_dir", type=str, default="./midi_data",
        help="Final output directory for filtered MIDI files (default: ./midi_data)",
    )
    parser.add_argument(
        "--giant_dir", type=str, default=None,
        help="Path to pre-existing GiantMIDI-Piano MIDI files (for 'giant' dataset)",
    )
    parser.add_argument(
        "--lakh_full", action="store_true", default=False,
        help="Download the full Lakh matched set (~1.6 GB / ~170K songs) instead of clean_midi",
    )
    parser.add_argument(
        "--no_filter", action="store_true", default=False,
        help="Skip quality filtering — copy all extracted MIDI files as-is",
    )

    args = parser.parse_args()

    # --list: just print info and exit
    if args.list:
        print_dataset_list()
        return

    # If no datasets specified, default to all
    datasets = args.datasets if args.datasets else ["lakh", "giant", "slakh"]

    download_dir = Path(args.download_dir).resolve()
    output_dir = Path(args.output_dir).resolve()

    download_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 68)
    print("  MidiGPT External Dataset Downloader")
    print("=" * 68)
    print(f"  Datasets:      {', '.join(datasets)}")
    print(f"  Download dir:  {download_dir}")
    print(f"  Output dir:    {output_dir}")
    print()

    # Load filter function
    if args.no_filter:
        filter_fn, filter_stats_cls = None, None
        print("  Filtering: DISABLED (--no_filter)")
    else:
        filter_fn, filter_stats_cls = _get_check_midi()
        if filter_fn is not None:
            print("  Filtering: ENABLED (via filter_midi_dataset.check_midi)")
        else:
            print("  Filtering: UNAVAILABLE (filter_midi_dataset.py not found)")
    print()

    # Run each dataset handler
    summaries: List[dict] = []
    overall_start = time.time()

    if "lakh" in datasets:
        print("-" * 68)
        print(f"  [1/3] Lakh MIDI Dataset {'(full matched)' if args.lakh_full else '(clean_midi)'}")
        print("-" * 68)
        result = handle_lakh(
            download_dir=download_dir,
            output_dir=output_dir,
            use_full=args.lakh_full,
            filter_fn=filter_fn,
            filter_stats_cls=filter_stats_cls,
        )
        summaries.append(result)

    if "giant" in datasets:
        result = handle_giant(
            download_dir=download_dir,
            output_dir=output_dir,
            giant_dir=Path(args.giant_dir) if args.giant_dir else None,
            filter_fn=filter_fn,
            filter_stats_cls=filter_stats_cls,
        )
        summaries.append(result)

    if "slakh" in datasets:
        result = handle_slakh(
            download_dir=download_dir,
            output_dir=output_dir,
            filter_fn=filter_fn,
            filter_stats_cls=filter_stats_cls,
        )
        summaries.append(result)

    overall_elapsed = time.time() - overall_start

    # Final summary
    print()
    print("=" * 68)
    print("  DOWNLOAD SUMMARY")
    print("=" * 68)
    grand_total = 0
    grand_passed = 0
    for s in summaries:
        status = "SKIPPED" if s["skipped"] else f"{s['passed']}/{s['total']} passed"
        elapsed_str = f"{s['elapsed']:.1f}s" if not s["skipped"] else "-"
        print(f"  {s['dataset']:>8s}:  {status:>24s}   ({elapsed_str})")
        grand_total += s["total"]
        grand_passed += s["passed"]

    print(f"  {'TOTAL':>8s}:  {grand_passed}/{grand_total} files in {output_dir}")
    print(f"  Total time: {overall_elapsed:.1f}s")
    print("=" * 68)
    print()


if __name__ == "__main__":
    main()
