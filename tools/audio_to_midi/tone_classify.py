"""'other' 스템의 악기 패밀리 간이 분류기 (Sprint 44 HHH3).

OpenL3 / PANNs / VGGish 같은 무거운 임베딩 모델 **없이** librosa 기본
피처만으로 3-class 추정:

    strings (violin/viola/cello 등) — 지속음, 저~고 배음비, 중역 centroid
    brass   (trumpet/trombone 등)   — 강한 배음, 중~고 centroid, 넓은 dynamic
    woodwind (flute/clarinet 등)    — 약한 배음, 높은 harmonic ratio

간이 규칙 기반 — MVP 데모에서 수동 교정 전 "대략적 라벨링" 목적.
OpenL3 대체 아님. 정확도 목표: 60-70% (랜덤 33% 대비 2배).

방법:
    1. librosa harmonic_tonnetz / mfcc / spectral_centroid 로 6-dim feat 추출
    2. 규칙 기반 스코어 (if centroid<1500 Hz and harm_ratio>0.6 → strings ...)
    3. 가장 높은 스코어 반환 + confidence (0-1)

추후 업그레이드: OpenL3 + k-NN (Sprint 45+). 본 모듈의 API 는 유지.

API:
    classify_other(audio_path: str) → (family: str, confidence: float, feats: dict)
"""
from __future__ import annotations

import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


FAMILIES = ("strings", "brass", "woodwind")


def _extract_features(audio_path: Path, sr: int = 22050) -> dict:
    """6-dim feature dict."""
    import librosa
    import numpy as np
    y, _ = librosa.load(str(audio_path), sr=sr, mono=True, duration=30)
    if len(y) == 0:
        return {}

    # Harmonic vs percussive
    y_harm, y_perc = librosa.effects.hpss(y)
    harm_ratio = float(np.sum(y_harm ** 2) / (np.sum(y ** 2) + 1e-9))

    # Spectral centroid (Hz)
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))

    # Spectral rolloff (Hz, 85 percentile)
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr,
                                                             roll_percent=0.85)))

    # Spectral bandwidth
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))

    # MFCC 2nd coefficient (brightness descriptor)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc2 = float(np.mean(mfcc[1]))

    # Zero-crossing rate (noisiness)
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))

    return {
        "harm_ratio": harm_ratio,
        "centroid": centroid,
        "rolloff": rolloff,
        "bandwidth": bandwidth,
        "mfcc2": mfcc2,
        "zcr": zcr,
    }


def _score_family(feats: dict) -> dict:
    """각 family 에 0-1 스코어. 규칙 기반.

    규칙 근거 (MIR 교과서 근사):
      strings  — 지속음, harm_ratio 높음, centroid 낮~중 (500-2000 Hz)
      brass    — 강한 배음, centroid 중~고 (1500-4000), bandwidth 넓음
      woodwind — 깨끗한 배음, centroid 중 (1000-3000), zcr 낮음
    """
    if not feats:
        return {f: 0.0 for f in FAMILIES}

    h = feats["harm_ratio"]
    c = feats["centroid"]
    r = feats["rolloff"]
    bw = feats["bandwidth"]
    zcr = feats["zcr"]

    def _gauss(x: float, mu: float, sigma: float) -> float:
        import math
        return math.exp(-((x - mu) ** 2) / (2 * sigma ** 2))

    scores = {
        "strings": 0.5 * _gauss(c, 1200, 800) + 0.3 * h + 0.2 * (1 - zcr),
        "brass":   0.4 * _gauss(c, 2600, 1000) + 0.3 * _gauss(bw, 2000, 800)
                   + 0.3 * (1 - h),
        "woodwind": 0.4 * _gauss(c, 1800, 700) + 0.3 * h + 0.3 * (1 - zcr / 0.2),
    }
    # Normalize to 0-1
    mx = max(scores.values())
    if mx > 0:
        scores = {k: v / mx for k, v in scores.items()}
    return scores


def classify_other(audio_path: str | Path) -> tuple[str, float, dict]:
    """오디오 스템 → (family, confidence, feats).

    의존: librosa (이미 convert.py 의존).
    실패 시 ("other", 0.0, {}).
    """
    try:
        feats = _extract_features(Path(audio_path))
    except Exception as e:
        print(f"[tone_classify] 특징 추출 실패: {type(e).__name__}: {e}")
        return ("other", 0.0, {})
    if not feats:
        return ("other", 0.0, {})
    scores = _score_family(feats)
    best = max(scores, key=scores.get)
    # confidence = best - second_best (margin)
    sorted_v = sorted(scores.values(), reverse=True)
    conf = sorted_v[0] - sorted_v[1] if len(sorted_v) > 1 else sorted_v[0]
    return (best, float(conf), {"feats": feats, "scores": scores})


def main():
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--audio", required=True,
                    help="분류할 오디오 (wav/mp3)")
    args = ap.parse_args()
    family, conf, info = classify_other(args.audio)
    print(json.dumps({"family": family, "confidence": conf, **info},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
