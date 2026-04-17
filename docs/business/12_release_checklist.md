# 0.9.0-beta 출시 체크리스트

> 작성 : 2026-04-17
> 목표 출시 : 2026-06-01 (첫째 주)
> 관련 : [09_8주_Sprint_6월데드라인.md](09_8주_Sprint_6월데드라인.md),
>        [11_demo_storyboard.md](11_demo_storyboard.md)

**원칙** : 체크 표시가 안 된 항목이 하나라도 있으면 태그 금지.

---

## 1. 코드 / 빌드

- [ ] `main` 브랜치 CI 그린 (GitHub Actions 세팅 후)
- [ ] `python scripts/doctor.py` 5/5 OK (참조 머신 기준)
- [ ] `python scripts/e2e_test.py` 4/4 PASS (server 기동 상태)
- [ ] `juce_daw_clean/build.bat --install` 성공 — VST3 / Standalone 아티팩트 존재
- [ ] `juce_daw_clean/smoke.bat` 3/3 OK
- [ ] Cubase 15, Ableton Live 12, Reaper — 최소 2종에서 로드 확인
- [ ] 64bit Windows 10 / 11 설치 검증 (클린 VM 권장)
- [ ] 플러그인 1시간 연속 구동 — 메모리 누수 < 50MB, CPU idle < 3%

## 2. LLM / 생성 품질

- [ ] SFT LoRA 재학습 완료 (valid_batches > 0, Best loss < 3.0)
- [ ] 재학습 후 생성 결과 밀도 — `generate_json` 출력이 입력 대비 0.5~1.5x 노트 수
- [ ] City pop LoRA 1개 + base LoRA 최소. 스타일 전환 청취 시 식별 가능
- [ ] FSM grammar — 중복 노트 0 건, Bar 역행 0 건 (1000 샘플 검사)
- [ ] score_loglik 재랭킹이 동작 — num_return_sequences=3 에서 선택이 고정 결과 아님

## 3. Audio2MIDI

- [ ] PTI 체크포인트 `~/piano_transcription_inference_data/note_F1=...` 123MB 존재
- [ ] 피아노 녹음 샘플 5곡 — 각각 F1 > 85% (수동 평가)
- [ ] ADTOF 없어도 파이프라인 FAIL 없이 librosa fallback 작동
- [ ] 6초 미만 오디오 드롭 — crash 없음 (BPM=0 방어 확인)
- [ ] 10분 이상 오디오 드롭 — 타임아웃 메시지 표시, UI 안 멈춤

## 4. UX / UI

- [ ] 한/영 언어 토글 — 모든 라벨 + 툴팁 + 상태 메시지 대응
- [ ] First-run 튜토리얼 — 새 설치 머신에서 1회 표시, 이후 안 나옴
- [ ] 크래시 복구 다이얼로그 — 강제 종료 재현 후 다음 실행에서 제시
- [ ] Report 버튼 — Desktop 에 zip 생성 + 탐색기 오픈
- [ ] 키보드 단축키 7종 — Cubase 에서도 포커스 시 동작
- [ ] 리사이즈 — 580×420 ~ 1600×1100 범위에서 레이아웃 깨짐 없음
- [ ] Dark / Light 테마 토글 — 재시작 후 유지

## 5. 문서

- [ ] `QUICKSTART.md` 실제 새 머신에서 그대로 따라가면 동작 (드라이런)
- [ ] `CHANGELOG.md` — 0.9.0-beta 섹션 확정 (Unreleased 에서 내려옴)
- [ ] `CREDITS.md` — 모든 의존성 라이선스 확인 ✅
- [ ] `LICENSE` — MIT or JUCE 상용 라이선스 결정 완료
- [ ] README 스크린샷 최소 3장 (플러그인 창 / 피아노롤 / 서버 info)
- [ ] 시연 영상 촬영/편집 완료 ([11_demo_storyboard.md](11_demo_storyboard.md))

## 6. 법무 / 라이선스

- [ ] JUCE : GPLv3 준수 배포 vs 상용 라이선스 구매 결정
- [ ] MAESTRO (CC-BY-NC-SA) 데이터로 학습된 체크포인트가 배포물에 포함되는지 검토
- [ ] ADTOF (AGPL) 는 external install 로 유지 (번들하지 않음)
- [ ] 개인정보 : PluginLogger 가 PII 수집 안 하는지 확인 (파일 경로만)
- [ ] 약관 / 면책 조항 : "생성 결과의 저작권은 사용자 소유, 품질 무보증" 포함

## 7. 배포 인프라

- [ ] `scripts/make_release.bat 0.9.0-beta` 실행 — zip 생성 확인
- [ ] zip 해제 후 QUICKSTART.md 절차로 다른 머신에서 동작 (최소 1회)
- [ ] GitHub Release 초안 작성 (CHANGELOG 발췌 + 다운로드 URL)
- [ ] 체크포인트 / 데이터셋은 별도 호스팅 (Zenodo or 자체 S3) — 링크 확인
- [ ] 서버 배포 가이드 (로컬 서버 실행) 는 QUICKSTART 섹션 3 에 포함됨

## 8. 커뮤니케이션

- [ ] 테스터 3-5명 청취 라벨 완료 (Phase B DPO 재료)
- [ ] 사업 문서 09 의 "Week 5 게이트" 통과 — 외부 평균 점수 ≥ 5/10
- [ ] 이메일 / Discord / Slack 발표 초안 준비
- [ ] 시연 영상 YouTube 업로드 (unlisted → 출시일 public)

---

## 태그 릴리스 절차 (모두 체크 후)

```cmd
scripts\tag_release.bat 0.9.0-beta
REM git tag v0.9.0-beta + 검증 + make_release.bat 0.9.0-beta 실행
REM (서명/원격푸시는 사용자 수동)
```

출시 완료 후 `CHANGELOG.md` 의 `[Unreleased]` → `[0.9.0-beta] - 2026-06-XX` 로 확정.
