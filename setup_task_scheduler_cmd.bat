@echo off
REM Run this ONCE, as Administrator (right-click this file -> Run as administrator).
REM Sets up two scheduled tasks using schtasks.exe  -  no PowerShell needed.
REM
REM Covers: catch-up at every login (after a crash, reboot, or the laptop
REM being off), plus a daily run at 11:45 PM.
REM Does NOT cover: automatic relaunch if the script crashes mid-run during
REM the day  -  that specific extra needs setup_task_scheduler.ps1 instead.

for /f "delims=" %%P in ('where python') do set PYTHON_EXE=%%P
set SCRIPT_DIR=%~dp0
set SCRIPT_PATH=%SCRIPT_DIR%run_daily.py

echo Using Python at: %PYTHON_EXE%
echo Using script at: %SCRIPT_PATH%
echo.

schtasks /create /TN "OptionChainPipeline_AtLogon" ^
    /TR "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" ^
    /SC ONLOGON ^
    /RL LIMITED ^
    /F

schtasks /create /TN "OptionChainPipeline_Daily" ^
    /TR "\"%PYTHON_EXE%\" \"%SCRIPT_PATH%\"" ^
    /SC DAILY ^
    /ST 23:45 ^
    /RL LIMITED ^
    /F

echo.
echo Done. Two scheduled tasks created:
echo   - OptionChainPipeline_AtLogon  (runs every time you log in)
echo   - OptionChainPipeline_Daily    (runs daily at 11:45 PM)
echo.
echo Verify with: schtasks /query /TN "OptionChainPipeline_AtLogon"
echo To test immediately: schtasks /run /TN "OptionChainPipeline_AtLogon"
pause
