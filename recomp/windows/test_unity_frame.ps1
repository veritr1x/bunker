param([string]$Cxx='C:\mingw64\bin\g++.exe',[string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-unity-frame'))
$ErrorActionPreference='Stop'
[System.IO.Directory]::CreateDirectory($BuildDirectory)|Out-Null
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskExe=Join-Path $taskBuild 'test.exe'
& $Cxx '-std=c++17' '-O2' '-DADDRESS_SIZE_BITS=64' "-I$PSScriptRoot\..\work\remill-src\include" (Join-Path $PSScriptRoot 'unity_frame_test.cpp') (Join-Path $PSScriptRoot 'unity_lifecycle.cpp') (Join-Path $PSScriptRoot 'jni_host.cpp') (Join-Path $PSScriptRoot '..\whole\runtime.cpp') '-static' '-latomic' '-o' $taskExe
if($LASTEXITCODE){throw 'Bounded native frame FIFO build failed'}
& $taskExe
if($LASTEXITCODE){throw 'Bounded native frame FIFO test failed'}
