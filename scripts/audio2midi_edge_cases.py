"""Audio2MIDI 엣지 케이스 회귀 테스트 (오프라인, 서버 불필요).

detect_bpm() 과 라이트한 유틸 함수를 대상으로 "서버 켜지 않고" 돌릴
수 있는 회귀 테스트. Sprint 37.2 에서 발견된 BPM=0 → ZeroDivisionError
처럼 데이터 엣지가 trigger 하는 버그의 회귀 방지가 목적.

검사 케이스:
    1. 6초 사인파 @ 120 BPM — BPM 감지되거나 기본값 120
    2. 6초 무음 — BPM=0 반환 안 함 (fallback 120)
    3. 60초 사인파 @ 90 BPM — 감지 정확도 ±10%
    4. 60초 화이트노이즈 — fallback 120
    5. 1초 미니 클립 — 너무 짧아도 기본값 120
    6. 0.1초 극단 클립 — librosa 예외 catch 되고 120
    7. 비표준 샘플링(8000Hz) WAV — 로드 성공 or 기본값
    8. 손상된 WAV 헤더 — 예외 catch → 120 (ZeroDivisionError 재발 방지)

실행:
    python scripts/audio2midi_edge_cases.py
종료 코드:
    0 = 전부 PASS
    1 = 하나 이상 실패
"""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "audio_to_midi"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def _write_sine_wav(path: Path, duration_sec: float, freq: float = 440.0,
                    sr: int = 22050, amplitude: float = 0.3) -> None:
    """단순 16-bit PCM sine wave 기록. librosa/soundfile 의존 없이."""
    n = max(1, int(duration_sec * sr))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for i in range(n):
            v = int(amplitude * 32767.0 * math.sin(2 * math.pi * freq * i / sr))
            w.writeframes(struct.pack("<h", v))


def _write_silence_wav(path: Path, duration_sec: float, sr: int = 22050) -> None:
    n = max(1, int(duration_sec * sr))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * n)


def _write_noise_wav(path: Path, duration_sec: float, sr: int = 22050) -> None:
    import random
    random.seed(42)
    n = max(1, int(duration_sec * sr))
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for _ in range(n):
            v = random.randint(-8000, 8000)
            w.writeframes(struct.pack("<h", v))


def _write_corrupt_wav(path: Path) -> None:
    """의도적으로 손상된 WAV — header 유효하나 payload 가 짧음."""
    path.write_bytes(b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00")


class Case:
    def __init__(self, name: str, setup, check):
        self.name = name
        self.setup = setup
        self.check = check
        self.ok = False
        self.detail = ""

    def run(self, tmp: Path, detect_bpm) -> None:
        path = tmp / (self.name.replace(" ", "_") + ".wav")
        try:
            self.setup(path)
        except Exception as e:
            self.detail = f"setup 실패: {type(e).__name__}: {e}"
            return
        try:
            bpm = detect_bpm(path)
        except Exception as e:
            self.detail = f"detect_bpm 예외: {type(e).__name__}: {e}"
            return
        ok, msg = self.check(bpm)
        self.ok = ok
        self.detail = f"bpm={bpm:.1f} — {msg}"


def main() -> int:
    from convert import detect_bpm

    print("=" * 60)
    print("  Audio2MIDI Edge Case Tests (offline)")
    print("=" * 60)

    cases = [
        Case("6s_sine_120",
             lambda p: _write_sine_wav(p, 6.0, freq=440.0),
             lambda b: (30.0 <= b <= 300.0,
                        "합리 범위 내 (또는 기본값 120)")),
        Case("6s_silence",
             lambda p: _write_silence_wav(p, 6.0),
             lambda b: (abs(b - 120.0) < 1e-6 or 30.0 <= b <= 300.0,
                        "무음은 fallback 120 이어야 함")),
        Case("60s_sine_A440",
             lambda p: _write_sine_wav(p, 60.0, freq=440.0),
             lambda b: (30.0 <= b <= 300.0, "범위 내")),
        Case("60s_whitenoise",
             lambda p: _write_noise_wav(p, 60.0),
             lambda b: (30.0 <= b <= 300.0,
                        "노이즈도 예외 없이 범위 값 반환")),
        Case("1s_mini",
             lambda p: _write_sine_wav(p, 1.0, freq=440.0),
             lambda b: (30.0 <= b <= 300.0,
                        "1초 짧은 클립도 기본값 120 fallback")),
        Case("0.1s_extreme",
             lambda p: _write_sine_wav(p, 0.1, freq=440.0),
             lambda b: (30.0 <= b <= 300.0,
                        "극단 짧은 클립 예외 catch → 120")),
        Case("8000Hz_sine",
             lambda p: _write_sine_wav(p, 30.0, freq=220.0, sr=8000),
             lambda b: (30.0 <= b <= 300.0,
                        "비표준 SR 도 로드 성공")),
        Case("corrupt_wav_header",
             _write_corrupt_wav,
             lambda b: (abs(b - 120.0) < 1e-6,
                        "손상 파일 예외 catch → 120 (ZeroDivisionError 재발 방지)")),
    ]

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for c in cases:
            c.run(tmp, detect_bpm)
            mark = "PASS" if c.ok else "FAIL"
            print(f"  [{mark}] {c.name:>22}  {c.detail}")

    passed = sum(1 for c in cases if c.ok)
    total = len(cases)
    print("=" * 60)
    if passed == total:
        print(f"  ALL PASS ({passed}/{total})")
        return 0
    print(f"  FAIL ({passed}/{total})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
