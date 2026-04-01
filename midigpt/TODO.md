# MidiGPT TODO — 자체 MIDI LLM 구축 로드맵

## Phase 1: 데이터 준비
- [ ] MAESTRO 전체 데이터셋 다운로드 (1,276곡)
- [ ] 추가 MIDI 데이터셋 수집 (Lakh MIDI, 직접 보유 파일 등 — 목표 500곡+)
- [ ] 데이터 정리 및 폴더 구조화
- [ ] tokenize_dataset.py 실행하여 전체 토큰화
- [ ] 토큰화 결과 검증 (토큰 수, 분포 확인)

## Phase 2: Pre-training (Base Model 학습)
- [ ] 학습 데이터 디렉토리 구성 (midigpt_data/tokens/)
- [ ] train_pretrain.py 실행 (RTX 4090, 12-24시간)
- [ ] 학습 로그 확인 (loss 수렴 여부)
- [ ] 생성 품질 검증 (음악적으로 유의미한 시퀀스인지)
- [ ] midigpt_base.pt 체크포인트 저장

## Phase 3: SFT LoRA Fine-tuning
- [ ] 원본→변주 쌍 데이터 수집 시작 (목표: 200쌍)
- [ ] SFT 데이터 형식 정의 및 저장 파이프라인 구축
- [ ] review_panel.py에 SFT 데이터 저장 기능 추가
- [ ] train_sft_lora.py 실행 (2-4시간)
- [ ] LoRA-Variation 생성 품질 검증

## Phase 4: DPO (인간 리뷰 기반 강화학습)
- [ ] 리뷰 UI 구현 (👍/👎/수정 후 채택)
- [ ] DPO 데이터 축적 파이프라인 구축
- [ ] 50쌍 축적 후 첫 DPO 학습 실행
- [ ] v2.09 Rule DB 13가지 오류 기준으로 rejected 자동 태깅
- [ ] HarmonyEngine 자동 검증 → DPO rejected 연결

## Phase 5: 앱 통합
- [ ] ai_engine.py에 MidiGPT 추론 연결
- [ ] ONNX 변환 스크립트 작성
- [ ] 유저 환경 자동 감지 (GPU/CPU, VRAM, 양자화 단계)
- [ ] LoRA 핫스왑 UI (스타일별 전환)
- [ ] build_exe.py에 모델 파일 포함
- [ ] 최소 사양 테스트 (RTX 3060 / CPU only)

## Phase 6: 지속적 개선
- [ ] 스타일별 LoRA 분리 학습 (jazz, pop, classical 등)
- [ ] 리뷰 데이터 500쌍 돌파 시 DPO 재학습
- [ ] 모델 성능 지표 대시보드 (채택률, 규칙 위반율)
- [ ] 리뷰 2000쌍 돌파 시 Base 모델 확장 검토 (50M→100M)

## 현재 완료된 항목
- [x] 토큰화 시스템 (vocab 672개, encoder, decoder)
- [x] 50M Transformer 아키텍처 (12L/12H/576D, RoPE+SwiGLU+RMSNorm)
- [x] Dataset/DataLoader (pretrain/sft/dpo 3모드)
- [x] Pre-training 학습 스크립트
- [x] SFT LoRA 학습 스크립트
- [x] DPO 학습 스크립트
- [x] LoRA 구현 (적용/저장/로드/머지)
- [x] 추론 엔진 (자동 디바이스 감지, LoRA 핫스왑)
- [x] 배치 토큰화 스크립트
