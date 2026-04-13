"""
MidiDecoder — Converts token ID sequences back to MIDI files.

Token sequence → note events → MIDI file (via mido)
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:
    import mido
except ImportError:
    mido = None

from .vocab import (
    MidiVocab, VOCAB, NOTE_NAMES, CHORD_QUALITIES,
    NUM_POSITIONS, PITCH_MIN, PITCH_MAX, NUM_VELOCITIES,
    NUM_CC_EXPRESSION, NUM_CC_MODULATION, NUM_PITCH_BEND,
)


@dataclass
class DecodedNote:
    """A note reconstructed from tokens."""
    pitch: int
    velocity: int
    start_tick: int
    duration_tick: int
    track_type: str = "accomp"


class MidiDecoder:
    """Decodes token ID sequences back to MIDI."""

    def __init__(self, vocab: MidiVocab | None = None, ticks_per_beat: int = 480):
        self.vocab = vocab or VOCAB
        self.ticks_per_beat = ticks_per_beat
        self.ticks_per_bar = ticks_per_beat * 4      # 4/4 time
        self.ticks_per_pos = self.ticks_per_bar // NUM_POSITIONS

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    def decode_to_notes(self, token_ids: list[int]) -> list[DecodedNote]:
        """Decode token IDs to a list of DecodedNote objects."""
        tokens = self.vocab.decode_ids(token_ids)
        return self._tokens_to_notes(tokens)

    def decode_to_midi(
        self,
        token_ids: list[int],
        output_path: str,
        tempo: float = 120.0,
    ) -> str:
        """Decode token IDs and write a MIDI file.

        Returns the output file path.
        """
        if mido is None:
            raise ImportError("mido is required for MIDI file output")

        notes = self.decode_to_notes(token_ids)
        self._write_midi(notes, output_path, tempo)
        return output_path

    def decode_tokens_to_midi(
        self,
        tokens: list[str],
        output_path: str,
        tempo: float = 120.0,
    ) -> str:
        """Decode string tokens directly to MIDI file."""
        if mido is None:
            raise ImportError("mido is required for MIDI file output")

        notes = self._tokens_to_notes(tokens)
        self._write_midi(notes, output_path, tempo)
        return output_path

    # ------------------------------------------------------------------
    # Legacy backward compatibility
    # ------------------------------------------------------------------
    @staticmethod
    def _expand_legacy_tokens(tokens: list[str]) -> list[str]:
        """Expand legacy combined chord tokens into factored pairs.

        Old format: ``Chord_Cmaj7`` (single token)
        New format: ``ChordRoot_C  ChordQual_maj7`` (two tokens)

        ``Chord_NC`` is kept as-is since it still exists in the new vocab.
        Tokens that are already in the new format are passed through
        unchanged.
        """
        expanded: list[str] = []
        for tok in tokens:
            if tok == "Chord_NC":
                expanded.append(tok)
                continue
            decomposed = VOCAB.decode_legacy_chord(tok)
            if decomposed is not None:
                expanded.extend(decomposed)
            else:
                expanded.append(tok)
        return expanded

    # ------------------------------------------------------------------
    # Token parsing
    # ------------------------------------------------------------------
    def _tokens_to_notes(self, tokens: list[str]) -> list[DecodedNote]:
        """Parse token strings into note events.

        Handles both old combined ``Chord_Cmaj7`` tokens and new factored
        ``ChordRoot_`` / ``ChordQual_`` tokens transparently.
        """
        # Expand any legacy chord tokens before parsing
        tokens = self._expand_legacy_tokens(tokens)

        notes: list[DecodedNote] = []

        current_bar = 0
        current_pos = 0
        current_track = "accomp"
        current_pitch: int | None = None
        current_vel = 8  # default mid velocity
        current_dur = 4  # default quarter note

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            # Skip special and condition tokens
            if tok.startswith("<") or tok.startswith("Key_") or \
               tok.startswith("Style_") or tok.startswith("Sec_") or \
               tok.startswith("Tempo_") or tok.startswith("Chord_") or \
               tok.startswith("ChordRoot_") or tok.startswith("ChordQual_") or \
               tok.startswith("Bass_") or tok.startswith("Func_") or \
               tok.startswith("Dyn_") or tok.startswith("Art_"):
                i += 1
                continue

            # Skip expressive tokens (recognised but not mapped to note events)
            # These are valid model output — not "unknown" — but represent
            # CC/PitchBend/Pedal data that doesn't affect note decoding.
            if tok.startswith("Expr_") or tok.startswith("Mod_") or \
               tok.startswith("Pedal_") or tok.startswith("PB_") or \
               tok.startswith("InstFam_"):
                i += 1
                continue

            # Bar marker
            if tok.startswith("Bar_"):
                try:
                    current_bar = int(tok.split("_")[1])
                except (ValueError, IndexError):
                    pass
                i += 1
                continue

            # Position
            if tok.startswith("Pos_"):
                try:
                    current_pos = int(tok.split("_")[1])
                except (ValueError, IndexError):
                    pass

                # After Pos, expect Pitch, Vel, Dur in sequence
                # Collect the note group
                current_pitch = None
                i += 1
                continue

            # Track type
            if tok.startswith("Track_"):
                current_track = tok.split("_", 1)[1]
                i += 1
                continue

            # Pitch
            if tok.startswith("Pitch_"):
                try:
                    current_pitch = int(tok.split("_")[1])
                except (ValueError, IndexError):
                    current_pitch = None
                i += 1
                continue

            # Velocity
            if tok.startswith("Vel_"):
                try:
                    current_vel = int(tok.split("_")[1])
                except (ValueError, IndexError):
                    pass
                i += 1
                continue

            # Duration — this completes a note
            if tok.startswith("Dur_"):
                try:
                    current_dur = int(tok.split("_")[1])
                except (ValueError, IndexError):
                    current_dur = 4

                if current_pitch is not None:
                    start_tick = (current_bar * self.ticks_per_bar +
                                 current_pos * self.ticks_per_pos)
                    duration_tick = current_dur * self.ticks_per_pos

                    # Convert velocity bin back to MIDI velocity
                    midi_vel = min(127, current_vel * 8 + 4)

                    notes.append(DecodedNote(
                        pitch=current_pitch,
                        velocity=midi_vel,
                        start_tick=start_tick,
                        duration_tick=duration_tick,
                        track_type=current_track,
                    ))
                    current_pitch = None

                i += 1
                continue

            # Unknown token, skip
            i += 1

        return notes

    # ------------------------------------------------------------------
    # MIDI file writing
    # ------------------------------------------------------------------
    def _write_midi(
        self,
        notes: list[DecodedNote],
        output_path: str,
        tempo: float = 120.0,
    ):
        """Write decoded notes to a MIDI file."""
        mid = mido.MidiFile(ticks_per_beat=self.ticks_per_beat)

        # Group notes by track type
        track_groups: dict[str, list[DecodedNote]] = {}
        for note in notes:
            track_groups.setdefault(note.track_type, []).append(note)

        # Track type -> default GM program number
        _TRACK_PROGRAM = {
            "melody": 0, "accomp": 0, "bass": 32, "drums": 0,
            "pad": 89, "lead": 80, "arp": 46, "other": 0,
            "strings": 48, "brass": 61, "woodwind": 73,
            "vocal": 54, "guitar": 25, "fx": 98,
        }

        for track_name, track_notes in track_groups.items():
            track = mido.MidiTrack()
            mid.tracks.append(track)

            # Track name
            track.append(mido.MetaMessage('track_name', name=track_name, time=0))

            # Program change (skip for drums)
            if track_name != "drums":
                program = _TRACK_PROGRAM.get(track_name, 0)
                track.append(mido.Message('program_change', program=program, time=0))

            # Tempo (first track only)
            if track_name == list(track_groups.keys())[0]:
                track.append(mido.MetaMessage(
                    'set_tempo',
                    tempo=mido.bpm2tempo(tempo),
                    time=0,
                ))

            # Sort notes by start time
            track_notes.sort(key=lambda n: (n.start_tick, n.pitch))

            # Build note on/off events
            events: list[tuple[int, str, int, int]] = []
            for note in track_notes:
                events.append((note.start_tick, "note_on", note.pitch, note.velocity))
                events.append((note.start_tick + note.duration_tick, "note_off", note.pitch, 0))

            # Sort by time, then note_off before note_on at same time
            events.sort(key=lambda e: (e[0], 0 if e[1] == "note_off" else 1))

            # Convert to delta times
            prev_time = 0
            for abs_time, msg_type, pitch, vel in events:
                delta = abs_time - prev_time
                if msg_type == "note_on":
                    track.append(mido.Message('note_on', note=pitch, velocity=vel, time=delta))
                else:
                    track.append(mido.Message('note_off', note=pitch, velocity=0, time=delta))
                prev_time = abs_time

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        mid.save(output_path)
