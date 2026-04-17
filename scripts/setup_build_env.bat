@echo off
REM MidiGPT - Windows build environment setup (Sprint 37.4 이슈4)
REM
REM CMake 와 Visual Studio Build Tools 가 없으면 juce_daw_clean 을 빌드할 수
REM 없다. 이 스크립트는 두 가지를 자동 점검하고, 없으면 공식 다운로드
REM 페이지를 기본 브라우저로 연다. 설치 자체는 관리자 권한 UI 가 필요해
REM 완전 자동화는 불가.
REM
REM 사용법:
REM   scripts\setup_build_env.bat           - 현재 상태 점검 + 다운로드 URL 오픈
REM   scripts\setup_build_env.bat --silent  - 오픈 없이 점검만

setlocal enabledelayedexpansion
set "SILENT=0"
if /i "%~1"=="--silent" set "SILENT=1"

set "MISSING=0"

echo ============================================================
echo   MidiGPT - Windows Build Environment Check
echo ============================================================
echo.

REM --- CMake ---
where cmake >nul 2>&1
if errorlevel 1 (
    echo [MISSING]  cmake  ^(required^)
    echo            download: https://cmake.org/download/
    echo            direct:   https://github.com/Kitware/CMake/releases/download/v3.31.5/cmake-3.31.5-windows-x86_64.msi
    set /a MISSING+=1
    if "%SILENT%"=="0" start https://cmake.org/download/
) else (
    for /f "tokens=3" %%v in ('cmake --version ^| findstr /B "cmake version"') do set "CMAKE_VER=%%v"
    echo [OK]       cmake !CMAKE_VER!
)

REM --- Visual Studio 2022 (any edition) ---
set "VS_FOUND=0"
for %%E in (Community Professional Enterprise BuildTools) do (
    if exist "%ProgramFiles%\Microsoft Visual Studio\2022\%%E\VC\Tools\MSVC" set "VS_FOUND=1"
    if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\2022\%%E\VC\Tools\MSVC" set "VS_FOUND=1"
)
if "%VS_FOUND%"=="0" (
    echo [MISSING]  Visual Studio 2022 ^(Community/BuildTools/+^)
    echo            download:  https://visualstudio.microsoft.com/downloads/
    echo            최소:      "C++ CMake tools for Windows" + MSVC v143 워크로드
    set /a MISSING+=1
    if "%SILENT%"=="0" start https://visualstudio.microsoft.com/downloads/
) else (
    echo [OK]       Visual Studio 2022 detected
)

REM --- JUCE submodule ---
if exist "%~dp0..\juce_daw_clean\external\JUCE\CMakeLists.txt" (
    echo [OK]       JUCE submodule present
) else (
    echo [MISSING]  JUCE ^(juce_daw_clean\external\JUCE^)
    echo            fix:  cd juce_daw_clean ^&^& git clone https://github.com/juce-framework/JUCE.git external\JUCE
    set /a MISSING+=1
)

echo.
echo ============================================================
if %MISSING% gtr 0 (
    echo   %MISSING%개 구성요소가 누락. 위 링크에서 설치 후 재실행.
    exit /b 1
)
echo   전부 OK - `juce_daw_clean\build.bat --install` 실행 가능.
endlocal
