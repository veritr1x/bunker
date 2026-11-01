param(
  [string]$DllDirectory='C:\Users\user\AppData\Local\Programs\Microsoft VS Code\0870c2a0c7',
  [string]$BuildDirectory=(Join-Path $PSScriptRoot '..\work\graphics-probe'),
  [string]$Cxx='C:\mingw64\bin\g++.exe'
)
$ErrorActionPreference='Stop'
$taskDllDirectory=(Resolve-Path -LiteralPath $DllDirectory).ProviderPath
$taskBuildDirectory=[IO.Path]::GetFullPath($BuildDirectory)
New-Item -ItemType Directory -Force -Path $taskBuildDirectory | Out-Null
$taskSource=Join-Path $PSScriptRoot 'graphics_probe.cpp'
$taskExe=Join-Path $taskBuildDirectory 'graphics-probe.exe'
$taskStdout=Join-Path $taskBuildDirectory 'result.json'
$taskStderr=Join-Path $taskBuildDirectory 'stderr.log'
function Get-ProbeFileEvidence([string]$Path) {
  $taskItem=Get-Item -LiteralPath $Path
  $taskSignature=Get-AuthenticodeSignature -LiteralPath $Path
  [ordered]@{
    path=$taskItem.FullName; sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    bytes=$taskItem.Length; file_version=$taskItem.VersionInfo.FileVersion
    product_version=$taskItem.VersionInfo.ProductVersion; company=$taskItem.VersionInfo.CompanyName
    signature_status=[string]$taskSignature.Status
    signer=if($taskSignature.SignerCertificate){$taskSignature.SignerCertificate.Subject}else{$null}
  }
}
$taskEvidence=[ordered]@{
  diagnostic_only=$true; sdk_or_redistribution_approval=$false
  utc=[DateTime]::UtcNow.ToString('o'); source=(Get-ProbeFileEvidence $taskSource)
  compiler=(Get-ProbeFileEvidence $Cxx); dll_directory=$taskDllDirectory
  requested_backend='ANGLE Vulkan hardware only; no ES3.0/default/D3D/software fallback'
  libraries=@((Get-ProbeFileEvidence (Join-Path $taskDllDirectory 'libEGL.dll')),
              (Get-ProbeFileEvidence (Join-Path $taskDllDirectory 'libGLESv2.dll')))
}
$taskEvidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBuildDirectory 'provenance.json') -Encoding utf8
& $Cxx '-std=c++17' '-O2' '-Wall' '-Wextra' '-Werror' '-static' '-municode' $taskSource '-o' $taskExe
if($LASTEXITCODE){throw 'Graphics diagnostic compilation failed'}
$taskProcess=Start-Process -FilePath $taskExe -ArgumentList ('"'+$taskDllDirectory+'"') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
if(-not $taskProcess.WaitForExit(60000)){
  $taskProcess.Kill(); $taskProcess.WaitForExit()
  $taskEvidence.timeout_seconds=60
  $taskEvidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBuildDirectory 'provenance.json') -Encoding utf8
  throw 'Graphics diagnostic timed out after60seconds; see preserved output'
}
$taskProcess.WaitForExit()
$taskEvidence.exit_code=$taskProcess.ExitCode
$taskEvidence.executable=(Get-ProbeFileEvidence $taskExe)
if((Get-Item -LiteralPath $taskStdout).Length){
  $taskResult=Get-Content -Raw -LiteralPath $taskStdout | ConvertFrom-Json
  $taskEvidence.loaded_graphics_libraries=@($taskResult.loaded_modules | Where-Object {
    ($_ -like "$taskDllDirectory\*") -or ((Split-Path -Leaf $_) -match 'vulkan|nvoglv|nvapi|amdvlk|atio6')
  } | ForEach-Object {Get-ProbeFileEvidence $_})
}
$taskEvidence | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskBuildDirectory 'provenance.json') -Encoding utf8
Get-Content -Raw -LiteralPath $taskStdout
if($taskProcess.ExitCode){throw "Graphics capability gate failed with exit$($taskProcess.ExitCode); evidence preserved in$taskBuildDirectory"}
