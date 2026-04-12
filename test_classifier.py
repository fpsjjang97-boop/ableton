"""
Classifier Regression Test — test_classifier.py
================================================

Regression test for ``MidiEncoder._classify_track`` to prevent the
2026-04-08 BUG 6 from coming back.

Tests two layers:

1. **Real-world track names** from the 54-song seed dataset are mapped
   to the semantically correct vocab.TRACK_TYPES category.

2. **GM program number ranges** map to the full 14-category vocab,
   not the broken 2-3-category collapse of the pre-2026-04-09 code.

Usage:
    python test_classifier.py                   # run all tests
    python test_classifier.py --verbose         # show every check

This test must pass before any retraining is considered valid.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.tokenizer.encoder import MidiEncoder
from midigpt.tokenizer.vocab import VOCAB, TRACK_TYPES


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _mock_instrument(name: str = "", program: int = 0,
                     avg_pitch: int | None = None):
    """Build a fake pretty_midi.Instrument-like object for classifier input."""
    inst = MagicMock()
    inst.name = name
    inst.program = program
    inst.is_drum = False

    if avg_pitch is not None:
        note = MagicMock()
        note.pitch = avg_pitch
        inst.notes = [note]
    else:
        inst.notes = []

    return inst


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: list[str] = []

    def check(self, label: str, actual: str, expected: str, verbose: bool):
        ok = (actual == expected)
        if ok:
            self.passed += 1
            if verbose:
                print(f"  [OK  ] {label}: {actual}")
        else:
            self.failed += 1
            msg = f"  [FAIL] {label}: got '{actual}', expected '{expected}'"
            self.failures.append(msg)
            print(msg)

    def check_in(self, label: str, actual: str, expected_set: set, verbose: bool):
        ok = (actual in expected_set)
        if ok:
            self.passed += 1
            if verbose:
                print(f"  [OK  ] {label}: {actual}")
        else:
            self.failed += 1
            msg = f"  [FAIL] {label}: got '{actual}', expected one of {expected_set}"
            self.failures.append(msg)
            print(msg)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
def test_real_world_track_names(encoder, result, verbose):
    """Real track names from midi_data/ 54-song seed dataset."""
    print("\n[TEST 1] Real-world track names from user data")

    # Format: (track_name, program, expected_category)
    cases = [
        # --- Bass family ---
        ("BASS_FINGER",        33, "bass"),
        ("SYNTHBASS",           0, "bass"),
        ("SYNTYBASS",           0, "bass"),   # typo in one file
        # --- Keys family (→ accomp) ---
        ("E.PIANO",             0, "accomp"),
        ("E.PIANO",             4, "accomp"),
        ("Piano",               0, "accomp"),
        ("Rhodes",              4, "accomp"),
        # --- Guitar family ---
        ("E.GUITAR1",          27, "guitar"),
        ("E.GUITAR2",          27, "guitar"),
        ("E.GUITAR1_MUTE",     28, "guitar"),
        ("Guitar",              0, "guitar"),
        ("Acoustic Guitar",    24, "guitar"),
        # --- Pad family ---
        ("SYNTHPAD",            0, "pad"),
        ("Pad 1 (new age)",    88, "pad"),
        # --- Strings family ---
        ("VIOLIN_LEGATO1",     40, "strings"),
        ("VIOLIN2_LEGATO",     40, "strings"),
        ("Violin Section",     48, "strings"),
        ("String Ensemble",    48, "strings"),
        ("Cello",              42, "strings"),
        # --- Lead ---
        ("SYNTHPLUCK",         80, "lead"),
        # --- Melody ---
        ("MELODY",              0, "melody"),
        # --- Vocal ---
        ("VOCAL",               0, "vocal"),
        ("Voice",              53, "vocal"),
        # --- Brass ---
        ("Trumpet",            56, "brass"),
        ("French Horn",        60, "brass"),
        # --- Woodwind ---
        ("Flute",              73, "woodwind"),
        ("Saxophone",          66, "woodwind"),
    ]

    for name, prog, expected in cases:
        inst = _mock_instrument(name=name, program=prog)
        actual = encoder._classify_track(inst)
        result.check(f"'{name}' (prog={prog})", actual, expected, verbose)


def test_gm_program_ranges(encoder, result, verbose):
    """GM program numbers → correct category (no name hint)."""
    print("\n[TEST 2] GM program ranges (no track name)")

    # Format: (program, expected_category)
    cases = [
        (  0, "accomp"),     # Acoustic Grand Piano
        (  4, "accomp"),     # Electric Piano 1
        ( 16, "accomp"),     # Drawbar Organ
        ( 24, "guitar"),     # Nylon Guitar  (was: accomp)
        ( 27, "guitar"),     # Clean Electric Guitar
        ( 30, "guitar"),     # Distortion Guitar
        ( 32, "bass"),       # Acoustic Bass
        ( 33, "bass"),       # Electric Bass (finger)
        ( 35, "bass"),       # Fretless Bass
        ( 40, "strings"),    # Violin       (was: pad)
        ( 42, "strings"),    # Cello
        ( 48, "strings"),    # String Ensemble 1 (was: pad)
        ( 52, "strings"),    # Choir Aahs (eh, but 48-55 → strings)
        ( 56, "brass"),      # Trumpet      (was: lead)
        ( 60, "brass"),      # French Horn
        ( 64, "woodwind"),   # Soprano Sax  (was: melody)
        ( 68, "woodwind"),   # Oboe
        ( 73, "woodwind"),   # Flute        (was: melody)
        ( 80, "lead"),       # Lead 1 (square)
        ( 83, "lead"),       # Lead 4 (chiff)
        ( 88, "pad"),        # Pad 1 (new age)
        ( 94, "pad"),        # Pad 7 (halo)
        ( 96, "fx"),         # FX 1 (rain)
        (100, "fx"),         # FX 5 (brightness)
    ]

    for prog, expected in cases:
        inst = _mock_instrument(name="", program=prog)
        actual = encoder._classify_track(inst)
        result.check(f"prog={prog:>3}", actual, expected, verbose)


def test_all_categories_reachable(encoder, result, verbose):
    """All primary TRACK_TYPES must be reachable from realistic inputs.

    Note on ``other``: this is a pure safety-net fallback that is
    effectively unreachable for valid MIDI (program numbers 0-127 all
    map to a specific family). So we require the 13 *primary* categories
    to be reachable and treat ``other`` as a reserved safety net.

    This catches the original BUG 6 regression where ``guitar``,
    ``strings``, ``brass``, ``woodwind``, ``vocal`` were orphan vocab
    entries never reached by any code path.
    """
    print("\n[TEST 3] All 13 primary TRACK_TYPES are reachable")

    reached: set[str] = set()
    probes = [
        _mock_instrument(name="MELODY"),                # melody
        _mock_instrument(name="E.PIANO"),               # accomp
        _mock_instrument(name="BASS_FINGER"),           # bass
        _mock_instrument(name="KICK DRUM"),             # drums
        _mock_instrument(name="SYNTHPAD"),              # pad
        _mock_instrument(name="LEAD SYNTH"),            # lead
        _mock_instrument(name="ARP SEQ"),               # arp
        _mock_instrument(name="GUITAR E"),              # guitar
        _mock_instrument(name="VIOLIN_LEGATO"),         # strings
        _mock_instrument(name="TRUMPET"),               # brass
        _mock_instrument(name="FLUTE"),                 # woodwind
        _mock_instrument(name="VOCAL LEAD"),            # vocal
        _mock_instrument(name="FX ATMO"),               # fx
    ]

    for inst in probes:
        cat = encoder._classify_track(inst)
        reached.add(cat)

    # 'other' is a safety net — not expected to be reached in normal data
    required = set(TRACK_TYPES) - {"other"}
    missing = required - reached
    if missing:
        result.failed += 1
        msg = f"  [FAIL] Unreachable primary categories: {sorted(missing)}"
        result.failures.append(msg)
        print(msg)
    else:
        result.passed += 1
        if verbose:
            print(f"  [OK  ] All 13 primary categories reachable: {sorted(reached)}")
            print(f"         ('other' reserved as safety-net fallback)")
        else:
            print(f"  [OK  ] All 13 primary categories reachable")


def test_accomp_ratio_sanity(encoder, result, verbose):
    """Given a diverse set of tracks, accomp should NOT dominate.

    Catches the regression where everything collapses to accomp.
    """
    print("\n[TEST 4] Accomp ratio sanity")

    diverse_inputs = [
        # Common DAW track names from user's dataset
        _mock_instrument(name="BASS_FINGER",       program=33),
        _mock_instrument(name="E.PIANO",           program=0),
        _mock_instrument(name="SYNTHPAD",          program=88),
        _mock_instrument(name="VIOLIN_LEGATO1",    program=40),
        _mock_instrument(name="VIOLIN2_LEGATO",    program=40),
        _mock_instrument(name="E.GUITAR1",         program=27),
        _mock_instrument(name="E.GUITAR2",         program=27),
        _mock_instrument(name="SYNTHBASS",         program=0),
        _mock_instrument(name="MELODY",            program=0),
        _mock_instrument(name="DRUM KIT",          program=0),
    ]

    categories = [encoder._classify_track(i) for i in diverse_inputs]
    accomp_count = categories.count("accomp")
    accomp_pct = 100 * accomp_count / len(categories)

    if verbose:
        print(f"         categories: {categories}")
        print(f"         accomp ratio: {accomp_pct:.0f}%")

    # We expect E.PIANO → accomp, so accomp > 0 is OK.
    # But for this diverse set, it should NOT be > 40%.
    if accomp_pct > 40:
        result.failed += 1
        msg = (f"  [FAIL] accomp dominates: {accomp_pct:.0f}% of diverse set "
               f"(categories: {categories})")
        result.failures.append(msg)
        print(msg)
    else:
        result.passed += 1
        print(f"  [OK  ] accomp ratio = {accomp_pct:.0f}% (< 40%)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    encoder = MidiEncoder(VOCAB)
    result = TestResult()

    print("=" * 70)
    print("  MidiGPT Classifier Regression Test")
    print("=" * 70)

    test_real_world_track_names(encoder, result, args.verbose)
    test_gm_program_ranges(encoder, result, args.verbose)
    test_all_categories_reachable(encoder, result, args.verbose)
    test_accomp_ratio_sanity(encoder, result, args.verbose)

    print()
    print("=" * 70)
    print(f"  {result.passed} passed, {result.failed} failed")
    print("=" * 70)

    if result.failed > 0:
        print("\nFailures:")
        for f in result.failures:
            print("  " + f)

    sys.exit(0 if result.failed == 0 else 1)


if __name__ == "__main__":
    main()
