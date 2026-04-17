# MidiGPT — Quick Start  (한 / EN)

> 5분 안에 AI 가 DAW 안에서 MIDI 를 생성하게 만들기.

---

## 한국어

### 1) 필요한 것
- **Windows 10 / 11** (macOS / Linux 는 Phase C)
- **Python 3.10 또는 3.11** — `python --version` 으로 확인.  
  3.13 은 `basic-pitch` 와 호환 안 됨 — 3.10 권장.
- **CUDA-지원 NVIDIA GPU** (8GB+ VRAM). 없으면 CPU 모드 (느림).
- **Cubase 15 / Ableton Live 12 / Reaper** 등 VST3 호스팅 DAW
- **(재빌드 시에만)** CMake 3.22+, Visual Studio 2022 Community + C++ 워크로드

### 2) 한 번만 — 셋업
```cmd
REM 1. 오디오 의존성 (demucs + basic-pitch + librosa 등)
scripts\setup_audio2midi.bat

REM 2. 피아노 정확도 업그레이드 체크포인트 (~123MB)
py -3.10 scripts\download_checkpoints.py

REM 3. 점검
py -3.10 scripts\doctor.py
REM → [1] 서버 [2] A2M 의존성 [3] 피아노 전사 [4] VST3 [5] 모델 전부 OK 여야 함
REM     [3] 만 FAIL 이어도 동작 (정확도 하락)
```

### 3) 매번 — 실행
```cmd
REM 터미널 A: 서버 (유지)
py -3.10 -m midigpt.inference_server --model .\checkpoints\midigpt_best.pt

REM 터미널 B 또는 Cubase: 플러그인 로드
REM   - Standalone: juce_daw_clean\build\MidiGPTPlugin_artefacts\Release\Standalone\MidiGPT.exe
REM   - VST3:       DAW 에서 MIDI 트랙 → MidiGPT 인서트
```

### 4) 쓰는 법
1. DAW 에서 MIDI 를 재생 → 플러그인이 자동 캡처 (`Captured: N` 카운트 상승)
2. **Space** 또는 **Generate** 버튼 → 10~30초 후 변주 MIDI 가 재생 시작
3. **Ctrl+E** → 결과 `.mid` 로 저장
4. **Ctrl+Z** → 이전 변주로 되돌리기
5. 오디오 레퍼런스를 쓰려면 `.wav` / `.mp3` 를 플러그인 창에 **드래그 앤 드롭**

### 5) 문제가 생기면
```cmd
py -3.10 scripts\doctor.py         REM 5개 체크 한 번에 진단
py -3.10 scripts\e2e_test.py       REM 서버 파이프라인 회귀 검사
```

+ 리포트가 필요하면 플러그인 창의 **Report** 버튼 → Desktop 에 진단 zip 생성

---

## English

### 1) Prerequisites
- **Windows 10 / 11** (macOS / Linux in Phase C)
- **Python 3.10 or 3.11** (3.13 incompatible with `basic-pitch`).
- **NVIDIA GPU with 8GB+ VRAM** (CPU works but slow)
- **VST3 host**: Cubase 15, Ableton Live 12, Reaper, etc.
- **(only to rebuild)** CMake 3.22+, Visual Studio 2022 Community with C++ workload

### 2) One-time setup
```cmd
REM 1. Audio dependencies (demucs, basic-pitch, librosa, ...)
scripts\setup_audio2midi.bat

REM 2. Piano accuracy upgrade checkpoint (~123 MB)
py -3.10 scripts\download_checkpoints.py

REM 3. Verify
py -3.10 scripts\doctor.py
REM  All 5 checks should PASS. [3] (Tier 1 checkpoints) can FAIL — plugin
REM  still works, just with lower piano/drum transcription accuracy.
```

### 3) Every session
```cmd
REM Terminal A (keep open):
py -3.10 -m midigpt.inference_server --model .\checkpoints\midigpt_best.pt

REM Terminal B or DAW: load the plugin
REM   Standalone: juce_daw_clean\build\MidiGPTPlugin_artefacts\Release\Standalone\MidiGPT.exe
REM   VST3:       insert "MidiGPT" on a MIDI track in your DAW
```

### 4) How to use
1. Play MIDI in your DAW → plugin auto-captures (watch the `Captured:` counter)
2. Press **Space** or click **Generate** → variation starts playing in 10-30 s
3. **Ctrl+E** → export the result as `.mid`
4. **Ctrl+Z** → revert to the previous variation
5. To use an audio reference: drag a `.wav` / `.mp3` onto the plugin window

### 5) Troubleshooting
```cmd
py -3.10 scripts\doctor.py         REM Full 5-point diagnostic
py -3.10 scripts\e2e_test.py       REM Server pipeline regression test
```

If you need to file an issue, click the **Report** button in the plugin —
it dumps diagnostics to a folder on your Desktop that you can zip and attach.

---

## FAQ

**Q. 생성 결과가 너무 희소해요 (노트가 드물어요).**  
SFT LoRA 체크포인트가 없어서 pre-training only 모드로 돌기 때문입니다.
`lora_sft_best.bin` 을 다운로드 받거나, 동료에게 최근 LoRA 를 요청하세요.

**Q. Audio → MIDI 가 드럼밖에 못 뽑아내요.**  
입력 오디오에 선명한 피치 악기가 있는지 확인. 심플한 synth / 효과음은 PTI 가 0 notes 를
반환할 수 있습니다 — 정상 거동. 실제 피아노 / 베이스 / 기타 녹음으로 다시 시도.

**Q. Cubase 가 플러그인을 인식 못 해요.**  
`scripts\setup_build_env.bat` 에서 cmake/VS 확인 → `juce_daw_clean\build.bat --install`
(관리자 권한) 으로 `%ProgramFiles%\Common Files\VST3\` 에 복사. Cubase → Studio →
VST Plug-in Manager → Update.

**Q. 첫 호출이 엄청 느려요.**  
Demucs, PTI, PyTorch 가 첫 inference 때 모델 로드. 2-3번째부터는 빨라집니다.
