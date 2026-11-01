param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe'
)
$ErrorActionPreference = 'Stop'
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'guest\manifest.json') | ConvertFrom-Json
if ($taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.base -ne 0x70000000 -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count) { throw 'Incomplete or wrong-target NDK pthread caller manifest.' }
$taskLoader = Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if ($LASTEXITCODE -ne 0) { throw 'Pthread ELF data-loader compilation failed.' }
$taskExecutable = Join-Path $taskBuild 'test-windows-pthreads.exe'
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-DPTHREAD_GUEST_IMAGE=`"$($taskBuild.Replace('\', '/'))/pthread-guest.so`"", "-I$taskRemill\include", "-I$taskBuild", (Join-Path $PSScriptRoot 'pthread_test.cpp'), (Join-Path $PSScriptRoot 'pthread_host.cpp'), (Join-Path $PSScriptRoot '..\whole\runtime.cpp'), $taskLoader)
foreach ($taskObject in $taskManifest.objects) { $taskArguments += Join-Path $taskBuild "guest\$(Split-Path -Leaf $taskObject)" }
$taskArguments += @('-static', '-latomic', '-o', $taskExecutable)
& $Cxx @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Windows pthread ABI test build failed.' }
& $taskExecutable
if ($LASTEXITCODE -ne 0) { throw 'Windows pthread ABI tests failed.' }
Write-Output $taskExecutable
