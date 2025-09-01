@echo off
echo 📧 启动 SuperSecretary 邮件监控服务
echo ====================================
echo.
echo 正在启动邮件监控（每5分钟检查一次）...
echo 按 Ctrl+C 停止监控
echo.
python main.py receive --interval 300
pause