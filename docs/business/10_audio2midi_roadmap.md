# Audio → MIDI 정밀화 로드맵

> 작성: 2026-04-17
> 관련: [09_8주_Sprint_6월데드라인.md](09_8주_Sprint_6월데드라인.md)
> 현 구현: `tools/audio_to_midi/convert.py` + `agents/audio2midi.py` (Demucs + Basic Pitch + librosa)

---

## 현실 인식

오디오 → MIDI 는 **완벽히 풀린 문제가 아니다**. 현재 파이프라인의 실측 정확도:

| 입력 종류 | 노트 F1 | 주요 실패 |
|---|---|---|
| 솔로 피아노 (깔끔 녹음) | 70-85% | 페달 중첩, 조용한 음 놓침 |
| 솔로 기타/베이스 | 70-85% | 유령 노트, 하모닉 오인 |
| 폴리포닉 믹스 전체 | **50-70%** | 스템 누설, 중성 노트 손실 |
| 드럼 | **55-65%** | 3-band 분류 제한, 심벌/톰 구분 불가 |
| 보컬 멜로디 | 60-75% | 비브라토/슬라이드로 피치 혼동 |

"Melodyne Studio 급" (95%+) 은 현재 오픈소스로는 도달 불가. 단, Tier 2 조합으로 **85-92%** 는 가능.

---

## Tier 1 — 단기 개선 (MVP 전, 1-2주)

**목표**: 노트 F1 +10-15%p. 기존 파이프라인의 가장 약한 고리만 교체.

| 교체 | 도구 | 효과 | 작업량 |
|---|---|---|---|
| 피아노 스템 전용 | **Onsets & Frames** (Google Magenta) | 피아노 F1 70 → 95% | 1일 (핑 dep + 분기) |
| 드럼 채보 | **ADTOF** (학습 기반 4-class) | 드럼 F1 55 → 80% | 1.5일 |
| 베이스/모노 솔로 | **pYIN + onset** (단일 F0 특화) | 베이스 75 → 88% | 0.5일 |
| 비트 그리드 | **madmom** 비트/다운비트 트래커 | 타이밍 ±50ms → ±10ms | 0.5일 |
| 후보 재랭킹 | **MidiGPT `score_loglik`** (ACE-2 구현 완료) | 5-10% 추가 | 0.5일 |

**조립 로직**:
```
분리 (Demucs 유지)
  ├─ piano.wav    → Onsets & Frames           (신규)
  ├─ drums.wav    → ADTOF                     (신규)
  ├─ bass.wav     → pYIN + onset              (신규)
  ├─ guitar.wav   → Basic Pitch (fallback)    (기존)
  ├─ vocals.wav   → Basic Pitch + CREPE F0    (기존+α)
  └─ other.wav    → Basic Pitch               (기존)
                ↓
madmom 비트 그리드 스냅
                ↓
각 스템 threshold 3~5개로 병렬 채보
                ↓
MidiGPT score_loglik 재랭킹 → 최고 후보 선택
                ↓
최종 MIDI
```

**예상 최종 F1 (폴리포닉 믹스)**: 50-70% → **75-85%**

---

## Tier 2 — 중기 개선 (Phase B, 1-2개월)

**목표**: F1 +10-15%p 추가. 앙상블 + 다중 모델 교차검증.

1. **앙상블 분리**
   - Demucs v4 htdemucs_6s (현재)
   - + **Mel-Roformer** (Bytedance 2024) — 보컬/드럼 강점
   - + **MDX-Net** KimberleyJSN/Roformer 변형
   - → Wiener filter 로 3 스템 평균 → SDR +2dB

2. **MT3 병행 채보**
   - Google **MT3** (multi-instrument T5) 또는 **mr-MT3** (2024 개선판)
   - Basic Pitch 결과와 교차검증:
     - 두 모델 합의 → confidence=high
     - 불일치 → flag + UI 에 표시 (수동 교정 유도)

3. **Source-filter 반복 정제** (합성-비교)
   - 예측 MIDI 를 해당 악기 SoundFont 로 합성
   - 원본 stem 과 **mel-spectrogram L2 diff** 계산
   - diff 가 큰 구간 → threshold 재조정 후 재채보
   - 2-3회 반복 수렴

4. **톤 분류기** — "other" 스템 세분화
   - timbre embedding (OpenL3 / PANNs) + k-NN
   - strings (violin/viola/cello/contrabass) / brass / woodwind 로 재라우팅
   - 각 카테고리별 전문 모델로 처리

**예상 최종 F1**: 75-85% → **85-92%** (상업 수준 접근)

---

## Tier 3 — 장기 연구 (Phase C 이후, 6개월+)

1. **MT3 fine-tuning on 자사 MIDI**
   - 자사 MIDI (현 5,852 파일 + 확장) 를 DDSP 또는 SF2 렌더로 합성
   - MT3 를 해당 오디오-MIDI 쌍에 finetune
   - **도메인 내** (city pop, 재즈, 메탈) 정확도 +15-20%p

2. **DDSP 기반 미분가능 합성**
   - MIDI → 오디오 경로를 미분가능하게
   - `loss = spectrogram(audio_predicted) - spectrogram(audio_original)`
   - `loss.backward()` → MIDI 파라미터 직접 gradient 업데이트
   - "Transcribe then refine by gradient descent" — 학습된 모델 없이도 국소 개선 가능

3. **MidiGPT multimodal**
   - 오디오 스펙트로그램 패치를 토큰화 → MidiGPT 어휘에 추가
   - 대규모 오디오-MIDI 쌍으로 사전학습
   - 단일 end-to-end 모델로 audio → MIDI
   - **리소스**: 2-3개월 GPU, 1000시간 쌍 데이터

**예상 최종 F1**: 92%+ (자사 도메인 내 Melodyne 경쟁력)

---

## 악기별 정밀 추출 설계 (통합 파이프라인)

```
오디오 입력
  │
  ▼
[Stage A] 앙상블 분리
  Demucs + Mel-Roformer → 6 스템
  Wiener filter 로 스템 누설 억제
  │
  ▼
[Stage B] 악기별 전문 채보기
  ┌─ piano     → Onsets & Frames  (96% F1)
  ├─ bass      → pYIN + onset      (단일 F0)
  ├─ guitar    → MT3              (폴리포닉)
  ├─ drums     → ADTOF            (4-class)
  ├─ vocals    → CREPE + onset    (F0 + 발음)
  ├─ strings   → 톤 분류 → 하위 악기 개별 처리
  └─ brass     → MT3 + 톤 분류
  │
  ▼
[Stage C] MidiGPT 재랭킹      ← ACE-2 활용
  스템별 3~5개 후보 생성 (다른 threshold)
  MidiGPT.score_loglik 로 음악성 채점
  최고 점수 후보 채택
  │
  ▼
[Stage D] 비트 그리드 동기화
  madmom beat + downbeat 트래커
  swing-aware 양자화 (셔플 리듬 보존)
  │
  ▼
[Stage E] 합성-비교 정제
  각 스템 MIDI → SoundFont 합성
  원본 stem 과 spectral diff
  diff 높은 구간 재채보 (2-3회)
  │
  ▼
[Stage F] 신뢰도 UI (수동 교정)
  노트별 confidence (녹/황/적)
  사용자 수정 → threshold 튜닝 피드백
  │
  ▼
최종 MIDI (Type 1, 트랙 분리)
```

---

## 당장 해야 할 것 (Sprint 35 ZZ1)

| # | 항목 | 추가 복잡도 | 효과 |
|---|---|---|---|
| ZZ1a | `/audio_to_midi` FastAPI 엔드포인트 — `convert.py` 래핑 | 낮음 | 클라이언트 연결 |
| ZZ1b | 플러그인 드롭존 `.wav/.mp3` 허용 + "⚠ Beta" 라벨 | 낮음 | UX 정직성 |
| ZZ1c | `convert.py` 에 **Onsets & Frames** 분기 (피아노 스템) | 중간 | Tier 1 단일 최대 개선 |
| ZZ1d | `convert.py` 끝단 **MidiGPT score_loglik 재랭킹** | 낮음 | 5-10% 추가 |

Tier 1 나머지 (ADTOF / pYIN / madmom) 는 **Sprint 36 이상**에서 순차 추가.
Tier 2~3 는 Phase B/C 범위.

---

## 기대 수준 커뮤니케이션 (UI 문구 가이드)

- **"Beta / 실험적"** 라벨 상시 노출
- 변환 완료 후: "트랙 수/노트 수 + ⚠ 정확도는 곡 복잡도에 따라 50-85% 범위. 편집 도구에서 검토 권장"
- 피아노-only / 솔로 녹음 시: "고정확도 모드 (Onsets & Frames)" 뱃지
- 폴리포닉 믹스 시: "참고용 — 수동 교정 필요" 뱃지

---

## 참고 문헌 / 도구 링크

- Demucs: https://github.com/facebookresearch/demucs
- Basic Pitch: https://github.com/spotify/basic-pitch
- Onsets & Frames: https://github.com/magenta/magenta/tree/main/magenta/models/onsets_frames_transcription
- MT3: https://github.com/magenta/mt3
- ADTOF: https://github.com/MZehren/ADTOF
- pYIN (librosa): https://librosa.org/doc/main/generated/librosa.pyin.html
- CREPE: https://github.com/marl/crepe
- madmom: https://github.com/CPJKU/madmom
- Mel-Roformer: https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model

라이선스 체크 필수 — 대부분 Apache 2.0 / MIT 이지만 MT3 는 일부 가중치가 제한적일 수 있음.
