@echo off
rem starts the collector and starts it again if it ever closes
rem put this file in the same folder as collect.py

cd /d "%~dp0"

:start
python collect.py
echo collector stopped, starting again in 30 seconds...
timeout /t 30 /nobreak
goto start
