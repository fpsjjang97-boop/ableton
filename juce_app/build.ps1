$ErrorActionPreference = "Continue"
$log = "E:\Ableton\repo\juce_app\build_log.txt"
"Build started $(Get-Date)" | Out-File $log

# Load VS environment
$vcvars = "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat"
$envBefore = @{}
cmd /c "`"$vcvars`" x64 >nul 2>&1 && set" | ForEach-Object {
    if ($_ -match "^(.+?)=(.*)$") {
        $envBefore[$matches[1]] = $matches[2]
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}
"VS Environment loaded" | Tee-Object -FilePath $log -Append

# Verify tools
$clPath = (Get-Command cl.exe -ErrorAction SilentlyContinue).Source
$cmakePath = (Get-Command cmake.exe -ErrorAction SilentlyContinue).Source
$ninjaPath = (Get-Command ninja.exe -ErrorAction SilentlyContinue).Source
"cl: $clPath" | Tee-Object -FilePath $log -Append
"cmake: $cmakePath" | Tee-Object -FilePath $log -Append
"ninja: $ninjaPath" | Tee-Object -FilePath $log -Append

# Build
Set-Location E:\Ableton\repo\juce_app
if (!(Test-Path build)) { New-Item -ItemType Directory -Name build | Out-Null }
Set-Location build

# Clean
Remove-Item -Recurse -Force CMakeFiles -ErrorAction SilentlyContinue
Remove-Item -Force CMakeCache.txt -ErrorAction SilentlyContinue

"=== CMake Configure ===" | Tee-Object -FilePath $log -Append
$configOutput = & cmake .. -G Ninja -DCMAKE_BUILD_TYPE=Release 2>&1
$configOutput | Out-String | Tee-Object -FilePath $log -Append

"=== Building ===" | Tee-Object -FilePath $log -Append
$buildOutput = & cmake --build . --config Release 2>&1
$buildOutput | Out-String | Tee-Object -FilePath $log -Append

"=== Result ===" | Tee-Object -FilePath $log -Append
Get-ChildItem -Recurse -Filter *.exe -ErrorAction SilentlyContinue | ForEach-Object {
    "EXE: $($_.FullName)" | Tee-Object -FilePath $log -Append
}

"=== BUILD COMPLETE ===" | Tee-Object -FilePath $log -Append
