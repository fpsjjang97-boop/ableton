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

# ---------------------------------------------------------------------------
# Scoring constants (ported from midi_analyzer v2 pipeline)
# ---------------------------------------------------------------------------

# Template vectors for cosine similarity: 12-element chroma, root boosted +0.5
_TEMPLATE_VECS: list[dict] = []  # populated in _build_all_template_vecs()

def _build_all_template_vecs() -> list[dict]:
    """Pre-build 216 template vectors (12 roots × 18 chord types)."""
    vecs = []
    for root in range(12):
        for ctype, intervals in _CHORD_TEMPLATES.items():
            pcs = frozenset((root + iv) % 12 for iv in intervals)
            vec = np.zeros(12)
            for pc in pcs:
                vec[pc] = 1.0
            vec[root] += 0.5  # root boost
            norm = np.linalg.norm(vec)
            if norm > 1e-9:
                vec = vec / norm
            vecs.append({
                "root": root,
                "chord_type": ctype,
                "pitch_classes": pcs,
                "template_vec": vec,
            })
    return vecs

_TEMPLATE_VECS = _build_all_template_vecs()

# Cosine similarity
def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

# Krumhansl-Schmuckler key profiles
_KS_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_KS_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

def _estimate_key(chroma: np.ndarray) -> tuple[int, str, float]:
    """Krumhansl-Schmuckler key estimation. Returns (root_pc, mode, correlation)."""
    if chroma.sum() < 1e-9:
        return 0, "major", 0.0
    best_root, best_mode, best_corr = 0, "major", -1.0
    for root in range(12):
        rotated = np.roll(chroma, -root)
        for mode, profile in [("major", _KS_MAJOR), ("minor", _KS_MINOR)]:
            corr = float(np.corrcoef(rotated, profile)[0, 1])
            if corr > best_corr:
                best_root, best_mode, best_corr = root, mode, corr
    return best_root, best_mode, best_corr

# Circle-of-fifths progression bonus
_CIRCLE_BONUS: dict[int, float] = {7: 0.06, 5: 0.06, 2: 0.03, 10: 0.03}

# Dominant motion constants
_DOM_TYPES = frozenset({"7", "7sus4", "7b9", "7#9", "9", "13"})
_LEADING_TYPES = frozenset({"dim", "dim7", "m7b5"})
_SUBDOM_TYPES = frozenset({"min", "m7", "m6", "m9", "madd9", "m7b5"})
_TONIC_TRIAD_TYPES = frozenset({"maj", "min", "sus4", "sus2"})
_TONIC_7TH_TYPES = frozenset({"maj7", "m7", "m9", "6", "m6", "add9", "madd9", "maj9"})

# Extension intervals for evidence checking
_EXT_INTERVALS: dict[str, int] = {
    "7": 10, "maj7": 11, "m7": 10, "m7b5": 10, "dim7": 9,
    "7sus4": 10, "7b9": 10, "7#9": 10, "9": 10, "m9": 10,
    "maj9": 11, "6": 9, "m6": 9, "add9": 2, "madd9": 2,
    "11": 10, "13": 10,
}

# Seventh chord underlying triad kind (for shell check)
_SEVENTH_TRIAD_KIND: dict[str, str] = {
    "7": "maj", "maj7": "maj", "m7": "min", "m9": "min",
    "m7b5": "dim", "dim7": "dim", "7sus4": "sus4", "7b9": "maj", "7#9": "maj",
    "6": "maj", "m6": "min", "add9": "maj", "madd9": "min",
    "9": "maj", "maj9": "maj", "11": "sus4", "13": "maj",
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
        self, pitches: list[int], bass_pitch: Optional[int] = None,
        bass_is_structural: bool = True,
    ) -> dict:
        """Identify chord using full-candidate scoring (GPT method).

        Scores ALL 12 roots × ALL qualities simultaneously.
        score = matched*2 - missing*1.2 - extra*1.5 + bass_bonus
        """
        _nc = {"label": "N.C.", "root": None, "quality": None,
               "bass": None, "confidence": 0.0, "alternatives": [],
               "pitch_classes": [], "is_slash": False}
        if not pitches:
            return _nc

        pcs_set = set(p % 12 for p in pitches)
        pcs = sorted(pcs_set)
        bass_pc = (bass_pitch % 12) if bass_pitch is not None else (min(pitches) % 12)
        bass_name = _PC_NAMES[bass_pc]

        if not bass_is_structural:
            return {**_nc, "bass": bass_name,
                    "pitch_classes": [_PC_NAMES[pc] for pc in pcs],
                    "label": "N.C.(bass-insufficient)"}

        # Score ALL candidates: 12 roots × all qualities
        candidates: list[tuple[float, int, str, bool]] = []  # (score, root, quality, is_slash)
        observed = pcs_set

        for root in range(12):
            for quality, template in _CHORD_TEMPLATES.items():
                formula = set((root + iv) % 12 for iv in template)
                inter = formula & observed
                missing = formula - observed
                extra = observed - formula

                if len(extra) > 3:
                    continue

                score = len(inter) * 2.0 - len(missing) * 1.2 - len(extra) * 1.5

                # Bass alignment (graduated)
                is_slash = root != bass_pc
                if root == bass_pc:
                    score += 0.8    # bass = root: best
                elif (bass_pc - root) % 12 in {iv % 12 for iv in template}:
                    score += 0.4    # bass = chord tone: OK (inversion)
                else:
                    score -= 0.6    # bass = non-chord tone: penalty

                # hc_sus4_branch_lock: if 4th present + no 3rd, boost sus4
                fourth = (root + 5) % 12
                maj3 = (root + 4) % 12
                min3 = (root + 3) % 12
                if root == bass_pc and fourth in observed:
                    if maj3 not in observed and min3 not in observed:
                        if quality in ("sus4", "7sus4"):
                            score += 0.5

                candidates.append((round(score, 3), root, quality, is_slash))

        if not candidates:
            return {**_nc, "bass": bass_name,
                    "pitch_classes": [_PC_NAMES[pc] for pc in pcs]}

        # Sort by score descending
        candidates.sort(key=lambda c: -c[0])

        # Build result from top candidate
        top_score, top_root, top_quality, top_is_slash = candidates[0]
        root_name = _PC_NAMES[top_root]

        label = f"{root_name}{top_quality}" if top_quality != "maj" else root_name
        if top_is_slash:
            label = f"{label}/{bass_name}"

        # Confidence: normalize score to 0-1 range
        max_possible = len(pcs_set) * 2.0 + 0.8
        confidence = round(max(0.0, min(1.0, top_score / max(max_possible, 1))), 3)

        # Alternatives (top 2-4, deduplicated labels)
        alternatives: list[dict] = []
        seen_labels = {label}
        for sc, rt, qt, sl in candidates[1:]:
            alt_root = _PC_NAMES[rt]
            alt_label = f"{alt_root}{qt}" if qt != "maj" else alt_root
            if sl:
                alt_label = f"{alt_label}/{bass_name}"
            if alt_label not in seen_labels:
                seen_labels.add(alt_label)
                alt_conf = round(max(0.0, min(1.0, sc / max(max_possible, 1))), 3)
                alternatives.append({"label": alt_label, "confidence": alt_conf})
            if len(alternatives) >= 3:
                break

        return {
            "label": label, "root": root_name, "quality": top_quality,
            "bass": bass_name, "confidence": confidence,
            "alternatives": alternatives,
            "pitch_classes": [_PC_NAMES[pc] for pc in pcs],
            "is_slash": top_is_slash,
        }

    # ------------------------------------------------------------------
    # 1b. Chroma-based Scoring Engine (v2 pipeline)
    # ------------------------------------------------------------------

    def _compute_chroma(
        self, notes: list[Note], win_start: int, win_end: int,
        beat_per_bar: int,
    ) -> tuple[np.ndarray, int, frozenset, dict, dict, frozenset]:
        """Compute weighted chroma vector for a segment.

        Returns: (chroma_12, bass_pc, pitch_classes, pc_durations, pc_velocities, pc_on_strong)
        """
        chroma = np.zeros(12)
        if not notes:
            return chroma, -1, frozenset(), {}, {}, frozenset()

        window_ticks = win_end - win_start
        pc_durations: dict[int, float] = {}
        pc_velocities: dict[int, int] = {}
        durations_raw: list[float] = []

        # Compute per-note effective duration
        note_data = []
        for n in notes:
            eff_start = max(n.start_tick, win_start)
            eff_end = min(n.end_tick, win_end)
            dur = max(0, eff_end - eff_start)
            pc = n.pitch % 12
            note_data.append((n, pc, dur))
            durations_raw.append(dur)
            pc_durations[pc] = pc_durations.get(pc, 0) + dur
            pc_velocities[pc] = max(pc_velocities.get(pc, 0), n.velocity)

        avg_dur = np.mean(durations_raw) if durations_raw else 1.0
        bass_pitch = min(notes, key=lambda n: n.pitch).pitch
        bass_pc = bass_pitch % 12

        # Beat positions for strong-beat detection
        beat_in_bar_start = ((win_start // _BEAT) % beat_per_bar) + 1
        is_downbeat = beat_in_bar_start == 1
        is_on_beat = True  # grid segments always start on beat

        pc_on_strong: set[int] = set()

        for n, pc, dur in note_data:
            if dur <= 0:
                continue
            base_weight = dur * (n.velocity / 127.0)

            # Strong beat boost
            onset_in_win = max(n.start_tick, win_start)
            onset_beat = ((onset_in_win // _BEAT) % beat_per_bar) + 1
            if onset_beat == 1 or is_on_beat:
                base_weight *= 1.2
                pc_on_strong.add(pc)

            # Bass note boost
            if n.pitch == bass_pitch:
                base_weight *= 1.4

            # Long note boost
            if avg_dur > 0 and dur > avg_dur * 1.5:
                base_weight *= 1.25

            # Short note attenuation
            if avg_dur > 0 and dur < avg_dur * 0.3:
                base_weight *= 0.65

            chroma[pc] += base_weight

        pitch_classes = frozenset(pc for pc in pc_durations if pc_durations[pc] > 0)
        return chroma, bass_pc, pitch_classes, pc_durations, pc_velocities, frozenset(pc_on_strong)

    @staticmethod
    def _same_root_tier4_eligible(bass_pc: int, chord_type: str, pcs: frozenset) -> bool:
        """Check if a same-root candidate qualifies for Tier 4 (full shell)."""
        if chord_type in ("aug", "aug7", "dim", "dim7", "m7b5"):
            return False
        triad_kind = _SEVENTH_TRIAD_KIND.get(chord_type, chord_type)
        if triad_kind == "maj":
            return (bass_pc + 4) % 12 in pcs and (bass_pc + 7) % 12 in pcs
        elif triad_kind == "min":
            return (bass_pc + 3) % 12 in pcs and (bass_pc + 7) % 12 in pcs
        elif triad_kind == "dim":
            return (bass_pc + 3) % 12 in pcs and (bass_pc + 6) % 12 in pcs
        elif triad_kind == "sus4":
            return (bass_pc + 5) % 12 in pcs and (bass_pc + 7) % 12 in pcs
        elif triad_kind == "sus2":
            return (bass_pc + 2) % 12 in pcs and (bass_pc + 7) % 12 in pcs
        elif triad_kind == "aug":
            return (bass_pc + 4) % 12 in pcs and (bass_pc + 8) % 12 in pcs
        return False

    def _build_raw_candidates(
        self, chroma: np.ndarray, bass_pc: int, pcs: frozenset,
        prev_root: Optional[int],
    ) -> list[dict]:
        """Build chord candidates using 4-tier bass-first pipeline."""
        if chroma.sum() < 1e-9 or bass_pc < 0:
            return []

        def _prog(tpl_root):
            if prev_root is None:
                return 0.0
            return _CIRCLE_BONUS.get((tpl_root - prev_root) % 12, 0.0)

        # Upper chroma for slash detection
        upper_chroma = chroma.copy()
        upper_chroma[bass_pc] *= 0.15

        rows: list[dict] = []
        seen: set[tuple] = set()

        for tpl in _TEMPLATE_VECS:
            root, ctype = tpl["root"], tpl["chord_type"]
            tpl_pcs = tpl["pitch_classes"]
            tpl_vec = tpl["template_vec"]
            key = (root, ctype, bass_pc if root != bass_pc else -1)
            if key in seen:
                continue
            seen.add(key)

            cos = _cosine_sim(chroma, tpl_vec)

            if root == bass_pc:
                # Tier 4 or 3: same-root
                if self._same_root_tier4_eligible(bass_pc, ctype, pcs):
                    tier, bonus = 4, 0.12
                else:
                    tier, bonus = 3, 0.05
                rows.append({
                    "root": root, "chord_type": ctype, "slash_bass": -1,
                    "score": cos + bonus + _prog(root), "tier": tier,
                    "tpl_pcs": tpl_pcs,
                })
            elif bass_pc in tpl_pcs:
                # Tier 3a: inversion (bass is chord tone)
                rows.append({
                    "root": root, "chord_type": ctype, "slash_bass": bass_pc,
                    "score": cos + 0.05 + _prog(root), "tier": 3,
                    "tpl_pcs": tpl_pcs,
                })
            else:
                # Try slash chord (upper structure)
                upper_sim = _cosine_sim(upper_chroma, tpl_vec)
                if upper_sim > 0.50:
                    rows.append({
                        "root": root, "chord_type": ctype, "slash_bass": bass_pc,
                        "score": upper_sim + _prog(root), "tier": 2,
                        "tpl_pcs": tpl_pcs,
                    })
                else:
                    # Tier 1: fallback root position
                    rows.append({
                        "root": root, "chord_type": ctype, "slash_bass": -1,
                        "score": cos - 0.04 + _prog(root), "tier": 1,
                        "tpl_pcs": tpl_pcs,
                    })

        # Sort by tier desc, then score desc; keep top 48 → deduplicate to 12
        rows.sort(key=lambda r: (-r["tier"], -r["score"]))
        dedup: list[dict] = []
        dedup_keys: set[tuple] = set()
        for r in rows[:48]:
            dk = (r["root"], r["chord_type"], r["slash_bass"])
            if dk not in dedup_keys:
                dedup_keys.add(dk)
                dedup.append(r)
            if len(dedup) >= 12:
                break
        return dedup

    # ── Rule adjustment functions ──

    def _adj_sus4(self, c: dict, bass_pc: int, pcs: frozenset,
                  pc_durations: dict, window_dur: float) -> float:
        root = c["root"]
        if root != bass_pc and c["slash_bass"] < 0:
            return 0.0
        effective_root = bass_pc
        fourth = (effective_root + 5) % 12
        maj3 = (effective_root + 4) % 12
        min3 = (effective_root + 3) % 12
        has_4th = fourth in pcs
        if not has_4th:
            return 0.0
        # Check if 3rd is structural
        third_dur = pc_durations.get(maj3, 0) + pc_durations.get(min3, 0)
        third_structural = (third_dur / max(window_dur, 1)) > 0.10 if window_dur > 0 else False

        ctype = c["chord_type"]
        if ctype in ("sus4", "7sus4"):
            if third_structural:
                return -0.22  # False sus4 — 3rd is actually present
            return 0.15  # Confirmed sus4
        else:
            # Non-sus4 candidate but 4th is present
            if not third_structural:
                if ctype in ("min", "m7", "m7b5"):
                    return -0.18  # Suppress minor when sus4 is more likely
        return 0.0

    def _adj_same_root_shell(self, c: dict, bass_pc: int, pcs: frozenset) -> float:
        if c["slash_bass"] >= 0 or c["root"] != bass_pc:
            return 0.0
        root = c["root"]
        # Shell definitions
        shells = [
            ({0, 4, 7, 10}, {"7", "6"}),
            ({0, 3, 7, 10}, {"m7", "m6"}),
            ({0, 4, 7, 11}, {"maj7"}),
            ({0, 4, 7}, {"maj", "7", "maj7", "6", "add9"}),
            ({0, 3, 7}, {"min", "m7", "m9", "m6", "madd9"}),
            ({0, 4, 10}, {"7"}),
            ({0, 3, 10}, {"m7", "m7b5"}),
            ({0, 4, 11}, {"maj7"}),
            ({0, 5, 7}, {"sus4", "7sus4"}),
        ]
        rel_pcs = frozenset((pc - root) % 12 for pc in pcs)
        for shell_pcs, types in shells:
            if c["chord_type"] in types and shell_pcs.issubset(rel_pcs):
                return 0.08
        # Partial shell: root + 3rd or root + 5th
        if {0, 4}.issubset(rel_pcs) or {0, 3}.issubset(rel_pcs) or {0, 7}.issubset(rel_pcs):
            return 0.04
        return 0.0

    def _adj_extension_evidence(
        self, c: dict, chroma: np.ndarray, pc_durations: dict,
        pc_on_strong: frozenset, window_dur: float,
    ) -> float:
        ext_iv = _EXT_INTERVALS.get(c["chord_type"])
        if ext_iv is None:
            return 0.0
        ext_pc = (c["root"] + ext_iv) % 12
        total_energy = chroma.sum()
        evidence = 0.0
        if total_energy > 0 and chroma[ext_pc] / total_energy >= 0.10:
            evidence += 1.0
        if window_dur > 0 and pc_durations.get(ext_pc, 0) / window_dur >= 0.15:
            evidence += 1.0
        if ext_pc in pc_on_strong:
            evidence += 1.0
        if evidence >= 2.0:
            return 0.04
        elif evidence >= 1.0:
            return -0.07
        return -0.12

    def _adj_dominant_motion(
        self, c: dict, prev_root: Optional[int], prev_type: Optional[str],
        next_bass_pc: Optional[int], bass_pc: int, pcs: frozenset,
    ) -> float:
        delta = 0.0
        root = c["root"]
        ctype = c["chord_type"]

        # Forward: this chord → next
        if next_bass_pc is not None:
            interval_to_next = (next_bass_pc - root) % 12
            if ctype in _DOM_TYPES:
                if interval_to_next == 5:  # V→I
                    delta += 0.22
                    if c["slash_bass"] >= 0:
                        delta = min(delta + 0.08, 0.30)
                elif interval_to_next == 9:  # V→vi (deceptive)
                    delta += 0.08
            elif ctype in ("maj",) and interval_to_next == 5:
                b7 = (root + 10) % 12
                delta += 0.06 if b7 in pcs else 0.04
            elif ctype in _LEADING_TYPES and interval_to_next == 1:
                delta += 0.08
            elif ctype in _SUBDOM_TYPES and interval_to_next == 7:  # ii→V
                delta += 0.05
            elif ctype in ("min", "m7") and interval_to_next == 5:
                delta += 0.03

        # Backward: prev chord → this
        if prev_root is not None and prev_type is not None:
            interval_from_prev = (root - prev_root) % 12
            if prev_type in _DOM_TYPES:
                if interval_from_prev == 5:  # prev was V, this is I
                    if ctype in _TONIC_TRIAD_TYPES:
                        delta += 0.12
                    elif ctype in _TONIC_7TH_TYPES:
                        delta += 0.09
                elif interval_from_prev == 9:  # prev was V, this is vi
                    delta += 0.09
            elif prev_type in _LEADING_TYPES and interval_from_prev == 1:
                delta += 0.08
            elif prev_type in _DOM_TYPES and ctype in _DOM_TYPES:
                delta += 0.07  # Secondary dominant chain

        return delta

    def _adj_no_third_quality(self, c: dict, bass_pc: int, pcs: frozenset) -> float:
        if c["root"] != bass_pc or c["slash_bass"] >= 0:
            return 0.0
        maj3 = (bass_pc + 4) % 12
        min3 = (bass_pc + 3) % 12
        if maj3 not in pcs and min3 not in pcs:
            if c["chord_type"] in ("maj", "min", "7", "maj7", "m7", "m7b5", "6", "m6"):
                return -0.06
        return 0.0

    def _adj_slash_bass_awareness(self, c: dict, bass_pc: int) -> float:
        if c["root"] != bass_pc and c["slash_bass"] < 0:
            return -0.06
        return 0.0

    def _adj_major_third_in_bass(self, c: dict, bass_pc: int, pcs: frozenset) -> float:
        if c["chord_type"] != "maj" or c["slash_bass"] != bass_pc:
            return 0.0
        root = c["root"]
        if (bass_pc - root) % 12 == 4:  # Bass is major 3rd
            p5 = (root + 7) % 12
            if root in pcs and bass_pc in pcs and p5 in pcs:
                return 0.20
        return 0.0

    def _adj_unexplained_strong_pc(
        self, c: dict, bass_pc: int, pc_durations: dict, window_dur: float,
    ) -> float:
        explained = set(c["tpl_pcs"])
        if c["slash_bass"] >= 0:
            explained.add(c["slash_bass"])
        explained.add(bass_pc)
        # add9 for major slash
        if c["chord_type"] == "maj" and c["slash_bass"] >= 0:
            explained.add((c["root"] + 2) % 12)
        total_penalty = 0.0
        for pc, dur in pc_durations.items():
            ratio = dur / max(window_dur, 1)
            if ratio >= 0.14 and pc not in explained:
                total_penalty -= min(0.22, 0.10 + ratio * 0.22)
        return max(total_penalty, -0.42)

    def _adj_plain_triad_over_add9_slash(self, c: dict, bass_pc: int, pcs: frozenset) -> float:
        if c["chord_type"] != "add9" or c["slash_bass"] < 0:
            return 0.0
        root = c["root"]
        if (bass_pc - root) % 12 == 4:
            p5 = (root + 7) % 12
            if root in pcs and bass_pc in pcs and p5 in pcs:
                return -0.24
        return 0.0

    def _apply_rule_adjustments(
        self, candidates: list[dict], chroma: np.ndarray, bass_pc: int,
        pcs: frozenset, pc_durations: dict, pc_velocities: dict,
        pc_on_strong: frozenset, window_dur: float,
        prev_root: Optional[int], prev_type: Optional[str],
        next_bass_pc: Optional[int],
    ) -> list[dict]:
        """Apply all 9 rule adjustment functions to candidates."""
        for c in candidates:
            adj = 0.0
            adj += self._adj_sus4(c, bass_pc, pcs, pc_durations, window_dur)
            adj += self._adj_same_root_shell(c, bass_pc, pcs)
            adj += self._adj_extension_evidence(c, chroma, pc_durations, pc_on_strong, window_dur)
            adj += self._adj_dominant_motion(c, prev_root, prev_type, next_bass_pc, bass_pc, pcs)
            adj += self._adj_no_third_quality(c, bass_pc, pcs)
            adj += self._adj_slash_bass_awareness(c, bass_pc)
            adj += self._adj_major_third_in_bass(c, bass_pc, pcs)
            adj += self._adj_unexplained_strong_pc(c, bass_pc, pc_durations, window_dur)
            adj += self._adj_plain_triad_over_add9_slash(c, bass_pc, pcs)
            c["score"] = round(c["score"] + adj, 4)
        candidates.sort(key=lambda c: -c["score"])
        return candidates[:7]

    def _score_segment(
        self, chroma: np.ndarray, bass_pc: int, pcs: frozenset,
        pc_durations: dict, pc_velocities: dict, pc_on_strong: frozenset,
        window_dur: float,
        prev_root: Optional[int], prev_type: Optional[str],
        next_bass_pc: Optional[int],
        ambiguity_threshold: float = 0.08,
    ) -> dict:
        """Score a single segment and return analysis result dict."""
        _nc = {"chord": "N.C.", "root": None, "root_pc": None, "quality": None,
               "bass": None, "confidence": 0.0, "alternatives": [],
               "is_slash": False, "was_ambiguous": False}
        if chroma.sum() < 1e-9:
            return _nc

        if bass_pc >= 0:
            candidates = self._build_raw_candidates(chroma, bass_pc, pcs, prev_root)
        else:
            # No bass: cosine scan all templates
            candidates = []
            seen: set[tuple] = set()
            for tpl in _TEMPLATE_VECS:
                root, ctype = tpl["root"], tpl["chord_type"]
                cos = _cosine_sim(chroma, tpl["template_vec"])
                prog = _CIRCLE_BONUS.get((root - prev_root) % 12, 0.0) if prev_root is not None else 0.0
                dk = (root, ctype, -1)
                if dk not in seen:
                    seen.add(dk)
                    candidates.append({
                        "root": root, "chord_type": ctype, "slash_bass": -1,
                        "score": cos + prog, "tier": 1, "tpl_pcs": tpl["pitch_classes"],
                    })
            candidates.sort(key=lambda c: -c["score"])
            candidates = candidates[:12]

        if not candidates:
            return _nc

        # Apply rules
        candidates = self._apply_rule_adjustments(
            candidates, chroma, bass_pc, pcs, pc_durations,
            pc_velocities, pc_on_strong, window_dur,
            prev_root, prev_type, next_bass_pc,
        )

        if not candidates:
            return _nc

        # Build result
        top = candidates[0]
        root_name = _PC_NAMES[top["root"]]
        bass_name = _PC_NAMES[bass_pc] if bass_pc >= 0 else None
        is_slash = top["slash_bass"] >= 0 and top["slash_bass"] != top["root"]

        ctype = top["chord_type"]
        label = f"{root_name}{ctype}" if ctype != "maj" else root_name
        if is_slash:
            label = f"{label}/{_PC_NAMES[top['slash_bass']]}"

        alternatives = []
        for alt in candidates[1:4]:
            alt_root = _PC_NAMES[alt["root"]]
            alt_label = f"{alt_root}{alt['chord_type']}" if alt["chord_type"] != "maj" else alt_root
            if alt["slash_bass"] >= 0 and alt["slash_bass"] != alt["root"]:
                alt_label = f"{alt_label}/{_PC_NAMES[alt['slash_bass']]}"
            alternatives.append({"label": alt_label, "confidence": round(alt["score"], 3)})

        was_ambiguous = (len(candidates) >= 2 and
                         (candidates[0]["score"] - candidates[1]["score"]) < ambiguity_threshold)

        return {
            "chord": label, "root": root_name, "root_pc": top["root"],
            "quality": ctype, "bass": bass_name,
            "confidence": round(max(0, min(1.0, top["score"])), 3),
            "alternatives": alternatives, "is_slash": is_slash,
            "was_ambiguous": was_ambiguous,
        }

    def _consolidate_by_measure(
        self, raw_analyses: list[dict], seg_data: list[dict],
        beat_per_bar: int, prev_root_init: Optional[int] = None,
        prev_type_init: Optional[str] = None,
        ambiguity_threshold: float = 0.08,
    ) -> list[dict]:
        """Re-score at half-bar level: sum chroma within each half-bar."""
        from collections import defaultdict

        # Group by (bar, half): half 0 = beat 1-2, half 1 = beat 3-4
        half_bar_beats = max(2, beat_per_bar // 2)
        half_groups: dict[tuple[int, int], list[int]] = defaultdict(list)
        for i, sd in enumerate(seg_data):
            bar = sd["bar"]
            beat_in_bar = sd.get("beat_in_bar", 1)
            half = 0 if beat_in_bar <= half_bar_beats else 1
            half_groups[(bar, half)].append(i)

        merged: list[dict] = []
        prev_root = prev_root_init
        prev_type = prev_type_init

        for (bar_num, half_idx) in sorted(half_groups.keys()):
            indices = half_groups[(bar_num, half_idx)]
            if not indices:
                continue
            groups = [indices]

            for grp in groups:
                if not grp:
                    continue
                # Sum chroma and merge metadata
                combined_chroma = np.zeros(12)
                combined_pcs: set[int] = set()
                combined_durations: dict[int, float] = {}
                combined_velocities: dict[int, int] = {}
                combined_on_strong: set[int] = set()
                total_dur = 0.0
                total_notes = 0

                # Bass: prefer downbeat, then longest-sounding
                group_bass_durs: dict[int, float] = defaultdict(float)
                first_bass = seg_data[grp[0]].get("bass_pc", -1)

                for i in grp:
                    sd = seg_data[i]
                    combined_chroma += sd["chroma"]
                    combined_pcs |= sd.get("pcs", set())
                    for pc, dur in sd.get("pc_durations", {}).items():
                        combined_durations[pc] = combined_durations.get(pc, 0) + dur
                    for pc, vel in sd.get("pc_velocities", {}).items():
                        combined_velocities[pc] = max(combined_velocities.get(pc, 0), vel)
                    combined_on_strong |= sd.get("pc_on_strong", set())
                    total_dur += sd.get("window_dur", _BEAT)
                    total_notes += sd.get("notes_count", 0)
                    bp = sd.get("bass_pc", -1)
                    if bp >= 0:
                        group_bass_durs[bp] += sd.get("window_dur", _BEAT)

                structural_bass = first_bass
                if group_bass_durs:
                    structural_bass = max(group_bass_durs, key=group_bass_durs.get)

                # next_bass: look at next group or next bar
                next_bass = None
                grp_last = grp[-1]
                if grp_last + 1 < len(seg_data):
                    next_bass = seg_data[grp_last + 1].get("bass_pc")

                result = self._score_segment(
                    combined_chroma, structural_bass, frozenset(combined_pcs),
                    combined_durations, combined_velocities, frozenset(combined_on_strong),
                    total_dur, prev_root, prev_type, next_bass, ambiguity_threshold,
                )

                result["start_tick"] = seg_data[grp[0]]["start_tick"]
                result["end_tick"] = seg_data[grp[-1]]["end_tick"]
                result["bar"] = bar_num
                result["beat_in_bar"] = seg_data[grp[0]].get("beat_in_bar", 1)
                result["beat_position"] = str(seg_data[grp[0]].get("beat_in_bar", 1))
                result["notes_count"] = total_notes
                result["is_continuation"] = False

                merged.append(result)
                if result.get("root_pc") is not None:
                    prev_root = result["root_pc"]
                    prev_type = result.get("quality")

        return merged

    # ------------------------------------------------------------------
    # 2. Track-level Harmony Analysis (v2 — chroma + cosine + rules)
    # ------------------------------------------------------------------

    def analyze_harmony(
        self,
        track: Track,
        key: str = "C",
        scale: str = "minor",
        time_sig_num: int = 4,
        time_sig_den: int = 4,
        **_kwargs,
    ) -> dict:
        """Analyze a MIDI track: auto chord-change detection + direct identify_chord.

        Segments are created where pitch_classes or bass actually change.
        No fixed grid — the music's own harmonic rhythm determines boundaries.
        """
        if not track.notes:
            return {
                "segments": [], "key_estimate": key, "key_confidence": 0.0,
                "meter_verified": True, "overall_score": 0, "num_segments": 0,
                "ambiguity_count": 0, "chord_count": 0,
                "issues": ["Track is empty"],
            }

        bar_ticks = _BEAT * time_sig_num

        # ── 1. Auto chord-change detection ──
        notes = sorted(track.notes, key=lambda n: n.start_tick)

        # Build micro-segments at every note boundary
        boundaries = sorted(set(
            [n.start_tick for n in notes] + [n.end_tick for n in notes]
        ))
        micros: list[dict] = []
        for i in range(len(boundaries) - 1):
            ts, te = boundaries[i], boundaries[i + 1]
            if te <= ts:
                continue
            sounding = [n for n in notes if n.start_tick < te and n.end_tick > ts]
            if not sounding:
                continue
            pcs = frozenset(n.pitch % 12 for n in sounding)
            bass_pc = min(sounding, key=lambda n: n.pitch).pitch % 12
            micros.append({"start": ts, "end": te, "pcs": pcs, "bass_pc": bass_pc})

        if not micros:
            return {
                "segments": [], "key_estimate": key, "key_confidence": 0.0,
                "meter_verified": True, "overall_score": 0, "num_segments": 0,
                "ambiguity_count": 0, "chord_count": 0,
                "issues": ["No segments (empty)"],
            }

        # Merge: same bass AND identical PCs only
        merged_boundaries: list[dict] = [dict(micros[0])]
        for m in micros[1:]:
            p = merged_boundaries[-1]
            if m["bass_pc"] == p["bass_pc"] and m["pcs"] == p["pcs"]:
                p["end"] = m["end"]
            else:
                merged_boundaries.append(dict(m))

        # Snap boundaries to beat grid and enforce minimum 1 beat
        def _snap(tick: int) -> int:
            return round(tick / _BEAT) * _BEAT

        for mb in merged_boundaries:
            mb["start"] = _snap(mb["start"])
            mb["end"] = _snap(mb["end"])

        # Remove zero-length after snap, merge consecutive same-snap
        snapped: list[dict] = []
        for mb in merged_boundaries:
            if mb["end"] <= mb["start"]:
                continue
            if snapped and mb["start"] == snapped[-1]["end"] and mb["bass_pc"] == snapped[-1]["bass_pc"] and mb["pcs"] == snapped[-1]["pcs"]:
                snapped[-1]["end"] = mb["end"]
            else:
                snapped.append(mb)

        # Enforce minimum 1 beat: absorb short segments into previous
        # Enforce maximum 4 beats: split long segments at beat grid
        _MAX_DUR = _BEAT * 4
        expanded: list[dict] = []
        for mb in snapped:
            dur = mb["end"] - mb["start"]
            if dur > _MAX_DUR:
                cursor = mb["start"]
                while cursor < mb["end"]:
                    chunk_end = min(cursor + _MAX_DUR, mb["end"])
                    if chunk_end - cursor >= _BEAT:
                        expanded.append({"start": cursor, "end": chunk_end,
                                         "pcs": mb["pcs"], "bass_pc": mb["bass_pc"]})
                    cursor = chunk_end
            else:
                expanded.append(mb)

        final_bounds: list[dict] = [expanded[0]] if expanded else []
        for m in expanded[1:]:
            if m["end"] - m["start"] < _BEAT:
                final_bounds[-1]["end"] = m["end"]
            else:
                final_bounds.append(m)

        # ── 2. Build segments with raw notes + chord labels ──
        raw_segments: list[dict] = []
        for fb in final_bounds:
            h_start, h_end = fb["start"], fb["end"]
            bar = h_start // bar_ticks + 1
            beat_in_bar = (h_start % bar_ticks) // _BEAT + 1

            notes_in = track.get_notes_in_range(h_start, h_end)
            if not notes_in:
                continue

            window_ticks = h_end - h_start
            structural = self._extract_structural_pitches(
                notes_in, h_start, h_end, max(window_ticks, 1)
            )

            onset_notes = [n for n in notes_in if n.start_tick >= h_start]
            if not onset_notes:
                onset_notes = notes_in
            bass_note = min(onset_notes, key=lambda n: (n.pitch, -n.duration_ticks))

            bass_eff_start = max(bass_note.start_tick, h_start)
            bass_eff_end = min(bass_note.end_tick, h_end)
            bass_occ = bass_eff_end - bass_eff_start
            bass_is_structural = (bass_occ >= (window_ticks * 0.08) or bass_note.velocity >= 60)

            raw_notes = []
            for n in sorted(notes_in, key=lambda n: (n.start_tick, n.pitch)):
                eff_start = max(n.start_tick, h_start)
                eff_end = min(n.end_tick, h_end)
                raw_notes.append({
                    "pitch": n.pitch,
                    "name": _PC_NAMES[n.pitch % 12] + str(n.pitch // 12 - 1),
                    "start_tick": n.start_tick,
                    "duration_ticks": n.duration_ticks,
                    "effective_duration": eff_end - eff_start,
                    "velocity": n.velocity,
                })

            pcs_sorted = sorted(set(n.pitch % 12 for n in notes_in))
            bass_info = {
                "pitch": bass_note.pitch,
                "name": _PC_NAMES[bass_note.pitch % 12] + str(bass_note.pitch // 12 - 1),
                "pc": _PC_NAMES[bass_note.pitch % 12],
            }

            chord_info = self.identify_chord(
                structural, bass_note.pitch,
                bass_is_structural=bass_is_structural,
            )

            dur_beats = round((h_end - h_start) / _BEAT, 2)
            raw_segments.append({
                "start_tick": h_start,
                "end_tick": h_end,
                "bar": bar,
                "beat_in_bar": beat_in_bar,
                "beat_position": str(beat_in_bar),
                "duration_beats": dur_beats,
                "raw_notes": raw_notes,
                "bass": bass_info,
                "pitch_classes": [_PC_NAMES[pc] for pc in pcs_sorted],
                "notes_count": len(notes_in),
                "chord": chord_info["label"],
                "root": chord_info["root"],
                "root_pc": _PC_NAMES.index(chord_info["root"]) if chord_info["root"] in _PC_NAMES else None,
                "quality": chord_info["quality"],
                "confidence": chord_info["confidence"],
                "alternatives": chord_info["alternatives"],
                "is_slash": chord_info["is_slash"],
                "was_ambiguous": False,
                "is_continuation": False,
            })

        if not raw_segments:
            return {
                "segments": [], "key_estimate": key, "key_confidence": 0.0,
                "meter_verified": True, "overall_score": 0, "num_segments": 0,
                "ambiguity_count": 0, "chord_count": 0,
                "issues": ["No segments (empty)"],
            }

        # ── 2. Estimate key via Krumhansl-Schmuckler ──
        global_chroma = np.zeros(12)
        for n in track.notes:
            global_chroma[n.pitch % 12] += n.duration_ticks * (n.velocity / 127.0)
        key_root_pc, key_mode, key_conf = _estimate_key(global_chroma)
        estimated_key = _PC_NAMES[key_root_pc]
        if key_conf > 0.5:
            key = estimated_key

        # ── 3. Merge consecutive identical chords ──
        merged = self._merge_adjacent(raw_segments)

        # ── 4. Final stats ──
        conf_vals = [s["confidence"] for s in merged if s["confidence"] > 0]
        avg_confidence = float(np.mean(conf_vals)) if conf_vals else 0.0
        overall_score = int(round(avg_confidence * 100)) if not np.isnan(avg_confidence) else 0
        ambiguity_count = sum(1 for s in merged if s.get("was_ambiguous", False))

        issues: list[str] = []
        low_conf = [s for s in merged if 0 < s["confidence"] < 0.5]
        if low_conf:
            issues.append(f"{len(low_conf)} segment(s) with low confidence")
        nc_count = sum(1 for s in merged if "N.C." in s.get("chord", ""))
        if nc_count > 0:
            issues.append(f"{nc_count} segment(s) with no chord")

        return {
            "segments": merged,
            "key_estimate": key,
            "key_confidence": round(key_conf, 3),
            "meter_verified": True,
            "overall_score": overall_score,
            "num_segments": len(merged),
            "ambiguity_count": ambiguity_count,
            "chord_count": len(set(s["chord"] for s in merged
                                   if s["chord"] != "N.C." and "insufficient" not in s.get("chord", ""))),
            "issues": issues,
        }

    def _merge_adjacent(self, analyses: list[dict]) -> list[dict]:
        """No merging — keep every half-bar segment as-is.

        Each half-bar has unique raw_notes, so merging would lose data.
        """
        return [seg.copy() for seg in analyses]

    def _extract_structural_pitches(
        self,
        notes: list[Note],
        win_start: int,
        win_end: int,
        window_ticks: int,
    ) -> list[int]:
        """Extract structurally significant pitches, filtering surface notes."""
        threshold = window_ticks * 0.2
        structural = []
        for n in notes:
            effective_start = max(n.start_tick, win_start)
            effective_end = min(n.end_tick, win_end)
            occupancy = effective_end - effective_start
            if occupancy >= threshold:
                structural.append(n.pitch)
            elif n.velocity > 80:
                structural.append(n.pitch)
        if not structural:
            structural = [n.pitch for n in notes]
        return structural

    def _merge_segments(self, segments: list[dict]) -> list[dict]:
        """Legacy merge for half-bar segments. Kept for compatibility."""
        if not segments:
            return []
        merged = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            same_chord = seg["chord"] == prev["chord"]
            is_cont = seg.get("is_continuation", False)
            same_bar = seg["bar"] == prev["bar"]
            same_bass = seg.get("bass") == prev.get("bass")
            if same_chord and is_cont and same_bar and same_bass:
                prev["end_tick"] = seg["end_tick"]
                prev["notes_count"] += seg["notes_count"]
            else:
                merged.append(seg.copy())
        return merged

    def _merge_beat_segments(self, segments: list[dict], beats_per_bar: int) -> list[dict]:
        """Merge beat-level segments using split audit rules."""
        if not segments:
            return []
        merged = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            same_chord = seg["chord"] == prev["chord"]
            same_bass = seg.get("bass") == prev.get("bass")
            is_cont = seg.get("is_continuation", False)
            is_nc = "N.C." in seg.get("chord", "")
            if is_nc and is_cont and prev["chord"] != "N.C.":
                prev["end_tick"] = seg["end_tick"]
                prev["notes_count"] += seg.get("notes_count", 0)
                continue
            if same_chord and same_bass:
                prev["end_tick"] = seg["end_tick"]
                prev["notes_count"] += seg.get("notes_count", 0)
            else:
                merged.append(seg.copy())
        for seg in merged:
            seg["beat_position"] = str(seg.get("beat_in_bar", 1))
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

        return Track(name="AI Harmony Voicing", notes=notes, color="#CF9FFF", instrument=0, channel=1)  # Piano
