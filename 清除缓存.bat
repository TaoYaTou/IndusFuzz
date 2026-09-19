@echo off
chcp 65001 >nul
cd /d "%~dp0"
title IndusFuzz Cache Cleanup
echo Starting IndusFuzz cache cleanup...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0clean_cache.ps1"
set "EXITCODE=%ERRORLEVEL%"
echo.
if not "%EXITCODE%"=="0" (
    echo [ERROR] Cleanup script exited with code: %EXITCODE%
) else (
    echo [DONE] Cache cleanup finished
)
echo.
echo ============================================================
echo  Press any key to close this window...
echo ============================================================
pause >nul
