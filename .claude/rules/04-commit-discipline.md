# Rule 04 — 커밋·재학습 규약

## 4.1 커밋 메시지 형식

기존 로그를 따른다 (`git log --oneline` 참조):

```
<type>(<scope>): <요약 한글>
```

**type:**
- `fix` — 버그 수정
- `feat` — 새 기능
- `chore` — 문서·도구·빌드
- `refactor` — 동작 변화 없는 구조 변경
- `merge` — 브랜치 병합

**scope 예시:** `sft`, `lora`, `tokenizer`, `inference`, `daw`, `pipeline`

**좋은 예:**
```
fix(sft): fp16 GradScaler 누락 + grad_accum loss 스케일링 누락 수정
fix(lora): LoRALinear 파라미터 생성 시 base 레이어 device/dtype 상속
feat: A+B+C 병행 — 데이터/추론/DAW 3축 동시 강화 (2026-04-10)
```

## 4.2 재학습/재토크나이징 표기

**규약:** 다음 중 하나라도 변경하면 커밋 메시지 본문에 `BREAKING: retrain required` 또는 `BREAKING: retokenize required` 를 명시한다.

- `midigpt/tokenizer/vocab.py` — 어휘 변경 = 체크포인트 비호환
- `midigpt/tokenizer/encoder.py` — 인코딩 규칙(특히 `_classify_track`, `_time_to_position`, `_time_to_duration`) = 분포 변경 = 재학습 권장
- `midigpt/tokenizer/decoder.py` — 디코딩 규칙 = 기존 생성 결과와 비호환 (재학습은 불필요, 하지만 정성 평가는 재수행)
- `midigpt/model.py` — 아키텍처(layer 수, 차원, RoPE 등) = 체크포인트 비호환
- SFT/DPO 페어 스키마 = 기존 페어 폐기 필요

### 과거 위반
- `_classify_track` 수정 후 재학습 표기 없이 병합 → 협업자가 구 체크포인트로 inference 했다가 분류 불일치.
- 이제는 encoder 파일 상단 docstring 의 `History` 섹션에도 변경 기록을 남긴다 (자기문서화).

## 4.3 커밋 단위

**규약:**
- **하나의 커밋 = 하나의 의미 있는 변경**. 여러 버그를 한 번에 고쳐도 OK 이지만, 그럴 땐 메시지에 번호/목록으로 열거.
- 리뷰어가 diff 만 보고 "무엇이 왜 바뀌었는지" 이해할 수 있어야 함.

## 4.4 대용량 바이너리

**규약:**
- `.mid`, `.pt`, `.npy` 는 Git LFS 또는 별도 저장소. 일반 커밋에 섞지 말 것.
- `midi_data/` 같은 데이터 디렉토리에 대량 추가 시 **별도 커밋**, 메시지에 파일 수와 용도 명시.

## 4.5 자동화된 후크

- 커밋 시 `--no-verify` **금지** — 훅이 있으면 통과시키거나, 훅의 근본 원인 해결.
- `--amend` 는 origin 에 push 되기 전에만 허용 — push 후 history 재작성 금지.

## 4.6 브랜치 / 머지

**규약:**
- 기본 브랜치: `main`.
- 위험한 작업(`reset --hard`, `push --force`, `branch -D`)은 **사용자 확인 없이 실행 금지**.
- 머지 충돌은 해결해서 올린다 — 한 쪽을 통째로 버리지 말 것(지난 merge 커밋 `0d8b0ee` 는 예외적인 clean-room 대체).

## 4.7 사업 문서 / 민감 정보

- `.env`, `credentials.json`, API 키는 절대 커밋하지 않는다.
- Cubase 리버스 결과, Ghidra 출력은 `juce_app_quarantine/` 에 있으며 **read 금지, commit 당연 금지**.
