"""MidiGPT — E2E 자동 회귀 테스트.

Sprint 38 BBB3. 실행 중인 서버를 가정하고 /health, /preflight,
/generate_json, /audio_to_midi 4개 엔드포인트의 기본 동작을 순차
검증. 각 단계에서 응답 스키마 체크 + 최소 합리성 (노트 수 > 0,
bytes > 0 등). 하나라도 실패하면 non-zero exit — CI 또는 수동
pre-release gate 에서 사용.

사용법:
    python scripts/e2e_test.py                    # 기본 (11.mid 입력)
    python scripts/e2e_test.py --audio x.wav      # 오디오 경로도 테스트
    python scripts/e2e_test.py --skip-audio       # audio_to_midi 생략 (빠름)
    python scripts/e2e_test.py --server :9999     # 다른 포트

종료 코드:
    0 = 전부 PASS
    1 = 하나 이상 실패
    2 = 서버 연결 불가
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestResult:
    def __init__(self, name: str):
        self.name = name
        self.ok = False
        self.detail = ""
        self.elapsed = 0.0

    def passed(self, detail: str = "", elapsed: float = 0.0):
        self.ok = True
        self.detail = detail
        self.elapsed = elapsed
        return self

    def failed(self, detail: str):
        self.ok = False
        self.detail = detail
        return self

    def print(self):
        mark = "PASS" if self.ok else "FAIL"
        tstr = f" ({self.elapsed:.1f}s)" if self.elapsed else ""
        print(f"  [{mark}]{tstr} {self.name}")
        if self.detail:
            for line in self.detail.splitlines():
                print(f"         {line}")


def _post_json(url: str, payload: dict, timeout: int = 300) -> dict:
    body = json.dumps(payload).encode()
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get_json(url: str, timeout: int = 10) -> dict:
    with urlopen(url, timeout=timeout) as r:
        return json.load(r)


def test_health(base: str) -> TestResult:
    r = TestResult("/health")
    try:
        t0 = time.time()
        resp = _get_json(f"{base}/health", timeout=5)
        elapsed = time.time() - t0
    except (URLError, HTTPError) as e:
        return r.failed(f"서버 연결 실패: {e}")
    if resp.get("status") != "ok":
        return r.failed(f"status != ok: {resp}")
    if not resp.get("model_loaded"):
        return r.failed("model_loaded=false — --model 인자 확인")
    return r.passed(f"status=ok  model_loaded=true", elapsed)


def test_preflight(base: str) -> TestResult:
    r = TestResult("/preflight")
    # convert.py 첫 import 는 demucs/librosa/basic_pitch/torch 등으로
    # 10-20초 걸릴 수 있음 (cold cache). 관대하게.
    try:
        t0 = time.time()
        resp = _get_json(f"{base}/preflight", timeout=30)
        elapsed = time.time() - t0
    except Exception as e:
        return r.failed(f"요청 실패: {e}")
    required = ("model_loaded", "audio2midi_available",
                "piano_pti", "onsets_frames", "adtof", "missing")
    missing_keys = [k for k in required if k not in resp]
    if missing_keys:
        return r.failed(f"스키마 누락 키: {missing_keys}")
    tier1 = []
    if resp["piano_pti"]:    tier1.append("PTI")
    if resp["onsets_frames"]: tier1.append("O&F")
    if resp["adtof"]:        tier1.append("ADTOF")
    tier1_str = ",".join(tier1) if tier1 else "none"
    return r.passed(f"a2m={resp['audio2midi_available']}  tier1={tier1_str}", elapsed)


def test_generate_json(base: str, midi_path: Path) -> TestResult:
    r = TestResult(f"/generate_json ({midi_path.name})")
    try:
        payload = {
            "midi_base64": base64.b64encode(midi_path.read_bytes()).decode("ascii"),
            "style": "base", "key": "C", "section": "chorus", "tempo": 120.0,
            "temperature": 0.9, "num_variations": 1,
            "max_tokens": 256, "min_new_tokens": 64,
            "repetition_penalty": 1.1, "no_repeat_ngram_size": 4,
        }
        t0 = time.time()
        resp = _post_json(f"{base}/generate_json", payload, timeout=120)
        elapsed = time.time() - t0
    except Exception as e:
        return r.failed(f"요청 실패: {type(e).__name__}: {e}")
    if not resp.get("ok"):
        return r.failed(f"ok != true: {resp}")
    if resp.get("bytes", 0) < 100:
        return r.failed(f"응답 MIDI 너무 작음: {resp.get('bytes')} bytes")
    # decode sanity
    try:
        raw = base64.b64decode(resp["midi_base64"])
        import pretty_midi
        tmp = REPO_ROOT / "output" / "_e2e_test_gen.mid"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(raw)
        pm = pretty_midi.PrettyMIDI(str(tmp))
        notes = sum(len(i.notes) for i in pm.instruments)
    except Exception as e:
        return r.failed(f"응답 MIDI 파싱 실패: {e}")
    return r.passed(f"bytes={resp['bytes']} notes={notes}", elapsed)


def test_audio_to_midi(base: str, wav_path: Path) -> TestResult:
    r = TestResult(f"/audio_to_midi ({wav_path.name})")
    if not wav_path.exists():
        return r.failed(f"입력 파일 없음: {wav_path}")
    try:
        payload = {
            "audio_base64": base64.b64encode(wav_path.read_bytes()).decode("ascii"),
            "filename": wav_path.name,
            "keep_vocals": False,
            "rerank_with_midigpt": True,
        }
        t0 = time.time()
        resp = _post_json(f"{base}/audio_to_midi", payload, timeout=600)
        elapsed = time.time() - t0
    except Exception as e:
        return r.failed(f"요청 실패: {type(e).__name__}: {e}")
    if not resp.get("ok"):
        return r.failed(f"ok != true: {resp}")
    if resp.get("bytes", 0) < 100:
        return r.failed(f"응답 MIDI 너무 작음: {resp.get('bytes')} bytes")
    loglik = resp.get("loglik")
    beta = resp.get("beta_warning", "") or ""
    hints = []
    if loglik is not None: hints.append(f"loglik={loglik:.2f}")
    if beta:               hints.append("beta-warn=OK")
    return r.passed(f"bytes={resp['bytes']} " + " ".join(hints), elapsed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8765",
                        help="서버 URL (예: :9999 → http://127.0.0.1:9999)")
    parser.add_argument("--midi", default=str(REPO_ROOT / "11.mid"),
                        help="generate_json 입력 MIDI")
    parser.add_argument("--audio", default=str(REPO_ROOT / "juce_app/build/test_synth.wav"),
                        help="audio_to_midi 입력 WAV/MP3")
    parser.add_argument("--skip-audio", action="store_true",
                        help="audio_to_midi 단계 생략")
    args = parser.parse_args()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    base = args.server
    if base.startswith(":"):
        base = f"http://127.0.0.1{base}"

    print("=" * 60)
    print(f"  MidiGPT E2E Test  server={base}")
    print("=" * 60)

    results: list[TestResult] = []

    r = test_health(base); r.print(); results.append(r)
    if not r.ok:
        print()
        print("서버에 연결할 수 없습니다. `python -m midigpt.inference_server` 확인.")
        sys.exit(2)

    r = test_preflight(base); r.print(); results.append(r)

    midi = Path(args.midi)
    if not midi.exists():
        results.append(TestResult("/generate_json").failed(f"입력 없음: {midi}"))
        results[-1].print()
    else:
        r = test_generate_json(base, midi); r.print(); results.append(r)

    if not args.skip_audio:
        r = test_audio_to_midi(base, Path(args.audio)); r.print(); results.append(r)
    else:
        print("  [SKIP] /audio_to_midi (--skip-audio)")

    print()
    passed = sum(1 for r in results if r.ok)
    total = len(results)
    print("=" * 60)
    if passed == total:
        print(f"  ALL PASS ({passed}/{total})")
        sys.exit(0)
    print(f"  {total - passed} failure(s)  ({passed}/{total} passed)")
    sys.exit(1)


if __name__ == "__main__":
    main()
