param([Parameter(Mandatory=$true)][string]$BuildDirectory,[string]$Cxx='C:\mingw64\bin\g++.exe',[string]$Cc='C:\mingw64\bin\gcc.exe',[switch]$Run)
$ErrorActionPreference='Stop';$taskBuild=(Resolve-Path -LiteralPath $BuildDirectory).ProviderPath
$taskMeta=Get-Content -Raw -LiteralPath (Join-Path $taskBuild 'managed_inputs.json')|ConvertFrom-Json
if($taskMeta.status -ne 'prepared' -or $taskMeta.objects.Count -ne 3548 -or $taskMeta.gate.expected_files -ne 24){throw 'Wrong Managed-copy input lineage'}
function Native-Path([string]$p){if($p -match '^/mnt/([a-z])/(.*)$'){return $Matches[1].ToUpper()+':\'+$Matches[2].Replace('/','\')};if($p.StartsWith('/')){return (& wsl.exe -e wslpath -w $p).Trim()};return $p}
function Verify-Hash([string]$p,[string]$sha){if((Get-FileHash -Algorithm SHA256 -LiteralPath $p).Hash.ToLowerInvariant() -ne $sha){throw "Frozen input changed: $p"}}
foreach($p in $taskMeta.source_hashes.PSObject.Properties){Verify-Hash (Join-Path $taskBuild ('sources\'+$p.Name)) $p.Value}
foreach($p in $taskMeta.input_hashes.PSObject.Properties){Verify-Hash (Native-Path $p.Name) $p.Value}
foreach($p in $taskMeta.remill_header_hashes.PSObject.Properties){Verify-Hash (Join-Path $taskBuild ('remill-include\'+$p.Name)) $p.Value}
foreach($m in $taskMeta.modules){Verify-Hash (Native-Path $m.data) $m.sha256}
Verify-Hash (Native-Path $taskMeta.apk) $taskMeta.apk_sha256
Verify-Hash (Native-Path $taskMeta.zlib_backend) $taskMeta.zlib_sha256
$taskRecord=[ordered]@{status='frozen inputs verified';inputs_sha256=(Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $taskBuild 'managed_inputs.json')).Hash.ToLowerInvariant();host_commit=$taskMeta.host_commit;cxx_version=(& $Cxx --version|Select-Object -First 1)}
function Save-Record{[System.IO.File]::WriteAllText((Join-Path $taskBuild 'managed_build_record.json'),($taskRecord|ConvertTo-Json -Depth 12),[System.Text.UTF8Encoding]::new($false))}
Save-Record
$taskCommon=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64',"-I$taskBuild\remill-include","-I$taskBuild","-I$taskBuild\zlib-include",'-Wa,-mbig-obj')
& $Cxx @taskCommon '-c' (Join-Path $taskBuild 'sources\windows\unity_managed_copy.cpp') '-o' (Join-Path $taskBuild 'managed-harness.o')
if($LASTEXITCODE){$taskRecord.status='harness compile failed';Save-Record;throw 'Managed harness compilation failed'}
foreach($o in $taskMeta.objects){Verify-Hash (Native-Path $o.path) $o.sha256}
& $Cc '-O2' '-c' (Join-Path $taskBuild 'sources\fastaes\elfload.c') '-o' (Join-Path $taskBuild 'managed-elfload.o')
if($LASTEXITCODE){throw 'Original ELF loader compilation failed'}
$taskArgs=$taskCommon+@('-static','-Wl,--wrap=sub_7024c6e4,--wrap=sub_7024c36c,--wrap=sub_70e71d10,--wrap=sub_70e71dcc',(Join-Path $taskBuild 'managed-harness.o'),(Join-Path $taskBuild 'managed-elfload.o'),(Join-Path $taskBuild 'once-component.o'))
foreach($name in @('jni_host','android_context','android_internal_storage','android_assets','apk_assets','java_native_libraries','filesystem','module_registry','pthread_host','libc','logging','zlib_host','signal_host','semaphore_host')){$taskArgs+=Join-Path $taskBuild ("sources\windows\$name.cpp")}
$taskGrowdownSource=Join-Path $taskBuild 'sources\windows\growdown_memory.cpp';if(Test-Path -LiteralPath $taskGrowdownSource){$taskArgs+=$taskGrowdownSource}
foreach($name in @('runtime','format')){$taskArgs+=Join-Path $taskBuild ("sources\whole\$name.cpp")}
foreach($o in $taskMeta.objects){$taskArgs+=Native-Path $o.path}
$taskExe=Join-Path $taskBuild 'bunker-unity-managed-copy.exe';$taskArgs+=@((Native-Path $taskMeta.zlib_backend),'-latomic','-lbcrypt','-o',$taskExe)
$taskResponse=Join-Path $taskBuild 'managed-link.rsp';$taskQuoted=foreach($a in $taskArgs){'"'+$a.Replace('\','/').Replace('"','\"')+'"'}
[System.IO.File]::WriteAllLines($taskResponse,[string[]]$taskQuoted,[System.Text.UTF8Encoding]::new($false));& $Cxx "@$taskResponse"
if($LASTEXITCODE){$taskRecord.status='native link failed';Save-Record;throw 'Managed-copy native link failed'}
$taskRecord.status='native link passed';$taskRecord['executable_sha256']=(Get-FileHash -Algorithm SHA256 -LiteralPath $taskExe).Hash.ToLowerInvariant();Save-Record
if($Run){
 $taskStorage=Join-Path $taskBuild 'data';if(Test-Path -LiteralPath $taskStorage){throw 'Managed run requires new storage; preserve previous process evidence'}
 [System.IO.Directory]::CreateDirectory($taskStorage)|Out-Null
 & $taskExe (Join-Path $taskBuild 'native') (Native-Path $taskMeta.apk) $taskStorage 2>&1|Tee-Object -FilePath (Join-Path $taskBuild 'managed-run.log')
 $taskRecord['run_exit_code']=$LASTEXITCODE;Save-Record
 if($LASTEXITCODE){throw 'Original Managed-copy gate failed; exact first failure retained'}
}
