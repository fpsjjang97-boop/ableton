"""LoRA 핫스왑 클라이언트 예시 (Sprint 45 III2).

inference_server 의 다중 LoRA API 사용법을 보여준다. 서버는 기본
http://127.0.0.1:8765 로 기동되어 있다고 가정 (별도 터미널에서
`python -m midigpt.inference_server --model checkpoints/midigpt_best.pt`).

순서:
    1. GET /loras              — 현재 등록/활성 확인
    2. POST /register_lora     — 메모리 preload (파일 I/O)
    3. POST /activate_lora     — 즉시 전환 (I/O 없음)
    4. POST /blend_loras       — 가중 평균
    5. POST /activate_lora {null} — deactivate

사용:
    # 실서버 가정
    python examples/lora_hotswap_client.py \\
        --server http://127.0.0.1:8765 \\
        --jazz_bin ./lora_checkpoints/lora_jazz.bin \\
        --classical_bin ./lora_checkpoints/lora_classical.bin

파일이 없어도 dry-run 모드로 API 시퀀스만 출력 (--dry_run).
"""
from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _post(url: str, body: dict, timeout: int = 30) -> dict:
    req = Request(url, data=json.dumps(body).encode("utf-8"),
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get(url: str, timeout: int = 10) -> dict:
    with urlopen(url, timeout=timeout) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--server", default="http://127.0.0.1:8765")
    ap.add_argument("--jazz_bin", help="jazz LoRA .bin 경로")
    ap.add_argument("--classical_bin", help="classical LoRA .bin 경로")
    ap.add_argument("--dry_run", action="store_true",
                    help="서버 호출 없이 API 시퀀스만 출력")
    args = ap.parse_args()

    steps = []

    # 1) 현재 상태
    steps.append(("GET", f"{args.server}/loras", None))
    # 2) register jazz
    if args.jazz_bin:
        steps.append(("POST", f"{args.server}/register_lora",
                      {"name": "jazz", "path": args.jazz_bin}))
    # 3) register classical
    if args.classical_bin:
        steps.append(("POST", f"{args.server}/register_lora",
                      {"name": "classical", "path": args.classical_bin}))
    # 4) activate jazz
    steps.append(("POST", f"{args.server}/activate_lora",
                  {"name": "jazz"}))
    # 5) blend 0.7 jazz + 0.3 classical
    steps.append(("POST", f"{args.server}/blend_loras",
                  {"weights": {"jazz": 0.7, "classical": 0.3}}))
    # 6) 상태 확인
    steps.append(("GET", f"{args.server}/loras", None))
    # 7) deactivate
    steps.append(("POST", f"{args.server}/activate_lora", {"name": None}))

    print("=" * 60)
    print("  LoRA 핫스왑 클라이언트 예시 (Sprint 45 III2)")
    print(f"  Server: {args.server}   dry_run={args.dry_run}")
    print("=" * 60)

    for i, (method, url, body) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {method} {url}")
        if body:
            print(f"    body: {json.dumps(body, ensure_ascii=False)}")
        if args.dry_run:
            continue
        try:
            if method == "GET":
                resp = _get(url)
            else:
                resp = _post(url, body or {})
            print(f"    resp: {json.dumps(resp, ensure_ascii=False)}")
        except HTTPError as e:
            print(f"    HTTP {e.code}: {e.read()[:200]!r}")
        except URLError as e:
            print(f"    URL error: {e}")
        except Exception as e:
            print(f"    exception: {type(e).__name__}: {e}")

    print()
    print("완료. 활성 LoRA 상태를 확인하려면: GET /loras")


if __name__ == "__main__":
    sys.exit(main())
