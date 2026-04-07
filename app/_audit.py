"""System audit script."""
import sys, os
sys.path.insert(0, "E:/Ableton/repo/app")
sys.path.insert(0, "E:/Ableton/repo")

print("=== CORE ENGINE STATUS ===")

from core.audio_engine import AudioEngine
ae = AudioEngine()
print(f"AudioEngine available={ae.available}")
print(f"  send_cc={hasattr(ae,'send_cc')}, pitch_bend={hasattr(ae,'pitch_bend')}")

try:
    import fluidsynth
    print("pyfluidsynth: OK")
except Exception:
    print("pyfluidsynth: MISSING")

from core.ai_engine import AIEngine
ai = AIEngine()
print(f"AIEngine: harmony={bool(ai.harmony_engine)}, pattern_db={bool(getattr(ai,'pattern_db',None))}")

from core.midi_io import MIDIInputManager
mi = MIDIInputManager()
print(f"MIDI input ports: {mi.get_input_ports() or 'NONE'}")

from config import DEFAULT_SOUNDFONT, SOUNDFONT_SEARCH_PATHS
sf = None
for p in SOUNDFONT_SEARCH_PATHS:
    f2 = os.path.join(p, DEFAULT_SOUNDFONT)
    if os.path.isfile(f2):
        sf = f2
        break
print(f"SoundFont: {sf or 'NOT FOUND'}")

fs_bin = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fluidsynth", "bin")
if os.path.isdir(fs_bin):
    dlls = [f for f in os.listdir(fs_bin) if f.endswith(".dll")]
    print(f"  FluidSynth DLLs: {dlls[:5]}")

print()
print("=== UI SIGNAL AUDIT ===")

from ui.transport import TransportWidget
t = TransportWidget()
for s in ["play_clicked","stop_clicked","record_clicked","left_locator_changed",
          "right_locator_changed","punch_in_toggled","punch_out_toggled",
          "cycle_toggled","prev_marker_clicked","next_marker_clicked","preroll_toggled"]:
    print(f"  Transport.{s:30s} {'OK' if hasattr(t,s) else 'MISSING'}")

print()
from ui.track_inspector import TrackInspectorPanel
ti = TrackInspectorPanel()
for s in ["volume_changed","pan_changed","program_changed","mute_toggled","solo_toggled",
          "insert_clicked","send_level_changed","eq_band_changed",
          "quick_control_changed","articulation_changed","set_track"]:
    print(f"  Inspector.{s:30s} {'OK' if hasattr(ti,s) else 'MISSING'}")

print()
from ui.chord_pad_panel import ChordPadPanel
cp = ChordPadPanel()
for s in ["chord_triggered","chord_notes_changed"]:
    print(f"  ChordPad.{s:30s} {'OK' if hasattr(cp,s) else 'MISSING'}")

from ui.expression_map_editor import ExpressionMapEditor
em = ExpressionMapEditor()
for s in ["articulation_changed","map_changed"]:
    print(f"  ExprMap.{s:30s} {'OK' if hasattr(em,s) else 'MISSING'}")

from ui.step_sequencer import StepSequencerPanel
ss = StepSequencerPanel()
for s in ["step_toggled","pattern_changed"]:
    print(f"  StepSeq.{s:30s} {'OK' if hasattr(ss,s) else 'MISSING'}")

from ui.effects_panel import EffectsChainPanel
ep = EffectsChainPanel()
for s in ["effect_toggled","dry_wet_changed","send_level_changed"]:
    print(f"  Effects.{s:30s} {'OK' if hasattr(ep,s) else 'MISSING'}")

from ui.arrangement_view import ArrangementPanel
av = ArrangementPanel()
for s in ["set_project","update_playhead"]:
    print(f"  Arrangement.{s:30s} {'OK' if hasattr(av,s) else 'MISSING'}")

from ui.mixer_panel import MixerPanel
mp = MixerPanel()
for s in ["channel_strip_effect_toggled","channel_insert_slot_clicked","channel_send_level_changed"]:
    print(f"  Mixer.{s:30s} {'OK' if hasattr(mp,s) else 'MISSING'}")

print()
print("=== DEPENDENCY STATUS ===")
for d in ["PyQt6","mido","numpy","pyfluidsynth","sounddevice","rtmidi","scipy","torch","onnxruntime"]:
    try:
        __import__(d)
        print(f"  {d:20s} OK")
    except Exception:
        print(f"  {d:20s} MISSING")

print()
print("=== SUMMARY ===")
