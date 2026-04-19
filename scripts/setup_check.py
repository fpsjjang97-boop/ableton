"""
MidiGPT — Setup Sanity Check
=============================

Run this on a fresh clone to verify the environment is correctly set up
for training and inference.

    python scripts/setup_check.py

The script reports a green/yellow/red status for each check and exits
non-zero on the first hard failure so it can be wired into CI later.

Checks performed:
  1. Python version (>= 3.10)
  2. Required packages (torch, numpy, pretty_midi, mido)
  3. CUDA availability + GPU info
  4. Project import (midigpt model + tokenizer + inference engine)
  5. Model instantiation (50M Transformer construction without crash)
  6. Vocabulary integrity
  7. Data directories present (midi_data/, TEST MIDI/)
  8. Disk space for checkpoints + intermediate data
"""
from __future__ import annotations

import importlib
import shutil
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pretty output helpers (no external dependency)
# ---------------------------------------------------------------------------
def _color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


GREEN = lambda s: _color("32", s)
YELLOW = lambda s: _color("33", s)
RED = lambda s: _color("31", s)
BOLD = lambda s: _color("1", s)


PASS = GREEN("[ OK  ]")
WARN = YELLOW("[WARN ]")
FAIL = RED("[FAIL ]")


_failures: list[str] = []
_warnings: list[str] = []


def report(level: str, name: str, detail: str = "") -> None:
    line = f"{level} {name}"
    if detail:
        line += f"  —  {detail}"
    print(line)
    if level == FAIL:
        _failures.append(name)
    elif level == WARN:
        _warnings.append(name)


def section(title: str) -> None:
    print()
    print(BOLD(f"=== {title} ==="))


# ---------------------------------------------------------------------------
# 1. Python version
# ---------------------------------------------------------------------------
def check_python() -> None:
    section("1. Python")
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        report(FAIL, "Python version", f"{detail} (need >= 3.10)")
    elif v < (3, 11):
        report(WARN, "Python version", f"{detail} (3.11+ recommended)")
    else:
        report(PASS, "Python version", detail)


# ---------------------------------------------------------------------------
# 2. Package imports
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = [
    ("torch", "2.0"),
    ("numpy", "1.24"),
    ("pretty_midi", "0.2.10"),
    ("mido", "1.3"),
]


def _version_ge(actual: str, required: str) -> bool:
    """Naive lexical version compare (works for x.y.z numeric strings)."""
    def _norm(s: str) -> tuple[int, ...]:
        out: list[int] = []
        for part in s.split("."):
            digits = "".join(ch for ch in part if ch.isdigit())
            out.append(int(digits) if digits else 0)
        return tuple(out)
    return _norm(actual) >= _norm(required)


def check_packages() -> None:
    section("2. Required packages")
    for name, min_ver in REQUIRED_PACKAGES:
        try:
            mod = importlib.import_module(name)
            actual = getattr(mod, "__version__", "unknown")
            if actual == "unknown":
                report(WARN, name, "version unknown")
            elif _version_ge(actual, min_ver):
                report(PASS, name, f"{actual} (>= {min_ver})")
            else:
                report(FAIL, name, f"{actual} < required {min_ver}")
        except ImportError as e:
            report(FAIL, name, f"not installed ({e})")


# ---------------------------------------------------------------------------
# 3. CUDA / GPU
# ---------------------------------------------------------------------------
def check_cuda() -> None:
    section("3. CUDA / GPU")
    try:
        import torch
    except ImportError:
        report(FAIL, "torch import", "skipping CUDA check")
        return

    if not torch.cuda.is_available():
        report(
            WARN,
            "CUDA",
            "not available — training will run on CPU (very slow)",
        )
        return

    n = torch.cuda.device_count()
    report(PASS, "CUDA available", f"{n} device(s)")
    for i in range(n):
        name = torch.cuda.get_device_name(i)
        vram_gb = torch.cuda.get_device_properties(i).total_memory / 1e9
        report(PASS, f"  GPU {i}", f"{name} ({vram_gb:.1f} GB)")
        if vram_gb < 8:
            report(
                WARN,
                f"  GPU {i} VRAM",
                "< 8 GB — use --batch_size 4 --grad_accum 8",
            )


# ---------------------------------------------------------------------------
# 4. Project import
# ---------------------------------------------------------------------------
def check_project_import() -> None:
    section("4. Project imports")
    targets = [
        ("midigpt.model", "MidiGPT, MidiGPTConfig"),
        ("midigpt.tokenizer.vocab", "VOCAB"),
        ("midigpt.tokenizer.encoder", "MidiEncoder, SongMeta"),
        ("midigpt.tokenizer.decoder", "MidiDecoder"),
        ("midigpt.training.ema", "EMA"),
        ("midigpt.training.lora", "apply_lora, LoRAConfig"),
        ("midigpt.inference.engine", "MidiGPTInference"),
    ]
    for module_path, names in targets:
        try:
            importlib.import_module(module_path)
            report(PASS, module_path, names)
        except Exception as e:
            report(FAIL, module_path, f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 5. Model instantiation
# ---------------------------------------------------------------------------
def check_model_instantiation() -> None:
    section("5. Model instantiation")
    try:
        from midigpt.model import MidiGPT, MidiGPTConfig

        cfg = MidiGPTConfig()
        model = MidiGPT(cfg)
        params = model.count_parameters()
        report(
            PASS,
            "MidiGPT(MidiGPTConfig())",
            f"{params:,} params (~{params / 1e6:.1f}M)",
        )

        # Quick forward pass on a tiny dummy batch
        import torch

        dummy = torch.zeros((1, 16), dtype=torch.long)
        with torch.no_grad():
            logits, loss, kv = model(dummy)
        report(
            PASS,
            "forward(dummy)",
            f"logits {tuple(logits.shape)}, kv layers={len(kv)}",
        )
    except Exception as e:
        traceback.print_exc()
        report(FAIL, "model construction", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 6. Vocabulary integrity
# ---------------------------------------------------------------------------
def check_vocab() -> None:
    section("6. Vocabulary")
    try:
        from midigpt.tokenizer.vocab import VOCAB

        size = VOCAB.size
        report(PASS, "VOCAB.size", str(size))
        # Spot-check a few token IDs
        for tok in ("<PAD>", "<BOS>", "<EOS>", "<SEP>", "ChordRoot_C"):
            tid = VOCAB.encode_token(tok)
            if tid == VOCAB.unk_id and tok != "<UNK>":
                report(FAIL, f"token '{tok}'", "missing from vocab")
            else:
                report(PASS, f"token '{tok}'", f"id={tid}")
    except Exception as e:
        report(FAIL, "vocab inspection", f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# 7. Data directories
# ---------------------------------------------------------------------------
def check_data_dirs() -> None:
    section("7. Data directories")

    candidates = [
        ("midi_data/", REPO_ROOT / "midi_data"),
        ("TEST MIDI/", REPO_ROOT / "TEST MIDI"),
        ("Ableton/midi_raw/", REPO_ROOT / "Ableton" / "midi_raw"),
    ]
    total = 0
    for label, path in candidates:
        if not path.exists():
            report(WARN, label, "not found")
            continue
        midis = list(path.rglob("*.mid")) + list(path.rglob("*.midi"))
        total += len(midis)
        if midis:
            report(PASS, label, f"{len(midis)} MIDI files")
        else:
            report(WARN, label, "directory empty")

    if total == 0:
        report(FAIL, "training data", "no MIDI files anywhere — pull from git first")
    else:
        report(PASS, "total MIDI files", str(total))


# ---------------------------------------------------------------------------
# 8. Disk space
# ---------------------------------------------------------------------------
def check_disk_space() -> None:
    section("8. Disk space")
    try:
        usage = shutil.disk_usage(REPO_ROOT)
        free_gb = usage.free / 1e9
        if free_gb < 5:
            report(FAIL, "free disk", f"{free_gb:.1f} GB (need >= 5 GB)")
        elif free_gb < 20:
            report(WARN, "free disk", f"{free_gb:.1f} GB (20+ recommended)")
        else:
            report(PASS, "free disk", f"{free_gb:.1f} GB")
    except Exception as e:
        report(WARN, "disk check", str(e))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    import argparse
    argparse.ArgumentParser(
        description="MidiGPT 환경 sanity check (Python/packages/CUDA/vocab/data). 인자 없음."
    ).parse_args()

    print(BOLD("MidiGPT setup check"))
    print(f"Repo root: {REPO_ROOT}")

    check_python()
    check_packages()
    check_cuda()
    check_project_import()
    check_model_instantiation()
    check_vocab()
    check_data_dirs()
    check_disk_space()

    print()
    print(BOLD("=== Summary ==="))
    if not _failures and not _warnings:
        print(GREEN("All checks passed. Ready to train."))
        return 0
    if _warnings:
        print(YELLOW(f"Warnings ({len(_warnings)}):"))
        for w in _warnings:
            print(f"  - {w}")
    if _failures:
        print(RED(f"Failures ({len(_failures)}):"))
        for f in _failures:
            print(f"  - {f}")
        print()
        print(RED("Fix the failures above before training."))
        return 1
    print(YELLOW("Setup is usable but not optimal."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
