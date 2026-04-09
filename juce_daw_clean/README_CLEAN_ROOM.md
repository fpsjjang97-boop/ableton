# MidiGPT DAW — Clean Room 영역

> 생성: 2026-04-09
> 상태: Clean Room — 타 회사의 상용 소프트웨어를 참조하지 않고 처음부터 작성된 영역
> 데드라인: 2026-06-01 (첫째 주) — VST3 Plugin 시연 가능 수준

---

## 이 폴더는 무엇인가

본 폴더 `juce_daw_clean/` 는 MidiGPT 프로젝트의 **DAW 구현 영역** 이며, 다음 원칙을 따른다:

1. **어떤 상용 소프트웨어의 바이너리도 참조하지 않는다** — Ghidra, IDA, OllyDbg, dnSpy 등 역공학 도구의 산출물을 사용하지 않는다
2. **디컴파일된 코드를 본 사람이 작성하지 않는다** — Clean room 원칙에 따라, 본 폴더의 코드를 쓰는 주체(Claude AI 어시스턴트 또는 인간 협력자)는 이전에 해당 상용 소프트웨어의 내부 구조를 본 적이 없어야 한다
3. **참고 자료는 오직 공개된 소스만 사용한다** — JUCE 공식 문서, VST3 SDK 공개 문서, Steinberg 개발자 포털 공개 자료, 오픈소스 DAW (라이선스 호환 범위 안에서)

## 왜 이런 폴더가 필요한가

2026-04-09 이전에 본 프로젝트에는 `juce_app/` 폴더가 있었고, 그 안의 `Source/Core/` 의 일부가 **Steinberg Cubase 15 의 Ghidra 디컴파일 결과물을 참고한 파생 코드** 를 포함하고 있었다. 본 프로젝트의 법적 안정성과 상용화 가능성을 확보하기 위해, 해당 폴더는 `juce_app_quarantine/` 로 격리되었고, DAW 코드는 본 폴더에서 처음부터 새로 작성된다.

격리의 의미:
- `juce_app_quarantine/` 의 내용물은 본 clean room 작성에 **일절 참조하지 않는다**
- 본 clean room 의 작성자는 격리 폴더의 파일을 **읽지 않는다**
- 격리 폴더는 법적 정리 이후 삭제 또는 영구 보관 처리된다

## 참고 자료 (공개 소스만)

본 폴더의 모든 코드는 다음 자료를 기반으로 한다:

| 자료 | 라이선스 | URL |
|------|----------|-----|
| JUCE Framework 공식 문서 | JUCE License (GPLv3 + Commercial) | https://juce.com/learn/documentation |
| JUCE GitHub (public) | GPLv3 / Commercial | https://github.com/juce-framework/JUCE |
| JUCE Tutorials (공식) | 공개 | https://juce.com/learn/tutorials |
| VST3 SDK 공식 | Steinberg Proprietary / GPLv3 이중 | https://steinbergmedia.github.io/vst3_dev_portal/ |
| VST3 Developer Portal | 공개 | https://steinbergmedia.github.io/ |
| The Audio Programmer (YouTube) | 공개 교육 자료 | https://www.theaudioprogrammer.com/ |
| Cubase 사용자 매뉴얼 (Steinberg 공식 PDF) | 공개 배포 | Steinberg 웹사이트 |
| Cubase Operation Manual — 사용자 관점 관찰 노트만 | N/A | 본인이 정식 라이선스로 사용하고 관찰한 내용 |

**절대 참조하지 않는 것**:
- Cubase / Steinberg 제품의 디컴파일 결과물
- Cubase / Steinberg 제품의 DLL, EXE, 내부 리소스 파일
- Cubase 코드를 본 사람의 기억이나 노트
- 본 프로젝트의 `juce_app_quarantine/` 폴더

## 라이선스

- JUCE 의 GPLv3 조건 하에서 개발 시작. 상용 출시 단계에서 JUCE 상용 라이선스 전환 검토 필요.
- 본 폴더의 모든 코드는 MidiGPT 팀의 원본 저작물이며, 향후 상용 라이선스 또는 오픈소스 라이선스로 전환 가능.

## 작성 주체

본 폴더의 초기 skeleton 은 Claude (Anthropic) AI 어시스턴트에 의해 2026-04-09 에 생성되었다. 작성 시점에 해당 AI 세션은 Cubase 15 의 내부 구조, Ghidra 디컴파일 결과물, 또는 `juce_app_quarantine/` 폴더의 내용을 **한 번도 읽지 않은 상태** 였다.

## 폴더 구조 (초기)

```
juce_daw_clean/
├── README_CLEAN_ROOM.md       ← 이 파일
├── CMakeLists.txt             ← JUCE 빌드 설정
├── Source/
│   ├── PluginProcessor.h      ← VST3 AudioProcessor (JUCE 표준)
│   ├── PluginProcessor.cpp
│   ├── PluginEditor.h         ← 플러그인 UI (JUCE Component)
│   └── PluginEditor.cpp
└── (future)
    ├── AI/                    ← LLM 통합 (HTTP 클라이언트)
    ├── Core/                  ← 트랙/타임라인 모델
    └── UI/                    ← 피아노롤/파라미터 UI
```

## 변경 이력

- 2026-04-09: 폴더 생성, clean room 원칙 확립
