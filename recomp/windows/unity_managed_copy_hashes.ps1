param([Parameter(Mandatory=$true)][string]$InputFile)
$ErrorActionPreference='Stop'
$taskFiles=[System.IO.File]::ReadAllText($InputFile)|ConvertFrom-Json
$taskHashes=[ordered]@{};$taskAlgorithm=[System.Security.Cryptography.SHA256]::Create()
try{foreach($taskFile in $taskFiles){
 $taskStream=[System.IO.File]::OpenRead($taskFile.path)
 try{$taskHashes[$taskFile.key]=[BitConverter]::ToString($taskAlgorithm.ComputeHash($taskStream)).Replace('-','').ToLowerInvariant()}
 finally{$taskStream.Dispose()}
}}finally{$taskAlgorithm.Dispose()}
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::Write(($taskHashes|ConvertTo-Json -Depth 3 -Compress))
