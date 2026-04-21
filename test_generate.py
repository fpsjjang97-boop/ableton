"""Quick test: generate a MIDI variation from an existing file.

9차 리포트 대응 (2026-04-21):
  - 직전 버전은 LoRA register / activate 호출이 빠져 있어
    ``active_lora: None`` 으로 SFT 학습 결과가 생성에 반영되지
    않았다. Base model 로만 돌아가므로 SFT 재학습이 "효과 없는
    것처럼" 보인 것. 이제 checkpoints/lora/lora_sft_best.bin 을
    자동 로드.
  - min_bars 는 engine.py 기본값이 8 이지만 호출부에 명시해서
    "정말 가드가 적용되고 있나" 를 호출 사이트에서 분명히 한다.
"""
import os
import sys
sys.path.insert(0, ".")

from midigpt.inference.engine import InferenceConfig, MidiGPTInference
from midigpt.tokenizer.encoder import SongMeta

# ------------------------------------------------------------------
# 1. Load model
# ------------------------------------------------------------------
config = InferenceConfig(
    model_path="./checkpoints/midigpt_latest.pt",
    device="cuda",
)
engine = MidiGPTInference(config)

# ------------------------------------------------------------------
# 2. Register + activate the SFT LoRA weights (9차 fix)
#    Without this the engine runs the base model only and SFT
#    training contributes nothing to inference.
# ------------------------------------------------------------------
lora_path = "./checkpoints/lora/lora_sft_best.bin"
if os.path.isfile(lora_path):
    engine.register_lora("sft", lora_path)
    engine.activate_lora("sft")
    print(f"[LoRA] registered + activated: {lora_path}")
else:
    print(f"[LoRA] WARNING — {lora_path} not found; generating with BASE MODEL only")

print(engine.get_status())

# ------------------------------------------------------------------
# 3. Pick a test input + meta
# ------------------------------------------------------------------
input_midi  = "./TEST MIDI/CITY POP 105 4-4 DRUM E.PIANO.mid"
output_midi = "./output/test_generated.mid"
os.makedirs(os.path.dirname(output_midi), exist_ok=True)

meta = SongMeta(tempo=105.0, key="C", style="city_pop", section="verse")

# ------------------------------------------------------------------
# 4. Generate — min_bars explicit so the EOS suppression is clearly
#    active at the call site (engine.py default is also 8).
# ------------------------------------------------------------------
result_path = engine.generate_to_midi(
    midi_path=input_midi,
    output_path=output_midi,
    meta=meta,
    max_tokens=1024,
    min_new_tokens=256,
    min_bars=8,
    temperature=0.85,
    repetition_penalty=1.1,
    no_repeat_ngram_size=4,
)
print(f"\nGenerated: {result_path}")
