param([switch]$Execute)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'native_tree_cleanup.ps1')
try{(Get-Process -Id $PID).PriorityClass='BelowNormal'}catch{}
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$taskRoot=$taskRoot.TrimEnd('\','/')
function Assert-TaskPath([string]$Path){
 $full=[IO.Path]::GetFullPath($Path)
 if(-not $full.StartsWith($taskRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup target outside workspace'}
 if($full -eq $taskRoot){throw 'Workspace root cannot be removed'}
 return $full
}
$reportRoot=Join-Path $taskRoot 'artifacts/storage-cleanup'
[IO.Directory]::CreateDirectory($reportRoot) | Out-Null
$targets=@()
foreach($base in @('.codex-tools','artifacts','artifacts/city-review')){
 $basePath=Join-Path $taskRoot $base
 if(Test-Path -LiteralPath $basePath){
  $targets+=@(Get-ChildItem -LiteralPath $basePath -Directory -Force | Where-Object {
   $_.Name -match '^(pytest[-_]|\.pytest_cache$)' -or ($base -eq '.codex-tools' -and $_.Name -match '^reliability-.*-test-tmp$')
  } | ForEach-Object {$_.FullName})
 }
}
foreach($name in @('.pytest_cache','.ruff_cache','.city-asset-check','.city-startup-check','.pytest_city_tmp','.scratch-codex-schema')){
 $path=Join-Path $taskRoot $name;if(Test-Path -LiteralPath $path){$targets+=$path}
}
$before=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($taskRoot)).AvailableFreeSpace
$removed=0;$skipped=0
foreach($path in $targets){
 $checked=Assert-TaskPath $path
 $relative=$checked.Substring($taskRoot.Length+1).Replace('\','/')
 $tracked=@(& git -c core.hooksPath=NUL -c core.fsmonitor=false -c "safe.directory=$taskRoot" -C $taskRoot ls-files -- $relative)
 if($LASTEXITCODE -ne 0){throw 'Tracked-file check failed'}
 if($tracked.Count){$skipped++;continue}
 if(-not $Execute){continue}
 try{
  $item=Get-Item -LiteralPath $checked -Force
  if($item.LinkType -in @('Junction','SymbolicLink')){throw 'Top-level link is not a cleanup target'}
  $stats=[MarketDeskCleanup.NativeTree]::Remove($taskRoot,$checked)
  if(Test-Path -LiteralPath $checked){throw 'Some temporary files remain locked'}
  $removed++
 }catch{$skipped++}
}
$after=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($taskRoot)).AvailableFreeSpace
$report=[pscustomobject]@{candidates=$targets.Count;removed=$removed;skipped=$skipped;free_bytes_before=$before;free_bytes_after=$after;observed_freed_bytes=($after-$before)}
$report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $reportRoot 'test-cleanup-result.json') -Encoding UTF8
$report | ConvertTo-Json -Compress
