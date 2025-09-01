@echo off
chcp 65001 >nul

REM ================================
REM SuperSecretary Stop Script
REM ================================

REM Change to script directory
cd /d "%~dp0"

echo ================================
echo Stopping SuperSecretary Service...
echo ================================

REM Check Python interpreter exists
if not exist ".\.conda\secpy312\python.exe" (
    echo ERROR: Python interpreter not found at .\.conda\secpy312\python.exe
    echo Please make sure conda environment is properly installed
    pause
    exit /b 1
)

REM Stop secretary service
echo Stopping secretary service...
.\.conda\secpy312\python.exe -m app.main secretary stop

echo Stop command sent
echo Service may take a few seconds to fully stop

pause