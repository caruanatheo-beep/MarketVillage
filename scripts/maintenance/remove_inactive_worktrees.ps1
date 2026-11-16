param([int]$Limit=0,[switch]$Execute)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'native_tree_cleanup.ps1')
try{(Get-Process -Id $PID).PriorityClass='BelowNormal'}catch{}
$taskRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')).TrimEnd('\','/')
$reportRoot=Join-Path $taskRoot 'artifacts/storage-cleanup'
$area=[IO.Path]::GetFullPath((Join-Path $taskRoot '.city-worktrees'))
$plan=Get-Content -LiteralPath (Join-Path $reportRoot 'worktree-cleanup-plan.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if(-not $plan.root.Equals($taskRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected cleanup workspace'}
$python=Join-Path $taskRoot '.codex-tools/python312/python.exe'
$before=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($taskRoot)).AvailableFreeSpace
$removed=0;$skipped=0;$bytes=0L;$files=0L
$details=@();$failures=@()
foreach($row in $plan.worktrees){
 if($Limit -gt 0 -and $removed -ge $Limit){break}
 $path=[IO.Path]::GetFullPath($row.path)
 if(-not ([IO.Path]::GetDirectoryName($path)).Equals($area,[StringComparison]::OrdinalIgnoreCase) -or $row.task_id -notmatch '^[a-f0-9]{32}$'){throw 'Unsafe worktree target'}
 if(-not (Test-Path -LiteralPath $path)){continue}
 try{
  $checkText=& $python (Join-Path $PSScriptRoot 'check_cleanup_candidate.py') $row.task_id --allow-orphan --native-delete 2>$null
  $check=$checkText | ConvertFrom-Json
  if($LASTEXITCODE -ne 0 -or -not $check.safe){throw ('Candidate check: '+$check.reason)}
  if(-not $check.safe -or $check.path -ne $path){throw 'Invalid candidate verification'}
  if(-not $Execute){Write-Output ('Verified candidate '+$row.task_id);continue}
  $stats=[MarketDeskCleanup.NativeTree]::Remove($taskRoot,$path)
  $bytes+=$stats[1];$files+=$stats[0]
  if(Test-Path -LiteralPath $path){throw 'Native worktree removal failed'}
  $baseline=Join-Path $area ($row.task_id+'.baseline.json')
  if(Test-Path -LiteralPath $baseline){Remove-Item -LiteralPath $baseline -Force}
  $removed++
  $details+=[pscustomobject]@{task_id=$row.task_id;bytes=$stats[1];files=$stats[0]}
  if($removed%10 -eq 0){Write-Output ('Removed '+$removed+' inactive worktrees')}
 }catch{$skipped++;$failures+=[pscustomobject]@{task_id=$row.task_id;reason=$_.Exception.Message};if($skipped -le 5){Write-Output ('Skipped candidate: '+$_.Exception.Message)}}
}
$after=[IO.DriveInfo]::new([IO.Path]::GetPathRoot($taskRoot)).AvailableFreeSpace
$report=[pscustomobject]@{removed=$removed;skipped=$skipped;logical_bytes_removed=$bytes;files_removed=$files;free_bytes_before=$before;free_bytes_after=$after;observed_freed_bytes=($after-$before);details=$details;failures=$failures}
$name=if($Limit -gt 0){'worktree-cleanup-sample.json'}else{'worktree-cleanup-result.json'}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $reportRoot $name) -Encoding UTF8
[pscustomobject]@{removed=$removed;skipped=$skipped;logical_gib_removed=[math]::Round($bytes/1GB,3);files_removed=$files;observed_freed_gib=[math]::Round(($after-$before)/1GB,3)} | ConvertTo-Json -Compress
