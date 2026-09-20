@echo off
chcp 65001 >nul
setlocal

cd /d "%~dp0"

REM Dynamically read version from src/core/version.py (single source of truth)
set "VENV_PY=%~dp0agentscope_env\Scripts\python.exe"
for /f "usebackq delims=" %%v in ("%VENV_PY%" -c "import sys; sys.path.insert(0, r'%~dp0'); from src.core.version import get_version; print(get_version())" 2^>nul) do set "VERSION=%%v"
if "%VERSION%"=="" set "VERSION=1.8.4"
set "RELEASE_DIR=IndusFuzz-v%VERSION%-win64"
set "ZIP_NAME=IndusFuzz-v%VERSION%-win64.zip"

echo ============================================
echo   生成 IndusFuzz 发布包
echo   版本: %VERSION%
echo ============================================
echo.

if not exist "dist\IndusFuzz.exe" (
    echo [错误] dist\IndusFuzz.exe 不存在，请先运行 build.bat
    pause
    exit /b 1
)

echo [1/6] 创建发布目录...
if exist "%RELEASE_DIR%" rmdir /s /q "%RELEASE_DIR%"
mkdir "%RELEASE_DIR%"
echo 完成。
echo.

echo [2/6] 复制 EXE 和文档...
copy "dist\IndusFuzz.exe" "%RELEASE_DIR%\" >nul
copy "README.md" "%RELEASE_DIR%\" >nul 2>nul
copy "README.zh.md" "%RELEASE_DIR%\" >nul 2>nul
copy "CHANGELOG.md" "%RELEASE_DIR%\" >nul 2>nul
copy "LICENSE" "%RELEASE_DIR%\" >nul 2>nul
copy "requirements.txt" "%RELEASE_DIR%\" >nul 2>nul
echo 完成。
echo.

echo [3/6] 复制配置...
xcopy "config" "%RELEASE_DIR%\config\" /E /I /Y >nul
echo 完成。
echo.

echo [4/6] 复制文档...
mkdir "%RELEASE_DIR%\docs" 2>nul
copy "docs\IndusFuzz 协议扩展 PRD.md" "%RELEASE_DIR%\docs\" >nul 2>nul
echo 完成。
echo.

echo [5/6] 复制字体...
mkdir "%RELEASE_DIR%\assets\fonts" 2>nul
copy "assets\fonts\simhei.ttf" "%RELEASE_DIR%\assets\fonts\" >nul 2>nul
echo 完成。
echo.

echo [6/6] 创建 reports 空目录...
mkdir "%RELEASE_DIR%\reports" 2>nul
echo. > "%RELEASE_DIR%\reports\.gitkeep"
echo 完成。
echo.

echo 生成 ZIP 包...
if exist "%ZIP_NAME%" del "%ZIP_NAME%"
powershell -Command "Compress-Archive -Path '%RELEASE_DIR%\*' -DestinationPath '%ZIP_NAME%' -Force"
if errorlevel 1 (
    echo [错误] ZIP 生成失败
    pause
    exit /b 1
)

echo.
echo ============================================
echo   发布包生成成功！
echo   %ZIP_NAME%
echo ============================================
pause


