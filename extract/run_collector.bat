@echo off
rem starts the collector and starts it again if it ever closes
rem to stop for good: ctrl+c, then press N when it asks
rem put this file in the same folder as 01-collect_data.py

cd /d "%~dp0"

:start
"%~dp0..\.venv\Scripts\python.exe" 01-collect_data.py
choice /c YN /t 30 /d Y /m "collector stopped. restarting in 30 seconds. press N to stop for good"
if errorlevel 2 goto end
goto start

:end
echo collector stopped.