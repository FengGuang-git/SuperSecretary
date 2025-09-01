# SuperSecretary 邮件功能使用指南

## 📧 邮件功能概述

本项目已整合完整的邮件发送和接收功能，支持通过QQ邮箱进行邮件通信。

## 🔧 环境配置

在 `.env` 文件中配置邮箱信息：

```env
# SMTP 发件配置
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=your_email@qq.com
SMTP_PASS=your_authorization_code

# IMAP 收件配置  
IMAP_HOST=imap.qq.com
IMAP_PORT=993
IMAP_USER=your_email@qq.com
IMAP_PASS=your_authorization_code

# 邮件白名单（可选）
MAIL_ALLOWED_SENDERS=allowed1@example.com,allowed2@example.com
```

> **注意**: QQ邮箱需要使用授权码而不是登录密码

## 🚀 使用方法

### 主入口程序

```bash
# 发送邮件
python main.py send --to recipient@example.com --subject "测试主题" --body "邮件内容"

# 接收并处理邮件（单次）
python main.py receive --once

# 持续监控邮件（每5分钟检查一次）
python main.py receive --interval 300

# 处理一次邮件（等同于 email_gateway）
python main.py gateway

# 管理日记
python main.py diary add --text "今日工作内容" --date 2025-08-31
python main.py diary report --start 2025-08-25 --end 2025-08-31
```

### 独立功能脚本

```bash
# 测试SMTP发送
python test_smtp.py

# 测试IMAP接收  
python test_imap_simple.py

# 完整邮件功能测试
python test_email_complete.py

# 邮件交互测试（发送+等待回复）
python test_email_interaction.py

# 读取最新邮件
python read_recent_email.py
```

## 📨 邮件指令格式

### 接收邮件指令

Agent 会自动处理主题包含以下前缀的邮件：
- `SEC: 日记` - 记录日记
- `SEC: 日记 YYYY-MM-DD` - 记录指定日期的日记  
- `SEC: 周报` - 生成周报

支持 `Re:` 和 `Fwd:` 前缀自动识别。

### 发送邮件

邮件发送支持纯文本格式，自动使用UTF-8编码。

## 🔒 安全特性

- **白名单过滤**: 只处理白名单发件人的邮件
- **主题过滤**: 只处理特定主题前缀的邮件
- **连接超时**: 防止网络问题导致的长时间阻塞
- **重试机制**: 自动重试失败的连接操作

## 🛠️ 技术实现

### 发送功能 (`_send_mail`)
- 使用 SMTP_SSL 安全连接
- 支持 EmailMessage 构建邮件
- 自动处理连接结束软错误

### 接收功能 (`process_once`)
- 使用 IMAP4_SSL 安全连接  
- 仅搜索 UNSEEN 邮件提高效率
- 本地主题过滤避免服务端搜索问题
- 双超时机制（socket + search）
- 指数退避重试策略

### 邮件解析
- 自动解码邮件主题（支持各种编码）
- 提取纯文本内容
- 支持多部分邮件解析

## 📊 日志输出

邮件处理过程会输出详细日志，包括：
- 连接状态和时间
- 登录结果
- 未读邮件数量
- 主题匹配数量
- 处理结果统计

## 🐛 常见问题

### SSL握手超时
如果遇到SSL握手超时，程序会自动重试3次

### 连接被重置  
可能是网络问题，检查防火墙和代理设置

### 授权码错误
确保使用QQ邮箱的授权码而不是登录密码

## 🔗 相关文件

- `app/email_gateway.py` - 邮件网关核心功能
- `app/report_secretary.py` - 日记和周报功能
- `main.py` - 主入口程序
- 各种测试脚本在项目根目录