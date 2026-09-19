@echo off
chcp 65001 >nul
cd /d "%~dp0"
title IndusFuzz Build
echo Starting IndusFuzz build script...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
    echo [ERROR] Build script exited with code: %EXITCODE%
    echo [HINT] Please screenshot the error above and send to developer
) else (
    echo [DONE] Build process finished
)
echo.
echo ============================================================
echo  Press any key to close this window...
echo ============================================================
pause >nul
