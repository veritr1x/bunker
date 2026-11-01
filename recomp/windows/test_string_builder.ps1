param([string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\windows-string-builder'),[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe')
$ErrorActionPreference='Stop'
$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskManifest=Get-Content -Raw (Join-Path $taskBuild 'guest\manifest.json')|ConvertFrom-Json
if($taskManifest.base -ne 0x72000000 -or $taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count){throw 'Incomplete StringBuilder fixture'}
$taskLoader=Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if($LASTEXITCODE){throw 'Loader compilation failed'}
$taskArgs=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$PSScriptRoot\..\work\remill-src\include","-I$taskBuild\guest","-DSTRING_BUILDER_IMAGE=`"$($taskBuild.Replace('\','/'))/string-builder.so`"",(Join-Path $PSScriptRoot 'string_builder_test.cpp'),(Join-Path $PSScriptRoot 'jni_host.cpp'),(Join-Path $PSScriptRoot '..\whole\runtime.cpp'),$taskLoader)
foreach($taskObject in $taskManifest.objects){$taskArgs+=Join-Path $taskBuild "guest\$(Split-Path -Leaf $taskObject)"}
$taskExe=Join-Path $taskBuild 'test-string-builder.exe';$taskArgs+=@('-static','-latomic','-o',$taskExe)
& $Cxx @taskArgs
if($LASTEXITCODE){throw 'StringBuilder compilation failed'}
& $taskExe
if($LASTEXITCODE){throw 'StringBuilder checks failed'}
