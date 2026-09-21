# Run this ONCE, from an elevated (Administrator) PowerShell prompt, to set
# up the two triggers that give this pipeline its "never look back" behavior
# on Windows:
#
#   1. "At log on"  -  the moment the laptop turns on / wakes / you log in,
#      after any crash, reboot, or being off overnight, the pipeline runs
#      and catches up automatically. No manual restart, ever.
#   2. Daily at a fixed time  -  the routine end-of-day sync, in case the
#      laptop was already on and logged in when the trading day ended.
#
# Both tasks are configured with Task Scheduler's own restart-on-failure
# (3 attempts, 5 minutes apart) as a first line of defense, independent of
# any retry logic inside the Python code itself.

$pythonExe = (Get-Command python).Source
$scriptPath = Join-Path $PSScriptRoot "run_daily.py"
$workingDir = $PSScriptRoot

# Wrap the path in literal double-quotes using single-quoted strings for the
# quote characters themselves  -  mixing backtick-escaping and variable
# interpolation in one double-quoted string (an earlier version of this
# line) is genuinely ambiguous PowerShell and broke the parser.
$scriptPathQuoted = '"' + $scriptPath + '"'
$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $scriptPathQuoted -WorkingDirectory $workingDir

$triggerLogon = New-ScheduledTaskTrigger -AtLogOn
$triggerDaily = New-ScheduledTaskTrigger -Daily -At "11:45PM"

$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

Register-ScheduledTask -TaskName "OptionChainPipeline_AtLogon" `
    -Action $action -Trigger $triggerLogon -Settings $settings `
    -Description "Runs the option-chain data sync/report at every login  -  catches up after any crash or time the laptop was off." `
    -Force

Register-ScheduledTask -TaskName "OptionChainPipeline_Daily" `
    -Action $action -Trigger $triggerDaily -Settings $settings `
    -Description "Runs the option-chain data sync/report daily at 11:45 PM, after both markets close." `
    -Force

Write-Host "Done. Two scheduled tasks created:"
Write-Host "  - OptionChainPipeline_AtLogon (runs every time you log in)"
Write-Host "  - OptionChainPipeline_Daily   (runs daily at 11:45 PM)"
Write-Host ""
Write-Host "Verify in Task Scheduler (taskschd.msc) under Task Scheduler Library."
Write-Host "To test immediately without waiting: right-click either task -> Run."
