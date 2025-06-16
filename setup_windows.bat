@echo off
echo Setting up CaseFolio AI on Windows...
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo [2/4] Redis Setup Instructions:
echo.
echo Option A: Install Redis for Windows
echo   1. Download Redis from: https://github.com/microsoftarchive/redis/releases
echo   2. Extract and run redis-server.exe
echo.
echo Option B: Use Windows Subsystem for Linux (WSL)
echo   1. Install WSL: wsl --install
echo   2. In WSL terminal: sudo apt update && sudo apt install redis-server
echo   3. Start Redis: sudo service redis-server start
echo.
echo Press any key once Redis is running...
pause

echo.
echo [3/4] Creating .env file...
if not exist .env (
    copy .env.example .env
    echo Created .env file. Please edit it with your OpenAI API key.
) else (
    echo .env file already exists.
)

echo.
echo [4/4] Setup complete!
echo.
echo To run CaseFolio AI:
echo   1. Start Redis (if not already running)
echo   2. Run: start_services.bat
echo   3. Open chronoanchor_workbench.html in your browser
echo.
pause