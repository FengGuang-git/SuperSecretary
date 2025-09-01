@echo off
echo 启动邮件MCP服务...
cd /d "%~dp0"
python app/mcp/email_mcp_server.py
pause