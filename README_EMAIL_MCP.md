# 邮件MCP服务使用说明

## 概述
邮件MCP服务提供了邮件发送和接收功能，可以通过MCP协议与AI助手集成。

## 功能特性

### 可用工具
1. **send_email** - 发送邮件
   - 参数: to_email(收件人邮箱), subject(邮件主题), body(邮件正文)
   - 返回: 发送结果信息

2. **receive_emails** - 接收未读邮件
   - 参数: max_emails(最大接收数量，默认10)
   - 返回: 邮件列表，包含发件人、主题、日期、正文等信息

3. **check_email_credentials** - 检查邮件服务配置
   - 返回: 配置检查结果

## 配置要求

### 环境变量
需要设置以下环境变量：

```bash
# SMTP配置
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587

# IMAP配置  
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# 邮箱账号
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### 白名单配置
- 允许的发件人: kunlunqiaofu@gmail.com
- 允许的主题前缀: "SEC: 日记", "SEC: 周报"

## 启动方式

### 方式一: 直接运行MCP服务
```bash
python app/mcp/email_mcp_server.py
```

### 方式二: 使用批处理脚本
```bash
start_email_mcp.bat
```

### 方式三: 通过AI助手自动启动
配置在config.json中，AI助手会自动启动邮件MCP服务。

## 集成到AI助手

邮件MCP服务已经配置在 `config.json` 中，AI助手会自动识别并使用以下工具：

- `send_email` - 发送邮件
- `receive_emails` - 接收邮件
- `check_email_credentials` - 检查配置

## 使用示例

### 发送邮件
```
请使用send_email工具发送邮件到example@email.com，主题为"测试邮件"，正文为"这是一封测试邮件"
```

### 接收邮件
```
请使用receive_emails工具查看最近的未读邮件
```

### 检查配置
```
请检查邮件服务配置是否正常
```

## 故障排除

1. **认证失败**: 检查邮箱密码是否为应用专用密码
2. **连接超时**: 检查网络连接和防火墙设置
3. **服务未启动**: 确认MCP服务正在运行

## 安全说明

- 邮箱密码使用环境变量存储，避免硬编码
- 实现了发件人白名单机制
- 支持SSL/TLS加密通信