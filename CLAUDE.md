# MidiGPT — Claude 작업 규약

MIDI 생성 모델(50M param, REMI 계층 토크나이저) + JUCE VST3 플러그인 프로젝트.

## 1. 작업 프로세스 (필수)

모든 코드 변경은 **4단계**를 거친다. 단순 오타 수정도 예외 없음 — 단계를 생략한 만큼 5차까지의 버그 패턴이 반복된다.

```
  [Design Composer] → [Main Coder] + [Sub Coder] → [Reviewer]
        │                   │              │            │
   계약 정의·실패       핵심 로직 구현   테스트·유틸   적대적 리뷰
     모드 열거                                       (bug-history 대조)
```

각 단계의 상세 정의: `.claude/agents/role-*.md`

**착수 금지 조건:** Design Composer 산출물(변경 대상·입출력 계약·실패 모드·영향 범위)이 명시되지 않은 변경은 Main Coder에게 넘어가지 못한다.

**머지 금지 조건:** Reviewer가 `rules/05-bug-history.md`의 패턴 대조를 통과시키지 않은 변경은 커밋되지 않는다.

## 2. 참조

- 계약·정책: `.claude/rules/`
  - `01-contracts.md` — 파일 포맷·토큰·체크포인트 스키마
  - `02-fallback-policy.md` — 기본값 / unknown / 에러 경계
  - `03-windows-compat.md` — 인코딩 / 경로 / 개행
  - `04-commit-discipline.md` — 커밋·재학습 규약
  - `05-bug-history.md` — 1~5차 버그 패턴 (회귀 금지 목록)
- 역할: `.claude/agents/role-*.md`
- 도메인 전문: `.claude/agents/dev-*.md`, `persona-*.md`
- 체크리스트: `.claude/skills/`

## 3. 도메인 agent vs 역할 agent

두 축은 **직교**한다:
- **도메인** (dev-ml, dev-juce, dev-integration, dev-test, dev-docs): *어느 코드 영역*
- **역할** (role-design-composer, role-main-coder, role-sub-coder, role-reviewer): *어느 작업 단계*

예: ML 영역의 버그 수정 = `dev-ml` 도메인 지식 × `role-*` 프로세스.

## 4. 반복 버그 패턴 (요약)

`rules/05-bug-history.md`의 상위 요약. 이 패턴들이 `role-reviewer`의 필수 체크 대상이다:

1. **스키마 불일치** — 같은 디렉토리에 섞이는 메타 파일(`summary.json`)이 데이터 loader의 glob에 걸림
2. **묵시적 fallback** — 명시적 이름이 있는데 매치 실패 시 기본값으로 침묵 강등 (program=0 → accomp)
3. **경계 조건 누락** — fp16 GradScaler, LoRA dtype/device 상속, Windows 인코딩
4. **EOS 조기 종료** — inference 경로에 suppression이 부분 적용
5. **재학습 규약 누락** — 토크나이저/분류기 변경 후 체크포인트 호환성 표기 안 됨

## 5. 신규 작업 착수 시

1. `rules/05-bug-history.md` 를 먼저 읽는다. 유사 패턴이면 설계 단계에서 방어.
2. `agents/role-design-composer.md` 의 산출물 템플릿으로 설계서 작성.
3. 구현 → 리뷰 → 커밋.

## 6. 프로젝트 루트 레이아웃

- `midigpt/` — Python ML 코드 (tokenizer/, training/, inference/, data/, model.py, pipeline.py)
- `juce_daw_clean/` — JUCE VST3 + Standalone (C++)
- `midi_data/`, `midi_data_combined/` — 학습 데이터
- `midigpt_pipeline/` — 파이프라인 중간 산출물 (augmented/, tokenized/, sft/)
- `checkpoints/` — 모델 가중치
- `.claude/` — 본 규약

## 7. Clean Room

- Cubase 바이너리, Ghidra 결과, `juce_app_quarantine/` 접근 금지
- 학습 데이터는 자작 MIDI + 공개 데이터셋(MAESTRO, Lakh, GiantMIDI, POP909 등)
