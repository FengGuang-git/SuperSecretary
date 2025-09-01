import imaplib
import os
from dotenv import load_dotenv

load_dotenv()

# IMAP配置
IMAP_HOST = os.getenv("IMAP_HOST", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")

def test_imap_connection():
    """简单测试IMAP连接"""
    print(f"测试IMAP连接: {IMAP_HOST}:{IMAP_PORT}")
    
    try:
        # 连接IMAP服务器
        print("正在连接IMAP服务器...")
        M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
        print("✓ 连接成功")
        
        # 登录
        print("正在登录...")
        M.login(IMAP_USER, IMAP_PASS)
        print("✓ 登录成功")
        
        # 选择收件箱
        print("正在选择收件箱...")
        M.select("INBOX")
        print("✓ 选择收件箱成功")
        
        # 简单搜索测试
        print("正在搜索未读邮件...")
        typ, data = M.search(None, 'UNSEEN')
        if typ == "OK":
            ids = data[0].split() if data and data[0] else []
            print(f"✓ 搜索成功，找到 {len(ids)} 封未读邮件")
        else:
            print(f"✗ 搜索失败: {typ}")
        
        # 关闭连接
        M.close()
        M.logout()
        print("✓ 连接已关闭")
        return True
        
    except Exception as e:
        print(f"✗ 连接失败: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    success = test_imap_connection()
    if success:
        print("\n✓ IMAP连接测试通过")
    else:
        print("\n✗ IMAP连接测试失败")