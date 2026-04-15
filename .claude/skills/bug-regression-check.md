# Skill — 과거 버그 회귀 확인

`role-reviewer` 가 변경을 머지 승인하기 전, 그리고 `role-main-coder` 가 자가 검증 시 돌리는 체크. 1~5차 테스터 리포트의 버그 범주가 되풀이되지 않도록 하는 최종 관문.

## 사용 시점

- 리뷰 직전 (Reviewer 의 필수 체크)
- 커밋 직전 (Main Coder 의 자가 검증)
- 릴리스 전 (전체 회귀 테스트)

## 순차 체크

### 1차: 구조적 패턴 (패턴 A~H)

`rules/05-bug-history.md` 의 A~H 를 **순서대로** 대조. 각 패턴에 대해:
1. 변경이 그 패턴에 해당하는가? (Y/N)
2. 해당하면 체크리스트의 모든 항목을 만족하는가?
3. 불만족 항목이 있으면 **머지 차단**

### 2차: 도메인별 회귀

#### Tokenizer / Encoder 변경
- [ ] `_classify_track` 의 14 카테고리 전부 도달 가능한가? (dead branch 없는가)
- [ ] substring 매치 충돌이 새로 생기지 않았는가?
  - bass ↔ brass ↔ bassoon ↔ bassdrum
  - string ↔ strings ↔ string_ prefix
  - drum ↔ drums ↔ bassdrum
- [ ] program=0 fallback 정책이 유지되었는가? (미지정과 Piano 를 구분)
- [ ] 상단 docstring `History` 섹션에 변경이 기록되었는가?

#### SFT / DPO 데이터 파이프라인
- [ ] 출력 디렉토리에 `sft_*.json` / `dpo_*.json` 외 메타 파일이 섞일 가능성은?
- [ ] Loader 가 스키마 검증하는가?
- [ ] 생성된 페어 수 리포트가 있는가?

#### 학습 스크립트
- [ ] GradScaler 존재?
- [ ] autocast_dtype 분기 (fp16/bf16)?
- [ ] Gradient accumulation 시 loss 스케일링?
- [ ] LoRA: 새 파라미터의 device/dtype 상속?

#### 추론
- [ ] EOS suppression 이 **모든 경로**에 적용? (test_generate, inference_server, engine)
- [ ] min_new_tokens 기본값?
- [ ] 잘못된 Bar 인덱스 입력 시 디코더가 복구하는가?

#### 파일 I/O
- [ ] 모든 `open()` 에 `encoding="utf-8"`?
- [ ] JSON `ensure_ascii=False`?
- [ ] stdout UTF-8 설정 (한글 print 가 있다면)?

### 3차: 커밋 메시지 / 문서

- [ ] 커밋 메시지 형식이 `rules/04-commit-discipline.md` 를 따르는가?
- [ ] BREAKING 변경이면 본문에 명시?
- [ ] 관련 파일 docstring 이 최신 상태?
- [ ] `rules/05-bug-history.md` 에 새 사례 추가 필요 없는가?

## 판정

| 결과 | 액션 |
|------|------|
| 모든 체크 통과 | 머지 승인 |
| 1차(패턴 A~H) 실패 | 머지 차단, 해당 패턴 번호와 함께 재작업 요청 |
| 2차(도메인) 실패 | 머지 차단, 구체 파일/라인 지목 |
| 3차(문서) 실패 | 머지 차단 (사소해 보여도, 미래의 혼란 비용이 높음) |

## 새 패턴 발견 시

체크 중 기존 A~H 에 속하지 않는 실수 패턴을 발견:
1. `rules/05-bug-history.md` 에 I, J, ... 로 추가
2. 구체적 "회귀 방지 체크" 항목 작성
3. 이번 변경에도 적용해서 통과 여부 확인
4. 이 파일(bug-regression-check.md) 의 "2차 도메인별 회귀" 에 추가

## 자기 강화 원칙

이 체크리스트는 **시간이 지나면서 길어져야 정상**. 짧아지고 있다면 규율이 약화되고 있다는 경고 신호.

반대로 너무 길어져서 실제로 돌리지 않게 되면, 관련성이 낮은 항목을 별도 파일로 분리 (예: `bug-regression-check-tokenizer.md`).
