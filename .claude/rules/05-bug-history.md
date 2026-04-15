# Rule 05 — 버그 히스토리 (회귀 금지 목록)

1~5차 테스터 리포트에서 발견된 버그의 **근본 패턴**. Reviewer 는 모든 변경을 이 목록에 대조한다. 새 버그가 추가되면 이 파일을 업데이트하는 것이 Reviewer 의 의무.

## 패턴 A — 디렉토리 내 메타 파일이 loader glob 에 섞임

**사례 (5차 Bug 1, 2026-04-15):**
- `build_sft_pairs.py` 가 `summary.json` 을 SFT 페어와 같은 디렉토리에 저장
- `dataset.py _load_sft` 가 `glob("*.json")` 으로 모두 로드
- 결과: `pair["input"]` KeyError (summary 에는 `input` 키 없음)

**일반화:** *같은 디렉토리에 "데이터 파일"과 "메타 파일"이 공존하면 loader glob 패턴이 둘을 섞을 수 있다.*

**회귀 방지 체크:**
- [ ] 새 스크립트가 데이터 디렉토리에 파일을 쓸 때, loader 의 glob 패턴과 충돌하는 이름인지 확인
- [ ] Loader 는 스키마 검증(필수 키 존재) 후 skip + warn
- [ ] Glob 패턴을 데이터 파일 접두사로 좁혀 두기 (`sft_*.json`)

---

## 패턴 B — 명시적 입력의 fallback이 기본값을 삼킴

**사례 (5차 Bug 3, 4차까지 누적):**
- MIDI 의 program number 기본값은 0 (Piano)
- `_classify_track` 이 "program=0" 을 "Piano family" 로 처리 → `accomp`
- 하지만 테스터 MIDI 는 program 을 **지정하지 않은** 상태 = 기본값 0 = "미지정"
- 결과: 모든 미분류 트랙이 `accomp` 으로 쏠림

**일반화:** *외부에서 받은 기본값(0, "", None)은 "명시적 값"이 아니다. 이것을 유효한 분류 키로 쓰면 조용한 편향이 생긴다.*

**회귀 방지 체크:**
- [ ] 분류/매칭 로직의 fallback 단계가 "비어있음"과 "기본값"을 구분하는가?
- [ ] substring 매치: 충돌 케이스(bassoon vs bass, brass vs bass, bassdrum 순서) 전부 열거되었는가?
- [ ] 마지막 fallback은 `"other"` / `"unknown"` 이어야 하며, 가장 흔한 카테고리가 되면 안 됨

---

## 패턴 C — 정책이 한 곳이 아닌 여러 곳에 흩어짐

**사례 (2026-04-08, EOS 조기 종료):**
- EOS suppression 이 `test_generate.py` 에만 적용
- `inference_server.py` 경로는 suppression 없음
- 테스터는 서버 경로로 테스트 → 조기 종료 계속 발견

**일반화:** *생성/검증/변환 정책이 여러 호출부에 복붙되면 한 쪽만 고쳐진다.*

**회귀 방지 체크:**
- [ ] 동일 정책이 2곳 이상에 구현되어 있지 않은가?
- [ ] 신규 엔드포인트/스크립트가 기존 정책 모듈을 공유 호출하는가?
- [ ] 정책 변경 시 모든 호출부가 업데이트되었는가?

---

## 패턴 D — 경계 조건(dtype/device/amp) 누락

**사례:**
- 5차 (`10364fb`): fp16 GradScaler 누락 → loss NaN, 모델이 조용히 학습 안 됨
- 5차 (`4b24bb8`): LoRALinear 가 base layer 의 device/dtype 상속 안 함 → cpu/gpu 혼합 에러
- `train_pretrain.py` 는 정상, `train_sft_lora.py` 만 결함 → 패턴 C 와 복합

**일반화:** *PyTorch 의 amp/dtype/device 는 "한 곳이 맞으면 다른 곳도 맞다" 고 가정하지 말 것.*

**회귀 방지 체크:**
- [ ] 새 학습 스크립트가 GradScaler + autocast_dtype 쌍을 갖추고 있는가?
- [ ] 새 Module 생성 시 parent 의 device/dtype 을 상속하는가?
- [ ] bf16 vs fp16 분기가 있는가? (Ampere 이하 환경 대비)

---

## 패턴 E — Windows 인코딩 / 경로

**사례 (2026-04-08):** 한글 파일명 포함 MIDI 처리 중 UnicodeDecodeError.

**일반화:** *Windows 기본 cp949 / 협업자 Linux utf-8 불일치.*

**회귀 방지 체크:**
- [ ] 새 `open()` 호출이 `encoding="utf-8"` 을 명시하는가?
- [ ] 한글 print 가 포함된 스크립트가 stdout UTF-8 을 설정하는가?
- [ ] 경로 연산이 `pathlib.Path` 인가?

자세한 규약: `rules/03-windows-compat.md`

---

## 패턴 F — 체크포인트 호환성 표기 누락

**사례:** 이전 `_classify_track` 수정 시 재학습 필요성을 커밋 메시지에 적지 않음 → 협업자가 구 체크포인트로 inference → 분포 불일치.

**일반화:** *Tokenizer / Vocab / 아키텍처를 건드리면 기존 체크포인트는 비호환이다.*

**회귀 방지 체크:**
- [ ] Tokenizer/Vocab/Architecture 변경인가? → 커밋 메시지에 `BREAKING: retrain required` 표기
- [ ] 변경 이력이 해당 파일 상단 History docstring 에 반영되었는가?

자세한 규약: `rules/04-commit-discipline.md`

---

## 패턴 G — "일단 되는 것"을 목표로 한 광범위 try/except

**사례:** `build_sft_pairs.py` 여러 곳에서 `except Exception` 후 `continue` → 실패한 파일이 조용히 drop, 최종 페어 수가 줄어든 줄 인지 못함.

**일반화:** *구체 예외 없이 광범위 catch 는 문제 은폐.*

**회귀 방지 체크:**
- [ ] `except Exception` / `except:` 광범위 catch 가 있는가? → 구체 예외로 좁히거나, skip 마다 warn + count
- [ ] 파이프라인 결과 요약에 "건너뛴 항목 수" 가 리포트되는가?

---

## 패턴 H — 상수 하드코딩

**사례:** `dataset.py:178` 이 SEP 토큰 ID 를 `3` 으로 하드코딩. `vocab._build()` 순서가 바뀌면 silent corruption.

**일반화:** *단일 출처(single source of truth) 를 우회하는 리터럴은 향후 버그 원천.*

**회귀 방지 체크:**
- [ ] 특수 토큰 ID 가 `vocab.bos_id / eos_id / pad_id / sep_id` 로 접근되는가?
- [ ] 카테고리 상수가 `vocab.TRACK_TYPES` 를 참조하는가?

---

## 패턴 열거 방식

새 버그 발견 시 Reviewer 는:
1. 근본 원인이 위 패턴 중 하나인지 확인 → 해당 섹션에 **사례 추가**
2. 새 패턴이면 새 섹션 작성 (A, B, C, … 순)
3. 체크리스트를 구체적으로 추가 (추상적 "주의" 금지)

**원칙:** 이 문서는 시간이 지나면서 길어져야 정상. 짧아지면 규율이 약화되고 있다는 신호.
