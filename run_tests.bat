@echo off
chcp 65001 >nul

echo ====================================
echo   IndusFuzz 一键测试启动器
echo ====================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE=%~dp0agentscope_env\Scripts\python.exe"
set "PROJECT_ROOT=%~dp0"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] 未找到虚拟环境 Python: %PYTHON_EXE%
    echo 请确认 agentscope_env 目录存在
    pause
    exit /b 1
)

echo [Python] %PYTHON_EXE%
echo [项目]   %PROJECT_ROOT%
echo.

"%PYTHON_EXE%" run_all_tests.py
set "EXITCODE=%ERRORLEVEL%"

echo.
echo ====================================
echo   测试完成，窗口将在 30 秒后自动关闭
echo   按任意键立即关闭
echo ====================================
echo.

timeout /t 30
pause
exit /b %EXITCODE%
