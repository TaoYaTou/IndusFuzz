@echo off
chcp 65001 >nul
echo ============================================
echo   IndusFuzz v1.5.0 一键启动
echo ============================================
echo.

cd /d "%~dp0"

set "VENV_PY=%~dp0..\agentscope_env\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [错误] 找不到虚拟环境: %VENV_PY%
    pause
    exit /b 1
)

"%VENV_PY%" main.py

echo.
echo 完成。报告位于 reports\ 目录。
pause