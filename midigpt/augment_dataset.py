"""
MIDI Data Augmentation Script — Key Transposition + Track Dropout
                               + Velocity Jitter + Time Stretch.

Generates augmented copies of MIDI files to increase training data.

Usage:
    python -m midigpt.augment_dataset \
        --input_dir ./midi_data \
        --output_dir ./midi_data_augmented \
        --transpose all \
        --dropout 3 \
        --vel_jitter 0.10 \
        --time_stretch 0.05 \
        --workers 4

Augmentation strategies:
    1. Key Transposition: Shift all melodic notes by N semitones (drums excluded)
       - "all"  → 11 transpositions (+1 ~ +11 semitones)
       - "6"    → 6 random transpositions
       - "none" → skip transposition

    2. Track Dropout: Remove random subsets of instrument tracks
       - N = number of dropout variations per file
       - Always keeps at least one harmonic + one other track
       - 0 = skip dropout

    3. Velocity Jitter (2026-04-10): Randomly perturb note velocities ±N%
       - Default ±10%. Clamp to 1-127. Preserves musical dynamics contour.
       - 0.0 = skip

    4. Time Stretch (2026-04-10): Scale note timing by ±N%
       - Default ±5%. Stretches start/end/duration uniformly.
       - 0.0 = skip
"""
from __future__ import annotations

import argparse
import copy
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    import pretty_midi
except ImportError:
    print("Error: pretty_midi required. Run: pip install pretty_midi")
    sys.exit(1)


# GM Program → track type (same as encoder.py / midi_embedding.py)
def classify_program(program: int, is_drum: bool) -> str:
    if is_drum:
        return "drums"
    if 0 <= program <= 7:
        return "keys"
    if 24 <= program <= 31:
        return "guitar"
    if 32 <= program <= 39:
        return "bass"
    if 40 <= program <= 55:
        return "strings"
    if 56 <= program <= 63:
        return "brass"
    if 64 <= program <= 79:
        return "woodwind"
    if 80 <= program <= 95:
        return "synth"
    return "other"


# ──────────────────────────────────────────────────────────────────
# 1. Key Transposition
# ──────────────────────────────────────────────────────────────────
def transpose_midi(pm: pretty_midi.PrettyMIDI, semitones: int) -> pretty_midi.PrettyMIDI:
    """Transpose all non-drum notes by N semitones. Clamp to MIDI range 0-127."""
    new_pm = copy.deepcopy(pm)
    for inst in new_pm.instruments:
        if inst.is_drum:
            continue  # Never transpose drum tracks
        for note in inst.notes:
            new_pitch = note.pitch + semitones
            if 0 <= new_pitch <= 127:
                note.pitch = new_pitch
            else:
                # Clamp to valid range (octave wrap)
                note.pitch = max(0, min(127, new_pitch))
    return new_pm


# ──────────────────────────────────────────────────────────────────
# 2. Track Dropout
# ──────────────────────────────────────────────────────────────────
def get_track_groups(pm: pretty_midi.PrettyMIDI) -> dict[str, list[int]]:
    """Group instrument indices by track type."""
    groups: dict[str, list[int]] = {}
    for idx, inst in enumerate(pm.instruments):
        track_type = classify_program(inst.program, inst.is_drum)
        groups.setdefault(track_type, []).append(idx)
    return groups


def dropout_midi(
    pm: pretty_midi.PrettyMIDI,
    rng: random.Random,
    min_groups: int = 2,
) -> pretty_midi.PrettyMIDI | None:
    """Remove random track groups while keeping at least min_groups.

    Rules:
      - Always keep at least one harmonic track (keys/guitar/strings/bass/brass/woodwind)
      - Always keep at least min_groups track groups total
      - Never produce a drums-only file
    Returns None if dropout is not possible (too few groups).
    """
    groups = get_track_groups(pm)

    if len(groups) <= min_groups:
        return None  # Can't drop anything meaningful

    harmonic_types = {"keys", "guitar", "strings", "bass", "brass", "woodwind", "synth"}
    harmonic_groups = [g for g in groups if g in harmonic_types]

    if not harmonic_groups:
        return None  # No harmonic tracks to preserve

    # Decide how many groups to keep (between min_groups and total-1)
    max_keep = len(groups) - 1
    n_keep = rng.randint(min_groups, max(min_groups, max_keep))

    # Always include at least one harmonic group
    kept = set()
    kept.add(rng.choice(harmonic_groups))

    # Fill remaining slots randomly
    remaining = [g for g in groups if g not in kept]
    rng.shuffle(remaining)
    while len(kept) < n_keep and remaining:
        kept.add(remaining.pop())

    # Check: not drums-only
    if kept == {"drums"}:
        return None

    # Build new MIDI with only kept tracks
    keep_indices = set()
    for group_name in kept:
        keep_indices.update(groups[group_name])

    new_pm = copy.deepcopy(pm)
    new_pm.instruments = [inst for idx, inst in enumerate(new_pm.instruments)
                          if idx in keep_indices]

    if not any(inst.notes for inst in new_pm.instruments):
        return None

    return new_pm


# ──────────────────────────────────────────────────────────────────
# 3. Velocity Jitter
# ──────────────────────────────────────────────────────────────────
def velocity_jitter(
    pm: pretty_midi.PrettyMIDI,
    rng: random.Random,
    ratio: float = 0.10,
) -> pretty_midi.PrettyMIDI:
    """Randomly perturb note velocities by ±ratio (e.g. 0.10 = ±10%).

    Clamps to 1-127. Preserves relative dynamics contour.
    """
    new_pm = copy.deepcopy(pm)
    for inst in new_pm.instruments:
        for note in inst.notes:
            jitter = rng.uniform(-ratio, ratio)
            new_vel = int(note.velocity * (1.0 + jitter))
            note.velocity = max(1, min(127, new_vel))
    return new_pm


# ──────────────────────────────────────────────────────────────────
# 4. Time Stretch
# ──────────────────────────────────────────────────────────────────
def time_stretch(
    pm: pretty_midi.PrettyMIDI,
    rng: random.Random,
    ratio: float = 0.05,
) -> pretty_midi.PrettyMIDI:
    """Scale all note start/end times by a random factor in [1-ratio, 1+ratio].

    E.g. ratio=0.05 → stretch factor between 0.95 and 1.05.
    Tempo markers are NOT adjusted — this creates subtle timing variation.
    """
    factor = rng.uniform(1.0 - ratio, 1.0 + ratio)
    new_pm = copy.deepcopy(pm)
    for inst in new_pm.instruments:
        for note in inst.notes:
            note.start = max(0.0, note.start * factor)
            note.end = max(note.start + 0.001, note.end * factor)
    return new_pm


# ──────────────────────────────────────────────────────────────────
# Combined augmentation for one file
# ──────────────────────────────────────────────────────────────────
def augment_file(
    midi_path: Path,
    output_dir: Path,
    transpose_mode: str = "all",
    n_dropout: int = 3,
    vel_jitter_ratio: float = 0.10,
    time_stretch_ratio: float = 0.05,
    seed: int = 42,
) -> list[dict]:
    """Generate augmented versions of a single MIDI file.

    Returns list of result dicts with status info.
    """
    results = []
    rng = random.Random(seed)

    try:
        pm = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as e:
        return [{"status": "error", "file": str(midi_path), "error": str(e)}]

    stem = midi_path.stem

    # ── Transposition ──
    if transpose_mode != "none":
        if transpose_mode == "all":
            shifts = list(range(1, 12))  # +1 ~ +11
        else:
            n_trans = int(transpose_mode)
            shifts = sorted(rng.sample(range(1, 12), min(n_trans, 11)))

        for shift in shifts:
            try:
                transposed = transpose_midi(pm, shift)
                out_name = f"{stem}_trans+{shift}.mid"
                out_path = output_dir / out_name
                transposed.write(str(out_path))
                results.append({
                    "status": "ok",
                    "type": "transpose",
                    "shift": shift,
                    "file": str(out_path),
                })
            except Exception as e:
                results.append({
                    "status": "error",
                    "type": "transpose",
                    "shift": shift,
                    "error": str(e),
                })

    # ── Track Dropout ──
    if n_dropout > 0:
        seen_combos = set()
        attempts = 0
        max_attempts = n_dropout * 5  # Avoid infinite loop

        while len([r for r in results if r.get("type") == "dropout"]) < n_dropout and attempts < max_attempts:
            attempts += 1
            dropped = dropout_midi(pm, rng)
            if dropped is None:
                break  # Can't create more unique dropouts

            # Track which combo we got (avoid duplicates)
            combo = frozenset(
                classify_program(inst.program, inst.is_drum)
                for inst in dropped.instruments
            )
            if combo in seen_combos:
                continue
            seen_combos.add(combo)

            combo_label = "+".join(sorted(combo))
            out_name = f"{stem}_drop_{combo_label}.mid"
            out_path = output_dir / out_name

            try:
                dropped.write(str(out_path))
                results.append({
                    "status": "ok",
                    "type": "dropout",
                    "kept_tracks": sorted(combo),
                    "file": str(out_path),
                })
            except Exception as e:
                results.append({
                    "status": "error",
                    "type": "dropout",
                    "error": str(e),
                })

    # ── Velocity Jitter ──
    if vel_jitter_ratio > 0:
        try:
            jittered = velocity_jitter(pm, rng, vel_jitter_ratio)
            out_name = f"{stem}_veljit.mid"
            out_path = output_dir / out_name
            jittered.write(str(out_path))
            results.append({
                "status": "ok",
                "type": "velocity_jitter",
                "ratio": vel_jitter_ratio,
                "file": str(out_path),
            })
        except Exception as e:
            results.append({
                "status": "error",
                "type": "velocity_jitter",
                "error": str(e),
            })

    # ── Time Stretch ──
    if time_stretch_ratio > 0:
        try:
            stretched = time_stretch(pm, rng, time_stretch_ratio)
            out_name = f"{stem}_tstretch.mid"
            out_path = output_dir / out_name
            stretched.write(str(out_path))
            results.append({
                "status": "ok",
                "type": "time_stretch",
                "ratio": time_stretch_ratio,
                "file": str(out_path),
            })
        except Exception as e:
            results.append({
                "status": "error",
                "type": "time_stretch",
                "error": str(e),
            })

    return results


# ──────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MIDI Data Augmentation")
    parser.add_argument("--input_dir", type=str, required=True,
                        help="Directory containing original MIDI files")
    parser.add_argument("--output_dir", type=str, required=True,
                        help="Output directory for augmented MIDI files")
    parser.add_argument("--transpose", type=str, default="all",
                        help="Transposition mode: 'all' (11 keys), '6' (random 6), 'none'")
    parser.add_argument("--dropout", type=int, default=3,
                        help="Number of track dropout variations per file (0=skip)")
    parser.add_argument("--vel_jitter", type=float, default=0.10,
                        help="Velocity jitter ratio (0.10 = +-10%%, 0=skip)")
    parser.add_argument("--time_stretch", type=float, default=0.05,
                        help="Time stretch ratio (0.05 = +-5%%, 0=skip)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (currently single-process)")

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all MIDI files
    midi_files = sorted(list(input_dir.rglob("*.mid")) + list(input_dir.rglob("*.midi")))

    if not midi_files:
        print(f"No MIDI files found in {input_dir}")
        return

    print(f"Found {len(midi_files)} MIDI files")
    print(f"Transpose: {args.transpose}")
    print(f"Track dropout: {args.dropout} variations/file")
    print(f"Velocity jitter: +-{args.vel_jitter*100:.0f}%")
    print(f"Time stretch: +-{args.time_stretch*100:.0f}%")
    print(f"Output: {output_dir}")
    print("=" * 60)

    start_time = time.time()
    total_ok = 0
    total_err = 0
    total_generated = 0

    for idx, midi_path in enumerate(midi_files):
        # Per-file seed for reproducibility
        file_seed = args.seed + idx

        results = augment_file(
            midi_path=midi_path,
            output_dir=output_dir,
            transpose_mode=args.transpose,
            n_dropout=args.dropout,
            vel_jitter_ratio=args.vel_jitter,
            time_stretch_ratio=args.time_stretch,
            seed=file_seed,
        )

        ok_count = sum(1 for r in results if r["status"] == "ok")
        err_count = sum(1 for r in results if r["status"] == "error")
        total_ok += ok_count
        total_err += err_count
        total_generated += ok_count

        status_char = "+" if ok_count > 0 else "!"
        print(f"  [{idx+1}/{len(midi_files)}] {status_char} {midi_path.name} → {ok_count} augmented", end="")
        if err_count:
            print(f" ({err_count} errors)", end="")
        print()

    elapsed = time.time() - start_time

    # Also copy originals to output dir
    print(f"\nCopying {len(midi_files)} original files...")
    for midi_path in midi_files:
        try:
            original_pm = pretty_midi.PrettyMIDI(str(midi_path))
            out_path = output_dir / f"{midi_path.stem}_original.mid"
            original_pm.write(str(out_path))
        except Exception:
            pass

    total_files = len(midi_files) + total_generated

    print("=" * 60)
    print(f"Done! Generated {total_generated} augmented files")
    print(f"Total dataset: {total_files} files ({len(midi_files)} originals + {total_generated} augmented)")
    print(f"Errors: {total_err}")
    print(f"Time: {elapsed:.1f}s")

    # Multiplier summary
    if len(midi_files) > 0:
        multiplier = total_files / len(midi_files)
        print(f"Data multiplier: x{multiplier:.1f}")


if __name__ == "__main__":
    main()
