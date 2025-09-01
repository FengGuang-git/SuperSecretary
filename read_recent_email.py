import os
import imaplib
import email
from dotenv import load_dotenv

load_dotenv()

# 配置
IMAP_HOST = os.getenv("IMAP_HOST", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")

def read_recent_email():
    """读取最近的邮件内容"""
    print("📨 正在读取最近的邮件...")
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            print(f"🔄 尝试连接 ({attempt + 1}/{max_retries})...")
            
            # 连接IMAP
            M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
            print("✅ IMAP连接成功")
            
            M.login(IMAP_USER, IMAP_PASS)
            print("✅ 登录成功")
            
            M.select("INBOX")
            print("✅ 选择收件箱成功")
            
            # 搜索所有邮件
            typ, data = M.search(None, "ALL")
            
            if typ == "OK" and data[0]:
                email_ids = data[0].split()
                print(f"✅ 找到 {len(email_ids)} 封邮件")
                
                # 读取最新邮件
                latest_id = email_ids[-1]
                typ, msg_data = M.fetch(latest_id, "(RFC822)")
                
                if typ == "OK":
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # 获取邮件信息
                    from_addr = email.utils.parseaddr(msg.get("From"))[1]
                    subject = msg.get("Subject", "")
                    date = msg.get("Date", "")
                    
                    print(f"\n📧 最新邮件信息:")
                    print(f"📨 发件人: {from_addr}")
                    print(f"📝 主题: {subject}")
                    print(f"📅 时间: {date}")
                    
                    # 提取纯文本内容
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                                break
                    else:
                        body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
                    
                    print(f"\n📄 邮件内容:")
                    print("=" * 50)
                    print(body.strip())
                    print("=" * 50)
                    
                    M.close()
                    M.logout()
                    return True
            
            M.close()
            M.logout()
            break  # 成功执行，退出重试循环
            
        except Exception as e:
            print(f"❌ 尝试 {attempt + 1} 失败: {e}")
            
            # 如果是最后一次尝试，打印详细错误信息
            if attempt == max_retries - 1:
                import traceback
                traceback.print_exc()
            
            # 等待一段时间后重试
            import time
            time.sleep(2)
    
    print("❌ 未找到邮件或连接失败")
    return False

if __name__ == "__main__":
    read_recent_email()