import os
import time
import ssl
import smtplib
import imaplib
import email
from dotenv import load_dotenv
from email.message import EmailMessage

load_dotenv()

# 配置
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.qq.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASS = os.getenv("IMAP_PASS", "")

def send_test_email():
    """发送测试邮件"""
    print("📤 正在发送测试邮件...")
    
    try:
        # 使用简单的SMTP发送方式
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx)
        server.login(SMTP_USER, SMTP_PASS)
        
        # 构建邮件内容
        from_addr = SMTP_USER
        to_addr = SMTP_USER  # 发给自己
        subject = "SEC: 测试邮件 - 请回复"
        
        body = """这是一封测试邮件。

请回复此邮件，主题保持 "Re: SEC: 测试邮件 - 请回复"，并在正文中输入一些测试内容。

回复后，我将读取您的回复内容并打印出来。

谢谢！"""
        
        message = f"From: {from_addr}\n"
        message += f"To: {to_addr}\n"
        message += f"Subject: {subject}\n\n"
        message += body
        
        server.sendmail(from_addr, to_addr, message.encode('utf-8'))
        server.quit()
        
        print("✅ 测试邮件发送成功！")
        print("📧 请检查您的收件箱，回复这封邮件")
        print("💡 回复时请保持主题前缀 'Re: SEC:'")
        return True
        
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def wait_for_reply(timeout_minutes=10):
    """等待用户回复，只读取白名单发件人的邮件"""
    print(f"\n⏳ 等待您的回复（最多等待 {timeout_minutes} 分钟）...")
    
    # 白名单发件人列表（可以在这里添加允许的发件人邮箱）
    whitelist_senders = [
        "kunlunqiaofu@gmail.com",  # 示例白名单邮箱
    ]
    
    print(f"🔒 白名单发件人: {', '.join(whitelist_senders)}")
    
    end_time = time.time() + timeout_minutes * 60
    
    while time.time() < end_time:
        try:
            # 连接IMAP
            M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT, timeout=30)
            M.login(IMAP_USER, IMAP_PASS)
            M.select("INBOX")
            
            # 搜索所有未读邮件
            typ, data = M.search(None, "UNSEEN")
            
            if typ == "OK" and data[0]:
                email_ids = data[0].split()
                
                # 检查每封未读邮件
                for email_id in email_ids:
                    typ, msg_data = M.fetch(email_id, "(RFC822)")
                    
                    if typ == "OK":
                        raw_email = msg_data[0][1]
                        msg = email.message_from_bytes(raw_email)
                        
                        # 获取发件人
                        from_addr = email.utils.parseaddr(msg.get("From"))[1]
                        subject = msg.get("Subject", "")
                        
                        # 检查是否在白名单中
                        if from_addr in whitelist_senders and "Re: SEC: 测试邮件" in subject:
                            print(f"✅ 找到来自白名单发件人 {from_addr} 的回复")
                            print(f"📝 主题: {subject}")
                            
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
                            
                            # 标记为已读
                            M.store(email_id, "+FLAGS", "\\Seen")
                            
                            M.close()
                            M.logout()
                            return True
                        else:
                            # 非白名单邮件，标记为已读但不处理
                            if from_addr not in whitelist_senders:
                                print(f"⚠️ 忽略非白名单发件人 {from_addr} 的邮件")
                                M.store(email_id, "+FLAGS", "\\Seen")
            
            M.close()
            M.logout()
            
            # 等待30秒再检查
            time.sleep(30)
            print(".", end="", flush=True)
            
        except Exception as e:
            print(f"\n⚠️ 检查邮件时出错: {e}")
            time.sleep(30)
    
    print(f"\n❌ 在 {timeout_minutes} 分钟内未收到白名单发件人的回复")
    return False

def main():
    """主函数"""
    print("🤖 开始邮件交互测试")
    print("=" * 50)
    
    # 发送测试邮件
    if not send_test_email():
        return
    
    # 等待回复
    print("\n" + "=" * 50)
    success = wait_for_reply(10)  # 等待10分钟
    
    if success:
        print("\n🎉 邮件交互测试完成！")
    else:
        print("\n❌ 测试未完成")

if __name__ == "__main__":
    main()