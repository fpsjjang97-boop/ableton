# MidiGPT — 8주 Sprint Plan (데드라인: 2026-06-01)

> 작성: 2026-04-09
> 데드라인: 2026-06-01 (첫째 주)
> 잔여 기간: **53일 / 약 8주**
> 관련: [06_출시_로드맵.md](06_출시_로드맵.md), [08_DAW_벤치마크_프레임워크.md](08_DAW_벤치마크_프레임워크.md)
> Clean room: `juce_daw_clean/` — [README_CLEAN_ROOM.md](../../juce_daw_clean/README_CLEAN_ROOM.md)

---

## 0. 변경된 전제

1. 기존 `juce_app/` 은 Cubase 15 Ghidra 디컴파일 결과의 파생물이 섞여 있어 **`juce_app_quarantine/` 로 격리** 되었다 (2026-04-09)
2. 새 DAW 코드는 **`juce_daw_clean/` 에서 처음부터 작성**
3. 메인 제품 형태 = **VST3 Plugin (Cubase 15 / Ableton Live / 다른 DAW 안에서 호스팅)**. Standalone Desktop 은 같은 코드베이스에서 `Standalone` 타겟으로 부수적 생산
4. LLM 쪽은 처음부터 깨끗한 영역이므로 **병렬 진행**
5. 출시 1.0 이 아닌 **"시연 가능한 MVP 베타"** 가 6월 첫째 주 마일스톤

---

## 1. 주차별 산출물

### Week 1 — 2026-04-10 ~ 04-16 (분류기 수정 → 재학습 → 빌드 환경 → 골격)

> 🆕 **2026-04-09 업데이트**: 2차 테스터 피드백에서 `_classify_track` 의 매핑
> 버그가 발견되어 Day 1-2 에 **분류기 수정 + 재학습** 이 추가되었다. 이건
> 데이터 추가 수집보다 훨씬 큰 효과를 낼 가능성이 있고, 재학습 결과에 따라
> 이후 Week 의 우선순위가 재조정될 수 있다.

**목표**:
1. 분류기 버그 수정 후 재학습으로 train/val gap 개선 (2.6 → 1.5 미만)
2. `juce_daw_clean/` 이 빈 VST3 로 Cubase 15 에 로드된다.

**Day 1-2 (분류기 수정 Sprint)**

| # | 작업 | 책임 | 검증 |
|---|------|------|------|
| 0a | `_classify_track` 수정 (14 카테고리 전체 사용) | Claude | ✅ 완료 (2026-04-09) |
| 0b | `test_roundtrip.py` 작성 | Claude | ✅ 완료 (2026-04-09) |
| 0c | `tools/audit_track_classification.py` 작성 | Claude | ✅ 완료 (2026-04-09) |
| 0d | `python tools/audit_track_classification.py --verbose --csv audit.csv` 실행 | 개발자 | ≥ 6 카테고리 사용, accomp < 60%, other < 10% |
| 0e | `python test_roundtrip.py --all` 실행 | 개발자 | 전부 PASS |
| 0f | `midigpt_pipeline/` 삭제 후 재토큰화 | 개발자 | 660 → (? ) 토큰 파일 |
| 0g | `train_pretrain.py` 재학습 10 epoch | 개발자 | train/val gap 측정 |
| 0h | 생성 결과 크기 / 트랙 다양성 비교 | 작곡가 | 평균 크기 ↑, 트랙 카테고리 다양화 |

**Day 3-7 (원래 Week 1 작업)**

| # | 작업 | 책임 | 검증 |
|---|------|------|------|
| 1 | JUCE 서브모듈 추가 (`external/JUCE`) | 개발자 | `git submodule status` OK |
| 2 | CMake 빌드 성공 (Windows / RTX 머신) | 개발자 | `MidiGPTPlugin.vst3` 생성 |
| 3 | Cubase 15 에서 빈 플러그인 로드 | 작곡가 | MIDI 트랙 인서트 슬롯에 로드 확인 |
| 4 | Standalone 타겟 빌드 + 실행 | 개발자 | 윈도우 한 개 뜸 |
| 5 | `inference_server.py` 의존성 설치 | 개발자 | `pip install fastapi uvicorn` 통과 |
| 6 | 서버 로컬 실행 + `/health` 응답 | 개발자 | `curl localhost:8765/health` OK |
| 7 | 특수 서브에이전트 5종 생성 | Claude | ✅ 완료 (2026-04-09) |

**Week 1 게이트**:
- [ ] 분류기 감사 통과 (≥ 6 카테고리, accomp < 60%)
- [ ] round-trip 테스트 전부 통과
- [ ] **재학습 train/val gap < 2.0** (목표: < 1.5 — 분류기 수정 효과가 크다면)
- [ ] 생성 MIDI 평균 크기 ≥ 3KB (이전 ~2KB)
- [ ] VST3 가 Cubase 15 에 "MidiGPT" 이름으로 표시
- [ ] 플러그인 창이 뜨고 UI 컨트롤이 표시 (슬라이더 2개 + 드롭다운 + 버튼 + 상태)
- [ ] HTTP 서버가 기동 + health check

---

### Week 2 — 2026-04-17 ~ 04-23 (MIDI IN/OUT 파이프라인)

**목표**: Cubase 에서 입력된 MIDI 가 플러그인을 통과해 MidiGPT 서버로 전달되고, 서버가 돌려준 MIDI 가 다시 Cubase 트랙으로 나온다.

| # | 작업 |
|---|------|
| 1 | `PluginProcessor::processBlock` 에서 MIDI 캡처 → 내부 버퍼 |
| 2 | "Generate" 버튼 → 캡처 버퍼를 `juce::MidiFile` 로 직렬화 |
| 3 | C++ HTTP 클라이언트 (JUCE `URL` 또는 `juce::WebInputStream`) 로 `/generate` 호출 |
| 4 | 응답 MIDI 바이트 → `juce::MidiMessageSequence` 역직렬화 |
| 5 | 다음 `processBlock` 에서 생성 결과를 MIDI 출력으로 전송 |
| 6 | 타이밍 이슈 (생성 중 DAW 재생 중단 여부) 설계 |
| 7 | 에러 처리 (서버 다운, 타임아웃, 잘못된 응답) |
| 8 | 병렬: 데이터 추가 수집 (Lakh 필터 적용 1차 500곡) |

**Week 2 게이트**:
- [ ] Cubase에서 MIDI → 플러그인 → 서버 → 플러그인 → Cubase 왕복 동작
- [ ] 10초 이내 왕복 (작은 입력 기준)
- [ ] 에러 상황에서 Crash 0건
- [ ] 데이터 +500곡 확보

---

### Week 3 — 2026-04-24 ~ 04-30 (UI 확장 + 상태 저장)

**목표**: 플러그인 UI 에서 생성 파라미터를 바꾸고, 결과를 파일로 저장/불러오기.

| # | 작업 |
|---|------|
| 1 | `PluginEditor` 에 PianoRoll 뷰 추가 (입력 + 생성 결과 시각화) |
| 2 | 현재 파라미터 (temperature, style, variations) 가 서버에 전달되는지 확인 |
| 3 | `getStateInformation` / `setStateInformation` 으로 Cubase 프로젝트 저장 시 플러그인 상태 보존 |
| 4 | "Export MIDI" 버튼 — 마지막 생성 결과를 파일로 저장 |
| 5 | "Compare" 뷰 — 원본 vs 생성 결과 나란히 표시 |
| 6 | 병렬: SFT LoRA 준비 (원본↔변주 페어 큐레이션) |

**Week 3 게이트**:
- [ ] 파라미터 변경 → 생성 결과가 실제로 달라짐
- [ ] Cubase 프로젝트 저장 후 재오픈 시 플러그인 상태 유지
- [ ] PianoRoll 뷰에 노트 표시
- [ ] SFT 페어 20-50건 확보

---

### Week 4 — 2026-05-01 ~ 05-07 (LoRA 핫스왑 + 첫 LoRA 학습)

**목표**: 스타일 드롭다운 변경 → 서버가 LoRA 를 핫스왑 → 결과물의 스타일이 바뀐다.

| # | 작업 |
|---|------|
| 1 | `inference_server.py` 의 `/load_lora` 엔드포인트 동작 검증 |
| 2 | 플러그인의 style 드롭다운 change 이벤트 → `/load_lora` 호출 |
| 3 | LoRA 로드 latency 측정 (목표 < 5초) |
| 4 | 첫 LoRA 학습 (city pop) — midigpt/training/train_sft_lora.py |
| 5 | 두 번째 LoRA 학습 (metal) |
| 6 | 세 번째 LoRA 학습 (jazz) — 외부 데이터 + SFT 페어 기반 |
| 7 | 같은 입력 + 다른 LoRA = 결과가 명확히 다른지 사람 청취 |

**Week 4 게이트**:
- [ ] LoRA 어댑터 ≥ 3개 (city pop / metal / jazz)
- [ ] LoRA 핫스왑 < 5초
- [ ] 3 LoRA 청취 시 장르 식별 가능 (개발자 자체 테스트 기준)
- [ ] 데이터 누적 ≥ 1000곡

---

### Week 5 — 2026-05-08 ~ 05-14 (외부 청취 + DPO 1차)

**목표**: 외부 작곡가 3-5명에게 결과 공유 + 첫 사람 청취 라벨 수집.

| # | 작업 |
|---|------|
| 1 | 외부 작곡가 3-5명 모집 완료 (사업가 책임, Week 4까지 시작) |
| 2 | 각자 30분 청취 → Google Form A/B 라벨링 |
| 3 | 라벨 데이터 → DPO 페어 빌드 (`midigpt/build_dpo_pairs.py` 재사용) |
| 4 | 사람 페어 50% + 자동 페어 50% 로 첫 DPO fine-tune |
| 5 | DPO 전후 결과 비교 청취 |
| 6 | 병렬: `inference_server.py` 안정화 (동시 요청, 메모리 누수 점검) |

**Week 5 게이트**:
- [ ] 외부 청취 평균 점수 ≥ 5/10 (첫 라운드, 낮아도 OK)
- [ ] 사람 라벨 ≥ 30건
- [ ] DPO 실행 성공 (SKIP 아님)
- [ ] 크래쉬 없이 서버 1시간 연속 운영

---

### Week 6 — 2026-05-15 ~ 05-21 (폴리쉬 + Audio2MIDI 통합)

**목표**: UI 폴리쉬 + 기존 `agents/audio2midi.py` 연동으로 오디오 입력도 받는다.

| # | 작업 |
|---|------|
| 1 | PluginEditor UI 색상/폰트/여백 정리 |
| 2 | 에러 메시지 한글화 |
| 3 | 플러그인 아이콘 / 스플래시 |
| 4 | `agents/audio2midi.py` → 서버 `/audio_to_midi` 엔드포인트 추가 |
| 5 | 플러그인에 "Drag audio here" 영역 추가 (선택) |
| 6 | README / 사용자 가이드 초안 |
| 7 | Known Issues 목록 |

**Week 6 게이트**:
- [ ] 외부 테스터가 앱 설치 ~ 첫 결과까지 < 5분
- [ ] UI 첫 인상 평점 ≥ 6/10 (내부)
- [ ] Audio2MIDI 기본 동작

---

### Week 7 — 2026-05-22 ~ 05-28 (최종 QA + 시연 영상)

**목표**: 버그 0 수준으로 끌어올리고, 외부용 시연 영상 촬영.

| # | 작업 |
|---|------|
| 1 | Cubase + Ableton + (선택) Logic 호환성 테스트 |
| 2 | 30분 연속 세션 crash 테스트 |
| 3 | 메모리 누수 측정 (Valgrind / Xcode Instruments) |
| 4 | 시연 영상 #1 — 기본 변주 생성 (2분) |
| 5 | 시연 영상 #2 — LoRA 스타일 전환 (2분) |
| 6 | 시연 영상 #3 — Audio → MIDI → 변주 (3분) |
| 7 | 랜딩 페이지 draft (사업가) |
| 8 | 베타 배포 패키지 (설치 스크립트 + 모델 다운로더) |

**Week 7 게이트**:
- [ ] 2개 이상 DAW 에서 동작 (Cubase + Ableton 필수)
- [ ] crash 0건 / 30분 세션
- [ ] 시연 영상 3개 제작
- [ ] 랜딩 페이지 draft 완성

---

### Week 8 — 2026-05-29 ~ 2026-06-01 (릴리즈)

**목표**: 6월 첫째 주에 **"외부에 보여줄 수 있는" MVP 베타 릴리즈**.

| # | 작업 |
|---|------|
| 1 | 마지막 버그 수정 스프린트 |
| 2 | 설치 패키지 최종 빌드 (Windows / macOS) |
| 3 | GitHub 릴리즈 페이지 (v0.1.0-beta) |
| 4 | 보도자료 / 트위터 / 한국 작곡가 커뮤니티 공지 (사업가) |
| 5 | 피드백 채널 오픈 (Discord) |
| 6 | **2026-06-01 — MVP 베타 공개** 🚀 |

**Week 8 게이트**:
- [ ] 설치 패키지 배포 가능
- [ ] GitHub 릴리즈 v0.1.0-beta 게시
- [ ] 시연 영상 3개 공개
- [ ] 외부 피드백 채널 동작
- [ ] 첫 외부 사용자 ≥ 10명

---

## 2. 병렬 워크스트림 (주당 대략 시간 배분)

| 워크스트림 | 주당 시간 비중 | 책임 |
|------------|----------------|------|
| JUCE VST3 개발 | 50% | 개발자 |
| LLM 재학습 / LoRA 학습 / DPO | 25% | 개발자 (GPU 병행) |
| 데이터 수집 / 큐레이션 | 15% | 작곡가 |
| 외부 청취 / 피드백 정리 | 5% | 작곡가 |
| 사업 문서 / 마케팅 / 패널 모집 | 5% | 사업가 |

→ 개발자 총 75%, 작곡가 20%, 사업가 5%. 균형이 개발자 편중이지만 MVP 단계에서는 불가피.

---

## 3. 리스크 + 회피

| 리스크 | 확률 | 임팩트 | 회피 |
|--------|------|--------|------|
| Week 1 JUCE 빌드 실패 | 중간 | 치명 | 개발자가 Day 1 에 JUCE 공식 `AudioPluginHost` 예제 먼저 빌드해서 환경 검증 |
| 데이터 재학습 후 gap 개선 미미 | 중간 | 큼 | Week 2 에 외부 데이터 (Lakh 필터) 통합으로 보강 |
| 사람 패널 5명 모집 지연 | 높음 | 중간 | Week 2부터 모집 시작, 3명이라도 먼저 피드백 |
| LoRA 학습이 과적합 | 중간 | 중간 | rank 축소 (32→16), 데이터 다변화 |
| VST3 → Cubase 호환성 이슈 | 중간 | 큼 | JUCE AudioPluginHost 로 1차 검증, 실패 시 Ableton 먼저 지원 |
| Cubase 관련 과거 git 히스토리 발견 | 높음 | 치명 | Week 1 에 법률 검토 시작, git history 정리 필요 시 BFG / filter-repo |
| 데드라인 내 완료 불가능 | 중간 | 큼 | Week 6 종료 시점에 정직한 재평가, 시연 수준 낮출 준비 |

---

## 4. 데드라인 내 "합의된 축소 기준"

Week 6 (5/21) 종료 시점에 아래 기준 중 **하나라도 미달** 이면 Week 7-8 에서 다음 축소를 적용:

| 지표 | 합격선 | 미달 시 대응 |
|------|--------|-------------|
| Cubase 호환성 | 동작 | Ableton 만 지원 + 시연 |
| LoRA 개수 | ≥ 3 | ≥ 1 (base + 1 스타일) |
| 외부 패널 | ≥ 3명 | 내부 테스터 2명 + 시연 영상으로 대체 |
| 사람 라벨 | ≥ 30건 | DPO 생략, base + SFT 만으로 시연 |
| 설치 패키지 | Win + Mac | Windows 만 |

→ **6월 1일에 반드시 뭔가를 내놓는다**. 완벽한 제품이 아니라 "진짜 동작하는 MVP 베타" 를 외부에 공개하는 것이 본 sprint 의 정의.

---

## 5. 종료 정의 (Definition of Done for Week 8)

6월 1일 자정 기준 다음이 모두 참이면 sprint 성공:

- [ ] `juce_daw_clean/` 에서 빌드된 VST3 가 최소 1개 DAW 에 로드된다
- [ ] 플러그인이 MidiGPT 서버와 통신해 실제 MIDI 변주를 생성한다
- [ ] 생성 결과가 "음악으로 들린다" (내부 청취 기준)
- [ ] 시연 영상 3개가 공개 가능한 상태
- [ ] `juce_app_quarantine/` 의 내용물이 어떤 clean 코드에도 섞이지 않았다
- [ ] 외부 사용자 1명 이상이 실제로 플러그인을 로드하는 걸 확인
- [ ] GitHub 레포에 v0.1.0-beta 릴리즈 태그가 있다

---

## 6. Week 1 즉시 액션 (지금 ~ 내일)

오늘 남은 시간 + 내일 할 것:

1. **본인 (개발자)**:
   - `juce_daw_clean/` 이 생성된 것 확인
   - `cd juce_daw_clean && git submodule add https://github.com/juce-framework/JUCE external/JUCE`
   - `cmake -B build` 로 첫 빌드 시도
   - `pip install fastapi uvicorn` (아직 없으면)
   - 데이터 오염 회수 후 `python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10` 재실행

2. **본인 (작곡가)**:
   - 외부 작곡가 패널 3-5명 모집 리스트 작성 시작
   - Cubase 를 정식 라이선스로 설치 (이미 보유하셨다면 OK)
   - midi_data/ 에 추가로 넣을 곡 5-10 개 준비

3. **본인 (사업가)**:
   - 랜딩 페이지 도메인 후보 3개 선정
   - 6월 1일 발표 커뮤니티/미디어 리스트 작성 시작

4. **Claude (저)**:
   - 비즈니스 문서 4개 Case B + 6월 데드라인 반영 업데이트 (작업 중)
   - Week 1 끝까지 개발자 지원 대기
   - LLM 재학습 결과가 나오면 즉시 분석 도움

---

## 변경 이력

- 2026-04-09: 초판 작성. Case B (Ghidra 파생 격리) + 6월 1일 데드라인 확정 후 작성.
