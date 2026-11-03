$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $root '.codex-tools\python312\pythonw.exe'
$worker = Join-Path $root 'scripts\run_city_worker.py'
if (-not (Test-Path -LiteralPath $python) -or -not (Test-Path -LiteralPath $worker)) {
    throw 'Python ou le worker City est introuvable dans ce dépôt.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $python -Argument ('"' + $worker + '"') -WorkingDirectory $root
$daily = New-ScheduledTaskTrigger -Daily -At '08:00'
$logon = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 10) -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName 'MarketDesk City Daily' -Action $action -Trigger @($daily, $logon) -Principal $principal -Settings $settings -Force | Out-Null
Write-Output 'MarketDesk City Daily installé : à 08:00 et à la connexion Windows.'
