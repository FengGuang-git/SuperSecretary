@echo off
setlocal

REM ================================
REM SuperSecretary 状态检查脚本
REM ================================

REM 切换到脚本所在目录
cd /d "%~dp0"

echo ================================
echo 📊 Checking SuperSecretary Service Status...
echo ================================

REM 检查Python解释器是否存在
if not exist ".\.conda\secpy312\python.exe" (
    echo ❌ 错误: 未找到Python解释器 .\.conda\secpy312\python.exe
    echo 请确保已正确安装conda环境
    pause
    exit /b 1
)

REM 检查服务状态
echo 📋 服务状态:
.\.conda\secpy312\python.exe -m app.main secretary status

echo.
echo 📝 最近日志文件:
for /f "delims=" %%i in ('dir /b /o-d logs\secretary_*.log 2^>nul') do (
    echo - %%i
    goto :break
)
:break

echo.
echo 💡 提示: 使用 start_secretary.bat 启动服务
pause
endlocal