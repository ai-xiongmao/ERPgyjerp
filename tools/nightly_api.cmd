@echo off
rem Nightly API-layer health check (no browser, no UI login needed).
rem Register (daily 02:30, takes 1-3 min):
rem   schtasks /Create /SC DAILY /ST 02:30 /TN "ERP-API-Nightly" ^
rem            /TR "D:\Automation\ERPgyjerp\tools\nightly_api.cmd" /F
rem Remove:  schtasks /Delete /TN "ERP-API-Nightly" /F
rem Manual:  tools\nightly_api.cmd
rem Log:     dashboard\.cache\nightly.log (gitignored)
rem
rem NOTE: keep this file ASCII-only. cmd.exe parses .cmd in the OEM code page,
rem so UTF-8 Chinese comments here would come out as mojibake. The Chinese
rem messages live in tools\nightly_api.py, which Python decodes correctly.

setlocal
cd /d "%~dp0.."

if not exist "dashboard\.cache" mkdir "dashboard\.cache"
set "LOG=dashboard\.cache\nightly.log"

echo.>> "%LOG%"
echo ===== %DATE% %TIME% =====>> "%LOG%"
".venv\Scripts\python.exe" tools\nightly_api.py >> "%LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [exit %RC%]>> "%LOG%"

rem Exit code is recorded by Task Scheduler as "Last Run Result".
rem 0=pass 1=cases failed 2=nothing selected 3=token expired
exit /b %RC%
