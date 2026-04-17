# Credits — MidiGPT

MidiGPT 는 아래 오픈소스 프로젝트들의 기여 위에 세워졌습니다. 감사합니다.

각 항목은 : 프로젝트명 · 역할 · 라이선스 · 저자/단체 · 공식 URL.

---

## 핵심 런타임

### JUCE
- **역할** : 플러그인 프레임워크 (VST3 + Standalone 빌드). MidiGPT 플러그인
  인프라의 약 70% 가 JUCE 클래스 위에 서 있음. `juce::AudioProcessor`,
  `juce::MidiMessageSequence`, `juce::URL`, `juce::FileLogger`,
  `juce::LookAndFeel_V4`, `juce::TooltipWindow` 등.
- **라이선스** : ISC (core) + GPLv3 / Commercial (full). 플러그인 배포 시
  상업 라이선스 또는 GPL 준수 필요 — 0.9.0-beta 출시 전 확정.
- **저자** : Raw Material Software / JUCE 팀
- **URL** : https://juce.com/ · https://github.com/juce-framework/JUCE

### PyTorch
- **역할** : MidiGPT 50M 모델 학습/추론. KV cache, AMP (fp16/bf16),
  LoRA 구현 전반.
- **라이선스** : BSD-3-Clause
- **저자** : Meta AI + PyTorch community
- **URL** : https://pytorch.org/

### FastAPI + Uvicorn
- **역할** : 추론 서버 `/health`, `/generate_json`, `/audio_to_midi`, `/preflight`.
- **라이선스** : MIT (FastAPI), BSD (Uvicorn)
- **저자** : Sebastián Ramírez (FastAPI), Encode (Uvicorn)
- **URL** : https://fastapi.tiangolo.com/ · https://www.uvicorn.org/

---

## Audio2MIDI 파이프라인 (옵션)

### Demucs
- **역할** : 오디오 소스 분리 (vocals / drums / bass / guitar / piano / other 6-stem).
- **라이선스** : MIT
- **저자** : Meta AI (FAIR)
- **URL** : https://github.com/facebookresearch/demucs

### Basic Pitch (Spotify)
- **역할** : 폴리포닉 pitch → MIDI 전사기. bass / guitar / other 트랙에 사용.
- **라이선스** : Apache 2.0
- **저자** : Spotify Research
- **URL** : https://github.com/spotify/basic-pitch

### Piano Transcription Inference (PTI)
- **역할** : 피아노 전용 SOTA 채보 (F1 ~96% on MAESTRO). Onsets & Frames 의
  PyTorch 포트.
- **라이선스** : Apache 2.0
- **저자** : Qiuqiang Kong 외 (ByteDance 2020)
- **URL** : https://github.com/qiuqiangkong/piano_transcription_inference
- **논문** : *High-resolution Piano Transcription with Pedals by Regressing Onsets
  and Offsets Times* (IEEE TASLP 2021)

### librosa (pYIN + beat tracker + onset detect)
- **역할** : 베이스 채보 (pYIN monophonic F0), 비트 트래킹 fallback, 드럼 onset.
- **라이선스** : ISC
- **저자** : LibROSA development team
- **URL** : https://librosa.org/
- **참조** : Mauch & Dixon, *pYIN: A Fundamental Frequency Estimator* (ICASSP 2014)

### madmom (선택)
- **역할** : 고정밀 비트/다운비트 트래킹 (MIDI 노트 16분음표 그리드 스냅).
- **라이선스** : BSD-3-Clause
- **저자** : CPJKU (Johannes Kepler University Linz)
- **URL** : https://github.com/CPJKU/madmom

### pretty_midi
- **역할** : MIDI 파일 I/O, 합성 (synthesize), 분석.
- **라이선스** : MIT
- **저자** : Colin Raffel
- **URL** : https://github.com/craffel/pretty-midi

### ADTOF (선택)
- **역할** : 드럼 전용 채보 (4-class kick/snare/hihat/tom).
- **라이선스** : AGPL-3.0 (주의 — 상업 배포 시 재고)
- **저자** : Mickaël Zehren 외
- **URL** : https://github.com/MZehren/ADTOF

---

## 아이디어 / 알고리즘 이식

### ACE-Step v1.5
- **이식한 것** : FSM constrained logits processor (개념), LM loglik 재랭킹
  (개념), DTW 정렬 (알고리즘).
- **소스 복사 없음** — 모든 코드는 MidiGPT 도메인에 맞춰 직접 구현.
- **라이선스** : Apache 2.0
- **저자** : ACE-Step 팀
- **URL** : https://github.com/ace-step/ACE-Step-1.5

### Onsets & Frames (Magenta)
- **이식한 것** : 피아노 전사 백엔드 자리 (현재는 PTI 가 우선). `piano_to_midi_oaf`
  코드 경로로 남아 있어 user 가 magenta 설치한 경우 활성.
- **라이선스** : Apache 2.0
- **저자** : Google Magenta
- **URL** : https://github.com/magenta/magenta

---

## 학습 데이터

MidiGPT 50M 은 아래 공개 데이터셋을 조합해 사전학습되었습니다. 각 데이터셋의
개별 라이선스를 준수합니다.

- **MAESTRO v3** — 피아노 독주 / Magenta, CC-BY-NC-SA 4.0.
  비상업 사용만 허용 — 상업 배포 시 제외 예정.
- **Lakh MIDI Dataset (LMD)** — 다양 장르 / Colin Raffel, CC-BY 4.0.
- **GiantMIDI-Piano** — 피아노 / ByteDance Research, CC-BY 4.0.
- **POP909** — 한국/팝 / Central Conservatory Music Beijing, CC-BY-NC-SA 4.0.
- 자체 제작 MIDI (약 1,200 곡) — MidiGPT 자체 소유.

---

## Python 생태계 (의존성)

- `numpy` (BSD-3), `scipy` (BSD-3), `soundfile` (BSD-3), `mido` (MIT),
  `pydantic` (MIT), `python-multipart` (Apache 2.0), `torchlibrosa` (MIT),
  `audioread` (MIT).

---

## 감사 인사

- 테스터 **유환** (1~6차 베타 리포트) — 현실적인 음악가 관점에서 갭/중복/
  조성/쏠림 등 핵심 버그를 구체적으로 제기해 방향 교정에 결정적 기여.
- **동료 개발자** — LLM 학습/재학습 라인, 서버 프로비저닝.
- **사업가 파트너** — 베타 테스터 모집, 사업 문서 9~13 시리즈 집필.

---

## 라이선스 원칙

MidiGPT 자체 코드는 **MIT** (또는 `LICENSE` 파일 참조). 단:
- JUCE 사용으로 인해 플러그인 배포는 **JUCE 상용 라이선스** 또는 **GPLv3 준수** 중 택일.
- ADTOF (AGPL) 를 번들한 배포는 전체가 AGPL 전염 — 0.9.0-beta 에서는
  ADTOF 를 optional external install 로 유지해 배포물 자체에 포함 안 함.
- MAESTRO (CC-BY-NC-SA) 유래 체크포인트는 **비상업 사용만** 허용 —
  상업 배포용 체크포인트는 MAESTRO 제외 재학습 필요.

위 라이선스 조건은 0.9.0-beta 출시 전 법무 확인 (`docs/business/12_release_checklist.md` 참고).
