@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

echo ==========================================
echo   AI News Bot - Listener
echo   Close this window to stop the bot.
echo ==========================================
echo.

python listener.py

echo.
echo Bot stopped. Press any key to close...
pause >nul
