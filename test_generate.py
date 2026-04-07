"""Quick test: generate a MIDI variation from an existing file."""
import sys
sys.path.insert(0, ".")

from midigpt.inference.engine import InferenceConfig, MidiGPTInference

# Load model
config = InferenceConfig(
    model_path="./checkpoints/midigpt_latest.pt",
    device="cuda",
)
engine = MidiGPTInference(config)
print(engine.get_status())

# Pick a test input
input_midi = "./TEST MIDI/CITY POP 105 4-4 DRUM E.PIANO.mid"
output_midi = "./output/test_generated.mid"

# Generate
from midigpt.tokenizer.encoder import SongMeta
meta = SongMeta(tempo=105.0, key="C", style="city_pop", section="verse")

result_path = engine.generate_to_midi(
    midi_path=input_midi,
    output_path=output_midi,
    meta=meta,
    max_tokens=1024,
    temperature=0.85,
)
print(f"\nGenerated: {result_path}")
