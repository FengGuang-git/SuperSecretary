#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件MCP服务集成测试脚本
"""
import time
from app.chat import Client

def test_email_mcp_integration():
    """测试邮件MCP服务集成"""
    print("=== 邮件MCP服务集成测试 ===")
    
    # 创建客户端
    client = Client()
    
    # 检查可用的邮件相关工具
    email_tools = [t for t in client.tools if 'email' in t['function']['name']]
    print(f"可用的邮件工具: {[t['function']['name'] for t in email_tools]}")
    
    # 测试配置检查
    print("\n1. 测试邮件配置检查...")
    try:
        result = client.funcDict['check_email_credentials']()
        print(f"配置检查结果: {result}")
    except Exception as e:
        print(f"配置检查失败: {e}")
    
    # 测试接收邮件
    print("\n2. 测试接收邮件...")
    try:
        result = client.funcDict['receive_emails'](max_emails=3)
        print(f"收到 {len(result)} 封邮件")
        for i, email in enumerate(result):
            print(f"  邮件 {i+1}: {email.get('subject', '无主题')} - {email.get('from', '未知发件人')}")
    except Exception as e:
        print(f"接收邮件失败: {e}")
    
    # 测试发送邮件（仅测试功能，不实际发送）
    print("\n3. 测试发送邮件功能...")
    try:
        # 使用测试邮箱避免实际发送
        result = client.funcDict['send_email'](
            to_email="test@example.com", 
            subject="测试邮件 - 请勿回复", 
            body="这是一封测试邮件，用于验证邮件MCP服务集成功能。"
        )
        print(f"发送测试结果: {result}")
    except Exception as e:
        print(f"发送邮件测试失败: {e}")
    
    print("\n=== 测试完成 ===")
    
    # 显示所有可用的MCP工具
    print("\n所有可用的MCP工具:")
    for tool in client.tools:
        tool_name = tool['function']['name']
        if any(keyword in tool_name for keyword in ['email', 'send', 'receive', 'check']):
            print(f"  📧 {tool_name}: {tool['function']['description']}")
        else:
            print(f"  🔧 {tool_name}")

if __name__ == "__main__":
    test_email_mcp_integration()