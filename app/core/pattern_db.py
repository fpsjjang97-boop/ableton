"""
PatternDB -- singleton pattern store that loads pattern_library/*.json
and provides query methods for the generation engine.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Map note name -> pitch class (0-11)
_NAME_TO_PC: dict[str, int] = {n: i for i, n in enumerate(NOTE_NAMES)}

# Also handle flats for robustness
_FLAT_MAP = {"Db": "C#", "Eb": "D#", "Fb": "E", "Gb": "F#", "Ab": "G#", "Bb": "A#", "Cb": "B"}

def _get_repo_root() -> Path:
    """Find repo root, supporting both normal Python and PyInstaller."""
    if getattr(sys, 'frozen', False):
        bundle = Path(getattr(sys, '_MEIPASS', ''))
        if (bundle / "pattern_library").is_dir():
            return bundle
        exe_dir = Path(sys.executable).resolve().parent
        for d in [exe_dir, exe_dir.parent, exe_dir.parent.parent]:
            if (d / "pattern_library").is_dir():
                return d
        return exe_dir
    return Path(__file__).resolve().parent.parent.parent

_REPO_ROOT = _get_repo_root()


def _note_pc(name: str) -> int:
    """Return pitch class for a note name like 'A', 'C#', 'Bb'."""
    name = _FLAT_MAP.get(name, name)
    return _NAME_TO_PC.get(name, -1)


def _parse_chord(label: str) -> tuple[str, str]:
    """Parse a chord label into (root_name, quality).

    Examples:
        'Am7'  -> ('A', 'm7')
        'C#min' -> ('C#', 'min')
        'Gsus4' -> ('G', 'sus4')
        'D'    -> ('D', '')
    """
    label = label.strip()
    if not label:
        return ("", "")
    # Match root: a letter optionally followed by # or b
    m = re.match(r'^([A-Ga-g][#b]?)(.*)', label)
    if not m:
        return (label, "")
    root = m.group(1)
    root = root[0].upper() + root[1:]  # normalise
    quality = m.group(2)
    return (root, quality)


def _transpose_chord(label: str, shift: int) -> str:
    """Transpose a single chord label by *shift* semitones.

    Handles slash chords like 'C/E' by transposing both parts.
    """
    if "/" in label:
        parts = label.split("/", 1)
        return _transpose_chord(parts[0], shift) + "/" + _transpose_chord(parts[1], shift)

    root, quality = _parse_chord(label)
    pc = _note_pc(root)
    if pc < 0:
        return label  # unparseable, return as-is
    new_pc = (pc + shift) % 12
    return NOTE_NAMES[new_pc] + quality


def _load_json(path: str | Path) -> dict | list | None:
    """Load a JSON file, returning None on any error."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


class PatternDB:
    """Singleton pattern store backed by pattern_library/*.json."""

    _instance: Optional[PatternDB] = None

    def __init__(self) -> None:
        self._lib_dir = _REPO_ROOT / "pattern_library"
        self._progressions: dict = {}   # raw from chord_progressions.json
        self._voicings: dict = {}       # raw from voicing_examples.json
        self._forms: dict = {}          # raw from form_templates.json
        self._genre_stats: dict = {}    # raw from genre_statistics.json
        self.reload()

    # ------------------------------------------------------------------ #
    #  Singleton accessor                                                 #
    # ------------------------------------------------------------------ #
    @classmethod
    def get(cls) -> PatternDB:
        """Return the singleton PatternDB instance (create on first call)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ #
    #  Data loading                                                       #
    # ------------------------------------------------------------------ #
    def reload(self) -> None:
        """Re-read all JSON files from disk."""
        self._progressions = _load_json(self._lib_dir / "chord_progressions.json") or {}
        self._voicings = _load_json(self._lib_dir / "voicing_examples.json") or {}
        self._forms = _load_json(self._lib_dir / "form_templates.json") or {}
        self._genre_stats = _load_json(self._lib_dir / "genre_statistics.json") or {}

    # ------------------------------------------------------------------ #
    #  Progression queries                                                #
    # ------------------------------------------------------------------ #
    def query_progressions(
        self,
        key: str = "C",
        scale: str = "minor",
        gram_size: int = 4,
        min_count: int = 2,
        style: Optional[str] = None,
    ) -> list[dict]:
        """Return chord progression patterns, transposed to the requested *key*.

        Each result dict:
            {"chords": ["Dm7", "G7", ...], "count": 15, "original": "Dm7 -> G7 -> ..."}

        Static patterns (all chords identical) are filtered out unless
        removing them would leave fewer than 2 results.
        """
        gram_key = f"{gram_size}_gram"
        patterns_section = self._progressions.get("patterns", {})
        raw_patterns: list[dict] = patterns_section.get(gram_key, [])

        # Compute transposition shift: original data is in C (pc=0)
        target_pc = _note_pc(key)
        if target_pc < 0:
            target_pc = 0
        shift = target_pc  # from C=0

        results: list[dict] = []
        for entry in raw_patterns:
            pattern_str: str = entry.get("pattern", "")
            count: int = entry.get("count", 0)
            if count < min_count:
                continue

            # Split by arrow separator (unicode or ascii)
            chords = re.split(r"\s*(?:\u2192|->)\s*", pattern_str)
            chords = [c.strip() for c in chords if c.strip()]

            # Transpose each chord
            transposed = [_transpose_chord(c, shift) for c in chords]

            results.append({
                "chords": transposed,
                "count": count,
                "original": pattern_str,
            })

        # Always filter out static patterns (all chords identical)
        non_static = [r for r in results if len(set(r["chords"])) > 1]
        results = non_static if non_static else results

        # Sort by count descending
        results.sort(key=lambda r: r["count"], reverse=True)

        # If too few results from this gram size, also try building
        # progressions by chaining 2-grams
        if len(results) < 5 and gram_size >= 4:
            chained = self._chain_2grams(key, scale, gram_size)
            results.extend(chained)
            # Deduplicate
            seen = set()
            unique = []
            for r in results:
                k = tuple(r["chords"])
                if k not in seen:
                    seen.add(k)
                    unique.append(r)
            results = unique

        return results

    def _chain_2grams(
        self, key: str, scale: str, target_len: int = 4
    ) -> list[dict]:
        """Build longer progressions by chaining 2-gram transitions.

        Uses the 2-gram frequency as a Markov transition probability.
        """
        raw_2grams = self._progressions.get("patterns", {}).get("2_gram", [])
        if not raw_2grams:
            return []

        target_pc = _note_pc(key)
        shift = target_pc if target_pc >= 0 else 0

        # Build transition map: chord -> [(next_chord, count), ...]
        transitions: dict[str, list[tuple[str, int]]] = {}
        for entry in raw_2grams:
            pattern_str = entry.get("pattern", "")
            count = entry.get("count", 0)
            parts = [c.strip() for c in pattern_str.split("→") if c.strip()]
            if len(parts) == 2 and parts[0] != parts[1] and count >= 2:
                src = _transpose_chord(parts[0], shift)
                dst = _transpose_chord(parts[1], shift)
                transitions.setdefault(src, []).append((dst, count))

        if not transitions:
            return []

        # Generate several progressions by random walk
        import random
        results = []
        start_chords = list(transitions.keys())

        for _ in range(10):
            start = random.choice(start_chords)
            chain = [start]
            current = start
            for _ in range(target_len - 1):
                nexts = transitions.get(current, [])
                if not nexts:
                    break
                # Weighted random choice
                total = sum(c for _, c in nexts)
                r = random.random() * total
                cumulative = 0
                chosen = nexts[0][0]
                for nxt, cnt in nexts:
                    cumulative += cnt
                    if r <= cumulative:
                        chosen = nxt
                        break
                chain.append(chosen)
                current = chosen

            if len(chain) >= target_len and len(set(chain)) > 1:
                results.append({
                    "chords": chain[:target_len],
                    "count": 1,
                    "original": " → ".join(chain[:target_len]) + " (chained)",
                })

        return results

    # ------------------------------------------------------------------ #
    #  Voicing queries                                                    #
    # ------------------------------------------------------------------ #
    def query_voicing(self, quality: str) -> list[dict]:
        """Return real voicing examples for a chord *quality*.

        quality: e.g. 'maj7', 'm7', '7', 'min', 'sus4', etc.
        """
        examples = self._voicings.get("examples", {})
        return list(examples.get(quality, []))

    # ------------------------------------------------------------------ #
    #  Form templates                                                     #
    # ------------------------------------------------------------------ #
    def get_form_template(self, style: Optional[str] = None) -> list[str]:
        """Return a section sequence from form_templates.json.

        If no matching style is found, returns the first available sequence.
        """
        stats = self._forms.get("statistics", {})
        sequences: list[list[str]] = stats.get("common_section_sequences", [])
        if not sequences:
            return []
        # For now, return the first sequence (most common)
        return list(sequences[0])

    # ------------------------------------------------------------------ #
    #  Style / genre introspection                                        #
    # ------------------------------------------------------------------ #
    # ------------------------------------------------------------------
    # Next-chord suggestion (Markov from 2-grams)
    # ------------------------------------------------------------------

    def suggest_next_chords(
        self,
        current_chords: list[str],
        key: str = "C",
        top_k: int = 3,
    ) -> list[dict]:
        """Suggest the next chord(s) given a sequence of current chords.

        Uses 2-gram transition frequencies from the pattern DB.
        Returns up to top_k suggestions, each: {"chord": "Am7", "confidence": 0.75}
        """
        if not current_chords:
            return []

        target_pc = _note_pc(key)
        shift = target_pc if target_pc >= 0 else 0

        # Build transition map from 2-grams
        raw_2grams = self._progressions.get("patterns", {}).get("2_gram", [])
        transitions: dict[str, list[tuple[str, int]]] = {}
        for entry in raw_2grams:
            pattern_str = entry.get("pattern", "")
            count = entry.get("count", 0)
            parts = [c.strip() for c in pattern_str.split("\u2192") if c.strip()]
            if not parts or len(parts) < 2:
                parts = [c.strip() for c in pattern_str.split("->") if c.strip()]
            if len(parts) == 2 and count >= 2:
                src = _transpose_chord(parts[0], shift)
                dst = _transpose_chord(parts[1], shift)
                transitions.setdefault(src, []).append((dst, count))

        # Also scan 4-grams for context-aware matching
        raw_4grams = self._progressions.get("patterns", {}).get("4_gram", [])
        for entry in raw_4grams:
            pattern_str = entry.get("pattern", "")
            count = entry.get("count", 0)
            parts = re.split(r"\s*(?:\u2192|->)\s*", pattern_str)
            parts = [c.strip() for c in parts if c.strip()]
            if len(parts) >= 2 and count >= 2:
                transposed = [_transpose_chord(c, shift) for c in parts]
                # Check if current_chords matches the beginning
                n = len(current_chords)
                for i in range(len(transposed) - 1):
                    window = transposed[max(0, i - n + 1):i + 1]
                    if len(window) >= 1 and window[-1] == current_chords[-1]:
                        if i + 1 < len(transposed):
                            nxt = transposed[i + 1]
                            transitions.setdefault(current_chords[-1], []).append((nxt, count))

        # Look up the last chord in current sequence
        last_chord = current_chords[-1]
        candidates = transitions.get(last_chord, [])

        if not candidates:
            # Try without quality (just root matching)
            last_root, _ = _parse_chord(last_chord)
            for src, nexts in transitions.items():
                src_root, _ = _parse_chord(src)
                if src_root == last_root:
                    candidates.extend(nexts)

        if not candidates:
            return []

        # Aggregate counts per chord
        chord_counts: dict[str, int] = {}
        for chord, count in candidates:
            chord_counts[chord] = chord_counts.get(chord, 0) + count

        # Filter out same-chord suggestions
        chord_counts.pop(last_chord, None)

        if not chord_counts:
            return []

        # Sort by count, take top_k
        total = sum(chord_counts.values())
        sorted_chords = sorted(chord_counts.items(), key=lambda x: -x[1])[:top_k]

        return [
            {
                "chord": chord,
                "confidence": round(count / total, 3),
                "count": count,
            }
            for chord, count in sorted_chords
        ]

    # Base style/genre lists — extended dynamically as DB grows
    _BASE_STYLES = [
        "ambient", "ballad", "bossa_nova", "cinematic", "classical",
        "edm", "experimental", "gospel", "hiphop", "jazz",
        "lo-fi", "pop", "r&b", "rock", "waltz",
    ]
    _BASE_GENRES = [
        "chamber", "classical", "electronic", "jazz", "pop", "recital", "schubert",
    ]
    _BASE_MOODS = [
        "bright", "calm", "dark", "dreamy", "energetic",
        "epic", "happy", "melancholy", "sad", "warm",
    ]

    def available_styles(self) -> list[str]:
        """Return available music styles.

        Combines base styles with any styles detected from the DB.
        """
        styles = set(self._BASE_STYLES)

        # Add form types as style hints
        form_stats = self._forms.get("statistics", {})
        form_dist = form_stats.get("form_type_distribution", {})
        for form_type in form_dist:
            if form_type not in ("unknown", "AABA"):
                styles.add(form_type.replace("-", "_"))

        return sorted(styles)

    def available_genres(self) -> list[str]:
        """Return genre categories from the corpus."""
        genres = set(self._BASE_GENRES)

        # Add from genre statistics source corpus description
        source = self._genre_stats.get("source_corpus", "")
        if "MAESTRO" in source:
            genres.update(["classical", "chamber", "recital"])

        return sorted(genres)

    def available_moods(self) -> list[str]:
        """Return available mood descriptors."""
        return sorted(self._BASE_MOODS)

    def available_keys(self) -> list[str]:
        """Return keys found in the analyzed corpus, sorted by frequency."""
        stats = self._genre_stats.get("statistics", {})
        key_dist = stats.get("key_distribution", {})
        if key_dist:
            return [k for k, _ in sorted(key_dist.items(), key=lambda x: -x[1])]
        return list(NOTE_NAMES)
