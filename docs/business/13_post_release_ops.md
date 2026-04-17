# Post-release 운영 계획

> 작성 : 2026-04-17
> 적용 시점 : 0.9.0-beta 출시 직후 ~ 1.0 GA
> 관련 : [12_release_checklist.md](12_release_checklist.md)

---

## 목적

출시 후 첫 **14일** 은 "사용자가 어디서 걸려 넘어지는가" 를 읽어내는
시간. 이 기간 동안 2단계로 대응:

1. **Triage (즉시)** : 크래시, 설치 실패, 서버 연결 불가 — 24시간 이내
   hotfix or 회피 문서화.
2. **Batch fix (주간)** : UX 불만, 생성 품질 피드백 — 다음 sprint 스코프로.

---

## 피드백 수집 채널

| 채널 | 용도 | 우선순위 대응 |
|---|---|---|
| GitHub Issues | 재현 가능한 버그 / 기능 제안 | 24h 내 triage 라벨 부착 |
| GitHub Discussions | 사용법 질문 / 일반 대화 | 주 1회 모아 FAQ 업데이트 |
| Discord (예정) | 실시간 코멘트 / 청취 공유 | 모더레이터 순환 당번 |
| Google Form | 구조화된 설문 (Week 1 / Week 2) | 응답 10개 이상 모이면 요약 |
| 플러그인 Report 버튼 | 자동 진단 zip | 이슈 링크와 함께 첨부 |

## 로그 수집 (옵션)

사용자 동의 없이 원격 수집 **안 함** (0.9.0-beta 는 완전 로컬). 대신:

- 플러그인 Report 버튼 — 사용자가 **명시적으로** Desktop 에 zip 을 만들고,
  원하는 경우 이슈에 첨부.
- 서버 `/metrics` 엔드포인트 — 로컬 uvicorn 로그만. 원격 텔레메트리 없음.

1.0 GA 에서는 opt-in 원격 에러 리포팅 (Sentry-lite) 을 검토 — 사용자가
처음 켤 때 동의 UI.

---

## 이슈 트리아지 룩업

| 신고 유형 | 초기 라벨 | SLA | 1차 응답 예시 |
|---|---|---|---|
| 크래시 (재현 있음) | `crash`, `P0` | 24h | "진단 zip 확인 중" + stack 분석 |
| 설치 실패 | `install`, `P1` | 48h | QUICKSTART FAQ 링크 + doctor.py 출력 요청 |
| 서버 연결 불가 | `server`, `P1` | 48h | preflight 결과 요청, 방화벽 확인 |
| 생성 품질 불만 | `quality`, `P2` | 1주 | SFT LoRA 상태 확인, 구체 샘플 요청 |
| 기능 제안 | `enhancement` | 2주 | 스프린트 반영 여부 검토 |
| 문서 오타 / 오류 | `docs` | 2주 | PR 환영 메시지 |

P0 이 주당 3건 초과 → 다음 sprint 의 50% 를 hotfix 로 할당.

---

## Hotfix 흐름

1. GitHub Issue 생성 (P0/P1 라벨)
2. `hotfix/0.9.0-beta.1` 브랜치 from `v0.9.0-beta` 태그
3. 최소 변경 + regression 테스트 추가 (`e2e_test.py`)
4. 리뷰 1인 + 테스터 (유환) 청취 1회
5. `scripts/tag_release.bat 0.9.0-beta.1` → GitHub Release patch
6. CHANGELOG.md `[0.9.0-beta.1]` 섹션 추가

**hotfix 창** : 0.9.0-beta 출시 후 14일 이내만 0.9.0-beta.X. 15일차부터는
0.9.1-beta 정규 릴리스로 병합.

---

## 주간 리뷰 (14일간)

매주 금요일 30분 :

1. 지난 7일 이슈 수 / 라벨 분포 요약
2. 해결된 것 / 열린 P0-P1 현황
3. 공통 불만 TOP 3 → 다음 sprint 백로그
4. 청취 피드백 (작곡가) → DPO 페어 후보
5. `doctor.py` 실패 패턴 집계 → 설치 가이드 개선점

---

## 1.0 GA 로 넘어가는 조건

0.9.0-beta 출시 후 다음이 모두 참일 때 1.0 GA 고려 (최소 4~6주) :

- [ ] P0 누적 < 10건, 전부 해결
- [ ] GitHub star ≥ 100 또는 외부 시연 청취 평균 ≥ 6/10
- [ ] LoRA ≥ 3개 안정 (city pop / jazz / metal)
- [ ] DPO 1차 완료 — 전/후 A/B 청취에서 50% 이상 선호
- [ ] macOS 빌드 1회 검증 (Apple Silicon arm64)
- [ ] 라이선스 이슈 제로 (특히 JUCE 상용 라이선스 확정)
- [ ] 시연 영상 뷰 ≥ 1,000

---

## Rollback 조건

**즉시 롤백** (GitHub Release 를 unlisted 로 내리기) :

- 연속 2회 이상의 데이터 손실 버그
- 악성 코드 / 공급망 공격 증거
- 치명적 라이선스 위반 발견

롤백 시 사용자 공지 : 24시간 이내 Discussions + 이메일 (베타 등록자).
