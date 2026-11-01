param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$Apk,
    [string]$StorageDirectory,
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe',
    [switch]$CompileOnly,
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskManifest = $null
if (-not $CompileOnly) {
    $taskManifest = Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'unity_bootstrap_link.json') | ConvertFrom-Json
    if (-not $taskManifest.complete -or $taskManifest.base -ne 0x70000000 -or $taskManifest.constructors -ne 417) { throw 'Real Unity bootstrap requires complete translation and all417 constructors.' }
    $taskLibrary = Join-Path $taskBuild 'native\libunity.so'
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskLibrary).Hash.ToLowerInvariant() -ne $taskManifest.unity_sha256) { throw 'Unity data image differs from translation.' }
}
$taskObject = Join-Path $taskBuild 'unity-bootstrap.o'
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-I$taskRemill\include", "-I$taskBuild", '-c', (Join-Path $PSScriptRoot 'unity_bootstrap.cpp'), '-o', $taskObject)
& $Cxx @taskArguments
if ($LASTEXITCODE -ne 0) { throw 'Unity bootstrap harness compilation failed.' }
if ($CompileOnly) { Write-Output 'Harness syntax/object check passed; full Unity translation is still required.'; return }
$taskLoader = Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if ($LASTEXITCODE -ne 0) { throw 'Unity bootstrap data-loader build failed.' }
$taskExecutable = Join-Path $taskBuild 'bunker-unity-bootstrap.exe'
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-I$taskRemill\include", '-static', $taskObject, $taskLoader)
foreach ($taskSource in @('jni_host.cpp','android_context.cpp','filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','..\whole\runtime.cpp','..\whole\format.cpp')) { $taskArguments += Join-Path $PSScriptRoot $taskSource }
foreach ($taskInput in $taskManifest.objects) { $taskArguments += Join-Path $taskBuild $taskInput }
$taskArguments += @('-latomic', '-lbcrypt', '-o', $taskExecutable)
# Response files avoid Windows command-line limits for the full Unity shards.
$taskResponse = Join-Path $taskBuild 'unity-bootstrap-link.rsp'
$taskEscaped = foreach ($taskArgument in $taskArguments) { '"' + $taskArgument.Replace('\','/').Replace('"','\"') + '"' }
[System.IO.File]::WriteAllLines($taskResponse, [string[]]$taskEscaped, [System.Text.UTF8Encoding]::new($false))
& $Cxx "@$taskResponse"
if ($LASTEXITCODE -ne 0) { throw 'Real Unity bootstrap linking failed.' }
Write-Output $taskExecutable
if ($Run) {
    if (-not $Apk) { throw '-Apk is required to execute the actual Unity bootstrap.' }
    $taskApk = (Resolve-Path -LiteralPath $Apk).ProviderPath
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskApk).Hash.ToLowerInvariant() -ne $taskManifest.apk_sha256) { throw 'APK differs from verified Java metadata.' }
    if (-not $StorageDirectory) { $StorageDirectory = Join-Path $taskBuild 'data' }
    [System.IO.Directory]::CreateDirectory($StorageDirectory) | Out-Null
    $taskStorage = (Resolve-Path -LiteralPath $StorageDirectory).ProviderPath
    & $taskExecutable $taskLibrary $taskApk $taskStorage 2>&1 | Tee-Object -FilePath (Join-Path $taskBuild 'unity-bootstrap-last-run.log')
    $taskExitCode = $LASTEXITCODE
    if ($taskExitCode -ne 0) { throw "Actual Unity bootstrap stopped with exit code $taskExitCode; inspect the explicit constructor/import diagnostic above." }
}
