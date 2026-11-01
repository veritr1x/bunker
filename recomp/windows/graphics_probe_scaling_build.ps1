param([int]$Jobs=6)
$ErrorActionPreference='Stop'
$taskWork=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work'))
$taskRoot=Join-Path $taskWork 'angle-scaling'
$taskSource=Join-Path $taskRoot 'src'
$taskBase=Join-Path $taskWork 'angle-native'
$taskGn=Join-Path $taskBase 'tools\mingw64\bin\gn.exe'
$taskSavedPath=$env:PATH;$taskSavedCC=$env:CC;$taskSavedCXX=$env:CXX
try{
  $env:PATH='C:\mingw64\bin;'+$env:PATH;$env:CC='gcc';$env:CXX='g++'
  python (Join-Path $PSScriptRoot 'graphics_probe_scaling_patch.py')
  if($LASTEXITCODE){throw 'Scaling source patch failed'}
  Push-Location -LiteralPath $taskSource
  try{
    python build/util/lastchange.py -o build/util/LASTCHANGE
    if($LASTEXITCODE){throw 'Scaling build timestamp generation failed'}
    python src/commit_id.py gen src/common/angle_commit.h
    if($LASTEXITCODE){throw 'Scaling commit metadata generation failed'}
  }finally{Pop-Location}
  python (Join-Path $PSScriptRoot 'graphics_probe_scaling_cache.py')
  if($LASTEXITCODE){throw 'Scaling independent build-cache preparation failed'}
  $taskProvenance=Get-Content -Raw (Join-Path $taskBase 'bundle\provenance.json')|ConvertFrom-Json
  $taskArguments=$taskProvenance.args
  if($taskArguments -notmatch 'angle_enable_vulkan=true' -or $taskArguments -notmatch 'angle_has_astc_encoder=true' -or $taskArguments -notmatch 'angle_shared_libvulkan=true'){throw 'Accepted native ANGLE Vulkan/ASTC/shared-loader flags missing'}
  $taskOutput=Join-Path $taskSource 'out\BunkerVulkanScaling'
  New-Item -ItemType Directory -Force -Path $taskOutput|Out-Null
  $taskArguments|Set-Content -LiteralPath (Join-Path $taskOutput 'args.gn') -Encoding utf8
  Push-Location -LiteralPath $taskSource
  try{
    & $taskGn gen out/BunkerVulkanScaling --threads=1
    if($LASTEXITCODE){throw 'Scaling GN generation failed'}
    & C:\mingw64\bin\ninja.exe -C out/BunkerVulkanScaling "-j$Jobs" libEGL libGLESv2
    if($LASTEXITCODE){throw 'Scaling ANGLE native build failed'}
  }finally{Pop-Location}
  [ordered]@{source_patch=(Get-Content -Raw (Join-Path $taskRoot 'scaling-patch.json')|ConvertFrom-Json);args=$taskArguments;files=@('libEGL.dll','libGLESv2.dll'|ForEach-Object{$taskFile=Join-Path $taskOutput $_;[ordered]@{path=$taskFile;sha256=(Get-FileHash -LiteralPath $taskFile -Algorithm SHA256).Hash.ToLowerInvariant()}})}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $taskRoot 'build-success.json') -Encoding utf8
}finally{$env:PATH=$taskSavedPath;$env:CC=$taskSavedCC;$env:CXX=$taskSavedCXX}
