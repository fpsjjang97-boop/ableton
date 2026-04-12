# MidiGPT VST3 Plugin — Build & Run Guide

> 이 폴더는 **MidiGPT LLM 을 VST3 플러그인 형태로 DAW (Cubase 15 / Ableton Live / Logic Pro) 에 통합** 하는 C++/JUCE 구현체다.
>
> 법적 안전성을 위해 clean room 원칙을 따르며, 어떤 상용 소프트웨어의 바이너리도 참조하지 않는다. 자세한 원칙은 [README_CLEAN_ROOM.md](README_CLEAN_ROOM.md) 참조.

---

## 0. 전제 조건

| 도구 | 버전 | 설치 방법 |
|------|------|-----------|
| CMake | 3.22+ | https://cmake.org/download/ |
| C++ 컴파일러 | C++17 지원 | Windows: Visual Studio 2022, macOS: Xcode, Linux: gcc 9+ |
| Python | 3.11+ | 기존 midigpt/ 환경과 동일 |
| Git | 2.30+ | 서브모듈 지원 |

**하드웨어 권장**: 추론 서버 구동을 위한 RTX 3060 이상 GPU (12GB+). 추론 서버 없이 플러그인만 빌드/로드는 CPU 만으로도 가능.

---

## 1. JUCE 서브모듈 추가 (최초 1회)

JUCE 는 본 리포에 포함되지 않으므로 직접 추가한다.

```bash
cd D:/Ableton/juce_daw_clean

# JUCE 를 external/ 하위에 서브모듈로 추가
git submodule add https://github.com/juce-framework/JUCE external/JUCE
git submodule update --init --recursive
```

JUCE 저장소 크기가 약 300MB 이므로 처음 clone 은 3-5 분 소요.

### 특정 JUCE 버전 사용 (선택)

안정성을 위해 특정 태그에 고정하고 싶다면:

```bash
cd external/JUCE
git checkout 8.0.0           # 또는 7.0.12, 프로젝트 호환성 확인
cd ../..
git add external/JUCE
```

---

## 2. 빌드 (Windows)

### Visual Studio 2022 (권장)

```cmd
cd D:\Ableton\juce_daw_clean
cmake -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Release
```

빌드 성공 시 산출물 위치:

```
build/
├── MidiGPTPlugin_artefacts/Release/VST3/MidiGPT.vst3      ← VST3 플러그인
└── MidiGPTPlugin_artefacts/Release/Standalone/MidiGPT.exe ← Standalone 앱
```

### Ninja (빠름)

```cmd
cmake -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build
```

---

## 3. 빌드 (macOS)

```bash
cd juce_daw_clean
cmake -B build -G Xcode -DCMAKE_OSX_DEPLOYMENT_TARGET=12.0
cmake --build build --config Release
```

산출물:
- `build/MidiGPTPlugin_artefacts/Release/VST3/MidiGPT.vst3`
- `build/MidiGPTPlugin_artefacts/Release/AU/MidiGPT.component`
- `build/MidiGPTPlugin_artefacts/Release/Standalone/MidiGPT.app`

---

## 4. 빌드 (Linux)

```bash
# 의존성 설치 (Ubuntu 22.04 예시)
sudo apt install -y build-essential libasound2-dev libjack-jackd2-dev \
    libcurl4-openssl-dev libfreetype-dev libfontconfig1-dev \
    libx11-dev libxcomposite-dev libxcursor-dev libxext-dev \
    libxinerama-dev libxrandr-dev libxrender-dev mesa-common-dev

cd juce_daw_clean
cmake -B build -G "Unix Makefiles" -DCMAKE_BUILD_TYPE=Release
cmake --build build -j$(nproc)
```

---

## 5. 플러그인 설치 / DAW 에 인식시키기

### Windows

CMake 의 `COPY_PLUGIN_AFTER_BUILD TRUE` 옵션으로 빌드 성공 시 자동 설치된다. 경로:

```
C:\Program Files\Common Files\VST3\MidiGPT.vst3
```

수동 복사가 필요하면:

```cmd
copy build\MidiGPTPlugin_artefacts\Release\VST3\MidiGPT.vst3 "%CommonProgramFiles%\VST3\"
```

### Cubase 15 에서 인식 시키기

1. Cubase 15 실행
2. **Studio → VST Plug-in Manager**
3. 우측 상단 **Update** 버튼 클릭 → 새 VST3 스캔
4. 리스트에 **MidiGPT** (Company: MidiGPT) 가 보이면 성공
5. 만약 안 보이면 **Add Plug-in Folder** 에 `C:\Program Files\Common Files\VST3\` 가 포함되어 있는지 확인

### Ableton Live 12 에서 인식 시키기

1. Live 실행
2. **Preferences → Plug-ins → VST3 Plug-In Custom Folder** 활성화
3. 경로 설정 (Windows: `C:\Program Files\Common Files\VST3\`)
4. **Rescan** 클릭
5. **Plug-ins** 브라우저에 **MidiGPT** 등장 확인

### Logic Pro (macOS)

AU 버전이 자동 설치됨:
```
~/Library/Audio/Plug-Ins/Components/MidiGPT.component
```

Logic 재시작 → 플러그인 매니저가 자동 스캔 → **Instrument → AU MIDI Controlled Effect → MidiGPT**.

---

## 6. 추론 서버 기동 (LLM 사용 시)

플러그인은 로컬에서 돌아가는 Python 추론 서버와 통신한다. 서버가 없으면 UI 는 동작하지만 generate 버튼은 "서버 연결 실패" 를 반환한다.

### 의존성 설치

```bash
cd D:/Ableton
pip install fastapi uvicorn
```

기존 MidiGPT 의존성(`torch`, `pretty_midi` 등)은 이미 설치돼 있다고 가정.

### 서버 기동

```bash
cd D:/Ableton
python -m midigpt.inference_server \
    --model ./checkpoints/midigpt_ema.pt \
    --port 8765
```

콘솔에 다음이 뜨면 정상:

```
[MidiGPT Server] Loading model: ./checkpoints/midigpt_ema.pt
MidiGPT: Using GPU — NVIDIA GeForce RTX 4080 (17.2GB)
MidiGPT: Model loaded (FP16)
[MidiGPT Server] Loaded. Listening on http://127.0.0.1:8765
[MidiGPT Server] Endpoints: /health /status /generate /load_lora
```

### Health Check

다른 터미널에서:

```bash
curl http://127.0.0.1:8765/health
# {"status":"ok","model_loaded":true}
```

### LoRA 어댑터 사용 (선택)

```bash
python -m midigpt.inference_server \
    --model ./checkpoints/midigpt_ema.pt \
    --lora_jazz ./loras/jazz.pt \
    --lora_citypop ./loras/citypop.pt \
    --lora_metal ./loras/metal.pt
```

---

## 7. 사용 방법 (DAW 안에서)

1. 새 MIDI 트랙 생성
2. MidiGPT 를 해당 트랙에 **MIDI Effect** 로 인서트
3. 플러그인 창 오픈
4. **Style** 드롭다운으로 어댑터 선택 (base / jazz / citypop / metal / classical)
5. **Temperature** 슬라이더로 창의성 강도 조절 (0.7 ~ 1.2 권장)
6. **Variations** 로 후보 개수 (1-5)
7. 트랙에 원본 MIDI 넣기
8. **Generate Variation** 버튼 클릭
9. 결과가 해당 트랙의 출력으로 흘러나옴

---

## 8. 문제 해결 (Troubleshooting)

### 빌드 실패: "Could NOT find JUCE"
- `external/JUCE` 서브모듈이 추가됐는지 확인: `git submodule status`
- 재시도: `git submodule update --init --recursive`

### 빌드 실패: "fatal error C1083: juce_audio_processors.h"
- JUCE 모듈 경로가 잘못됨. CMakeLists.txt 의 `add_subdirectory(external/JUCE ...)` 확인

### Cubase 에서 플러그인이 안 보임
- VST3 Plug-in Manager 에서 **Update** 클릭
- **Deny list** 에 MidiGPT 가 있는지 확인 → 있으면 제거
- `C:\Program Files\Common Files\VST3\MidiGPT.vst3` 파일 존재 확인
- **Cubase 를 재시작**

### "서버 연결 실패" 에러
- `python -m midigpt.inference_server ...` 가 실행 중인지 확인
- 포트 8765 가 다른 프로세스에 의해 사용 중인지 확인 (`netstat -an | findstr 8765`)
- Windows 방화벽이 차단하는지 확인 (localhost 는 보통 OK)

### 생성 결과가 이상함 (노트 적음, 음악 아님)
- 먼저 `python tools/audit_track_classification.py --verbose` 실행
- `python test_roundtrip.py` 실행
- 둘 다 PASS 여야 함
- 재학습이 필요한 경우: `python -m midigpt.pipeline --midi_dir ./midi_data --epochs 10`

### Plugin crash 발생
- 플러그인은 아직 alpha 단계. crash 로그를 `juce_app_quarantine/` 가 **아닌** `juce_daw_clean/crash_logs/` 에 저장해 주세요.

---

## 9. 개발자용 정보

### 폴더 구조

```
juce_daw_clean/
├── CMakeLists.txt                    # JUCE CMake 설정
├── README.md                         # 이 파일
├── README_CLEAN_ROOM.md              # Clean room 원칙
├── external/
│   └── JUCE/                         # JUCE submodule (git ignored)
└── Source/
    ├── PluginProcessor.h/cpp         # VST3 AudioProcessor
    ├── PluginEditor.h/cpp            # Plugin UI
    └── AIBridge.h/cpp                # HTTP client to inference server
```

### 향후 추가 예정 (Sprint Week 2-3)

- `Source/PianoRollView.h/cpp` — 입력/생성 MIDI 시각화
- `Source/StyleEnum.h` — LoRA 스타일 열거
- `Source/MidiExportHelper.h/cpp` — 생성 결과 파일 저장
- `Source/ServerLauncher.h/cpp` — Python 서버 자동 기동 (선택)

### 테스트

C++ 쪽은 아직 JUCE UnitTest 통합 전. Python 쪽:

```bash
cd D:/Ableton
python test_roundtrip.py --all
python test_classifier.py --verbose
python tools/audit_track_classification.py --verbose
```

---

## 변경 이력

- 2026-04-09: 초판. JUCE VST3 skeleton + AIBridge + 기본 UI
