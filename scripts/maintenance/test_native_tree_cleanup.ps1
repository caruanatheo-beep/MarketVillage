$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'native_tree_cleanup.ps1')
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$base=Join-Path (Join-Path $root 'artifacts/storage-cleanup') ('native-self-test-'+[guid]::NewGuid().ToString('N'))
$target=Join-Path $base 'remove';$keep=Join-Path $base 'keep'
[IO.Directory]::CreateDirectory($target) | Out-Null
[IO.Directory]::CreateDirectory($keep) | Out-Null
[IO.File]::WriteAllText((Join-Path $keep 'sentinel.txt'),'preserve')
$indirect=Join-Path $base 'indirect'
New-Item -ItemType Junction -Path $indirect -Target $keep | Out-Null
$blocked=$false
try{[MarketDeskCleanup.NativeTree]::Remove($root,(Join-Path $indirect 'nested')) | Out-Null}catch{$blocked=$true}
if(-not $blocked){throw 'Redirected ancestor was accepted'}
$readonly=Join-Path $target 'readonly.txt';[IO.File]::WriteAllText($readonly,'remove')
[IO.File]::SetAttributes($readonly,[IO.FileAttributes]::ReadOnly)
New-Item -ItemType Junction -Path (Join-Path $target 'linked') -Target $keep | Out-Null
$long=$target
1..6 | ForEach-Object {$long=Join-Path $long ('directory-'+('x'*25))}
[IO.Directory]::CreateDirectory(('\\?\'+$long)) | Out-Null
[IO.File]::WriteAllText(('\\?\'+(Join-Path $long 'long.txt')),'remove')
[IO.File]::SetAttributes(('\\?\'+$long),([IO.File]::GetAttributes(('\\?\'+$long)) -bor [IO.FileAttributes]::ReadOnly))
[IO.File]::SetAttributes($target,([IO.File]::GetAttributes($target) -bor [IO.FileAttributes]::ReadOnly))
$stats=[MarketDeskCleanup.NativeTree]::Remove($root,$target)
if(Test-Path -LiteralPath $target){throw 'Target remains after native cleanup'}
if(-not (Test-Path -LiteralPath (Join-Path $keep 'sentinel.txt'))){throw 'Junction target was touched'}
$blocked=$false
try{[MarketDeskCleanup.NativeTree]::Remove($root,(Split-Path $root -Parent)) | Out-Null}catch{$blocked=$true}
if(-not $blocked){throw 'Outside-workspace target was accepted'}
[MarketDeskCleanup.NativeTree]::Remove($root,$base) | Out-Null
[pscustomobject]@{long_paths=$true;readonly_files=$true;junction_target_preserved=$true;redirected_ancestor_blocked=$true;outside_workspace_blocked=$true;errors=$stats[3]} | ConvertTo-Json -Compress
