#!/usr/bin/env bash
# LoRA 핫스왑 — curl 버전 (Sprint 45 III2).
# 요구: bash, curl, jq (옵션, 예쁜 출력)
#
# 사용:
#   bash examples/lora_hotswap.sh \
#     http://127.0.0.1:8765 ./lora_checkpoints/lora_jazz.bin ./lora_checkpoints/lora_classical.bin

set -u
SERVER="${1:-http://127.0.0.1:8765}"
JAZZ="${2:-}"
CLASSICAL="${3:-}"

say() { printf "\n==> %s\n" "$*"; }

say "1) GET ${SERVER}/loras"
curl -sS "${SERVER}/loras" | ( command -v jq >/dev/null && jq . || cat )

if [ -n "${JAZZ}" ]; then
  say "2) register jazz"
  curl -sS -X POST "${SERVER}/register_lora" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"jazz\",\"path\":\"${JAZZ}\"}" \
    | ( command -v jq >/dev/null && jq . || cat )
fi

if [ -n "${CLASSICAL}" ]; then
  say "3) register classical"
  curl -sS -X POST "${SERVER}/register_lora" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"classical\",\"path\":\"${CLASSICAL}\"}" \
    | ( command -v jq >/dev/null && jq . || cat )
fi

say "4) activate jazz"
curl -sS -X POST "${SERVER}/activate_lora" \
  -H "Content-Type: application/json" \
  -d '{"name":"jazz"}' \
  | ( command -v jq >/dev/null && jq . || cat )

say "5) blend 0.7 jazz + 0.3 classical"
curl -sS -X POST "${SERVER}/blend_loras" \
  -H "Content-Type: application/json" \
  -d '{"weights":{"jazz":0.7,"classical":0.3}}' \
  | ( command -v jq >/dev/null && jq . || cat )

say "6) GET ${SERVER}/loras (최종 상태)"
curl -sS "${SERVER}/loras" | ( command -v jq >/dev/null && jq . || cat )

say "7) deactivate"
curl -sS -X POST "${SERVER}/activate_lora" \
  -H "Content-Type: application/json" \
  -d '{"name":null}' \
  | ( command -v jq >/dev/null && jq . || cat )

echo
