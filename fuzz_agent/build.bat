@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

set "VENV_PY=%~dp0..\agentscope_env\Scripts\python.exe"

if not exist "%VENV_PY%" (
    echo [错误] 找不到虚拟环境 Python: %VENV_PY%
    pause
    exit /b 1
)

echo ============================================
echo   IndusFuzz 打包脚本
echo ============================================
echo.

echo [1/4] 清理用户缓存（确保 EXE 为未使用状态）...
set "CACHE_DIR=%USERPROFILE%\.indusfuzz"
if exist "%CACHE_DIR%\config.json" (
    del /q "%CACHE_DIR%\config.json"
    echo   已清除缓存: %CACHE_DIR%\config.json
) else (
    echo   无缓存文件
)
echo.

echo [2/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo 完成。
echo.

echo [3/4] 执行 PyInstaller 打包...
"%VENV_PY%" -m PyInstaller --clean IndusFuzz.spec
if errorlevel 1 (
    echo [错误] 打包失败
    pause
    exit /b 1
)
echo.

echo [4/4] 检查产物...
if exist "dist\IndusFuzz.exe" (
    for %%A in ("dist\IndusFuzz.exe") do echo EXE 大小: %%~zA 字节
    echo 打包成功！
) else (
    echo [错误] dist\IndusFuzz.exe 不存在
    pause
    exit /b 1
)

echo.
pause
