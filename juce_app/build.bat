@echo off
set LOG=E:\Ableton\repo\juce_app\build_log.txt
echo Build started at %date% %time% > %LOG%

call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64 >> %LOG% 2>&1

cd /d E:\Ableton\repo\juce_app
if not exist build mkdir build
cd build
rmdir /s /q CMakeFiles 2>nul
del CMakeCache.txt 2>nul

echo === CMake Configure === >> %LOG% 2>&1
cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release >> %LOG% 2>&1

echo === Building === >> %LOG% 2>&1
cmake --build . --config Release >> %LOG% 2>&1

echo === Result === >> %LOG% 2>&1
dir /s /b *.exe >> %LOG% 2>nul

echo === BUILD COMPLETE === >> %LOG% 2>&1
