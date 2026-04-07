"""Test: generate from scratch (unconditional) + from short prompt."""
import sys
sys.path.insert(0, ".")

import torch
from midigpt.inference.engine import InferenceConfig, MidiGPTInference
from midigpt.tokenizer.vocab import VOCAB

config = InferenceConfig(
    model_path="./checkpoints/midigpt_latest.pt",
    device="cuda",
)
engine = MidiGPTInference(config)

# === Test 1: Unconditional generation (from BOS only) ===
print("=== Test 1: Unconditional generation ===")
bos_ids = [VOCAB.bos_id, VOCAB.encode_token("Key_C"), VOCAB.encode_token("Tempo_10"),
           VOCAB.encode_token("Bar_0"), VOCAB.encode_token("Track_drums")]

input_tensor = torch.tensor([bos_ids], dtype=torch.long, device=engine.device)
with torch.no_grad():
    output = engine._generate_with_harmony(
        input_tensor,
        max_new_tokens=2048,
        temperature=0.85,
        top_k=50,
        top_p=0.95,
        eos_id=VOCAB.eos_id,
    )

gen_ids = output[0].tolist()
gen_tokens = [VOCAB.decode_id(t) for t in gen_ids]

# Count structure tokens
bar_count = sum(1 for t in gen_tokens if t.startswith("Bar_"))
track_count = sum(1 for t in gen_tokens if t.startswith("Track_"))
note_count = sum(1 for t in gen_tokens if t.startswith("Pitch_"))
print(f"Total tokens: {len(gen_tokens)}")
print(f"Bars: {bar_count}, Tracks: {track_count}, Notes: {note_count}")
print(f"First 80 tokens: {gen_tokens[:80]}")

# Decode and save
notes = engine.decoder.decode_to_notes(gen_ids[len(bos_ids):])
print(f"Decoded notes: {len(notes)}")

# Check bar distribution
if notes:
    tpb = engine.decoder.ticks_per_bar
    bars_used = set(n.start_tick // tpb for n in notes)
    print(f"Bars used: {sorted(bars_used)[:20]}...")
    tracks_used = set(n.track_type for n in notes)
    print(f"Tracks used: {tracks_used}")

engine.decoder.decode_to_midi(gen_ids[len(bos_ids):], "./output/test_unconditional.mid", tempo=105.0)
print("Saved: ./output/test_unconditional.mid")

# === Test 2: Short prompt (first 2 bars of input) ===
print("\n=== Test 2: Short prompt (2 bars) ===")
input_ids = engine.encoder.encode_file("./TEST MIDI/HOUSE 123 4-4 ALL.mid")
# Find Bar_2 position to truncate
bar2_pos = None
for i, tid in enumerate(input_ids):
    tok = VOCAB.decode_id(tid)
    if tok == "Bar_2":
        bar2_pos = i
        break

if bar2_pos:
    prompt = input_ids[:bar2_pos]
    print(f"Prompt length: {len(prompt)} tokens (first 2 bars)")

    input_tensor = torch.tensor([prompt], dtype=torch.long, device=engine.device)
    with torch.no_grad():
        output = engine._generate_with_harmony(
            input_tensor,
            max_new_tokens=2048,
            temperature=0.85,
            top_k=50,
            top_p=0.95,
            eos_id=VOCAB.eos_id,
        )

    gen_ids2 = output[0].tolist()[len(prompt):]
    gen_tokens2 = [VOCAB.decode_id(t) for t in gen_ids2]
    bar_count2 = sum(1 for t in gen_tokens2 if t.startswith("Bar_"))
    note_count2 = sum(1 for t in gen_tokens2 if t.startswith("Pitch_"))
    print(f"Generated: {len(gen_tokens2)} tokens, {bar_count2} bars, {note_count2} notes")

    all_ids = prompt + gen_ids2
    engine.decoder.decode_to_midi(all_ids, "./output/test_house_continued.mid", tempo=123.0)
    print("Saved: ./output/test_house_continued.mid")
else:
    print("Could not find Bar_2 in input")

print("\nDone!")
