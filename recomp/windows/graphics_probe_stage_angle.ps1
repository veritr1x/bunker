$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work\angle-native'))
$taskBuild=Join-Path $taskRoot 'src\out\BunkerVulkanAstc'
$taskBundle=Join-Path $taskRoot 'bundle'
$taskBin=Join-Path $taskBundle 'bin'
New-Item -ItemType Directory -Force -Path $taskBin | Out-Null
$taskFiles=@('libEGL.dll','libGLESv2.dll','libthird_party_zlib.dll' | ForEach-Object {(Get-Item -LiteralPath (Join-Path $taskBuild $_)).FullName})
if(-not ($taskFiles | Where-Object {(Split-Path -Leaf $_) -eq 'libEGL.dll'}) -or -not ($taskFiles | Where-Object {(Split-Path -Leaf $_) -eq 'libGLESv2.dll'})){throw 'ANGLE DLL build is incomplete'}
$taskFiles+=@('C:\mingw64\bin\libgcc_s_seh-1.dll','C:\mingw64\bin\libstdc++-6.dll','C:\mingw64\bin\libwinpthread-1.dll')
$taskRecords=@()
foreach($taskFile in $taskFiles){
  $taskDestination=Join-Path $taskBin (Split-Path -Leaf $taskFile)
  Copy-Item -LiteralPath $taskFile -Destination $taskDestination -Force
  $taskRecords += [ordered]@{source=$taskFile;path=$taskDestination;sha256=(Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash.ToLowerInvariant();bytes=(Get-Item -LiteralPath $taskDestination).Length}
}
$taskSetup=Get-Content -Raw (Join-Path $taskRoot 'prepare-provenance.json')|ConvertFrom-Json
$taskLicenses=@()
foreach($taskRepo in $taskSetup.sources.PSObject.Properties){
  foreach($taskLicense in $taskRepo.Value.licenses_sha256.PSObject.Properties){
    $taskFile=Join-Path (Join-Path $taskRoot $taskRepo.Name) $taskLicense.Name
    $taskName=($taskRepo.Name -replace '[/\\]','_')+'_'+$taskLicense.Name
    $taskDestination=Join-Path $taskBundle "licenses\$taskName"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $taskDestination)|Out-Null
    Copy-Item -LiteralPath $taskFile -Destination $taskDestination -Force
    $taskLicenses += [ordered]@{source=$taskFile;path=$taskDestination;sha256=(Get-FileHash -LiteralPath $taskDestination -Algorithm SHA256).Hash.ToLowerInvariant()}
  }
}
Copy-Item -LiteralPath 'C:\mingw64\version_info.txt' -Destination (Join-Path $taskBundle 'compiler-version-info.txt') -Force
$taskRecord=[ordered]@{diagnostic_only=$true;redistribution_review_complete=$false;files=$taskRecords;licenses=$taskLicenses;source_provenance=$taskSetup;descriptor_fix=(Get-Content -Raw (Join-Path $taskRoot 'descriptor-portability-fix.json')|ConvertFrom-Json);build_fixes_sha256=(Get-FileHash -LiteralPath (Join-Path $taskRoot 'standalone-gn-fixes.patch') -Algorithm SHA256).Hash.ToLowerInvariant();profile_patch=(Get-Content -Raw (Join-Path $taskRoot 'profile-patch.json')|ConvertFrom-Json);portability_patches=(Get-Content -Raw (Join-Path $taskRoot 'portability-patches.json')|ConvertFrom-Json);args=(Get-Content -Raw (Join-Path $taskBuild 'args.gn'));compiler_sha256=(Get-FileHash -LiteralPath 'C:\mingw64\bin\g++.exe' -Algorithm SHA256).Hash.ToLowerInvariant();native_tools=(Get-Content -Raw (Join-Path $taskRoot 'tools\provenance.json')|ConvertFrom-Json)}
$taskRecord|ConvertTo-Json -Depth 15|Set-Content -LiteralPath (Join-Path $taskBundle 'provenance.json') -Encoding utf8
Write-Output "Workspace diagnostic dependency staged at$taskBin"
