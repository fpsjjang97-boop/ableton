# Rule 03 — Windows 호환성

프로젝트 주 개발 환경: **Windows 11 + git-bash/PowerShell**. 협업자는 Linux GPU 서버. 모든 코드가 **양쪽에서 돌아야 한다**.

## 3.1 파일 I/O 인코딩

**규약:** 모든 `open()` 호출은 `encoding="utf-8"` 을 **명시**한다.

```python
# OK
with open(path, "r", encoding="utf-8") as f: ...
with open(path, "w", encoding="utf-8") as f: ...

# 금지 — Windows 에서 cp949 로 열려 한글 파일명/내용 깨짐
with open(path) as f: ...
```

### 과거 위반
- 이전 리포트(2026-04-08): Windows 인코딩 버그 — `open()` 이 인코딩 생략되어 한글 트랙명/MIDI 파일명에서 UnicodeDecodeError.

## 3.2 stdout 인코딩

**규약:** `print()` 에 한글이 포함되는 스크립트는 UTF-8 stdout 을 보장한다.

```python
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
```

또는 환경변수 `PYTHONIOENCODING=utf-8` 를 파이프라인 진입점에서 설정.

## 3.3 경로

**규약:**
- 문자열 결합 대신 `pathlib.Path` 사용 (`Path(a) / b / c`)
- 하드코딩된 구분자 `/` 또는 `\\` 금지, 구분자가 필요하면 `os.sep` 또는 `Path`
- 명령줄에서 쓰는 경로는 forward slash 로 통일 (bash + PowerShell 모두 수용)
- 쉘 명령에서 공백/한글 포함 경로는 반드시 큰따옴표로 감쌈

## 3.4 개행

**규약:**
- 저장소 `.gitattributes` 가 있으면 이를 따른다. 없다면 신규 생성 파일은 LF 개행.
- Python 코드 `.py` 는 LF.
- 사용자에게 보여지는 텍스트(MIDI 메타, 생성 리포트 등)는 `\n` 사용, `\r\n` 강제 금지.

## 3.5 프로세스 기동

**규약:** `subprocess` 로 파이썬 재귀 호출 시 `sys.executable` 을 쓰고 `shell=False` 를 기본.

```python
# OK
subprocess.run([sys.executable, "-m", "midigpt.build_sft_pairs", ...], shell=False)

# 금지 — Windows 에서 "python" 이 PATH 에 없을 수 있음
subprocess.run("python -m ...", shell=True)
```

## 3.6 한글 파일명

**규약:**
- 입출력 디렉토리에 한글 파일명이 존재할 수 있음 (`원신_output.mid` 등).
- `glob`/`rglob` 는 유니코드 안전하므로 그대로 사용 가능.
- 콘솔 출력에 한글 파일명이 깨지면 3.2 규약 위반.

## 3.7 git

**규약:**
- `core.autocrlf=false` 권장 (양 측 개발자 모두).
- Windows 에서 `git diff` 결과에 CR 표시가 보이면 파일이 CRLF 로 체크인된 것 — 의도된 게 아니면 정리.

## 3.8 CUDA / bf16

**규약:**
- Windows 개발 환경(notebook/laptop)에서는 CUDA 미가용 가정 (`torch.cuda.is_available()` 분기).
- bf16 는 Ampere+ 에서만 — 협업자 서버가 그 이하면 fp16 로 자동 fallback (autocast dtype 동적 결정).
- GradScaler 는 fp16 에서 필수, bf16 에서는 비활성 — `use_amp` + `autocast_dtype` 을 짝으로 결정.

### 과거 위반
- 5차 Bug fix (커밋 `10364fb`): fp16 GradScaler 누락으로 loss 가 조용히 NaN.
- 5차 Bug fix (커밋 `4b24bb8`): LoRALinear 가 base layer 의 device/dtype 을 상속받지 않아 cpu/gpu 혼합.
