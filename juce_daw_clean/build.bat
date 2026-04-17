@echo off
REM ============================================================================
REM  MidiGPT VST3 Plugin — Windows Build Helper
REM ============================================================================
REM
REM  Requires:
REM    - Visual Studio 2022 with "Desktop development with C++" workload
REM    - CMake 3.22+ (either standalone or VS component "C++ CMake tools")
REM    - JUCE framework at juce_daw_clean/external/JUCE (already cloned)
REM
REM  Usage:
REM    build.bat              REM Release build
REM    build.bat Debug        REM Debug build
REM    build.bat clean        REM wipe build/ directory
REM
REM  Output:
REM    build/MidiGPTPlugin_artefacts/Release/VST3/MidiGPT.vst3
REM    build/MidiGPTPlugin_artefacts/Release/Standalone/MidiGPT.exe
REM
REM  VST3 is auto-copied to:
REM    C:\Program Files\Common Files\VST3\MidiGPT.vst3
REM
REM ============================================================================

setlocal
cd /d "%~dp0"

if "%1"=="clean" (
    echo [clean] removing build directory...
    rmdir /s /q build 2>nul
    echo [clean] done.
    exit /b 0
)

set BUILD_TYPE=%1
if "%BUILD_TYPE%"=="" set BUILD_TYPE=Release

echo.
echo ============================================================================
echo   MidiGPT VST3 Plugin Build
echo   Build type: %BUILD_TYPE%
echo ============================================================================
echo.

REM --- Sanity check: JUCE present? ---
if not exist "external\JUCE\CMakeLists.txt" (
    echo [ERROR] JUCE not found at external\JUCE
    echo         Run: git clone https://github.com/juce-framework/JUCE.git external\JUCE
    exit /b 1
)

REM --- Sanity check: cmake available? ---
where cmake >nul 2>&1
if errorlevel 1 (
    echo [ERROR] cmake not found in PATH
    echo         Install from https://cmake.org/download/ or add VS CMake component
    exit /b 1
)

REM --- Configure ---
echo [cmake] configuring...
cmake -B build -G "Visual Studio 17 2022" -A x64
if errorlevel 1 (
    echo [ERROR] cmake configure failed
    exit /b 1
)

REM --- Build ---
echo.
echo [cmake] building %BUILD_TYPE%...
cmake --build build --config %BUILD_TYPE% --parallel
if errorlevel 1 (
    echo [ERROR] build failed
    exit /b 1
)

echo.
echo ============================================================================
echo   Build complete
echo ============================================================================
echo.

REM --- Smoke artefact check (Sprint 35 ZZ2) ---
call "%~dp0smoke.bat" %BUILD_TYPE%
if errorlevel 1 (
    echo [WARN] smoke reported missing artefacts.
)

REM --- Show output ---
if exist "build\MidiGPTPlugin_artefacts\%BUILD_TYPE%\VST3\MidiGPT.vst3" (
    echo   VST3:       build\MidiGPTPlugin_artefacts\%BUILD_TYPE%\VST3\MidiGPT.vst3
)
if exist "build\MidiGPTPlugin_artefacts\%BUILD_TYPE%\Standalone\MidiGPT.exe" (
    echo   Standalone: build\MidiGPTPlugin_artefacts\%BUILD_TYPE%\Standalone\MidiGPT.exe
)
echo.
echo Next steps:
echo   1. Start Cubase 15
echo   2. Studio -^> VST Plug-in Manager -^> Update
echo   3. Find "MidiGPT" in the plugin list
echo   4. Insert into a MIDI track
echo.
echo   Also start the inference server in a separate terminal:
echo     python -m midigpt.inference_server --model .\checkpoints\midigpt_ema.pt
echo.

endlocal
