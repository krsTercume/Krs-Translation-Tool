@echo off
cd /d "%~dp0"
echo %~dp0 | find /i "\Temp\" >nul && echo WARNING: you are running from inside a zip. Extract the zip first!
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 src\main.py
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python is not installed or not in PATH. Install it from python.org and tick "Add Python to PATH".
  ) else (
    python src\main.py
  )
)
echo.
echo (If an error is shown above, send it to the developer.)
pause
