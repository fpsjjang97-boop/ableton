# Vocab v3 재설계 로드맵

작성일: 2026-04-21
기반 문서:
- `MidiGPT_개발자전달용_현재구조_결함리스트_2026-04-21.md` (결함 #1, #5, #6, #7, #8)
- `MidiGPT_개발자전달용_커서형작곡모델_정리_2026-04-21.txt`

## 상태

**설계 제안 — 구현 시작 전 동업자 정렬 필수.** Vocab 수정은
`checkpoints/*.pt` 호환 불가 (rules/05 패턴 F) → pre-train 처음부터
재학습 필요 (GPU 6.5 h+). 방향 확정 전까지 코드 변경 없음.

## 목표

현재 vocab v2 (size 527) 는 "next-token prediction 용 일반 토큰".
사용자 제품 목표 = "조건부 커서형 작곡기" 와 어긋남. v3 는
**조건부 생성** 을 타이트하게 제어할 수 있도록 재설계.

---

## 변경 요약

### 1. Task identity tokens (결함 #6)

현재: 모든 태스크가 동일 입력 형식. 모델은 입력만 보고 요청이 무엇인지
모름.

추가:
```
Task_continue      — 이어쓰기
Task_variation     — 변주 생성
Task_track_infill  — 특정 트랙 채우기
Task_bar_infill    — 특정 bar 채우기
Task_melody2accomp — 멜로디 → 반주
Task_chords2comp   — 코드 → 반주
Task_bass_only     — 베이스만 생성
```

위치: `<BOS>` 다음 첫 번째 토큰.

효과: 모델이 어떤 태스크인지 확정적으로 알아 샘플링 경로 분기.
SFT pair 생성 시에도 태스크별 분포 조절 가능.

### 2. SongContext tokens (결함 #8)

현재: Key / Style / Section / Tempo 만 존재. 곡 전체를 지휘하는
상위 메타는 없음.

추가:
```
Groove_<name>     — "laidback", "driving", "halftime", "swing", ...
Density_<0..3>    — 음 밀도 (sparse ~ dense)
Energy_<0..7>     — dynamic curve point (intro=0, build=4, chorus=7)
Motif_<id>        — 곡 내 동일 motif 마커 (반복 구조 명시)
Register_<low|mid|high|wide>  — 음역대
```

위치: `Key` / `Tempo` 다음, `Bar_0` 이전.

효과: 여러 트랙이 따로 생성돼도 동일 SongContext 를 공유 → 통일감.
bar 별 Energy_N 을 조정해 intro→build→chorus 흐름 명시 가능.

### 3. Style vocab 확장 (결함 #5)

현재 `TRACK_TYPES` 는 있지만 `STYLES` 목록은 제한적. 8개 기본 + 소수 확장.

추가:
```
ballad, rock, metal, kpop, citypop, jazz-waltz, shuffle, 
ambient-pad, house, techno, drum_n_bass, orchestral-dramatic,
orchestral-pastoral, lofi-hiphop, future-bass, trap
```

현재 `base / jazz / citypop / metal / classical` 에서 다수 장르 추가.

### 4. Target track conditioning (결함 #7)

현재: 한 번에 모든 트랙 생성. 특정 트랙만 생성하려는 제어 없음.

추가:
```
TargetTrack_<type>   — 생성 대상 트랙 하나 명시 (accomp/bass/drums/...)
FreezeTrack_<type>   — 생성 중 건드리지 말아야 할 트랙
```

SFT pair 에서 `<Task_track_infill> <TargetTrack_bass> [기존 트랙들] <SEP> [생성할 bass 토큰]` 형식으로 학습.

### 5. Chord-progression 강제 (결함 #4)

현재: `ChordRoot_X` / `ChordQual_Y` 이 소프트 컨디션. 모델이 무시 가능.

변경: Bar 시작마다 해당 bar 의 chord 토큰을 **강제 prefix** 로 주입.
Inference 때 FSM 에 "매 Bar_N 직후 이번 bar 의 ChordRoot/Qual 을
받기 전까지 다른 토큰 금지" 추가.

이건 vocab 변경 아닌 FSM 로직 변경. 호환 OK.

---

## 마이그레이션 경로

| 단계 | 내용 | 기간 |
|-----|------|------|
| 1 | vocab v3 제안 검토 (이 문서) | 1주 |
| 2 | 동업자 정렬 — GPU 자원 확보, 재학습 승인 | 1주 |
| 3 | `vocab.py` v3 구현 + encoder/decoder 업데이트 | 2~3일 |
| 4 | 기존 MIDI 데이터로 v3 토큰 재생성 (스크립트) | 1일 |
| 5 | Pre-train 재실행 (midi_data + 확장 데이터) | 6~10시간 |
| 6 | SFT pair 재생성 (task-conditioned) | 1일 |
| 7 | SFT LoRA 재학습 | 30분~1시간 |
| 8 | 회귀 + 품질 측정, reviewer gate 통과 | 1일 |

총 예상: 2~3주 (GPU 시간 제외).

---

## 호환성 영향

**BREAKING:**
- `checkpoints/midigpt_best.pt` (pre-train) — **폐기**. 처음부터 재학습.
- `checkpoints/lora/lora_sft_best.bin` — 폐기. 재학습.
- `midigpt_pipeline/tokenized/*.npy` — 재생성 필요.
- `midigpt_pipeline/sft/*.json` — 재생성 필요.

**호환 유지:**
- Tokenizer/encoder/decoder API signature (내부 구현만 변경).
- Dataset loader (`dataset.py`) — block_size 등 무변경.
- Training loop (`train_pretrain.py`, `train_sft_lora.py`) — 그대로 사용.
- Inference engine API — `generate_to_midi` signature 유지.
- DAW UI — 변경 없음. 스타일 드롭다운만 확장 (코드 수정 1곳).

---

## 위험 요소

1. **GPU 시간**: 처음부터 재학습은 RTX 4080 기준 6.5h + SFT 별도. 동업자
   일정 확보 필수.
2. **데이터 양 부족**: v3 의 task tokens 이 유효하려면 각 task 별로
   충분한 SFT pair 필요. `build_sft_pairs.py` 에 task 분기 추가 시
   일부 task 에서 pair 수가 부족할 가능성.
3. **기존 품질 퇴행**: v2 에서 잘 나오던 변주 패턴이 v3 에서 task
   다양성 수용하느라 품질 하락 가능. 회귀 테스트 필수.
4. **Style 스펙 확장의 실효성**: ballad 등 토큰 추가해도 해당 장르
   학습 데이터가 적으면 토큰 효과 미미. 데이터 확보가 vocab 확장보다
   먼저.

---

## 동업자 정렬 체크리스트

- [ ] 재학습 GPU 시간 확보 (6.5h+ pre-train, 30m SFT, 총 1일 이상 점유)
- [ ] v3 토큰 목록 리뷰 (이 문서의 "변경 요약" 5개 섹션)
- [ ] 스타일 목록 확정 (결함 #5 "ballad 포함 요구")
- [ ] task identity 종류 확정 (현재 7개 제안)
- [ ] SongContext 필드 확정 (Groove/Density/Energy/Motif/Register)
- [ ] Target-track 학습 페어 설계 — `build_sft_pairs.py` 에 task
      분기를 어떻게 넣을지
- [ ] 데이터 확보 전략 (각 task 최소 100 pair 목표)
- [ ] 기존 `midigpt_best.pt` 폐기 일정 (언제 v3 pre-train 시작할지)

---

## 다음 액션

1. 이 문서 리뷰 + 동업자 서면 검토 요청.
2. 정렬 완료 후 `midigpt/tokenizer/vocab.py` 에 v3 TOKEN 추가 PR 시작.
3. 당장은 **비-BREAKING 3건 (Harmonic boost, Reviewer, Unified Composer)**
   으로 체감 품질 개선 가능한지 먼저 측정. v3 는 그 이후 블록.
