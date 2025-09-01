#!/usr/bin/env python3
"""
测试agent邮件自动回复功能
模拟老板发送邮件，测试agent是否能正确回复
"""
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.header import Header
import os
from dotenv import load_dotenv

load_dotenv()

def send_test_email():
    """发送测试邮件给老板邮箱"""
    try:
        # 从环境变量获取SMTP配置
        smtp_server = os.getenv("SMTP_HOST")  # 使用SMTP_HOST而不是SMTP_SERVER
        smtp_port = int(os.getenv("SMTP_PORT", "465"))  # QQ邮箱使用465端口
        smtp_user = os.getenv("SMTP_USER")
        smtp_password = os.getenv("SMTP_PASS")  # 使用SMTP_PASS而不是SMTP_PASSWORD
        boss_email = os.getenv("BOSS_EMAIL")
        
        if not all([smtp_server, smtp_user, smtp_password, boss_email]):
            print("❌ 缺少SMTP配置，请检查.env文件")
            return False
        
        # 创建邮件内容（主题必须以SEC:开头才能被过滤）
        subject = "SEC: 测试邮件 - 请处理这个任务"
        body = """亲爱的秘书：

请帮我安排下周的会议，主题是关于项目进度汇报。
时间安排在周三下午2点，地点在会议室A。

请确认并回复。

谢谢！
老板
"""
        
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['From'] = smtp_user
        msg['To'] = boss_email
        msg['Subject'] = Header(subject, 'utf-8')
        
        # 发送邮件（使用SSL连接，与email_gateway.py保持一致）
        context = ssl.create_default_context()
        try:
            srv = smtplib.SMTP_SSL(smtp_server, smtp_port, context=context, timeout=60)
            srv.login(smtp_user, smtp_password)
            srv.sendmail(smtp_user, [boss_email], msg.as_string())
            srv.quit()
            
            print(f"✅ 测试邮件已发送到: {boss_email}")
            print(f"📧 主题: {subject}")
            return True
            
        except smtplib.SMTPResponseException as e:
            if getattr(e, "smtp_code", None) == -1 and getattr(e, "smtp_error", b"") == b"\x00\x00\x00":
                print(f"📨 测试邮件已发送到 {boss_email}（忽略连接结束软错误）")
                print(f"📧 主题: {subject}")
                return True
            else:
                print(f"❌ 发送失败：{e.smtp_code} {e.smtp_error!r}")
                return False
                
        except Exception as e:
            print(f"❌ 发送测试邮件失败: {e}")
            return False
        
    except Exception as e:
        print(f"❌ 发送测试邮件失败: {e}")
        return False

if __name__ == "__main__":
    print("🚀 开始测试agent邮件自动回复功能")
    print("=" * 50)
    
    # 发送测试邮件
    success = send_test_email()
    
    if success:
        print("\n📋 测试说明:")
        print("1. 邮件已发送到老板邮箱")
        print("2. 秘书服务会检测到新邮件")
        print("3. Agent会自动处理邮件并回复")
        print("4. 请检查老板邮箱是否收到自动回复")
        print("\n⏳ 等待agent处理邮件中...")
        print("（等待约30秒后检查邮件）")
        
        # 等待一段时间让agent处理
        time.sleep(35)
        print("\n✅ 测试完成！请检查老板邮箱是否收到自动回复。")
    else:
        print("❌ 测试失败，请检查配置")