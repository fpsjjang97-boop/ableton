@echo off
REM MidiGPT DAW - Artefact smoke test (Sprint 35 ZZ2)
REM
REM Checks that the expected build outputs exist and are non-trivial size.
REM Return code 0 = all artefacts present, 1 = any missing.
REM
REM Usage:
REM   smoke.bat              -  Release config (default)
REM   smoke.bat Debug        -  Debug config
REM
REM Invoked automatically at the end of build.bat.

setlocal enabledelayedexpansion
set "CONFIG=Release"
if not "%~1"=="" set "CONFIG=%~1"
cd /d "%~dp0"

set "FAIL=0"
set "VST3=build\MidiGPTPlugin_artefacts\%CONFIG%\VST3\MidiGPT.vst3"
set "SA_EXE=build\MidiGPTPlugin_artefacts\%CONFIG%\Standalone\MidiGPT.exe"
set "DAW_EXE=build\MidiGPTDAW_artefacts\%CONFIG%\MidiGPTDAW.exe"

call :check "VST3 bundle"        "%VST3%"
call :check "Plugin standalone"  "%SA_EXE%"
call :check "Standalone DAW"     "%DAW_EXE%"

if %FAIL% gtr 0 (
    echo.
    echo [smoke] %FAIL% artefact(s) missing or empty.
    exit /b 1
)
echo [smoke] OK - all artefacts present.
exit /b 0

:check
REM %1 = label, %2 = path
if exist %2 (
    REM VST3 on Windows is a BUNDLE DIRECTORY, not a single file — check dir too.
    if exist %2\Contents (
        echo   [OK]  %~1: %~2 ^(bundle^)
    ) else (
        for %%F in (%2) do set "SIZE=%%~zF"
        if !SIZE! lss 1024 (
            echo   [FAIL] %~1: %~2 too small ^(!SIZE! bytes^)
            set /a FAIL+=1
        ) else (
            echo   [OK]  %~1: %~2 ^(!SIZE! bytes^)
        )
    )
) else (
    echo   [FAIL] %~1 missing: %~2
    set /a FAIL+=1
)
exit /b 0
