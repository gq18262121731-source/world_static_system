@echo off
rem One-click launcher: backend + frontend + browser.
rem Double-click to start everything; extra args are passed through,
rem e.g.  start_all.bat -SkipFrontend -NoBrowser -Reload
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_all.ps1" %*
echo.
pause
