@echo off
setlocal enabledelayedexpansion

REM ================================
REM SuperSecretary 日志查看脚本
REM ================================

REM 切换到脚本所在目录
cd /d "%~dp0"

echo ================================
echo 📋 Viewing SuperSecretary Logs...
echo ================================

REM 检查日志目录是否存在
if not exist ".\logs" (
    echo ❌ 错误: 未找到日志目录 logs\
    echo 请先启动服务以生成日志文件
    pause
    exit /b 1
)

REM 查找最新的日志文件
set latest_log=
for /f "delims=" %%i in ('dir /b /o-d logs\secretary_*.log 2^>nul') do (
    set latest_log=logs\%%i
    goto :break
)

:break
if "!latest_log!"=="" (
    echo ❌ 错误: 未找到任何日志文件
    echo 请先启动服务以生成日志
    pause
    exit /b 1
)

echo 📄 最新日志文件: !latest_log!
echo 📊 文件大小: 
for %%F in (!latest_log!) do echo    %%~zF bytes
echo ================================

REM 显示日志最后50行
echo 🕐 显示最后50行日志:
echo.
tail -n 50 "!latest_log!" 2>nul
if errorlevel 1 (
    echo ⚠️  tail命令不可用，使用替代方法...
    echo.
    for /f "skip^=1 delims=[]" %%a in ('find /v /c "" "!latest_log!" 2^>nul') do set total=%%a
    if defined total (
        set /a skip=!total!-50
        if !skip! lss 0 set skip=0
        more +!skip! "!latest_log!"
    ) else (
        type "!latest_log!" | more
    )
)

echo.
echo 💡 提示:
echo - 查看完整日志: type "!latest_log!"
echo - 实时跟踪日志: tail -f "!latest_log!"
echo - 清空日志: type nul > "!latest_log!"

pause
endlocal