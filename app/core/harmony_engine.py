"""
Harmony Engine — loads the v2.07 Rule Database JSON and provides:
  1. MIDI track harmony analysis (chord labeling)
  2. Melody-aware voicing generation
  3. Song form (section) analysis
  4. Playability validation

All public methods return plain dicts/lists and never mutate inputs.
"""
from __future__ import annotations

import json
import math
import os
import re
from typing import Optional

import numpy as np

from core.models import (
    Note, Track, ProjectState, Section,
    TICKS_PER_BEAT, SCALE_INTERVALS, NOTE_NAMES,
    key_name_to_root, get_scale_pitches, midi_to_note_name,
)

_BEAT = TICKS_PER_BEAT
_BAR = _BEAT * 4

# Pitch-class to note names (sharps only, matching NOTE_NAMES)
_PC_NAMES = NOTE_NAMES  # ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

# Interval quality tables (semitones from root)
_CHORD_TEMPLATES: dict[str, list[int]] = {
    "maj":     [0, 4, 7],
    "min":     [0, 3, 7],
    "dim":     [0, 3, 6],
    "aug":     [0, 4, 8],
    "sus2":    [0, 2, 7],
    "sus4":    [0, 5, 7],
    "7":       [0, 4, 7, 10],
    "maj7":    [0, 4, 7, 11],
    "m7":      [0, 3, 7, 10],
    "m7b5":    [0, 3, 6, 10],
    "dim7":    [0, 3, 6, 9],
    "7sus4":   [0, 5, 7, 10],
    "add9":    [0, 2, 4, 7],
    "madd9":   [0, 2, 3, 7],
    "6":       [0, 4, 7, 9],
    "m6":      [0, 3, 7, 9],
    "9":       [0, 2, 4, 7, 10],
    "m9":      [0, 2, 3, 7, 10],
    "maj9":    [0, 2, 4, 7, 11],
    "7b9":     [0, 1, 4, 7, 10],
    "7#9":     [0, 3, 4, 7, 10],
    "11":      [0, 2, 4, 5, 7, 10],
    "13":      [0, 2, 4, 7, 9, 10],
}

_RULE_DB_FILENAME = "260327_최종본_v2.07_song_form_added.json"


def _find_rule_db() -> str:
    """Locate the rule database JSON relative to the repo root."""
    import sys as _sys

    # PyInstaller frozen bundle: check _MEIPASS first
    if getattr(_sys, 'frozen', False):
        bundle = getattr(_sys, '_MEIPASS', '')
        candidate = os.path.join(bundle, _RULE_DB_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        # Also check exe directory and parent
        exe_dir = os.path.dirname(os.path.abspath(_sys.executable))
        for d in [exe_dir, os.path.dirname(exe_dir), os.path.dirname(os.path.dirname(exe_dir))]:
            candidate = os.path.join(d, _RULE_DB_FILENAME)
            if os.path.isfile(candidate):
                return candidate

    # Normal Python: repo root is two levels up from this file
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    candidate = os.path.join(repo, _RULE_DB_FILENAME)
    if os.path.isfile(candidate):
        return candidate
    raise FileNotFoundError(f"Rule DB not found: {candidate}")


# ---------------------------------------------------------------------------
# HarmonyEngine
# ---------------------------------------------------------------------------

class HarmonyEngine:
    """Harmony analysis and voicing generation engine backed by the v2.07 rule DB."""

    def __init__(self, db_path: Optional[str] = None):
        path = db_path or _find_rule_db()
        with open(path, "r", encoding="utf-8") as f:
            self.db = json.load(f)

        self.schema_version = self.db.get("schema_version", 0)
        self.hard_constraints = self.db.get("hard_constraints", {}).get("rules", [])
        self.soft_constraints = self.db.get("soft_constraints", {}).get("rules", [])
        self.chord_quality_rules = self.db.get("chord_quality_rules", [])
        self.voicing_templates = self.db.get("voicing_templates", [])
        self.playability = self.db.get("playability_constraints", {})
        self.inversion_rules = self.db.get("inversion_rules", [])
        self.progression_rules = self.db.get("progression_resolution_rules", [])
        self.melody_rules = self.db.get("melody_alignment_rules", {}).get("rules", [])
        self.analysis_pipeline = self.db.get("analysis_pipeline", {})
        self.scoring_model = self.db.get("scoring_model", {})
        self.voicing_gen_rules = self.db.get("voicing_generation_rules", {})
        self.song_form_rules = self.db.get("song_form_analysis", {})
        self.style_profiles = self.voicing_gen_rules.get("style_inversion_profiles", [])
        self.rng = np.random.default_rng()

        # Build fast chord-quality lookup from DB
        self._cq_map: dict[str, dict] = {}
        for cq in self.chord_quality_rules:
            self._cq_map[cq.get("chord_quality", "")] = cq

    # ------------------------------------------------------------------
    # 1. Chord Identification (per pitch-set)
    # ------------------------------------------------------------------

    def identify_chord(
        self, pitches: list[int], bass_pitch: Optional[int] = None
    ) -> dict:
        """Identify the most likely chord from a set of MIDI pitches.

        Returns dict with keys: label, root, quality, bass, confidence,
        alternatives, pitch_classes, is_slash.
        """
        if not pitches:
            return {"label": "N.C.", "root": None, "quality": None,
                    "bass": None, "confidence": 0.0, "alternatives": [],
                    "pitch_classes": [], "is_slash": False}

        pcs = sorted(set(p % 12 for p in pitches))
        bass_pc = (bass_pitch % 12) if bass_pitch is not None else (min(pitches) % 12)

        best_score = -1.0
        best_label = "N.C."
        best_root = bass_pc
        best_quality = ""
        best_is_slash = False
        alternatives: list[dict] = []

        # Try every root and every chord template
        for root_pc in range(12):
            for quality, template in _CHORD_TEMPLATES.items():
                expected = set((root_pc + iv) % 12 for iv in template)
                match_count = len(expected & set(pcs))
                total = len(expected)
                if match_count < max(2, total - 1):
                    continue

                # Score: match ratio + bass alignment bonus
                score = match_count / total
                if root_pc == bass_pc:
                    score += 0.25  # bass-root alignment (from design_philosophy)
                elif bass_pc in expected:
                    score += 0.1   # bass is a chord tone (inversion)

                # Prefer more specific (longer) templates when tied
                score += len(template) * 0.01

                # sus4 priority: if 4th present and 3rd absent, boost sus4
                fourth_pc = (root_pc + 5) % 12
                third_pc_maj = (root_pc + 4) % 12
                third_pc_min = (root_pc + 3) % 12
                if quality in ("sus4", "7sus4"):
                    if fourth_pc in pcs and third_pc_maj not in pcs and third_pc_min not in pcs:
                        score += 0.15

                root_name = _PC_NAMES[root_pc]
                label = f"{root_name}{quality}" if quality != "maj" else root_name
                is_slash = (bass_pc != root_pc and bass_pc in expected)
                if is_slash:
                    bass_name = _PC_NAMES[bass_pc]
                    label = f"{label}/{bass_name}"

                entry = {
                    "label": label, "root": root_name, "quality": quality,
                    "score": round(score, 3), "is_slash": is_slash,
                }

                if score > best_score:
                    if best_score > 0:
                        alternatives.append({
                            "label": best_label, "confidence": round(best_score, 3)
                        })
                    best_score = score
                    best_label = label
                    best_root = root_name
                    best_quality = quality
                    best_is_slash = is_slash
                elif score > 0.5:
                    alternatives.append({"label": label, "confidence": round(score, 3)})

        # Keep top-3 alternatives
        alternatives = sorted(alternatives, key=lambda x: x["confidence"], reverse=True)[:3]

        return {
            "label": best_label,
            "root": best_root,
            "quality": best_quality,
            "bass": _PC_NAMES[bass_pc],
            "confidence": round(min(1.0, best_score), 3),
            "alternatives": alternatives,
            "pitch_classes": [_PC_NAMES[pc] for pc in pcs],
            "is_slash": best_is_slash,
        }

    # ------------------------------------------------------------------
    # 2. Track-level Harmony Analysis
    # ------------------------------------------------------------------

    def analyze_harmony(
        self,
        track: Track,
        key: str = "C",
        scale: str = "minor",
        time_sig_num: int = 4,
        time_sig_den: int = 4,
    ) -> dict:
        """Analyze a MIDI track and return per-segment chord labels.

        Follows the analysis pipeline from the rule DB:
        bass-first, structural vs surface separation, arpeggio awareness.
        """
        if not track.notes:
            return {
                "segments": [],
                "key_estimate": key,
                "meter_verified": True,
                "overall_score": 0,
                "issues": ["Track is empty"],
            }

        # Determine segmentation window (half-bar for 4/4)
        beat_per_bar = time_sig_num
        bar_ticks = _BEAT * beat_per_bar
        window_ticks = bar_ticks // 2  # half-bar segmentation

        total_ticks = max(n.end_tick for n in track.notes)
        num_windows = max(1, int(math.ceil(total_ticks / window_ticks)))

        segments: list[dict] = []
        prev_label = ""

        for i in range(num_windows):
            win_start = i * window_ticks
            win_end = win_start + window_ticks
            notes_in_win = track.get_notes_in_range(win_start, win_end)

            if not notes_in_win:
                segments.append({
                    "start_tick": win_start,
                    "end_tick": win_end,
                    "bar": i // 2 + 1,
                    "beat_position": "1" if i % 2 == 0 else "3",
                    "chord": prev_label or "N.C.",
                    "confidence": 0.0,
                    "notes_count": 0,
                    "bass": None,
                    "is_continuation": True,
                })
                continue

            # Pipeline step: identify structural bass (lowest, longest note)
            bass_candidates = sorted(notes_in_win, key=lambda n: (n.pitch, -n.duration_ticks))
            bass_note = bass_candidates[0]

            # Pipeline step: collect structural pitches
            # Weight by duration (humanized timing tolerance from rule DB)
            structural_pitches = self._extract_structural_pitches(
                notes_in_win, win_start, win_end, window_ticks
            )

            # Pipeline step: identify chord (bass-first approach)
            chord_info = self.identify_chord(structural_pitches, bass_note.pitch)

            # Pipeline step: check if this is a continuation of the previous chord
            is_continuation = (chord_info["label"] == prev_label and
                               chord_info["confidence"] < 0.7)

            segments.append({
                "start_tick": win_start,
                "end_tick": win_end,
                "bar": i // 2 + 1,
                "beat_position": "1" if i % 2 == 0 else "3",
                "chord": chord_info["label"],
                "confidence": chord_info["confidence"],
                "root": chord_info["root"],
                "quality": chord_info["quality"],
                "bass": chord_info["bass"],
                "alternatives": chord_info["alternatives"],
                "is_slash": chord_info["is_slash"],
                "notes_count": len(notes_in_win),
                "is_continuation": is_continuation,
            })
            prev_label = chord_info["label"]

        # Merge consecutive continuations into bar-level labels
        merged = self._merge_segments(segments)

        # Score the overall analysis
        avg_confidence = np.mean([s["confidence"] for s in merged if s["confidence"] > 0])
        overall_score = int(round(float(avg_confidence) * 100)) if not np.isnan(avg_confidence) else 0

        issues = []
        low_conf = [s for s in merged if 0 < s["confidence"] < 0.5]
        if low_conf:
            issues.append(f"{len(low_conf)} segment(s) with low confidence")
        slash_count = sum(1 for s in merged if s.get("is_slash"))
        if slash_count > len(merged) * 0.5:
            issues.append("Many slash chords — bass line may be independent")

        return {
            "segments": merged,
            "key_estimate": key,
            "meter_verified": True,
            "overall_score": overall_score,
            "chord_count": len(set(s["chord"] for s in merged if s["chord"] != "N.C.")),
            "issues": issues,
        }

    def _extract_structural_pitches(
        self,
        notes: list[Note],
        win_start: int,
        win_end: int,
        window_ticks: int,
    ) -> list[int]:
        """Extract structurally significant pitches, filtering surface notes.

        Follows rule DB: duration occupancy > 25% of window = structural.
        Short arpeggio notes contribute pitch class but not re-label authority.
        """
        threshold = window_ticks * 0.2
        structural = []
        for n in notes:
            # Clip note to window boundaries
            effective_start = max(n.start_tick, win_start)
            effective_end = min(n.end_tick, win_end)
            occupancy = effective_end - effective_start
            if occupancy >= threshold:
                structural.append(n.pitch)
            elif n.velocity > 80:
                # High-velocity short notes still count (accent rule)
                structural.append(n.pitch)

        if not structural:
            # Fallback: use all pitches
            structural = [n.pitch for n in notes]

        return structural

    def _merge_segments(self, segments: list[dict]) -> list[dict]:
        """Merge consecutive half-bar segments with the same chord into bar-level."""
        if not segments:
            return []

        merged = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            if (seg["chord"] == prev["chord"] and
                    seg.get("is_continuation", False) and
                    seg["bar"] == prev["bar"]):
                prev["end_tick"] = seg["end_tick"]
                prev["notes_count"] += seg["notes_count"]
            else:
                merged.append(seg.copy())
        return merged

    # ------------------------------------------------------------------
    # 3. Voicing Generation
    # ------------------------------------------------------------------

    # Degree-name to semitone offset mapping for voicing template resolution
    _DEGREE_TO_SEMITONE = {
        "1": 0, "b2": 1, "2": 2, "b3": 3, "3": 4, "4": 5, "b5": 6,
        "5": 7, "#5": 8, "6": 9, "b7": 10, "7": 11,
        "b9": 1, "9": 2, "#9": 3, "11": 5, "#11": 6, "b13": 8, "13": 9,
        "10": 16, "b10": 15,  # 10th = 3rd + octave
    }

    def _resolve_degree(self, degree_str: str, quality: str) -> Optional[int]:
        """Resolve a degree string like '3_or_b3' or '7_or_6_or_b7' to semitone offset.

        Quality-aware: minor chords get b3/b7, major get 3/7, dominant get 3/b7.
        """
        parts = degree_str.replace("_optional", "").split("_or_")
        parts = [p.strip() for p in parts if p.strip()]

        minor_qualities = {"min", "m7", "m7b5", "dim", "dim7", "m9", "m6", "madd9"}
        dominant_qualities = {"7", "7sus4", "7b9", "7#9", "9", "13"}
        is_minor = quality in minor_qualities
        is_dominant = quality in dominant_qualities
        # b7 chords: dominant + minor7 families
        uses_b7 = is_minor or is_dominant

        for part in parts:
            # --- 3rd handling ---
            if part == "3" and is_minor:
                continue  # minor chords skip major 3rd
            if part == "b3" and not is_minor:
                continue  # major/dominant chords skip minor 3rd

            # --- 7th handling (the critical fix) ---
            if part == "7":
                if uses_b7:
                    return 10  # b7 for dominant and minor7 chords
                else:
                    return 11  # major 7 for maj7 chords
            if part == "b7":
                return 10
            if part == "6":
                return 9

            # --- Standard lookup ---
            if part in self._DEGREE_TO_SEMITONE:
                return self._DEGREE_TO_SEMITONE[part]

        # Fallback
        first = parts[0] if parts else ""
        return self._DEGREE_TO_SEMITONE.get(first)

    def _select_voicing_template(self, quality: str, style: str, has_melody: bool) -> Optional[dict]:
        """Select the best voicing template from Rule DB for this chord quality and style."""
        candidates = []
        for vt in self.voicing_templates:
            applies = vt.get("applies_to", [])
            if quality in applies or any(quality.startswith(a.split("_")[0]) for a in applies):
                candidates.append(vt)

        if not candidates:
            return None

        # Prefer melody-support template when melody is present
        if has_melody:
            for c in candidates:
                if "melody" in c.get("id", ""):
                    return c

        # Style-based selection
        style_map = {
            "jazz": ["vt_rootless_A", "vt_shell_root"],
            "ballad": ["vt_spread_ballad", "vt_ballad_root10"],
            "pop": ["vt_shell_root", "vt_spread_ballad"],
            "classical": ["vt_spread_ballad", "vt_shell_root"],
        }
        preferred = style_map.get(style, ["vt_shell_root"])
        for pref_id in preferred:
            for c in candidates:
                if c.get("id") == pref_id:
                    return c

        return candidates[0]

    def _get_inversion_bass(
        self, root_pc: int, quality: str, chord_function: str,
        prev_bass_pc: Optional[int], bass_octave: int,
    ) -> tuple[int, str]:
        """Select bass note using Rule DB inversion rules.

        Returns (bass_midi, inversion_description).
        """
        # Map chord function to inversion rule
        func_map = {
            "tonic": "inv_tonic_stability",
            "predominant": "inv_predominant_flex",
            "dominant": "inv_dominant_resolution_bias",
        }
        rule_id = func_map.get(chord_function, "inv_tonic_stability")

        # Find matching rule
        rule = None
        for ir in self.inversion_rules:
            if ir.get("id") == rule_id:
                rule = ir
                break

        if not rule:
            bass_midi = (bass_octave + 1) * 12 + root_pc
            return bass_midi, "root (no inversion rule)"

        inversions = rule.get("preferred_inversions", [])
        template = _CHORD_TEMPLATES.get(quality, [0, 4, 7])

        best_score = -1
        best_bass_pc = root_pc
        best_desc = "root"

        for inv in inversions:
            degree = inv.get("bass_degree", "1")
            score = inv.get("score", 0.5)

            sem = self._DEGREE_TO_SEMITONE.get(degree)
            if sem is None:
                continue
            # Only allow degrees that are in the chord
            if sem not in template and sem % 12 not in [t % 12 for t in template]:
                continue

            candidate_pc = (root_pc + sem) % 12

            # Bonus for smooth bass motion from previous chord
            if prev_bass_pc is not None:
                dist = min(abs(candidate_pc - prev_bass_pc), 12 - abs(candidate_pc - prev_bass_pc))
                if dist <= 2:
                    score += 0.15  # Stepwise bass motion bonus

            if score > best_score:
                best_score = score
                best_bass_pc = candidate_pc
                best_desc = degree

        bass_midi = (bass_octave + 1) * 12 + best_bass_pc
        return bass_midi, best_desc

    def _detect_chord_function(self, quality: str) -> str:
        """Detect harmonic function (tonic/predominant/dominant) from quality."""
        if quality in ("7", "7sus4", "7b9", "7#9", "dim7"):
            return "dominant"
        if quality in ("m7", "m7b5", "madd9", "m6"):
            return "predominant"
        return "tonic"

    def _check_hard_constraints(
        self, pitches: list[int], melody_pitch: Optional[int]
    ) -> list[str]:
        """Check voicing against hard constraints from Rule DB. Return violations."""
        violations = []
        if not pitches:
            return violations

        for hc in self.hard_constraints:
            hc_id = hc.get("id", "")
            hc_type = hc.get("type", "")

            # HC: melody minor 9th clash
            if hc_type == "melody_clash" and melody_pitch is not None:
                forbidden = hc.get("forbidden_intervals_semitones", [1, -1, 11, -11, 13, -13])
                top_note = max(pitches)
                interval = top_note - melody_pitch
                if interval in forbidden:
                    violations.append(f"HC {hc_id}: minor 9th clash (interval {interval})")

            # HC: unplayable span
            elif hc_type == "playability":
                lh_max = hc.get("left_hand_max_semitones", 12)
                rh_max = hc.get("right_hand_max_semitones", 11)
                total_span = pitches[-1] - pitches[0] if len(pitches) >= 2 else 0
                if total_span > lh_max + rh_max:
                    violations.append(f"HC {hc_id}: span {total_span} exceeds {lh_max}+{rh_max}")

            # HC: low register mud cluster
            elif hc_type == "register_density":
                cond = hc.get("forbidden_if", {})
                below = cond.get("lowest_note_below_midi", 48)
                interval_lte = cond.get("adjacent_interval_semitones_lte", 2)
                simul_gte = cond.get("simultaneous_notes_gte", 3)
                low_notes = [p for p in pitches if p < below]
                if len(low_notes) >= simul_gte:
                    for i in range(len(low_notes) - 1):
                        if low_notes[i + 1] - low_notes[i] <= interval_lte:
                            violations.append(f"HC {hc_id}: mud cluster below MIDI {below}")
                            break

            # HC: cross-hand
            elif hc_type == "hand_order" and len(pitches) >= 3:
                mid = len(pitches) // 2
                lh_top = pitches[mid - 1] if mid > 0 else pitches[0]
                rh_bottom = pitches[mid]
                if rh_bottom < lh_top:
                    violations.append(f"HC {hc_id}: RH below LH")

        return violations

    def _apply_melody_alignment(
        self, rh_pitches: list[int], melody_pitch: int, quality: str
    ) -> tuple[list[int], list[str]]:
        """Apply melody alignment rules from Rule DB. Return (adjusted_pitches, applied_rules)."""
        applied = []
        result = list(rh_pitches)

        for mr in self.melody_rules:
            mr_id = mr.get("id", "")
            mode = mr.get("mode", "")

            # mar_avoid_minor9_clash
            if mr_id == "mar_avoid_minor9_clash":
                forbidden = mr.get("forbidden_intervals_against_melody_on_strong_beat", [1, 13, -1, -13])
                new_result = []
                for p in result:
                    interval = p - melody_pitch
                    if interval in forbidden:
                        applied.append(f"MAR {mr_id}: removed {midi_to_note_name(p)} (interval {interval})")
                    else:
                        new_result.append(p)
                result = new_result if new_result else result  # Don't empty the voicing

            # mar_melody_declared_function_tone_dedup
            elif mr_id == "mar_melody_declared_function_tone_dedup":
                melody_pc = melody_pitch % 12
                # Don't duplicate melody's pitch class in upper register close by
                new_result = []
                for p in result:
                    if p % 12 == melody_pc and abs(p - melody_pitch) <= 12:
                        applied.append(f"MAR {mr_id}: removed {midi_to_note_name(p)} (duplicates melody)")
                    else:
                        new_result.append(p)
                result = new_result if new_result else result

            # mar_prefer_melody_as_top_note_when_stable
            elif mr_id == "mar_prefer_melody_as_top_note_when_stable":
                # Ensure accompaniment stays below melody
                result = [p for p in result if p < melody_pitch or p - melody_pitch > 12]
                if not result:
                    result = list(rh_pitches)  # Fallback

        return result, applied

    def generate_voicing(
        self,
        chord_label: str,
        bass_octave: int = 3,
        rh_octave: int = 4,
        melody_pitch: Optional[int] = None,
        style: str = "pop",
        with_rationale: bool = False,
        prev_chord: Optional[str] = None,
        prev_bass_pc: Optional[int] = None,
    ) -> list[int] | tuple[list[int], dict]:
        """Generate a voiced chord using Rule DB v2.07 voicing templates,
        inversion rules, hard constraints, and melody alignment.

        When with_rationale=True, returns (pitches, rationale_dict).
        """
        rationale: list[str] = []
        constraints_applied: list[str] = []

        root_name, quality = self._parse_chord_label(chord_label)
        if root_name is None:
            empty_report = {"steps": [], "constraints": [], "warnings": ["Unparseable chord label"]}
            return ([], empty_report) if with_rationale else []

        root_pc = _PC_NAMES.index(root_name) if root_name in _PC_NAMES else 0
        rationale.append(f"Chord: {chord_label} -> root={root_name}(pc={root_pc}), quality={quality}")

        # --- Step 1: Select voicing template from Rule DB ---
        vt = self._select_voicing_template(quality, style, melody_pitch is not None)
        using_db_template = False

        if vt:
            vt_name = vt.get("name", vt.get("id", "?"))
            rationale.append(f"Voicing template: {vt_name} (Rule DB)")
            using_db_template = True

            # Resolve LH and RH degrees from template
            lh_degrees = vt.get("hands", {}).get("left_hand", ["1"])
            rh_degrees = vt.get("hands", {}).get("right_hand", ["3_or_b3", "5_or_tension"])
        else:
            rationale.append("Voicing template: fallback (no DB match)")
            lh_degrees = ["1"]
            rh_degrees = ["3_or_b3", "5", "7_or_b7"]

        # --- Step 2: Determine bass via inversion rules ---
        chord_func = self._detect_chord_function(quality)
        bass_midi, inv_desc = self._get_inversion_bass(
            root_pc, quality, chord_func, prev_bass_pc, bass_octave
        )
        rationale.append(f"Bass: {midi_to_note_name(bass_midi)} (function={chord_func}, inversion={inv_desc})")
        if inv_desc != "1" and inv_desc != "root":
            constraints_applied.append(f"Inversion rule: bass on {inv_desc} (function={chord_func})")

        # --- Step 3: Build LH pitches from template degrees ---
        lh_pitches = [bass_midi]
        for deg_str in lh_degrees[1:]:  # Skip first (already bass)
            sem = self._resolve_degree(deg_str, quality)
            if sem is not None:
                p = (bass_octave + 1) * 12 + (root_pc + sem) % 12
                while p <= bass_midi:
                    p += 12
                # Keep LH within reach
                if abs(p - bass_midi) <= self.playability.get("left_hand_max_semitones", 12):
                    lh_pitches.append(p)

        # --- Step 4: Build RH pitches from template degrees ---
        rh_pitches = []
        for deg_str in rh_degrees:
            if "guide_tone" in deg_str:
                # Guide tone = 3rd or 7th depending on quality
                sem = self._resolve_degree("3_or_b3", quality)
            elif "tension" in deg_str:
                sem = self._resolve_degree("9", quality)
                if sem is None:
                    sem = self._resolve_degree("5", quality)
            else:
                sem = self._resolve_degree(deg_str, quality)
            if sem is not None:
                p = (rh_octave + 1) * 12 + (root_pc + sem) % 12
                while p <= bass_midi:
                    p += 12
                rh_pitches.append(p)

        rh_labels = [midi_to_note_name(p) for p in rh_pitches]
        rationale.append(f"LH: {[midi_to_note_name(p) for p in lh_pitches]}")
        rationale.append(f"RH: {rh_labels}")

        # --- Step 5: Apply melody alignment rules ---
        if melody_pitch is not None:
            rh_pitches, mel_applied = self._apply_melody_alignment(rh_pitches, melody_pitch, quality)
            for ma in mel_applied:
                constraints_applied.append(ma)

        # --- Step 6: Check hard constraints ---
        all_pitches = sorted(set(lh_pitches + rh_pitches))
        hc_violations = self._check_hard_constraints(all_pitches, melody_pitch)
        for v in hc_violations:
            constraints_applied.append(v)

        # If hard constraint violated, try to fix
        if hc_violations:
            # Remove the offending top note and retry
            if len(rh_pitches) > 1 and melody_pitch is not None:
                top = max(rh_pitches)
                interval = top - melody_pitch
                if abs(interval) in [1, 11, 13]:
                    rh_pitches.remove(top)
                    constraints_applied.append(f"Fix: removed top {midi_to_note_name(top)} to resolve clash")

        # --- Step 7: Playability check (RH span) ---
        rh_max_span = self.playability.get("right_hand_max_semitones", 11)
        if rh_pitches and max(rh_pitches) - min(rh_pitches) > rh_max_span:
            while max(rh_pitches) - min(rh_pitches) > rh_max_span and len(rh_pitches) > 2:
                removed = rh_pitches.pop()
                constraints_applied.append(f"RH span limit: removed {midi_to_note_name(removed)}")

        # --- Step 8: Low register rules ---
        low_rules = self.playability.get("low_register_interval_rules", [])
        final_pitches = list(lh_pitches)
        for p in sorted(rh_pitches):
            ok = True
            for rule in low_rules:
                below = rule.get("below_midi", 0)
                forbid = rule.get("forbid_intervals", [])
                if p < below:
                    interval = p - bass_midi
                    if interval in forbid:
                        ok = False
                        constraints_applied.append(
                            f"Low register: removed {midi_to_note_name(p)} (interval {interval})"
                        )
                        break
            if ok:
                final_pitches.append(p)

        result = sorted(set(final_pitches))

        if with_rationale:
            final_names = [midi_to_note_name(p) for p in result]
            span = result[-1] - result[0] if len(result) >= 2 else 0
            report = {
                "chord": chord_label,
                "root": root_name,
                "quality": quality,
                "voicing_template": vt.get("name", "fallback") if vt else "fallback",
                "chord_function": chord_func,
                "inversion": inv_desc,
                "steps": rationale,
                "constraints": constraints_applied,
                "result": final_names,
                "total_span": span,
                "voice_count": len(result),
                "rules_enforced": {
                    "voicing_templates": using_db_template,
                    "inversion_rules": inv_desc != "1",
                    "hard_constraints": len(hc_violations),
                    "melody_alignment": len([c for c in constraints_applied if "MAR" in c]),
                    "playability": True,
                    "low_register": True,
                },
                "warnings": [],
            }
            if not constraints_applied:
                report["warnings"].append("No constraints triggered")
            return result, report

        return result

    def generate_voicing_track(
        self,
        track: Track,
        key: str = "C",
        scale: str = "minor",
        melody_track: Optional[Track] = None,
        style: str = "pop",
        octave: int = 4,
    ) -> Track:
        """Analyze harmony in *track* and generate a new voicing track.

        Uses the full rule DB pipeline: analyze -> label -> generate voicings
        with melody protection and voice-leading continuity.
        """
        analysis = self.analyze_harmony(track, key, scale)
        segments = analysis.get("segments", [])

        notes: list[Note] = []
        prev_pitches: list[int] = []

        for seg in segments:
            chord_label = seg.get("chord", "N.C.")
            if chord_label == "N.C.":
                continue

            start = seg["start_tick"]
            end = seg["end_tick"]
            duration = end - start

            # Get melody pitch at this segment for melody protection
            melody_p = None
            if melody_track:
                mel_notes = melody_track.get_notes_in_range(start, end)
                if mel_notes:
                    melody_p = max(mel_notes, key=lambda n: n.duration_ticks).pitch

            voicing_pitches = self.generate_voicing(
                chord_label,
                bass_octave=octave - 1,
                rh_octave=octave,
                melody_pitch=melody_p,
                style=style,
            )

            # Voice leading: minimize movement from previous voicing
            if prev_pitches and voicing_pitches:
                voicing_pitches = self._apply_voice_leading(prev_pitches, voicing_pitches)

            # Create notes
            for i, pitch in enumerate(voicing_pitches):
                vel = 70 if i == 0 else 60  # Bass slightly louder
                role = "bass" if i == 0 else ("root" if i == 1 else "third")
                notes.append(Note(
                    pitch=pitch,
                    velocity=vel,
                    start_tick=start,
                    duration_ticks=max(_BEAT // 2, duration - _BEAT // 8),
                    role=role,
                ))

            prev_pitches = voicing_pitches

        return Track(name="AI Voicing", notes=notes, color="#CF9FFF")

    def _find_progression_rule(
        self, prev_quality: str, cur_quality: str
    ) -> Optional[dict]:
        """Find a matching progression resolution rule from Rule DB."""
        for pr in self.progression_rules:
            prog = pr.get("progression", [])
            if len(prog) >= 2:
                # Match last two: prev_quality -> cur_quality
                if prog[0] == prev_quality and prog[1] == cur_quality:
                    return pr
                # Partial match: dominant patterns
                if prev_quality in ("7", "7sus4") and prog[0] in ("7", "V7/vi", "X7"):
                    if cur_quality in ("maj7", "m7") and prog[1] in ("maj7", "m7", "maj7_or_m7_target", "target_diatonic_or_tonicized_chord", "vi_or_vi7"):
                        return pr
        return None

    def _get_priority_tones(self, quality: str) -> list[tuple[int, float]]:
        """Get priority tones (semitone, score) from chord_quality_rules."""
        for cq in self.chord_quality_rules:
            if cq.get("chord_quality") == quality:
                result = []
                for pt in cq.get("priority_tones", []):
                    deg = pt.get("degree", "1")
                    sem = self._DEGREE_TO_SEMITONE.get(deg)
                    if sem is not None:
                        result.append((sem, pt.get("score", 0.5)))
                return result
        return []

    def _score_soft_constraints(
        self, prev_pitches: list[int], candidate: list[int]
    ) -> float:
        """Score a voicing candidate against soft constraints. Higher = better."""
        score = 0.0

        if len(prev_pitches) < 2 or len(candidate) < 2:
            return score

        prev_top = max(prev_pitches)
        cur_top = max(candidate)
        top_interval = cur_top - prev_top

        for sc in self.soft_constraints:
            sc_id = sc.get("id", "")
            sc_type = sc.get("type", "")

            # sc_stepwise_top_note: prefer small top-note movement
            if sc_id == "sc_stepwise_top_note":
                preferred = sc.get("preferred_intervals_semitones", [0, 1, 2, -1, -2])
                discouraged = sc.get("discouraged_intervals_semitones", [])
                if top_interval in preferred:
                    score += 1.0
                elif top_interval in discouraged:
                    score -= 1.0
                else:
                    score += 0.3  # acceptable range

            # sc_common_tone_retention: prefer shared notes
            elif sc_id == "sc_common_tone_retention":
                prev_pcs = set(p % 12 for p in prev_pitches[1:])
                cur_pcs = set(p % 12 for p in candidate[1:])
                common = len(prev_pcs & cur_pcs)
                score += common * 0.5

            # sc_inner_voice_min_motion: prefer small inner voice movement
            elif sc_id == "sc_inner_voice_min_motion":
                prev_inner = prev_pitches[1:-1] if len(prev_pitches) > 2 else []
                cur_inner = candidate[1:-1] if len(candidate) > 2 else []
                if prev_inner and cur_inner:
                    total_motion = sum(
                        min(abs(c - p) for p in prev_inner)
                        for c in cur_inner
                    ) / len(cur_inner)
                    if total_motion <= 2:
                        score += 0.8
                    elif total_motion <= 4:
                        score += 0.4

            # sc_penalize_static_close_position_defaults
            elif sc_id == "sc_penalize_static_close_position_defaults":
                if len(candidate) >= 3:
                    upper = sorted(candidate[1:])
                    intervals = [upper[i+1] - upper[i] for i in range(len(upper)-1)]
                    # Close position = all intervals 3-4 semitones
                    if all(2 <= iv <= 5 for iv in intervals):
                        score -= 0.5  # Penalize default stacking

            # sc_prefer_contextual_inversion_from_melody_and_bass
            elif sc_id == "sc_prefer_contextual_inversion_from_melody_and_bass":
                # Smooth bass motion bonus
                if len(prev_pitches) >= 1 and len(candidate) >= 1:
                    bass_motion = abs(candidate[0] - prev_pitches[0])
                    if bass_motion <= 2:
                        score += 0.6
                    elif bass_motion <= 5:
                        score += 0.3

        return score

    def _apply_voice_leading(
        self, prev: list[int], current: list[int],
        prev_quality: str = "", cur_quality: str = "",
        root_pc: int = 0,
    ) -> list[int]:
        """Apply voice leading using Rule DB soft constraints and progression rules.

        Bass note (first element) is always preserved.
        Progression resolution rules guide specific voice movements (ii-V, V-I).
        Soft constraints score candidate voicings for stepwise top, common tones, etc.
        """
        if len(current) <= 1:
            return current

        bass = current[0]
        upper = list(current[1:])
        prev_upper = list(prev[1:]) if len(prev) > 1 else []

        if not prev_upper or not upper:
            return current

        # --- Progression resolution: guide-tone specific voice leading ---
        pr = self._find_progression_rule(prev_quality, cur_quality)
        guide_adjustments: dict[int, int] = {}  # cur_pc -> target_pitch

        if pr:
            for gt in pr.get("guide_tone_rules", []):
                from_deg = gt.get("from_degree", "")
                to_deg = gt.get("to_degree", "")
                motion = gt.get("motion", "")

                from_sem = self._DEGREE_TO_SEMITONE.get(from_deg)
                to_sem = self._DEGREE_TO_SEMITONE.get(to_deg.split("_or_")[0])
                if from_sem is None or to_sem is None:
                    continue

                # Find the prev note matching from_deg
                prev_root_pc = prev[0] % 12 if prev else 0
                from_pc = (prev_root_pc + from_sem) % 12
                to_pc = (root_pc + to_sem) % 12

                # Find matching prev pitch
                for pv in prev_upper:
                    if pv % 12 == from_pc:
                        # Resolve to closest target
                        if "down_semitone" in motion:
                            target = pv - 1
                        elif "up_semitone" in motion:
                            target = pv + 1
                        elif "common_tone" in motion:
                            target = pv  # Hold
                        else:
                            target = pv  # Default hold
                        guide_adjustments[to_pc] = target
                        break

        # --- Apply adjustments to upper voices ---
        adjusted = []
        for cv in upper:
            cv_pc = cv % 12
            if cv_pc in guide_adjustments:
                # Use guide-tone resolution
                target = guide_adjustments[cv_pc]
                # Ensure it's in a reasonable range
                if abs(target - cv) <= 14 and target > bass:
                    adjusted.append(target)
                else:
                    adjusted.append(cv)
            else:
                # Standard closest-voice approach
                best_pitch = cv
                best_dist = 999
                for pv in prev_upper:
                    for candidate in [cv, cv - 12, cv + 12]:
                        if candidate <= bass or candidate > 127 or candidate < 0:
                            continue
                        d = abs(candidate - pv)
                        if d < best_dist:
                            best_dist = d
                            best_pitch = candidate
                adjusted.append(best_pitch)

        result = [bass] + sorted(adjusted)

        # --- Score with soft constraints and pick best octave variant ---
        # Generate a few candidates by shifting inner voices
        best = result
        best_score = self._score_soft_constraints(prev, result)

        # Try alternative: swap one inner voice octave
        for i in range(1, len(result)):
            alt = list(result)
            alt[i] = alt[i] + 12 if alt[i] + 12 <= 127 else alt[i] - 12
            if alt[i] > bass and alt[i] > 0:
                alt_sorted = [alt[0]] + sorted(alt[1:])
                alt_score = self._score_soft_constraints(prev, alt_sorted)
                if alt_score > best_score:
                    best = alt_sorted
                    best_score = alt_score

        return best

    def _parse_chord_label(self, label: str) -> tuple[Optional[str], str]:
        """Parse 'C#m7/B' into (root_name, quality). Returns (None, '') on failure."""
        if not label or label == "N.C.":
            return None, ""

        # Remove slash bass
        slash_idx = label.find("/")
        if slash_idx > 0:
            label = label[:slash_idx]

        # Extract root
        if len(label) >= 2 and label[1] in ("#", "b"):
            root = label[:2]
            quality_str = label[2:]
        elif label[0] in "ABCDEFG":
            root = label[0]
            quality_str = label[1:]
        else:
            return None, ""

        # Normalize root name to sharp notation
        flats_to_sharps = {"Bb": "A#", "Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#"}
        root = flats_to_sharps.get(root, root)

        # Map quality string to template key
        q_map = {
            "": "maj", "M": "maj", "Maj": "maj", "maj": "maj",
            "m": "min", "min": "min", "-": "min",
            "7": "7", "dom7": "7",
            "Maj7": "maj7", "M7": "maj7", "maj7": "maj7",
            "m7": "m7", "min7": "m7", "-7": "m7",
            "m7b5": "m7b5", "min7b5": "m7b5",
            "dim": "dim", "o": "dim", "dim7": "dim7", "o7": "dim7",
            "aug": "aug", "+": "aug",
            "sus2": "sus2", "sus4": "sus4", "sus": "sus4",
            "7sus4": "7sus4", "7sus": "7sus4",
            "add9": "add9", "madd9": "madd9",
            "6": "6", "m6": "m6",
            "9": "9", "m9": "m9", "Maj9": "maj9", "maj9": "maj9",
            "7b9": "7b9", "7#9": "7#9",
            "11": "11", "13": "13",
        }
        quality = q_map.get(quality_str, "maj")

        return root, quality

    # ------------------------------------------------------------------
    # 4. Song Form Analysis
    # ------------------------------------------------------------------

    def analyze_song_form(
        self, project: ProjectState
    ) -> dict:
        """Infer song structure (intro/verse/chorus/bridge/outro).

        Uses multi-cue scoring from the rule DB:
        - Energy curves (velocity/density changes)
        - Pattern repetition
        - Harmonic rhythm density
        - Bass motion patterns
        """
        if not project.tracks or all(not t.notes for t in project.tracks):
            return {"sections": [], "form_type": "unknown", "confidence": 0.0}

        # Combine all track notes
        all_notes = []
        for t in project.tracks:
            all_notes.extend(t.notes)
        if not all_notes:
            return {"sections": [], "form_type": "unknown", "confidence": 0.0}

        all_notes.sort(key=lambda n: n.start_tick)
        total_ticks = max(n.end_tick for n in all_notes)
        bar_ticks = _BEAT * project.time_signature.numerator

        num_bars = max(1, int(math.ceil(total_ticks / bar_ticks)))

        # Compute per-bar features
        bar_features = []
        for b in range(num_bars):
            bar_start = b * bar_ticks
            bar_end = bar_start + bar_ticks
            bar_notes = [n for n in all_notes
                         if n.end_tick > bar_start and n.start_tick < bar_end]

            density = len(bar_notes)
            avg_vel = np.mean([n.velocity for n in bar_notes]) if bar_notes else 0
            pitch_range = (max(n.pitch for n in bar_notes) - min(n.pitch for n in bar_notes)) if bar_notes else 0
            avg_pitch = np.mean([n.pitch for n in bar_notes]) if bar_notes else 60

            bar_features.append({
                "bar": b + 1,
                "start_tick": bar_start,
                "end_tick": bar_end,
                "density": density,
                "avg_velocity": float(avg_vel),
                "pitch_range": pitch_range,
                "avg_pitch": float(avg_pitch),
            })

        # Multi-cue section boundary detection
        # Look for significant changes in energy (velocity * density)
        energies = [bf["avg_velocity"] * bf["density"] for bf in bar_features]
        if not energies:
            return {"sections": [], "form_type": "unknown", "confidence": 0.0}

        max_energy = max(energies) if max(energies) > 0 else 1
        norm_energies = [e / max_energy for e in energies]

        # Detect boundaries: bars where energy changes significantly
        boundaries = [0]  # Always start at bar 0
        for i in range(1, len(norm_energies)):
            delta = abs(norm_energies[i] - norm_energies[i - 1])
            if delta > 0.25:  # 25% energy change threshold
                boundaries.append(i)

        # Also detect 4/8-bar phrase boundaries with repetition
        phrase_len = 4 if num_bars <= 32 else 8
        for b in range(phrase_len, num_bars, phrase_len):
            if b not in boundaries:
                boundaries.append(b)
        boundaries = sorted(set(boundaries))

        # Allowed labels from rule DB
        allowed_labels = self.song_form_rules.get(
            "allowed_primary_labels",
            ["intro", "verse", "prechorus", "chorus", "bridge", "outro",
             "interlude", "transition", "tag", "unknown", "hybrid"]
        )

        # Classify each section using energy profile
        sections: list[dict] = []
        for idx, boundary in enumerate(boundaries):
            next_boundary = boundaries[idx + 1] if idx + 1 < len(boundaries) else num_bars
            section_bars = list(range(boundary, next_boundary))
            if not section_bars:
                continue

            section_energies = [norm_energies[b] for b in section_bars if b < len(norm_energies)]
            avg_energy = np.mean(section_energies) if section_energies else 0

            # Heuristic section labeling
            position_ratio = boundary / max(num_bars, 1)
            label = self._classify_section(
                avg_energy, position_ratio, len(section_bars),
                idx, len(boundaries), allowed_labels
            )

            start_tick = boundary * bar_ticks
            end_tick = next_boundary * bar_ticks

            sections.append({
                "label": label,
                "start_bar": boundary + 1,
                "end_bar": next_boundary,
                "start_tick": start_tick,
                "end_tick": end_tick,
                "bars": len(section_bars),
                "avg_energy": round(float(avg_energy), 3),
                "confidence": round(0.5 + 0.3 * float(avg_energy), 3),
            })

        # Determine overall form type
        label_sequence = [s["label"] for s in sections]
        form_type = self._infer_form_type(label_sequence)
        avg_conf = np.mean([s["confidence"] for s in sections]) if sections else 0

        return {
            "sections": sections,
            "form_type": form_type,
            "confidence": round(float(avg_conf), 3),
            "total_bars": num_bars,
            "bar_features": bar_features,
        }

    def _classify_section(
        self,
        energy: float,
        position: float,
        bar_count: int,
        section_idx: int,
        total_sections: int,
        labels: list[str],
    ) -> str:
        """Classify a section based on multi-cue scoring."""
        # First/last section heuristics
        if section_idx == 0 and bar_count <= 4:
            return "intro"
        if section_idx == total_sections - 1 and position > 0.85:
            return "outro"

        # Energy-based classification
        if energy > 0.75:
            return "chorus"
        if energy > 0.5:
            if position < 0.4:
                return "verse"
            return "bridge"
        if energy > 0.3:
            if 0.2 < position < 0.5:
                return "verse"
            return "prechorus"
        return "interlude" if bar_count <= 2 else "verse"

    def _infer_form_type(self, label_sequence: list[str]) -> str:
        """Infer overall song form from section labels."""
        if not label_sequence:
            return "unknown"
        has_chorus = "chorus" in label_sequence
        has_verse = "verse" in label_sequence
        has_bridge = "bridge" in label_sequence

        if has_verse and has_chorus and has_bridge:
            return "AABA" if label_sequence.count("verse") >= 3 else "verse-chorus-bridge"
        if has_verse and has_chorus:
            return "verse-chorus"
        if has_verse:
            return "strophic"
        return "through-composed"

    # ------------------------------------------------------------------
    # 5. Playability Validation (Genre-Aware)
    # ------------------------------------------------------------------

    # Genre profiles: different genres have different playability expectations
    _GENRE_PROFILES = {
        "pop": {
            "label": "Pop / Accompaniment",
            "two_hand_span_max": 23,      # LH 12 + RH 11
            "max_simultaneous": 6,
            "max_density_per_beat": 4,
            "difficulty_ceiling": "intermediate",
            "low_register_strict": True,
        },
        "jazz": {
            "label": "Jazz",
            "two_hand_span_max": 26,      # Wider voicings
            "max_simultaneous": 8,
            "max_density_per_beat": 6,
            "difficulty_ceiling": "advanced",
            "low_register_strict": True,
        },
        "classical": {
            "label": "Classical Piano",
            "two_hand_span_max": 36,      # Virtuoso passages allowed
            "max_simultaneous": 10,
            "max_density_per_beat": 16,
            "difficulty_ceiling": "virtuoso",
            "low_register_strict": False,  # Composers write what they want
        },
        "edm": {
            "label": "EDM / Electronic",
            "two_hand_span_max": 48,      # Not hand-played
            "max_simultaneous": 16,
            "max_density_per_beat": 32,
            "difficulty_ceiling": "any",
            "low_register_strict": False,
        },
    }

    def detect_genre_profile(self, notes: list[Note]) -> str:
        """Auto-detect the most likely genre profile from note characteristics.

        Uses: note density, pitch range, simultaneous note count, velocity patterns.
        """
        if not notes:
            return "pop"

        from collections import defaultdict

        # Compute features
        tick_clusters: dict[int, list[int]] = defaultdict(list)
        for n in notes:
            tick_clusters[n.start_tick].append(n.pitch)

        # Max simultaneous notes
        max_simul = max(len(v) for v in tick_clusters.values()) if tick_clusters else 1

        # Average density (notes per beat)
        total_ticks = max(n.end_tick for n in notes) if notes else 1
        total_beats = total_ticks / _BEAT if total_ticks > 0 else 1
        density = len(notes) / total_beats

        # Pitch range
        pitches = [n.pitch for n in notes]
        pitch_range = max(pitches) - min(pitches) if pitches else 0

        # Velocity variance
        velocities = np.array([n.velocity for n in notes])
        vel_std = float(velocities.std()) if len(velocities) > 1 else 0

        # Cluster span statistics
        spans = []
        for pitches_in_tick in tick_clusters.values():
            if len(pitches_in_tick) >= 2:
                s = sorted(pitches_in_tick)
                spans.append(s[-1] - s[0])
        avg_span = np.mean(spans) if spans else 0

        # Classification logic
        if density > 8 and max_simul > 6 and pitch_range > 48:
            return "classical"
        if density > 4 and max_simul > 4 and vel_std > 15:
            return "classical"
        if avg_span > 24 and max_simul > 5:
            return "classical"
        if density > 10 and vel_std < 10:
            return "edm"
        if max_simul <= 6 and density < 6:
            if vel_std > 12:
                return "jazz"
            return "pop"

        return "pop"

    def validate_playability(
        self,
        notes: list[Note],
        genre: Optional[str] = None,
    ) -> dict:
        """Check notes against genre-appropriate playability constraints.

        Evaluates three separate dimensions:
        - playability: Can a human physically play this? (0-100)
        - difficulty:  How hard is it? (beginner/intermediate/advanced/virtuoso)
        - genre_fit:   Does it match the expected genre profile? (0-100)

        When genre is None, auto-detects from note characteristics.
        """
        if not notes:
            return {
                "score": 100, "issues": [], "pass": True,
                "difficulty": "beginner", "genre": "pop",
                "genre_fit": 100, "detail": {},
            }

        from collections import defaultdict

        # Auto-detect genre if not specified
        detected_genre = genre or self.detect_genre_profile(notes)
        profile = self._GENRE_PROFILES.get(detected_genre, self._GENRE_PROFILES["pop"])

        # Build tick clusters
        tick_clusters: dict[int, list[int]] = defaultdict(list)
        for n in notes:
            tick_clusters[n.start_tick].append(n.pitch)

        total_clusters = len(tick_clusters)
        if total_clusters == 0:
            return {
                "score": 100, "issues": [], "pass": True,
                "difficulty": "beginner", "genre": detected_genre,
                "genre_fit": 100, "detail": {},
            }

        # --- Metric 1: Span violations (percentage-based) ---
        span_max = profile["two_hand_span_max"]
        span_violations = 0
        extreme_spans = 0
        for tick, pitches in tick_clusters.items():
            if len(pitches) >= 2:
                s = sorted(pitches)
                span = s[-1] - s[0]
                if span > span_max:
                    span_violations += 1
                if span > 48:  # 4 octaves = physically impossible in one attack
                    extreme_spans += 1

        span_violation_rate = span_violations / max(total_clusters, 1)

        # --- Metric 2: Density analysis ---
        total_ticks = max(n.end_tick for n in notes)
        total_beats = max(1, total_ticks / _BEAT)
        density = len(notes) / total_beats
        density_limit = profile["max_density_per_beat"]
        density_score = min(100, int(100 * min(1.0, density_limit / max(density, 0.1))))

        # --- Metric 3: Simultaneous note count ---
        simul_counts = [len(v) for v in tick_clusters.values()]
        max_simul = max(simul_counts) if simul_counts else 0
        avg_simul = np.mean(simul_counts) if simul_counts else 0
        simul_limit = profile["max_simultaneous"]
        simul_violations = sum(1 for c in simul_counts if c > simul_limit)
        simul_violation_rate = simul_violations / max(total_clusters, 1)

        # --- Metric 4: Low register intervals ---
        low_rules = self.playability.get("low_register_interval_rules", [])
        low_violations = 0
        if profile["low_register_strict"]:
            for tick, pitches in tick_clusters.items():
                pitches_sorted = sorted(pitches)
                for rule in low_rules:
                    below = rule.get("below_midi", 0)
                    forbid = rule.get("forbid_intervals", [])
                    low_pitches = [p for p in pitches_sorted if p < below]
                    if len(low_pitches) >= 2:
                        for i in range(len(low_pitches) - 1):
                            if low_pitches[i + 1] - low_pitches[i] in forbid:
                                low_violations += 1
        low_violation_rate = low_violations / max(total_clusters, 1)

        # --- Compute Playability Score (percentage-based, not cumulative deduction) ---
        # Each metric contributes proportionally
        span_score = max(0, int(100 * (1.0 - span_violation_rate * 2)))
        simul_score = max(0, int(100 * (1.0 - simul_violation_rate * 2)))
        low_reg_score = max(0, int(100 * (1.0 - low_violation_rate * 3)))

        # Weighted combination
        playability_score = int(
            span_score * 0.35 +
            density_score * 0.15 +
            simul_score * 0.30 +
            low_reg_score * 0.20
        )
        playability_score = max(0, min(100, playability_score))

        # --- Difficulty Classification ---
        if density > 10 or max_simul > 8 or span_violation_rate > 0.3:
            difficulty = "virtuoso"
        elif density > 6 or max_simul > 6 or span_violation_rate > 0.15:
            difficulty = "advanced"
        elif density > 3 or max_simul > 4 or span_violation_rate > 0.05:
            difficulty = "intermediate"
        else:
            difficulty = "beginner"

        # --- Genre Fit Score ---
        # How well does the music match the detected genre's typical patterns?
        difficulty_levels = ["beginner", "intermediate", "advanced", "virtuoso"]
        ceiling = profile["difficulty_ceiling"]
        if ceiling == "any":
            genre_fit = 100
        else:
            ceiling_idx = difficulty_levels.index(ceiling) if ceiling in difficulty_levels else 3
            actual_idx = difficulty_levels.index(difficulty)
            if actual_idx <= ceiling_idx:
                genre_fit = 100
            else:
                genre_fit = max(30, 100 - (actual_idx - ceiling_idx) * 25)

        # --- Issues (summarized, not per-tick) ---
        issues: list[str] = []
        if span_violations > 0:
            issues.append(
                f"Span exceeds {span_max} semitones in {span_violations}/{total_clusters} "
                f"clusters ({span_violation_rate*100:.1f}%)"
            )
        if extreme_spans > 0:
            issues.append(
                f"{extreme_spans} clusters span >4 octaves (physically impossible single attack)"
            )
        if simul_violations > 0:
            issues.append(
                f">{simul_limit} simultaneous notes in {simul_violations} clusters"
            )
        if low_violations > 0:
            issues.append(
                f"{low_violations} forbidden low-register intervals"
            )

        return {
            "score": playability_score,
            "issues": issues,
            "pass": playability_score >= 60,
            "difficulty": difficulty,
            "genre": detected_genre,
            "genre_label": profile["label"],
            "genre_fit": genre_fit,
            "detail": {
                "span_score": span_score,
                "density_score": density_score,
                "simul_score": simul_score,
                "low_register_score": low_reg_score,
                "span_violations": span_violations,
                "span_violation_rate": round(span_violation_rate, 4),
                "max_simultaneous": max_simul,
                "avg_simultaneous": round(float(avg_simul), 2),
                "notes_per_beat": round(density, 2),
                "total_clusters": total_clusters,
            },
        }

    # ------------------------------------------------------------------
    # 6. Enhanced Track Analysis (integrates with AIEngine)
    # ------------------------------------------------------------------

    def analyze_track_harmony(
        self,
        track: Track,
        key: str = "C",
        scale: str = "minor",
    ) -> dict:
        """Full harmony analysis suitable for the Review Panel.

        Returns a combined result dict with harmony segments, playability,
        rule violations, and scoring model output.
        """
        harmony = self.analyze_harmony(track, key, scale)
        playability = self.validate_playability(track.notes)

        # Compute scoring model components (from rule DB scoring_model)
        components = self.scoring_model.get("components", [])
        component_scores = {}
        base_score = harmony.get("overall_score", 50)

        for comp in components:
            name = comp.get("name", "")
            weight = comp.get("weight", 0)
            if name == "harmonic_fit":
                component_scores[name] = base_score
            elif name == "playability":
                component_scores[name] = playability["score"]
            elif name == "melody_support":
                component_scores[name] = 70
            elif name == "bass_motion_coherence":
                segments = harmony.get("segments", [])
                if len(segments) > 1:
                    bass_notes = [s.get("bass", "") for s in segments if s.get("bass")]
                    unique_bass = len(set(bass_notes))
                    component_scores[name] = min(100, int(unique_bass / max(len(bass_notes), 1) * 100))
                else:
                    component_scores[name] = 50
            else:
                component_scores[name] = 60

        # Weighted final score (normalize weights)
        weighted_sum = sum(
            component_scores.get(c["name"], 50) * c.get("weight", 0)
            for c in components
        )
        total_weight = sum(c.get("weight", 0) for c in components)
        final_score = int(round(weighted_sum / total_weight)) if total_weight > 0 else base_score

        # Hard constraint violations (genre-aware: skip for virtuoso)
        hard_violations = []
        if playability.get("difficulty") not in ("virtuoso", "advanced"):
            for rule in self.hard_constraints[:5]:
                rule_id = rule.get("id", "")
                if "playability" in rule_id and playability["score"] < 80:
                    hard_violations.append(rule.get("label", rule_id))

        # Compile issues
        all_issues = harmony.get("issues", []) + playability.get("issues", [])
        if hard_violations:
            all_issues.extend([f"Hard constraint: {v}" for v in hard_violations])

        return {
            "harmony_segments": harmony.get("segments", []),
            "chord_count": harmony.get("chord_count", 0),
            "key_estimate": harmony.get("key_estimate", key),
            "playability_score": playability["score"],
            "playability_issues": playability.get("issues", []),
            "difficulty": playability.get("difficulty", "intermediate"),
            "genre_detected": playability.get("genre", "pop"),
            "genre_label": playability.get("genre_label", ""),
            "genre_fit": playability.get("genre_fit", 100),
            "playability_detail": playability.get("detail", {}),
            "component_scores": component_scores,
            "overall_score": final_score,
            "issues": all_issues,
            "rule_db_version": self.schema_version,
        }

    # ------------------------------------------------------------------
    # 7. Chord Progression from settings.json
    # ------------------------------------------------------------------

    def parse_settings_progression(
        self, chord_list: list[dict], key: str = "C", bpm: float = 120
    ) -> list[dict]:
        """Parse chord_progression from settings.json into labeled segments."""
        bar_ticks = _BAR
        cursor = 0
        segments = []

        for item in chord_list:
            chord_name = item.get("chord", "C")
            duration = item.get("duration", "full")
            dur_ticks = bar_ticks if duration == "full" else bar_ticks // 2

            root_name, quality = self._parse_chord_label(chord_name)
            segments.append({
                "chord": chord_name,
                "root": root_name,
                "quality": quality,
                "start_tick": cursor,
                "end_tick": cursor + dur_ticks,
                "duration": duration,
            })
            cursor += dur_ticks

        return segments

    def generate_from_progression(
        self,
        chord_list: list[dict],
        key: str = "C",
        scale: str = "major",
        style: str = "jazz",
        octave: int = 4,
        melody_track: Optional[Track] = None,
    ) -> Track:
        """Generate a voiced MIDI track from a settings.json chord progression.

        Uses Rule DB voicing templates, inversion rules, and progression
        resolution for guide-tone voice leading.
        """
        segments = self.parse_settings_progression(chord_list, key)
        notes: list[Note] = []
        prev_pitches: list[int] = []
        prev_chord: Optional[str] = None
        prev_bass_pc: Optional[int] = None

        for seg in segments:
            chord_label = seg["chord"]
            start = seg["start_tick"]
            end = seg["end_tick"]
            duration = end - start

            # Get melody protection
            melody_p = None
            if melody_track:
                mel_notes = melody_track.get_notes_in_range(start, end)
                if mel_notes:
                    melody_p = max(mel_notes, key=lambda n: n.duration_ticks).pitch

            voicing = self.generate_voicing(
                chord_label,
                bass_octave=octave - 1,
                rh_octave=octave,
                melody_pitch=melody_p,
                style=style,
                prev_chord=prev_chord,
                prev_bass_pc=prev_bass_pc,
            )

            if prev_pitches and voicing:
                _, cur_quality = self._parse_chord_label(chord_label)
                _, prev_q = self._parse_chord_label(prev_chord) if prev_chord else ("", "")
                root_name_cur, _ = self._parse_chord_label(chord_label)
                cur_root_pc = _PC_NAMES.index(root_name_cur) if root_name_cur in _PC_NAMES else 0
                voicing = self._apply_voice_leading(
                    prev_pitches, voicing,
                    prev_quality=prev_q, cur_quality=cur_quality,
                    root_pc=cur_root_pc,
                )

            # Style-aware rhythm
            if style in ("jazz", "lo-fi"):
                # Comp-style: staggered attack
                for i, pitch in enumerate(voicing):
                    stagger = i * 10  # slight stagger for jazz feel
                    vel = 65 + self.rng.integers(-5, 6)
                    notes.append(Note(
                        pitch=pitch,
                        velocity=int(vel),
                        start_tick=start + stagger,
                        duration_ticks=max(_BEAT // 2, duration - _BEAT // 4),
                        role="bass" if i == 0 else "third",
                    ))
            elif style == "pop":
                # Half-note chords
                for half in range(2):
                    half_start = start + half * (duration // 2)
                    half_dur = duration // 2 - _BEAT // 8
                    for i, pitch in enumerate(voicing):
                        vel = 75 if half == 0 else 65
                        notes.append(Note(
                            pitch=pitch,
                            velocity=vel,
                            start_tick=half_start,
                            duration_ticks=max(_BEAT // 4, half_dur),
                            role="bass" if i == 0 else "third",
                        ))
            else:
                # Default: sustained
                for i, pitch in enumerate(voicing):
                    notes.append(Note(
                        pitch=pitch,
                        velocity=70,
                        start_tick=start,
                        duration_ticks=max(_BEAT // 2, duration - _BEAT // 8),
                        role="bass" if i == 0 else "third",
                    ))

            prev_pitches = voicing
            prev_chord = chord_label
            prev_bass_pc = voicing[0] % 12 if voicing else None

        return Track(name="AI Harmony Voicing", notes=notes, color="#CF9FFF")
