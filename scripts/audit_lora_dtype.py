"""LoRA dtype/device 런타임 감사 — SFT NaN 후보 #2 점검.

목적: base model checkpoint 를 실제로 로드하고 LoRA 를 적용한 뒤,
모든 LoRALinear 의 (device, dtype) 이 base layer 와 일치하는지 확인.
또한 synthetic batch 로 forward 1회 돌려 NaN/Inf 가 즉시 발생하는지
관찰한다. 재학습은 동업자가 하지만 이 진단은 GPU 없이도 돌 수 있다
(CPU fp32 로 축소).

5차 커밋 4b24bb8 에서 LoRALinear 가 base layer 의 dtype/device 를 상속하도록
수정되었다. 본 감사는 그 수정이 현재 코드에서도 유지되는지, 그리고
fp16/bf16 로 전환했을 때 어떤 경로에서 dtype 혼합이 생길 수 있는지
확인한다.

검사 항목:
    1. Base model 체크포인트 로드 성공
    2. LoRA 적용 후 각 LoRALinear.lora_A / lora_B 의 dtype, device 가
       동일 모듈 original.weight 와 일치
    3. save_lora → load_lora 왕복 후 dtype 유지
    4. Synthetic forward (CPU fp32) 에서 NaN/Inf 없음
    5. autocast(fp16) synthetic forward 에서 NaN/Inf 없음 (CUDA 가능 시)

사용:
    python scripts/audit_lora_dtype.py --base_model checkpoints/midigpt_best.pt
    python scripts/audit_lora_dtype.py --base_model checkpoints/midigpt_best.pt --cpu_only
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import torch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from midigpt.model.transformer import MidiGPT
from midigpt.model.config import MidiGPTConfig
from midigpt.tokenizer.vocab import VOCAB
from midigpt.training.lora import (
    LoRAConfig,
    LoRALinear,
    apply_lora,
    load_lora,
    save_lora,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _load_model(base_model: Path, device: torch.device):
    if not base_model.exists():
        print(f"[ERROR] base_model 없음: {base_model}")
        return None, None
    ckpt = torch.load(base_model, map_location=device, weights_only=True)
    if "config" in ckpt:
        config = MidiGPTConfig(**ckpt["config"])
    else:
        config = MidiGPTConfig(vocab_size=VOCAB.size)
    model = MidiGPT(config).to(device)
    if "model_state_dict" in ckpt:
        model.load_state_dict(ckpt["model_state_dict"])
    else:
        model.load_state_dict(ckpt)
    return model, config


def audit(args) -> int:
    device = torch.device("cpu" if args.cpu_only else
                          ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"Device: {device}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Base model load
    # ------------------------------------------------------------------
    base_model = Path(args.base_model)
    print(f"Loading base model: {base_model}")
    model, config = _load_model(base_model, device)
    if model is None:
        return 2
    print(f"Params: {model.count_parameters():,}")
    print(f"block_size: {config.block_size}, n_embd: {config.n_embd}, "
          f"n_layer: {config.n_layer}, n_head: {config.n_head}")
    print(f"ckpt vocab_size: {config.vocab_size}, current VOCAB.size: {VOCAB.size}")
    vocab_mismatch = (config.vocab_size != VOCAB.size)
    if vocab_mismatch:
        print(f"[ALERT] vocab_size 불일치 — 체크포인트와 현재 VOCAB 가 어긋남. "
              f"{abs(config.vocab_size - VOCAB.size)} 토큰 차이. "
              f"SFT 재학습 전 데이터/vocab 정합 필수.")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 2. LoRA apply + dtype/device consistency
    # ------------------------------------------------------------------
    lora_config = LoRAConfig(r=16, alpha=32, dropout=0.05,
                             target_modules=["q_proj", "v_proj", "o_proj"])
    lora_params = apply_lora(model, lora_config)
    lora_layers = [(n, m) for n, m in model.named_modules() if isinstance(m, LoRALinear)]
    print(f"LoRA layers applied: {len(lora_layers)}")

    mismatches = []
    for name, layer in lora_layers:
        base_device = layer.original.weight.device
        base_dtype = layer.original.weight.dtype
        for pname, p in [("lora_A", layer.lora_A), ("lora_B", layer.lora_B)]:
            if p.device != base_device or p.dtype != base_dtype:
                mismatches.append({
                    "layer": name,
                    "param": pname,
                    "base_device": str(base_device),
                    "base_dtype": str(base_dtype),
                    "lora_device": str(p.device),
                    "lora_dtype": str(p.dtype),
                })

    if mismatches:
        print(f"[FAIL] dtype/device mismatch: {len(mismatches)} 건")
        for m in mismatches[:5]:
            print(f"  {m}")
    else:
        print("[OK] 모든 LoRALinear 가 base 와 dtype/device 일치")

    # ------------------------------------------------------------------
    # 3. Save → Load round-trip
    # ------------------------------------------------------------------
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "lora_rt.bin"
        save_lora(model, tmp)
        # Reload fresh model and apply + load
        model2, _ = _load_model(base_model, device)
        apply_lora(model2, lora_config)
        load_lora(model2, tmp, lora_config)

        # Verify dtypes preserved
        rt_mismatches = []
        layers2 = [(n, m) for n, m in model2.named_modules() if isinstance(m, LoRALinear)]
        for (n1, l1), (n2, l2) in zip(lora_layers, layers2):
            if l1.lora_A.dtype != l2.lora_A.dtype:
                rt_mismatches.append((n1, "A", l1.lora_A.dtype, l2.lora_A.dtype))
            if l1.lora_B.dtype != l2.lora_B.dtype:
                rt_mismatches.append((n1, "B", l1.lora_B.dtype, l2.lora_B.dtype))
        if rt_mismatches:
            print(f"[FAIL] save→load round-trip dtype 손실: {len(rt_mismatches)} 건")
            for m in rt_mismatches[:5]:
                print(f"  {m}")
        else:
            print("[OK] save_lora → load_lora 왕복 dtype 보존")
        del model2

    # ------------------------------------------------------------------
    # 4. Synthetic forward (fp32)
    # ------------------------------------------------------------------
    print("=" * 60)
    model.eval()
    B, T = 2, min(128, config.block_size)
    # 체크포인트 embedding 범위 내에서만 샘플링 (vocab_size 불일치 시 OOR 방지)
    vocab_range = min(config.vocab_size, VOCAB.size)
    idx = torch.randint(0, vocab_range, (B, T), device=device)
    targets = torch.randint(1, vocab_range, (B, T), device=device)

    with torch.no_grad():
        logits, loss, _ = model(idx, targets=targets)
    print(f"fp32 forward: logits.shape={logits.shape}, loss={loss.item():.4f}")
    fp32_bad = torch.isnan(logits).any().item() or torch.isinf(logits).any().item()
    print(f"  NaN/Inf in logits: {fp32_bad}")
    fp32_loss_bad = torch.isnan(loss).item() or torch.isinf(loss).item()
    print(f"  NaN/Inf in loss:   {fp32_loss_bad}")

    # ------------------------------------------------------------------
    # 5. autocast fp16 forward (CUDA 가능 시)
    # ------------------------------------------------------------------
    fp16_bad = None
    fp16_loss_bad = None
    if device.type == "cuda":
        with torch.no_grad(), torch.amp.autocast(device_type="cuda", dtype=torch.float16):
            logits16, loss16, _ = model(idx, targets=targets)
        fp16_bad = torch.isnan(logits16).any().item() or torch.isinf(logits16).any().item()
        fp16_loss_bad = torch.isnan(loss16).item() or torch.isinf(loss16).item()
        print(f"fp16 autocast forward: logits.shape={logits16.shape}, "
              f"loss={loss16.item():.4f}")
        print(f"  NaN/Inf in logits: {fp16_bad}")
        print(f"  NaN/Inf in loss:   {fp16_loss_bad}")
    else:
        print("fp16 autocast forward: skipped (no CUDA)")

    # ------------------------------------------------------------------
    # 6. Summary
    # ------------------------------------------------------------------
    print("=" * 60)
    failures = []
    if vocab_mismatch:
        failures.append(f"vocab_size mismatch (ckpt={config.vocab_size}, "
                        f"now={VOCAB.size})")
    if mismatches:
        failures.append(f"dtype/device mismatch ({len(mismatches)})")
    if fp32_bad or fp32_loss_bad:
        failures.append("fp32 forward NaN/Inf")
    if fp16_bad or fp16_loss_bad:
        failures.append("fp16 forward NaN/Inf")

    if failures:
        print(f"[ALERT] 실패 항목: {', '.join(failures)}")
        return 1
    print("[OK] LoRA dtype/device + forward sanity 전부 통과")
    print("판정: 5차 커밋 `4b24bb8` fix 가 유지되고 있으며, "
          "현재 코드에서 LoRA 측 NaN 발생 가능성은 낮음.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--base_model", type=str,
                    default="checkpoints/midigpt_best.pt")
    ap.add_argument("--cpu_only", action="store_true",
                    help="CUDA 가 있어도 CPU 로 실행")
    args = ap.parse_args()
    sys.exit(audit(args))


if __name__ == "__main__":
    main()
