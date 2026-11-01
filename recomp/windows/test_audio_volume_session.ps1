param([string]$Cxx='C:\mingw64\bin\g++.exe',[string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\audio-volume-session'))
$ErrorActionPreference='Stop'
[IO.Directory]::CreateDirectory($BuildDirectory)|Out-Null
$taskExe=Join-Path ([IO.Path]::GetFullPath($BuildDirectory)) 'test.exe'
& $Cxx '-std=c++17' '-O2' '-DADDRESS_SIZE_BITS=64' "-I$PSScriptRoot\..\work\remill-src\include" (Join-Path $PSScriptRoot 'audio_volume_session_test.cpp') (Join-Path $PSScriptRoot 'audio_volume_session.cpp') (Join-Path $PSScriptRoot 'audio_volume.cpp') (Join-Path $PSScriptRoot 'jni_host.cpp') (Join-Path $PSScriptRoot '..\whole\runtime.cpp') '-static' '-lole32' '-luuid' '-latomic' '-o' $taskExe
if($LASTEXITCODE){throw 'Audio volume session build failed'}
& $taskExe
if($LASTEXITCODE){throw 'Audio volume session gate failed'}
