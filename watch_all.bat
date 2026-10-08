@echo off
REM 服务守护监听：主后端 / 前端 / Vision 掉线自动拉起（窗口保持打开可见巡检日志）
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\watch_all.ps1"
pause
