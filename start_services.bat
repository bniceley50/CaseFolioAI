@echo off
echo Starting CaseFolio AI Services...
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please run setup_windows.bat first
    pause
    exit /b 1
)

REM Start Celery in new window
echo Starting Celery worker...
start "CaseFolio AI - Celery Worker" cmd /k "celery -A celery_app worker --loglevel=info --pool=solo"

REM Wait a moment for Celery to start
timeout /t 3 /nobreak >nul

REM Start FastAPI in new window
echo Starting API server...
start "CaseFolio AI - API Server" cmd /k "uvicorn api:app --reload --host 0.0.0.0 --port 8000"

REM Wait for API to start
timeout /t 3 /nobreak >nul

echo.
echo Services started!
echo.
echo Celery Worker: Running in separate window
echo API Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo To use CaseFolio AI:
echo   1. Open chronoanchor_workbench.html in your browser
echo   2. Click "Upload Document" to process a file
echo.
echo Press any key to open the UI in your default browser...
pause >nul

REM Open the UI
start chronoanchor_workbench.html