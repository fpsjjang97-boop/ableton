# MidiGPT — 개선 로드맵 명세

> Phase별 개선 항목, 위험도, 우선순위, 호환성 영향의 종합 로드맵
> 분류: 로드맵 영역
> 갱신: 2026-04-10

---

## 개요

MidiGPT 엔진의 향후 개선 항목을 4단계로 나눠 정리한 표준 로드맵.
각 항목은 다음 5가지 속성으로 분류한다:

- **등급**: 🟢 안전 / 🟡 주의 / 🟠 재학습 필요 / 🔴 호환성 깨짐
- **영역**: 모델 / 학습 / 데이터 / 추론 / 앱 / DAW
- **노력**: S(반나절) / M(수일) / L(2주+) / XL(분기 단위)
- **임팩트**: ★~★★★★★
- **선행 조건**: 다른 항목과의 의존성

---

## Phase 1 — 즉시 무위험 (이미 시작) ✅

### 완료
| 항목 | 등급 | 영역 | 상태 |
|------|------|------|------|
| KV Cache (추론) | 🟢 | 추론 | ✅ 2026-04-07 적용 |
| Repetition Penalty | 🟢 | 추론 | ✅ 2026-04-07 적용 |
| No-Repeat N-gram Block | 🟢 | 추론 | ✅ 2026-04-07 적용 |
| `num_return_sequences` | 🟢 | 추론 | ✅ 2026-04-07 적용 |
| EMA 체크포인트 | 🟢 | 학습 | ✅ 2026-04-07 적용 |
| `min_new_tokens` (EOS 조기종료 방지) | 🟢 | 추론 | ✅ 2026-04-08 적용 |
| `max_tokens` 기본값 상향 (512→1024) | 🟢 | 추론 | ✅ 2026-04-08 적용 |
| DPO quantile fallback | 🟢 | 학습 | ✅ 2026-04-08 적용 |
| 토큰 경로 자동 탐색 (3-path) | 🟢 | 데이터 | ✅ 2026-04-08 적용 |
| Windows UTF-8 인코딩 강제 (13곳) | 🟢 | 앱 | ✅ 2026-04-08 적용 |
| requirements.txt ASCII 정리 | 🟢 | 앱 | ✅ 2026-04-08 적용 |

### 잔여 (Phase 1 후속)
| 항목 | 등급 | 영역 | 노력 | 임팩트 | 비고 |
|------|------|------|------|--------|------|
| Beam Search / Diverse Beam | 🟢 | 추론 | S | ★★ | 후처리만 |
| Streaming Generation | 🟢 | 추론 | M | ★★ | 슬라이딩 윈도우 |
| Adapter Ensemble | 🟢 | 추론 | M | ★★ | LoRA 합치기 |
| Self-Consistency Scoring | 🟢 | 추론 | M | ★★★ | 음악 이론 점수 |
| Gradient Checkpointing | 🟢 | 학습 | S | ★ | VRAM 절약 |
| DeepSpeed ZeRO | 🟢 | 학습 | M | ★★★ | 큰 모델 가능 |
| Loss Masking (메타 토큰) | 🟢 | 학습 | S | ★★ | 노트 예측 집중 |
| VST3/CLAP 호스팅 모듈 | 🟢 | DAW | L | ★★★★ | LLM 무관 |
| Automation Lane UI | 🟢 | 앱 | M | ★★ | CC 곡선 편집 |

---

## Phase 2 — 데이터/증강 강화 (1~4주, 기존 모델 그대로)

| 항목 | 등급 | 영역 | 노력 | 임팩트 | 비고 |
|------|------|------|------|--------|------|
| Velocity Jitter (±10%) | 🟡 | 데이터 | S | ★★ | augmentation 추가 |
| Time Stretch (±5%) | 🟡 | 데이터 | S | ★★ | augmentation 추가 |
| Track Shuffle | 🟢 | 데이터 | S | ★ | 순서 무관 학습 |
| Lakh MIDI 통합 (+필터) | 🟠 | 데이터 | L | ★★★★★ | **필터 필수** |
| GiantMIDI-Piano 통합 | 🟢 | 데이터 | M | ★★★ | 피아노 전용 |
| MetaMIDI 통합 | 🟠 | 데이터 | XL | ★★★★ | 약 430K곡 |
| Slakh2100 통합 | 🟢 | 데이터 | M | ★★★ | 멀티 stem |
| 자동 품질 필터 | 🟢 | 데이터 | M | ★★★ | 노이즈/박자/밀도 |
| Continued Pretraining (낮은 LR) | 🟡 | 학습 | M | ★★★ | catastrophic forgetting 방지 |

⚠️ **Lakh 필수 필터**: 트랙 수≥4, 박자 일관성, 노트 밀도 정상, 키 일관성

---

## Phase 3 — Fine-tune로 신기능 (1~2개월)

기존 base 모델을 살리되, 추가 학습으로 신기능 주입.

| 항목 | 등급 | 영역 | 노력 | 임팩트 | 선행 |
|------|------|------|------|--------|------|
| **CFG 학습 (cond drop 10~20%)** | 🟠 | 학습 | M | ★★★★★ | — |
| Multi-task Heads (chord/key/sec) | 🟠 | 학습 | L | ★★★★ | — |
| Masked Music Modeling 추가 | 🟠 | 학습 | L | ★★★★ | infilling 가능 |
| Span Corruption (T5) | 🟠 | 학습 | L | ★★★ | 편곡 능력 |
| GRPO (DeepSeek-R1 방식) | 🟠 | 학습 | XL | ★★★★ | 음악 이론 reward 필요 |
| Voice Leading reward model | 🟠 | 학습 | L | ★★★★ | GRPO 선행 |
| Constitutional AI | 🟠 | 학습 | L | ★★★ | self-critique |
| FlashAttention-3 학습 적용 | 🟢 | 학습 | S | ★★ | 속도만 (numerics 미세) |

### CFG (Classifier-Free Guidance) — 자세히
**학습 변경**:
- 데이터 로드 시 10~20% 확률로 메타 토큰(`Key_X`, `Style_X`, `Sec_X`) 제거
- 그 외 학습 그대로

**추론 변경**:
- 두 번 forward (조건부, 무조건부)
- `logits = uncond + scale × (cond - uncond)`
- scale 1.0~3.0 권장

**효과**: 스타일/장르 통제력 비약적 상승

---

## Phase 4 — 메이저 재학습 (분기 단위, 호환성 깨짐)

여기는 새 base 모델로 가야 한다. 기존 LoRA는 모두 폐기.

### 토크나이저 확장 (한 번에 모아서)
| 항목 | 등급 | 영역 | 비고 |
|------|------|------|------|
| Chord Inversion 토큰 | 🔴 | 토크나이저 | 1st/2nd inv |
| Tension Notes (9/11/13) | 🔴 | 토크나이저 | append만 가능 |
| Tempo Curve / Rubato | 🔴 | 토크나이저 | 곡 내부 변화 |
| Time Signature 변화 | 🔴 | 토크나이저 | 5/4, 7/8 |
| Microtonal 토큰 | 🔴 | 토크나이저 | non-12TET |
| MPE per-note CC | 🔴 | 토크나이저 | 차세대 |
| Phrase Boundary | 🔴 | 토크나이저 | 4/8마디 분절 |
| Borrowed Chord 마커 | 🔴 | 토크나이저 | modal interchange |
| Bend Curve 토큰 | 🔴 | 토크나이저 | 단일→곡선 |

### 아키텍처 변경
| 항목 | 등급 | 영역 | 노력 | 임팩트 | 비고 |
|------|------|------|------|--------|------|
| GQA 변환 | 🟠 | 모델 | M | ★★★ | KV 메모리 1/4 |
| ALiBi 추가 | 🟠 | 모델 | M | ★★ | 길이 외삽 |
| Hierarchical Transformer | 🔴 | 모델 | XL | ★★★★★ | 8K+ 컨텍스트 |
| Mamba/SSM 하이브리드 | 🔴 | 모델 | XL | ★★★★★ | 32K 컨텍스트 가능 |
| MoE | 🔴 | 모델 | XL | ★★★★ | 장르별 expert |
| 2.5D positional encoding | 🔴 | 모델 | L | ★★★ | bar/beat/pitch 분리 |

### 멀티모달
| 항목 | 등급 | 영역 | 비고 |
|------|------|------|------|
| CLAP-style 텍스트 컨디셔닝 | 🔴 | 모델 | "happy jazz piano" 입력 |
| 이미지 → 음악 | 🔴 | 모델 | multimodal cond |
| 보컬 / 가사 토큰 | 🔴 | 토크나이저 | 텍스트 시퀀스 |

---

## 우선순위 추천 (효과 대비 노력)

### 🔥 즉시 효과 큰 것 (Phase 1+2)
1. **KV Cache + Repetition Penalty + N-gram block** ✅ 완료
2. **Lakh MIDI 통합 + 품질 필터** — 데이터 1700배
3. **EMA** ✅ 완료
4. **Velocity/Time 증강** — 코드 몇 줄
5. **Beam Search / Multi-Sample** — 후처리만

### 🎯 중기 (Phase 3, 큰 임팩트)
6. **CFG fine-tune** — 컨디션 통제력 비약적 상승
7. **Masked Music Modeling** — infilling
8. **Multi-task Pretraining**
9. **Voice Leading reward + GRPO**
10. **VST3/CLAP 호스팅** — DAW 정체성

### 🌱 장기 (Phase 4)
11. **vocab 확장** — 한 번에 모아서
12. **GQA + Hierarchical/Mamba** — vocab 확장과 동시
13. **CLAP-style 텍스트 컨디셔닝**
14. **MoE**

---

## 위험 요소 정리

| 시나리오 | 결과 |
|---------|------|
| vocab.py 중간에 토큰 끼워넣기 | 🔴 모든 .npy 잘못 해석 |
| vocab 확장 후 기존 LoRA 로드 | 🔴 shape mismatch crash |
| Lakh MIDI 무필터 통합 | 🟠 출력 품질 급락 |
| CFG를 cond drop 학습 없이 추론에만 적용 | 🟡 효과 0 |
| Velocity jitter ±30% | 🟠 augmentation artifact 학습 |
| GQA 변환 후 fine-tune 없이 사용 | 🟡 품질 저하 |
| 자기증류 (DPO 자동 페어) 비율 >50% | 🟡 distribution 좁아짐 |
| 합성 데이터 비율 >30% | 🟠 model collapse |

---

## 갱신 이력

- 2026-04-07: 초판 작성, Phase 1 안전 항목 5개 적용 완료
- 2026-04-08: 버그리포트 6건 + Q4 수정 반영
  - min_new_tokens / max_tokens 기본값 변경 (EOS 조기종료 해결)
  - DPO quantile fallback 도입 (점수 쏠림 시 자동 분위 분할)
  - 토큰 경로 자동 탐색 (data_dir 기본값 + 3-path 탐색)
  - Windows UTF-8 인코딩 일괄 강제 (에이전트 13곳)
  - requirements.txt ASCII 정리 (CP949 호환)
- 2026-04-10: 전체 명세 문서 동기화 (갱신일 통일)
