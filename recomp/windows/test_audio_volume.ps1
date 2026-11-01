param([string]$Cxx='C:\mingw64\bin\g++.exe',[string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\audio-volume'))
$ErrorActionPreference='Stop'
$taskBuild=[IO.Path]::GetFullPath($BuildDirectory)
New-Item -ItemType Directory -Force -Path $taskBuild | Out-Null
$taskExe=Join-Path $taskBuild 'test-audio-volume.exe'
& $Cxx '-std=c++17' '-O2' '-Wall' '-Wextra' '-Werror' '-static' (Join-Path $PSScriptRoot 'audio_volume.cpp') (Join-Path $PSScriptRoot 'audio_volume_test.cpp') '-lole32' '-luuid' '-pthread' '-o' $taskExe
if($LASTEXITCODE){throw 'Audio volume observer build failed'}
& $taskExe
if($LASTEXITCODE){throw 'Audio volume observer gate failed'}
$taskUnit=Join-Path $taskBuild 'test-audio-callback-state.exe'
& $Cxx '-std=c++17' '-O2' '-Wall' '-Wextra' '-Werror' '-static' (Join-Path $PSScriptRoot 'audio_volume_state_test.cpp') '-lole32' '-luuid' '-pthread' '-o' $taskUnit
if($LASTEXITCODE){throw 'Audio callback mechanics build failed'}
& $taskUnit
if($LASTEXITCODE){throw 'Audio callback mechanics gate failed'}
