@echo off
rem ============================================
rem  随取词典 - 启动脚本（后台运行，无控制台窗口）
rem ============================================
cd /d "%~dp0"

where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw main.py
) else (
    start "" python main.py
)
