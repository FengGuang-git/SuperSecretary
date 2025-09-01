import os
import ssl
import smtplib
from dotenv import load_dotenv

load_dotenv()

# 获取SMTP配置
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

print(f"测试SMTP配置：")
print(f"SMTP_HOST: {SMTP_HOST}")
print(f"SMTP_PORT: {SMTP_PORT}")
print(f"SMTP_USER: {SMTP_USER}")
print(f"SMTP_PASS长度: {len(SMTP_PASS)} 字符")

# 测试连接
try:
    print("\n尝试连接到SMTP服务器...")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
        print("连接成功，尝试登录...")
        server.login(SMTP_USER, SMTP_PASS)
        print("登录成功！SMTP配置正确")
        
        # 测试发送邮件
        print("\n尝试发送测试邮件...")
        from_addr = SMTP_USER
        to_addr = "kunlunqiaofu@gmail.com"
        subject = "测试邮件"
        body = "这是一封测试邮件，确认SMTP配置是否正确。"
        
        message = f"From: {from_addr}\n"
        message += f"To: {to_addr}\n"
        message += f"Subject: {subject}\n\n"
        message += body
        
        server.sendmail(from_addr, to_addr, message.encode('utf-8'))
        print(f"邮件发送成功！已发送到 {to_addr}")
        
except Exception as e:
    print(f"错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()