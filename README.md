# MIDI => 음악

MIDI 데이터를 임베딩하고 패턴을 생성하여 Ableton으로 음악을 제작하는 프로젝트

## 작업 단계

1. MIDI 데이터셋 수집
2. Data 임베딩
3. 패턴 생성
   - MCP 서버 연결 (Git 제공 예정)
4. Ableton 프로그램 사용
5. 데이터베이스 기반으로 음악 제작 테스트 및 고도화

## 전체적인 구조

| 항목 | 내용 |
|------|------|
| 플랫폼 | Ableton |
| 임베딩 자료 구조 | MIDI |
| MCP | [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) |
| MIDI 분석/생성 | [magenta/magenta](https://github.com/magenta/magenta) (Music Transformer) |

---

## 핵심 도구

### Ableton MCP — AI와 Ableton 연결
| 항목 | 내용 |
|------|------|
| 레포 | [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) |
| Stars | ⭐ 2,334 |
| 언어 | Python |
| 용도 | MCP 프로토콜을 통해 AI 모델이 Ableton Live를 직접 제어 |

### Google Magenta — Music Transformer
| 항목 | 내용 |
|------|------|
| 레포 | [magenta/magenta](https://github.com/magenta/magenta) |
| Stars | ⭐ 19,772 |
| 언어 | Python |
| 용도 | MIDI 노트 생성/분석, Music Transformer, MusicVAE, PerformanceRNN 등 |

---

## 오픈소스 MIDI 리소스 리스트

### 1. MIDI 데이터셋 (실제 MIDI 파일 컬렉션)

| # | 레포 | Stars | 설명 | MIDI 규모 |
|---|------|-------|------|-----------|
| 1 | [Metacreation-Lab/GigaMIDI-Dataset](https://github.com/Metacreation-Lab/GigaMIDI-Dataset) | ⭐81 | 현존 최대 심볼릭 음악 데이터셋 | **210만+** |
| 2 | [loubbrad/aria-midi](https://github.com/loubbrad/aria-midi) | ⭐78 | 솔로 피아노 녹음 → MIDI 변환 (약 10만 시간) | **118만+** |
| 3 | [jeffreyjohnens/MetaMIDIDataset](https://github.com/jeffreyjohnens/MetaMIDIDataset) | ⭐148 | MIDI + Spotify 매칭 (1080만 오디오-MIDI 매칭) | **43만+** |
| 4 | [patchbanks/Pop-K-MIDI-Dataset](https://github.com/patchbanks/Pop-K-MIDI-Dataset) | ⭐4 | 증강된 팝 멜로디 학습 데이터 | **30만+** |
| 5 | [craffel/midi-dataset](https://github.com/craffel/midi-dataset) | ⭐170 | Lakh MIDI Dataset 생성 코드 | **17만+** |
| 6 | [xmusic-project/XMIDI_Dataset](https://github.com/xmusic-project/XMIDI_Dataset) | ⭐34 | 감정/장르 라벨이 포함된 MIDI | **10만+** |
| 7 | [asigalov61/Tegridy-MIDI-Dataset](https://github.com/asigalov61/Tegridy-MIDI-Dataset) | ⭐261 | Music AI 모델 학습용 정밀 MIDI 데이터셋 | 대규모 |
| 8 | [lucasnfe/adl-piano-midi](https://github.com/lucasnfe/adl-piano-midi) | ⭐67 | 장르/아티스트별 분류된 피아노 MIDI | **1.1만+** |
| 9 | [asigalov61/Los-Angeles-MIDI-Dataset](https://github.com/asigalov61/Los-Angeles-MIDI-Dataset) | ⭐66 | MIR/Music AI용 SOTA MIDI 데이터셋 | 대규모 |
| 10 | [pozalabs/MID-FiLD](https://github.com/pozalabs/MID-FiLD) | ⭐20 | [AAAI'24] Fine-Level Dynamics MIDI 데이터셋 | — |
| 11 | [patchbanks/WaivOps-NRG-CP](https://github.com/patchbanks/WaivOps-NRG-CP) | ⭐5 | EDM 리듬 코드 진행 MIDI | — |

### 2. MIDI 처리 / 토크나이징 라이브러리

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [craffel/pretty-midi](https://github.com/craffel/pretty-midi) | ⭐1,007 | Python MIDI 처리 표준 라이브러리 |
| 2 | [Natooz/MidiTok](https://github.com/Natooz/MidiTok) | ⭐857 | 딥러닝용 MIDI 토크나이저 (REMI, TSD, CPWord, Octuple 등) |
| 3 | [YatingMusic/miditoolkit](https://github.com/YatingMusic/miditoolkit) | ⭐274 | 고수준 MIDI 처리/조작 툴킷 |
| 4 | [Yikai-Liao/symusic](https://github.com/Yikai-Liao/symusic) | ⭐180 | 심볼릭 음악 처리 통합 툴킷 (C++ 코어 + Python 바인딩) |
| 5 | [steinbergmedia/libmusictok](https://github.com/steinbergmedia/libmusictok) | ⭐46 | C++ MIDI 토크나이징 (MidiTok 호환) |
| 6 | [EleutherAI/aria-utils](https://github.com/EleutherAI/aria-utils) | ⭐6 | MIDI 토크나이저 및 전처리 유틸 |

### 3. AI 음악 생성 모델

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [magenta/magenta](https://github.com/magenta/magenta) | ⭐19,772 | Google — Music Transformer, MusicVAE, PerformanceRNN |
| 2 | [salu133445/musegan](https://github.com/salu133445/musegan) | ⭐2,013 | GAN 기반 멀티트랙 음악 생성 |
| 3 | [ElectricAlexis/NotaGen](https://github.com/ElectricAlexis/NotaGen) | ⭐1,173 | LLM 학습 패러다임 기반 심볼릭 음악 생성 |
| 4 | [bearpelican/musicautobot](https://github.com/bearpelican/musicautobot) | ⭐554 | fastai + Transformer MIDI 음악 생성 |
| 5 | [SkyTNT/midi-model](https://github.com/SkyTNT/midi-model) | ⭐352 | MIDI 이벤트 Transformer |
| 6 | [magenta/symbolic-music-diffusion](https://github.com/magenta/symbolic-music-diffusion) | ⭐280 | 디퓨전 모델 기반 심볼릭 음악 생성 |
| 7 | [carlosholivan/musicaiz](https://github.com/carlosholivan/musicaiz) | ⭐187 | 심볼릭 음악 생성/평가/분석 프레임워크 |
| 8 | [slSeanWU/MIDI-LLM](https://github.com/slSeanWU/MIDI-LLM) | ⭐90 | LLM(Llama 3.2) 기반 Text→MIDI 생성 |
| 9 | [vanstorm9/Midi-AI-Melody-Generator](https://github.com/vanstorm9/Midi-AI-Melody-Generator) | ⭐87 | LSTM 기반 MIDI 멜로디 생성 |
| 10 | [yjhuangcd/rule-guided-music](https://github.com/yjhuangcd/rule-guided-music) | ⭐86 | [ICML 2024] 규칙 기반 디퓨전 음악 생성 |
| 11 | [MusicLang/maidi](https://github.com/MusicLang/maidi) | ⭐28 | MIDI 기반 심볼릭 음악 생성 AI |

### 4. MIDI 임베딩 / 사전학습 / 이해

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [salu133445/muspy](https://github.com/salu133445/muspy) | ⭐509 | 심볼릭 음악 생성 툴킷 (데이터셋 관리, 표현 변환, 평가) |
| 2 | [wazenmai/MIDI-BERT](https://github.com/wazenmai/MIDI-BERT) | ⭐203 | MidiBERT-Piano: MIDI 사전학습 모델 |
| 3 | [RichardYang40148/mgeval](https://github.com/RichardYang40148/mgeval) | ⭐101 | 심볼릭 음악 생성 객관적 평가 도구 |
| 4 | [s-omranpour/DeepMusic](https://github.com/s-omranpour/DeepMusic) | ⭐42 | 신경망용 음악 데이터 전처리 패키지 |

### 5. MIDI MCP 서버 (AI/LLM 연동)

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [ahujasid/ableton-mcp](https://github.com/ahujasid/ableton-mcp) | ⭐2,334 | **AI ↔ Ableton Live MCP 연결** |
| 2 | [tubone24/midi-mcp-server](https://github.com/tubone24/midi-mcp-server) | ⭐33 | AI 모델이 텍스트로 MIDI 생성하는 MCP 서버 |
| 3 | [mikeborozdin/vibe-composer-midi-mcp](https://github.com/mikeborozdin/vibe-composer-midi-mcp) | ⭐20 | Vibe Composer MIDI MCP |
| 4 | [feamster/digitakt-midi-mcp](https://github.com/feamster/digitakt-midi-mcp) | ⭐3 | Digitakt MIDI MCP 연동 |
| 5 | [cfogelklou/midi-mcp](https://github.com/cfogelklou/midi-mcp) | ⭐1 | AI 에이전트 MIDI 재생 기능 |

### 6. MIDI 분석 / 패턴 도구

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [Cornerback24/Python-Midi-Analysis](https://github.com/Cornerback24/Python-Midi-Analysis) | ⭐22 | 노트 기반 MIDI 파일 분석 |
| 2 | [asigalov61/MIDI-TXT-MIDI](https://github.com/asigalov61/MIDI-TXT-MIDI) | ⭐8 | MIDI ↔ TXT 양방향 변환 (NLP 기반 Music AI) |
| 3 | [shiehn/midi_query](https://github.com/shiehn/midi_query) | ⭐6 | 조성/박자/코드 진행으로 MIDI 검색 |

### 7. 큐레이션 / 메타 리소스

| # | 레포 | Stars | 설명 |
|---|------|-------|------|
| 1 | [albertmeronyo/awesome-midi-sources](https://github.com/albertmeronyo/awesome-midi-sources) | ⭐313 | 웹상 MIDI 파일 소스 큐레이션 |
| 2 | [wayne391/symbolic-music-datasets](https://github.com/wayne391/symbolic-music-datasets) | ⭐134 | 심볼릭 음악 데이터셋 인덱스 |
| 3 | [dinhviettoanle/survey-music-nlp](https://github.com/dinhviettoanle/survey-music-nlp) | ⭐30 | NLP 기반 심볼릭 음악 생성/검색 서베이 |

---

## 11.mid 분석 결과

| 항목 | 값 |
|------|-----|
| 타입 | Type 1 (멀티트랙) |
| 트랙 | 2개 (메타 + Omnisphere 02) |
| BPM | 60 (후반부 리타르단도 43~61) |
| 박자 | 4/4 |
| 재생 시간 | 2분 11초 |
| 악기 | Omnisphere (신스 패드/앰비언트) |
| 노트 수 | 387개 |
| 음역 | G#1 ~ A#6 |
| 벨로시티 | 1~68 (부드러운 다이나믹) |
| 추정 조성 | Bb 마이너 / Db 메이저 |
| 서스테인 | CC64 139회 사용 |
| 스타일 | 앰비언트 / 시네마틱 |
