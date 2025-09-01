#!/usr/bin/env python3
"""
测试chat.py中的Client类
"""
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.chat import Client

def test_chat_client():
    """测试Client类的基本功能"""
    print("🚀 创建Client实例...")
    
    try:
        # 创建客户端实例
        client = Client()
        print("✅ Client实例创建成功")
        
        # 显示可用的工具数量
        print(f"📋 可用工具总数: {len(client.tools)}")
        
        # 显示邮件相关的工具
        email_tools = [tool for tool in client.tools if 'email' in tool['function']['name'].lower()]
        print(f"📧 邮件相关工具: {len(email_tools)}个")
        
        for tool in email_tools:
            tool_name = tool['function']['name']
            print(f"  - {tool_name}")
        
        print("\n🎯 测试完成！Client类可以正常使用。")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_chat_client()