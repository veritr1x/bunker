param([string]$Cxx='C:\mingw64\bin\g++.exe')
$ErrorActionPreference='Stop'
$taskWork=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\work'))
$taskRoot=Join-Path $taskWork 'angle-scaling'
$taskOutput=Join-Path $taskWork 'graphics-probe-scaling'
New-Item -ItemType Directory -Force -Path $taskOutput|Out-Null
$taskBase=@('-std=c++17','-O2','-DADDRESS_SIZE_BITS=64','-isystem',(Join-Path $taskWork 'remill-src\include'))
$taskObjects=@()
foreach($taskSource in @('graphics_probe_scaling.cpp','native_window.cpp','jni_host.cpp','..\whole\runtime.cpp')){
  $taskFile=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot $taskSource));$taskObject=Join-Path $taskOutput (([IO.Path]::GetFileNameWithoutExtension($taskFile))+'.o')
  $taskStrict=@();if($taskSource -in @('graphics_probe_scaling.cpp','native_window.cpp')){$taskStrict=@('-Wall','-Wextra','-Werror')}
  & $Cxx @taskBase @taskStrict '-c' $taskFile '-o' $taskObject
  if($LASTEXITCODE){throw "Scaling probe compile failed:$taskSource"}
  $taskObjects+=$taskObject
}
$taskExe=Join-Path $taskOutput 'test.exe'
& $Cxx '-static' '-municode' @taskObjects '-pthread' '-latomic' '-luser32' '-o' $taskExe
if($LASTEXITCODE){throw 'Scaling probe link failed'}
$taskPrevious=$env:BUNKER_ANGLE_SCALING_TRACE
try{
  $env:BUNKER_ANGLE_SCALING_TRACE='1'
  $taskProcess=Start-Process -FilePath $taskExe -ArgumentList ('"'+(Join-Path $taskRoot 'bundle\bin')+'"') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'result.json') -RedirectStandardError (Join-Path $taskOutput 'stderr.log')
  if(-not $taskProcess.WaitForExit(60000)){$taskProcess.Kill();$taskProcess.WaitForExit();throw 'Native scaling probe timed out'}
  $taskProcess.WaitForExit()
}finally{$env:BUNKER_ANGLE_SCALING_TRACE=$taskPrevious}
Get-Content -Raw (Join-Path $taskOutput 'result.json')
if($taskProcess.ExitCode){throw "Native scaling probe failed exit$($taskProcess.ExitCode)"}
