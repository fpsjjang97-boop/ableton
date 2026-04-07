"""Debug: check what tokens the model actually generates."""
import sys
sys.path.insert(0, ".")

from midigpt.inference.engine import InferenceConfig, MidiGPTInference
from midigpt.tokenizer.encoder import SongMeta
import torch

config = InferenceConfig(
    model_path="./checkpoints/midigpt_latest.pt",
    device="cuda",
)
engine = MidiGPTInference(config)

# Encode input
input_midi = "./TEST MIDI/CITY POP 105 4-4 DRUM E.PIANO.mid"
meta = SongMeta(tempo=105.0, key="C", style="city_pop", section="verse")

input_ids = engine.encoder.encode_file(input_midi, meta=meta)
print(f"Input tokens: {len(input_ids)}")
print(f"First 20 tokens: {[engine.vocab.decode_id(t) for t in input_ids[:20]]}")
print(f"Last 10 tokens: {[engine.vocab.decode_id(t) for t in input_ids[-10:]]}")

# Remove EOS, add SEP
if input_ids and input_ids[-1] == engine.vocab.eos_id:
    input_ids = input_ids[:-1]
input_ids.append(engine.vocab.sep_id)

# Generate
input_tensor = torch.tensor([input_ids], dtype=torch.long, device=engine.device)
with torch.no_grad():
    output = engine._generate_with_harmony(
        input_tensor,
        max_new_tokens=512,
        temperature=0.85,
        top_k=50,
        top_p=0.95,
        eos_id=engine.vocab.eos_id,
    )

generated_ids = output[0].tolist()[len(input_ids):]
print(f"\nGenerated tokens: {len(generated_ids)}")
decoded_tokens = [engine.vocab.decode_id(t) for t in generated_ids[:50]]
print(f"First 50 generated tokens: {decoded_tokens}")

# Try decode
notes = engine.decoder.decode_to_notes(generated_ids)
print(f"\nDecoded notes: {len(notes)}")
for n in notes[:10]:
    print(f"  {n}")
