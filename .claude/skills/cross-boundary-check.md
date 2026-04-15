# Skill — 컴포넌트 경계 감사

변경이 **두 컴포넌트 사이의 데이터 흐름**을 건드릴 때 돌리는 체크. 5차까지의 버그 상당수는 경계에서 발생했다.

## 경계의 정의

"한 파일/프로세스가 쓰고, 다른 파일/프로세스가 읽는 지점".

MidiGPT 의 주요 경계 예시:

| 생산자 | 소비자 | 매개 |
|--------|--------|------|
| `build_sft_pairs.py` | `dataset.py _load_sft` | `sft/*.json` |
| `build_dpo_pairs.py` | `dataset.py _load_dpo` | `dpo/*.json` |
| `tokenize.py` (내부) | `dataset.py _load_pretrain` | `tokens/*.npy` |
| `train_pretrain.py` | `train_sft_lora.py` | `checkpoints/*.pt` |
| `encoder.py` | `decoder.py` | 토큰 시퀀스 (vocab) |
| `inference_server.py` | JUCE AIBridge | HTTP multipart/JSON |
| `augment_dataset.py` | `build_sft_pairs.py (variation)` | `augmented/*.mid` |

## 체크 절차

### 1. 생산자 측 확인

**파일명 규약:**
- [ ] 데이터 파일과 메타 파일의 이름이 glob 으로 구분 가능한가? (패턴 A)
- [ ] 접두사로 좁혀 두기: `sft_*.json`, `tokens_*.npy` 등

**스키마:**
- [ ] 필수 키가 일관되게 들어가는가? (모든 경로에서)
- [ ] 선택 키는 명확히 optional 로 문서화?
- [ ] `rules/01-contracts.md` 와 일치?

**인코딩:**
- [ ] `encoding="utf-8"` 명시? (패턴 E)
- [ ] JSON 직렬화 시 `ensure_ascii=False` (한글 파일명 대비)?

### 2. 소비자 측 확인

**Glob 패턴:**
- [ ] 생산자가 같은 디렉토리에 쓰는 **모든** 파일 이름을 알고 있는가?
- [ ] Glob 패턴이 그 중 **데이터 파일만** 선택하는가?

**스키마 검증:**
- [ ] 필수 키 존재 확인 후 사용 (`"input" in pair` 등)
- [ ] 누락 시 skip + warn + count (`rules/02-fallback-policy.md` 학습 엄격 모드)
- [ ] 스키마 위반은 로드 실패가 아니라 per-item skip (파이프라인 전체 중단 방지)

**타입/범위:**
- [ ] 토큰 ID 가 `vocab.size` 범위 내인가?
- [ ] 리스트 길이가 합리적인가? (빈 리스트 skip)

### 3. 경계 양쪽의 계약 대조

- [ ] 생산자가 쓰는 키/포맷 ↔ 소비자가 읽는 키/포맷 — **문자 단위로 일치**?
- [ ] 특수값 해석 일치? (예: `-1` 이 "없음" 을 의미한다고 양쪽이 알고 있는가)
- [ ] 버전 표기? (스키마 변경 대비 `"schema_version": 1` 같은 필드)

### 4. 변경 시 양쪽 동시 업데이트

- [ ] 한 쪽만 변경되면 상대 쪽이 깨지는가? → 단일 커밋으로 양쪽 수정
- [ ] 과거 데이터와의 호환성? → 구 데이터 skip or 자동 마이그레이션

## 공통 함정

### 함정 1: "데이터 파일과 메타를 같이 두자"
- 증상: loader 가 메타를 데이터로 오인 (패턴 A)
- 해결: 이름 규약으로 분리 or loader glob 좁히기 + 스키마 검증

### 함정 2: "기본값이 있으니까 키 하나 빠져도 된다"
- 증상: 의도한 기본값과 실제 기본값이 다름 → 조용한 편향
- 해결: 필수 키는 명확히 `required` 표기, loader 가 KeyError 대신 skip+warn

### 함정 3: "한 쪽만 고치고 배포"
- 증상: 패턴 C — 정책이 두 곳에 흩어진 것의 변주
- 해결: 경계 양쪽 동시 검사 후 커밋

### 함정 4: "직렬화 포맷은 나중에 정리"
- 증상: v1 과 v2 가 같은 경로에서 공존, 로더가 둘 다 로드 시도
- 해결: `schema_version` 필드 도입 or 디렉토리 분리

## 출력 형식

경계 감사 결과는 아래 형식으로 설계서에 첨부:

```
경계 감사:
  경계: [생산자 파일] → [매개 포맷] → [소비자 파일]
  발견 이슈:
    - [이슈 설명, rules/05 패턴 번호]
  변경 계획:
    - 생산자 측: ...
    - 소비자 측: ...
    - 동시 커밋 필요: Y/N
```
