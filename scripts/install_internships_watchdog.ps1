$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $root '.codex-tools/python312/pythonw.exe'
$worker=Join-Path $root 'scripts/internships_refresh_watchdog.py'
if(-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $worker)){
 throw 'Watchdog runtime unavailable'
}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$worker+'" --recover') -WorkingDirectory $root
$interval=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 15)
$logon=New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal=New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'MarketDesk Internships Refresh Watchdog' -Action $action -Trigger @($interval,$logon) -Principal $principal -Settings $settings -Force | Out-Null
Write-Output 'Internships recovery check installed: every 15 minutes while signed in.'
