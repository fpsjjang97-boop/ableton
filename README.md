# Ableton MIDI AI — MidiGPT 자체 LLM 변주 자동화 프로젝트

> 자체 MIDI 전용 LLM(MidiGPT 50M)을 구축하여, MIDI 입력 → 변주 자동 생성 파이프라인 완성

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Ableton](https://img.shields.io/badge/DAW-Ableton_Live-black)
![MIDI](https://img.shields.io/badge/Data-MIDI-green)
![Model](https://img.shields.io/badge/Model-MidiGPT_50M-orange)

---

## 역할 분담

### 🎹 음악가 (동업자)
- **MIDI 데이터 제작 및 업로드**
- DAW에서 곡 작업 → Type 1 MIDI로 Export → Git에 Push
- 장르/스타일 다양하게 (팝, 재즈, 클래식, 라틴 등)
- 드럼은 GM(General MIDI) 매핑 준수
- CC 데이터 (서스테인/익스프레션) 포함 권장
- 자세한 기준: [DATA_GUIDE.md](midigpt/DATA_GUIDE.md)

### 💻 개발자
- **AI 모델 개발 및 학습 파이프라인 운영**
- MidiGPT 아키텍처 설계/구현
- 데이터 증강 (키 전조 + 트랙 드롭아웃)
- 토큰화 → 프리트레이닝 → LoRA 파인튜닝 → DPO 학습
- 앱 통합 및 배포

### 협업 흐름
```
음악가: MIDI 제작 → Git Push
                         ↓
개발자: 증강 → 토큰화 → 학습 → 모델 업데이트
                         ↓
음악가: 변주 결과 청취 → 피드백 (좋다/나쁘다)
                         ↓
개발자: DPO 학습에 반영 → 모델 개선
                         ↓
                      반복 (체급 상승)
```

---

## 현재 진행 상황

### Phase 1: MidiGPT 아키텍처 구축 ✅ 완료
- 50M 파라미터 Decoder-Only Transformer
- REMI 계층 토큰화 (672 토큰 어휘)
- RoPE + RMSNorm + SwiGLU + Flash Attention
- LoRA 핫스왑 시스템 (스타일별 어댑터 교체)

### Phase 2: 데이터 수집 ← **현재 단계**
- MAESTRO 2018: 93곡 (클래식 피아노)
- 동업자 업로드: 11곡 (J-POP, Color, Latin, Waltz)
- **목표: 2,000곡+**

### Phase 3: 프리트레이닝 (대기 중)
- 시험 학습 완료: 102곡 → Loss 5.00 → 3.08 (3 에포크)
- 본 학습 대기: 데이터 충분히 쌓이면 실행
- 올인원 파이프라인 구축 완료 (`python -m midigpt.pipeline`)

### Phase 4: LoRA 파인튜닝 (대기 중)
- SFT: 원본-변주 쌍 200개+ 필요
- DPO: 좋은/나쁜 변주 평가 100쌍+ 필요
- 스타일별 LoRA 분화 (Jazz, Classical, Lo-fi 등)

### Phase 5: 앱 통합 및 배포 (대기 중)
- 추론 엔진 → 앱 연결
- ONNX 변환 (경량 배포)
- 자동 피드백 루프

---

## 프로젝트 구조

```
├── midigpt/                    # MidiGPT 자체 LLM
│   ├── model/
│   │   ├── config.py           # 50M 모델 설정
│   │   └── transformer.py      # Transformer 아키텍처
│   ├── tokenizer/
│   │   ├── vocab.py            # 672-토큰 어휘
│   │   ├── encoder.py          # MIDI → 토큰
│   │   └── decoder.py          # 토큰 → MIDI
│   ├── training/
│   │   ├── train_pretrain.py   # 프리트레이닝
│   │   ├── train_sft_lora.py   # LoRA SFT 파인튜닝
│   │   ├── train_dpo.py        # DPO 선호도 학습
│   │   └── lora.py             # LoRA 구현
│   ├── inference/
│   │   └── engine.py           # 추론 엔진 (LoRA 핫스왑)
│   ├── augment_dataset.py      # 데이터 증강 (전조 + 드롭아웃)
│   ├── tokenize_dataset.py     # 배치 토큰화
│   ├── pipeline.py             # 올인원 파이프라인
│   └── DATA_GUIDE.md           # 데이터 수집 가이드
├── tools/
│   ├── midi_embedding.py       # 트랙별 분리 임베딩 (1차 필터)
│   ├── build_catalog.py        # 분류 카탈로그
│   ├── generate_variation.py   # 변주 생성기
│   └── compare_midi.py         # 원본 vs 변주 비교
├── TEST MIDI/                  # 동업자 업로드 MIDI (11곡)
├── midi_data/                  # 학습용 MIDI 저장소
├── Ableton/midi_raw/           # MAESTRO 2018 (93곡)
├── app/                        # Ableton 연동 앱
├── agents/                     # 멀티 에이전트 시스템
└── embeddings/                 # MIDI 임베딩 결과
```

---

## 현재 데이터

| 항목 | 수치 |
|------|------|
| MAESTRO MIDI | 93곡 (클래식 피아노) |
| 동업자 MIDI | 11곡 (J-POP, Color, Latin, Waltz) |
| 총 데이터 | 104곡 |
| 증강 후 예상 | ~1,560곡 (x15배) |
| 목표 | 2,000곡+ (원본 기준) |
| 시험 학습 Loss | 3.08 (목표: 1.5 이하) |

---

## 사용법

### 음악가 (MIDI 업로드)
```bash
# MIDI 파일을 midi_data/ 또는 TEST MIDI/에 넣고
git add "TEST MIDI/"
git commit -m "data: MIDI 학습 데이터 추가"
git push
```

### 개발자 (파이프라인 실행)
```bash
# 올인원: 증강 → 토큰화 → 학습
python -m midigpt.pipeline --midi_dir "./TEST MIDI" --epochs 10

# 또는 단계별:
python -m midigpt.augment_dataset --input_dir ./midi_data --output_dir ./augmented
python -m midigpt.tokenize_dataset --input_dir ./augmented --output_dir ./midigpt_data
python -m midigpt.training.train_pretrain --data_dir ./midigpt_data --epochs 10
```

---

## 라이선스

MIT License
