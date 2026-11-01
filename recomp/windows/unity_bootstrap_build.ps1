param(
    [Parameter(Mandatory = $true)][string]$BuildDirectory,
    [string]$Apk,
    [string]$StorageDirectory,
    [string]$Remill = (Join-Path $PSScriptRoot '..\work\remill-src'),
    [string]$Cxx = 'g++.exe',
    [string]$Cc = 'gcc.exe',
    [string]$ZlibDirectory = (Join-Path $PSScriptRoot '..\work\zlib-native'),
    [switch]$CompileOnly,
    [switch]$InitJni,
    [switch]$SurfaceGate,
    [int]$ClientWidth,
    [int]$ClientHeight,
    [switch]$Run
)
$ErrorActionPreference = 'Stop'
if($SurfaceGate -and ($ClientWidth -le $ClientHeight -or $ClientHeight -le 0 -or $ClientWidth -gt 32767)){throw '-SurfaceGate requires explicit landscape ClientWidth/ClientHeight in1..32767 pixels.'}
$taskBuild = (Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskRemill = (Resolve-Path -LiteralPath $Remill).ProviderPath
$taskZlib = (Resolve-Path -LiteralPath $ZlibDirectory).ProviderPath
if (-not (Test-Path -LiteralPath (Join-Path $taskZlib 'libz-inflate.a'))) { throw 'Prepare the verified static zlib backend with windows/prepare_zlib.py first.' }
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
if ($CompileOnly) { Write-Output 'Harness syntax/object check passed; no guest code was executed.'; return }
$taskLoader = Join-Path $taskBuild 'elfload.o'
& $Cc '-O2' '-c' (Join-Path $PSScriptRoot '..\fastaes\elfload.c') '-o' $taskLoader
if ($LASTEXITCODE -ne 0) { throw 'Unity bootstrap data-loader build failed.' }
$taskExecutable = Join-Path $taskBuild 'bunker-unity-bootstrap.exe'
$taskArguments = @('-std=c++17', '-O2', '-DADDRESS_SIZE_BITS=64', "-I$taskRemill\include", "-I$taskZlib\zlib-1.3.2", '-static', $taskObject, $taskLoader)
foreach ($taskSource in @('jni_host.cpp','android_context.cpp','android_assets.cpp','apk_assets.cpp','native_window.cpp','unity_lifecycle.cpp','filesystem.cpp','module_registry.cpp','pthread_host.cpp','libc.cpp','logging.cpp','zlib_host.cpp','..\whole\runtime.cpp','..\whole\format.cpp')) { $taskArguments += Join-Path $PSScriptRoot $taskSource }
foreach ($taskInput in $taskManifest.objects) { $taskArguments += Join-Path $taskBuild $taskInput }
$taskArguments += @((Join-Path $taskZlib 'libz-inflate.a'), '-latomic', '-lbcrypt', '-luser32', '-lgdi32', '-o', $taskExecutable)
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
    $taskRunArguments=@($taskLibrary,$taskApk,$taskStorage)
    if($SurfaceGate){$taskRunArguments+=@('--surface-gate',"$ClientWidth","$ClientHeight")}
    elseif($InitJni){$taskRunArguments+='--init-jni'}
    & $taskExecutable @taskRunArguments 2>&1 | Tee-Object -FilePath (Join-Path $taskBuild 'unity-bootstrap-last-run.log')
    $taskExitCode = $LASTEXITCODE
    if ($taskExitCode -ne 0) { throw "Actual Unity bootstrap stopped with exit code $taskExitCode; inspect the explicit startup/finalization diagnostic above." }
}
