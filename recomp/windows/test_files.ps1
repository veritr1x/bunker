param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$ZlibDirectory = (Join-Path $PSScriptRoot '..\work\zlib-native'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe'
)
$ErrorActionPreference = 'Stop'
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskExecutable = Join-Path $taskBuild 'test-windows-files.exe'
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-DFILES_ROOT=`"$($taskBuild.Replace('\', '/'))`"", "-I$taskRemill\include", "-I$taskBuild", (Join-Path $PSScriptRoot 'filesystem_test.cpp'), (Join-Path $PSScriptRoot 'filesystem.cpp'), (Join-Path $PSScriptRoot '..\whole\runtime.cpp'))
if (Test-Path -LiteralPath (Join-Path $taskBuild 'guest\manifest.json')) {
    $taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'guest\manifest.json') | ConvertFrom-Json
    if ($taskManifest.target -ne 'x86_64-w64-windows-gnu' -or $taskManifest.base -ne 0x60000000 -or $taskManifest.unsupported_traces.Count -or $taskManifest.unresolved_direct_targets.Count) { throw 'Incomplete or wrong-target NDK caller manifest.' }
    $taskLoader = Join-Path $taskBuild 'elfload.o'
    & $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
    if ($LASTEXITCODE -ne 0) { throw 'File ABI ELF data-loader compilation failed.' }
    $taskArguments += @('-DHAVE_GUEST_FILE_FIXTURE', "-DGUEST_FILES_IMAGE=`"$($taskBuild.Replace('\', '/'))/file-guest.so`"", $taskLoader,
        (Join-Path $PSScriptRoot 'jni_host.cpp'), (Join-Path $PSScriptRoot 'android_context.cpp'),(Join-Path $PSScriptRoot 'android_assets.cpp'),(Join-Path $PSScriptRoot 'apk_assets.cpp'),"-I$ZlibDirectory\zlib-1.3.2")
    foreach ($taskObject in $taskManifest.objects) { $taskArguments += Join-Path $taskBuild "guest\$(Split-Path -Leaf $taskObject)" }
    $taskArguments+=Join-Path $ZlibDirectory 'libz-inflate.a'
}
$taskArguments += @('-static', '-latomic', '-o', $taskExecutable)
& $Cxx @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Windows file ABI test build failed.' }
& $taskExecutable
if ($LASTEXITCODE -ne 0) { throw 'Windows file ABI tests failed.' }
Write-Output $taskExecutable
