"""
Score / Notation Engine — MIDI to sheet music conversion.

Covers: score view, lyrics, dynamics marks, articulation symbols,
part extraction, chord chart, guitar TAB, MusicXML export, PDF export.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
import xml.etree.ElementTree as ET
from pathlib import Path

from core.models import Note, Track, NOTE_NAMES, TICKS_PER_BEAT


# ── Note Duration Names ───────────────────────────────────────────────────

DURATION_NAMES = {
    TICKS_PER_BEAT * 4: ("whole", 1),
    TICKS_PER_BEAT * 3: ("half", 2),        # dotted half
    TICKS_PER_BEAT * 2: ("half", 2),
    int(TICKS_PER_BEAT * 1.5): ("quarter", 4),  # dotted quarter
    TICKS_PER_BEAT: ("quarter", 4),
    TICKS_PER_BEAT // 2: ("eighth", 8),
    TICKS_PER_BEAT // 4: ("16th", 16),
    TICKS_PER_BEAT // 8: ("32nd", 32),
}


def ticks_to_duration_name(ticks: int, tpb: int = TICKS_PER_BEAT) -> tuple[str, bool]:
    """Convert tick duration to note name + dotted flag."""
    ratio = ticks / tpb
    if ratio >= 4:
        return "whole", False
    elif ratio >= 3:
        return "half", True  # dotted
    elif ratio >= 2:
        return "half", False
    elif ratio >= 1.5:
        return "quarter", True
    elif ratio >= 1:
        return "quarter", False
    elif ratio >= 0.75:
        return "eighth", True
    elif ratio >= 0.5:
        return "eighth", False
    elif ratio >= 0.25:
        return "16th", False
    else:
        return "32nd", False


# ── Score Event ────────────────────────────────────────────────────────────

@dataclass
class ScoreNote:
    """A note as it appears on the score."""
    pitch: int = 60
    duration_name: str = "quarter"
    dotted: bool = False
    tied: bool = False
    accidental: str = ""        # sharp, flat, natural, ""
    beam_group: int = -1
    voice: int = 1              # 1 or 2 (for two-voice staves)
    lyrics: str = ""
    dynamic: str = ""           # pp, p, mp, mf, f, ff, fp, sfz
    articulation_mark: str = "" # staccato, accent, tenuto, fermata, trill, mordent, turn


@dataclass
class ScoreMeasure:
    """One measure of score notation."""
    number: int = 1
    notes: list[ScoreNote] = field(default_factory=list)
    time_sig: tuple[int, int] = (4, 4)
    key_sig: str = "C"
    clef: str = "treble"        # treble, bass, alto, tenor
    rehearsal_mark: str = ""
    tempo_text: str = ""
    repeat_start: bool = False
    repeat_end: bool = False


# ── Lyrics ─────────────────────────────────────────────────────────────────

@dataclass
class LyricEvent:
    """A lyric syllable attached to a note."""
    tick: int = 0
    text: str = ""
    syllable_type: str = "single"  # single, begin, middle, end


# ── Score Builder ──────────────────────────────────────────────────────────

class ScoreBuilder:
    """Converts MIDI tracks to score notation."""

    def __init__(self, tpb: int = TICKS_PER_BEAT):
        self.tpb = tpb

    def build_score(self, track: Track, key: str = "C", scale: str = "major",
                    time_sig: tuple[int, int] = (4, 4),
                    clef: str = "treble") -> list[ScoreMeasure]:
        """Convert a MIDI track to score measures."""
        ticks_per_bar = self.tpb * time_sig[0] * (4 // time_sig[1])
        total_ticks = track.duration_ticks if track.duration_ticks > 0 else ticks_per_bar * 4
        num_measures = (total_ticks + ticks_per_bar - 1) // ticks_per_bar

        measures = []
        for m in range(num_measures):
            bar_start = m * ticks_per_bar
            bar_end = bar_start + ticks_per_bar
            bar_notes = track.get_notes_in_range(bar_start, bar_end)

            score_notes = []
            for note in bar_notes:
                dur_name, dotted = ticks_to_duration_name(note.duration_ticks, self.tpb)
                acc = self._get_accidental(note.pitch, key, scale)
                dynamic = self._velocity_to_dynamic(note.velocity)
                art_mark = self._articulation_to_mark(note.articulation)

                score_notes.append(ScoreNote(
                    pitch=note.pitch,
                    duration_name=dur_name,
                    dotted=dotted,
                    accidental=acc,
                    dynamic=dynamic,
                    articulation_mark=art_mark,
                ))

            measures.append(ScoreMeasure(
                number=m + 1,
                notes=score_notes,
                time_sig=time_sig,
                key_sig=key,
                clef=clef,
            ))

        return measures

    def _get_accidental(self, pitch: int, key: str, scale: str) -> str:
        from core.models import SCALE_INTERVALS, key_name_to_root
        root = key_name_to_root(key)
        intervals = SCALE_INTERVALS.get(scale, SCALE_INTERVALS["major"])
        pc = pitch % 12
        relative = (pc - root) % 12
        if relative in intervals:
            return ""
        # Check if it needs sharp or flat
        note_name = NOTE_NAMES[pc]
        if '#' in note_name:
            return "sharp"
        return "flat"

    def _velocity_to_dynamic(self, velocity: int) -> str:
        if velocity < 25:
            return "pp"
        elif velocity < 45:
            return "p"
        elif velocity < 65:
            return "mp"
        elif velocity < 85:
            return "mf"
        elif velocity < 105:
            return "f"
        else:
            return "ff"

    def _articulation_to_mark(self, articulation: str) -> str:
        mapping = {
            "staccato": "staccato",
            "accent": "accent",
            "legato": "tenuto",
            "tremolo": "trill",
            "trill": "trill",
        }
        return mapping.get(articulation, "")


# ── MusicXML Export ────────────────────────────────────────────────────────

class MusicXMLExporter:
    """Export score to MusicXML format."""

    def export(self, measures: list[ScoreMeasure], title: str = "Score",
               composer: str = "") -> str:
        """Generate MusicXML string."""
        root = ET.Element("score-partwise", version="4.0")

        # Work
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = title

        # Identification
        ident = ET.SubElement(root, "identification")
        if composer:
            creator = ET.SubElement(ident, "creator", type="composer")
            creator.text = composer

        # Part list
        part_list = ET.SubElement(root, "part-list")
        score_part = ET.SubElement(part_list, "score-part", id="P1")
        ET.SubElement(score_part, "part-name").text = "Piano"

        # Part
        part = ET.SubElement(root, "part", id="P1")

        for measure in measures:
            mxml_measure = ET.SubElement(part, "measure", number=str(measure.number))

            # Attributes (first measure or when changed)
            if measure.number == 1:
                attrs = ET.SubElement(mxml_measure, "attributes")
                ET.SubElement(attrs, "divisions").text = str(TICKS_PER_BEAT)
                time = ET.SubElement(attrs, "time")
                ET.SubElement(time, "beats").text = str(measure.time_sig[0])
                ET.SubElement(time, "beat-type").text = str(measure.time_sig[1])
                clef = ET.SubElement(attrs, "clef")
                if measure.clef == "treble":
                    ET.SubElement(clef, "sign").text = "G"
                    ET.SubElement(clef, "line").text = "2"
                elif measure.clef == "bass":
                    ET.SubElement(clef, "sign").text = "F"
                    ET.SubElement(clef, "line").text = "4"

            # Notes
            for sn in measure.notes:
                note_elem = ET.SubElement(mxml_measure, "note")
                pitch_elem = ET.SubElement(note_elem, "pitch")
                step = NOTE_NAMES[sn.pitch % 12].replace('#', '')
                ET.SubElement(pitch_elem, "step").text = step
                if '#' in NOTE_NAMES[sn.pitch % 12]:
                    ET.SubElement(pitch_elem, "alter").text = "1"
                octave = (sn.pitch // 12) - 1
                ET.SubElement(pitch_elem, "octave").text = str(octave)

                # Duration
                dur_map = {"whole": 4, "half": 2, "quarter": 1,
                           "eighth": 0.5, "16th": 0.25, "32nd": 0.125}
                dur_val = dur_map.get(sn.duration_name, 1)
                if sn.dotted:
                    dur_val *= 1.5
                ET.SubElement(note_elem, "duration").text = str(int(dur_val * TICKS_PER_BEAT))
                ET.SubElement(note_elem, "type").text = sn.duration_name

                if sn.dotted:
                    ET.SubElement(note_elem, "dot")

                # Dynamics
                if sn.dynamic:
                    direction = ET.SubElement(mxml_measure, "direction")
                    direction_type = ET.SubElement(direction, "direction-type")
                    dynamics = ET.SubElement(direction_type, "dynamics")
                    ET.SubElement(dynamics, sn.dynamic)

        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def save(self, measures: list[ScoreMeasure], filepath: str, **kwargs):
        xml_str = self.export(measures, **kwargs)
        Path(filepath).resolve().write_text(xml_str, encoding="utf-8")


# ── Guitar TAB ─────────────────────────────────────────────────────────────

class GuitarTabBuilder:
    """Convert MIDI notes to guitar tablature."""

    STANDARD_TUNING = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4

    def __init__(self, tuning: list[int] = None):
        self.tuning = tuning or self.STANDARD_TUNING

    def note_to_fret(self, pitch: int) -> Optional[tuple[int, int]]:
        """Find best (string, fret) for a MIDI pitch."""
        candidates = []
        for s, open_pitch in enumerate(self.tuning):
            fret = pitch - open_pitch
            if 0 <= fret <= 24:
                candidates.append((s, fret))
        if not candidates:
            return None
        # Prefer lower fret positions
        candidates.sort(key=lambda c: c[1])
        return candidates[0]

    def build_tab(self, track: Track, tpb: int = TICKS_PER_BEAT) -> list[list[str]]:
        """Build guitar TAB as a list of string lines.

        Returns 6 lines (one per string, high E first) with fret numbers.
        """
        ticks_per_col = tpb // 4  # 16th note resolution
        total_cols = (track.duration_ticks // ticks_per_col) + 1 if track.duration_ticks > 0 else 16
        tab = [["-"] * total_cols for _ in range(6)]

        for note in track.notes:
            col = note.start_tick // ticks_per_col
            result = self.note_to_fret(note.pitch)
            if result and col < total_cols:
                string, fret = result
                tab[5 - string][col] = str(fret)

        return tab

    def format_tab(self, tab: list[list[str]], tuning_names: list[str] = None) -> str:
        """Format TAB lines as a string."""
        names = tuning_names or ["e", "B", "G", "D", "A", "E"]
        lines = []
        for i, row in enumerate(tab):
            prefix = names[i] if i < len(names) else " "
            lines.append(f"{prefix}|{''.join(row)}|")
        return "\n".join(lines)
