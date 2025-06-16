@echo off
echo Stopping CaseFolio AI Services...
echo.

REM Kill Celery processes
echo Stopping Celery workers...
taskkill /FI "WINDOWTITLE eq CaseFolio AI - Celery Worker*" /F >nul 2>&1

REM Kill Uvicorn processes
echo Stopping API server...
taskkill /FI "WINDOWTITLE eq CaseFolio AI - API Server*" /F >nul 2>&1

REM Also try to kill by process name
taskkill /IM celery.exe /F >nul 2>&1
taskkill /IM uvicorn.exe /F >nul 2>&1

echo.
echo Services stopped.
pause