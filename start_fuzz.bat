@echo off
chcp 65001 >nul

cd /d "%~dp0"

set "VENV_PY=%~dp0agentscope_env\Scripts\python.exe"

REM Dynamically read version from src/core/version.py (single source of truth)
for /f "usebackq delims=" %%v in (`"%VENV_PY%" -c "import sys; sys.path.insert(0, r'%~dp0'); from src.core.version import get_version; print(get_version())" 2^>nul`) do set "APP_VERSION=%%v"
if "%APP_VERSION%"=="" set "APP_VERSION=1.8.0"

echo ============================================
echo   IndusFuzz v%APP_VERSION% 一键启动
echo ============================================
echo.

if not exist "%VENV_PY%" (
    echo [错误] 找不到虚拟环境: %VENV_PY%
    pause
    exit /b 1
)

"%VENV_PY%" main.py

echo.
echo 完成。报告位于 reports\ 目录。
pause

