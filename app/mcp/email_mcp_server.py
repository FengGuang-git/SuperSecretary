# -*- coding: utf-8 -*-
"""
邮件MCP服务 - 提供邮件发送和接收功能的MCP服务器
"""
import os
import json
import smtplib
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import decode_header
from typing import Dict, List, Any, Optional
from fastmcp import FastMCP

# 创建FastMCP实例
mcp = FastMCP("email-mcp")

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 配置
SMTP_SERVER = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
IMAP_SERVER = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
EMAIL_USER = os.getenv("SMTP_USER", "")
EMAIL_PASSWORD = os.getenv("SMTP_PASS", "")

# 白名单配置
ALLOWED_SENDERS = set(os.getenv("MAIL_ALLOWED_SENDERS", "kunlunqiaofu@gmail.com").split(","))


def _send_email(to_email: str, subject: str, body: str) -> str:
    """发送邮件"""
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 连接SMTP服务器并发送
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
            
        return f"邮件发送成功: {subject} -> {to_email}"
    except Exception as e:
        return f"邮件发送失败: {str(e)}"


def _receive_emails(max_emails: int = 10) -> List[Dict[str, Any]]:
    """接收邮件"""
    emails = []
    try:
        # 连接IMAP服务器
        with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as mail:
            mail.login(EMAIL_USER, EMAIL_PASSWORD)
            mail.select('inbox')
            
            # 搜索未读邮件
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return emails
            
            # 获取邮件
            email_ids = messages[0].split()
            for i, email_id in enumerate(email_ids[:max_emails]):
                status, msg_data = mail.fetch(email_id, '(RFC822)')
                if status != 'OK':
                    continue
                
                # 解析邮件
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                # 解析邮件头
                subject, encoding = decode_header(msg['Subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding or 'utf-8')
                
                from_email = msg['From']
                date = msg['Date']
                
                # 解析邮件内容
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        if content_type == "text/plain" and "attachment" not in content_disposition:
                            body = part.get_payload(decode=True).decode()
                            break
                else:
                    body = msg.get_payload(decode=True).decode()
                
                emails.append({
                    'id': email_id.decode(),
                    'from': from_email,
                    'subject': subject,
                    'date': date,
                    'body': body,
                    'is_allowed': from_email in ALLOWED_SENDERS
                })
                
                # 标记为已读
                mail.store(email_id, '+FLAGS', r'\Seen')
                
    except Exception as e:
        return [{'error': f"接收邮件失败: {str(e)}"}]
    
    return emails


@mcp.tool()
def send_email(to_email: str, subject: str, body: str) -> str:
    """
    发送邮件
    
    Args:
        to_email: 收件人邮箱地址
        subject: 邮件主题
        body: 邮件正文内容
        
    Returns:
        发送结果信息
    """
    return _send_email(to_email, subject, body)


@mcp.tool()
def receive_emails(max_emails: int = 10) -> List[Dict[str, Any]]:
    """
    接收未读邮件
    
    Args:
        max_emails: 最大接收邮件数量，默认10封
        
    Returns:
        邮件列表，包含发件人、主题、日期、正文等信息
    """
    return _receive_emails(max_emails)


@mcp.tool()
def check_email_credentials() -> str:
    """
    检查邮件服务配置是否有效
    
    Returns:
        配置检查结果
    """
    if not EMAIL_USER or not EMAIL_PASSWORD:
        return "错误: 未配置邮箱用户名或密码"
    
    try:
        # 测试SMTP连接
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
        
        # 测试IMAP连接
        with imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as mail:
            mail.login(EMAIL_USER, EMAIL_PASSWORD)
            
        return "邮件服务配置正常"
    except Exception as e:
        return f"邮件服务配置错误: {str(e)}"


if __name__ == "__main__":
    # 启动MCP服务器
    mcp.run(transport="stdio")