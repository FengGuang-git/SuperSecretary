Write-Host "==============================="
Write-Host "   SuperSecretary 私人秘书服务"
Write-Host "==============================="
Write-Host ""
Write-Host "正在启动私人秘书服务..."
Write-Host "服务将自动："
Write-Host "  - 每天18:00提醒写工作总结"
Write-Host "  - 监控老板邮件并自动回复"
Write-Host "  - 每5分钟检查一次邮件"
Write-Host ""
Write-Host "按 Ctrl+C 停止服务"
Write-Host ""

Set-Location $PSScriptRoot
python main.py secretary start