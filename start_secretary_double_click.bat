@echo off
chcp 65001 >nul

REM ================================
REM SuperSecretary Double Click Startup Script
REM ================================

REM Change to script directory
cd /d "%~dp0"

REM Check Python environment
echo ================================
echo Starting SuperSecretary Service...
echo Current directory: %cd%
echo ================================

REM Check Python interpreter exists
if not exist ".\.conda\secpy312\python.exe" (
    echo ERROR: Python interpreter not found at .\.conda\secpy312\python.exe
    echo Please make sure conda environment is properly installed
    pause
    exit /b 1
)

REM Create logs directory
if not exist ".\logs" mkdir ".\logs"

REM Generate simple log filename
set logfile=logs\secretary_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%.log

echo Log file: %logfile%
echo Start time: %date% %time%
echo ================================

echo Starting secretary service...

REM Start service in current window (no redirection to keep window open)
.\.conda\secpy312\python.exe main.py secretary start

echo Service stopped
echo Check log file: %logfile%
echo To stop service: .\stop_secretary.bat
pause