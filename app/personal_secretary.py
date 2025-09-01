# app/personal_secretary.py
"""
私人秘书服务模块
负责每日提醒、工作总结督促和邮件互动
"""
import os
import time
import datetime
import threading
from typing import Optional
from dotenv import load_dotenv
from app.email_gateway import process_once, _send_mail
from app.report_secretary import add_diary, gen_weekly

load_dotenv()

class PersonalSecretary:
    """私人秘书类"""
    
    def __init__(self):
        self.running = False
        self.reminder_thread: Optional[threading.Thread] = None
        self.email_thread: Optional[threading.Thread] = None
        
        # 配置参数
        self.work_end_time = os.getenv("WORK_END_TIME", "18:00")  # 下班时间
        self.reminder_interval = int(os.getenv("REMINDER_INTERVAL", "3600"))  # 提醒间隔(秒)
        self.email_check_interval = int(os.getenv("EMAIL_CHECK_INTERVAL", "30"))  # 邮件检查间隔(秒)
        self.boss_email = os.getenv("BOSS_EMAIL", "")  # 老板邮箱
        self.user_email = os.getenv("SMTP_USER", "")  # 用户邮箱
    
    def _send_reminder(self, message: str):
        """发送提醒"""
        print(f"提醒: {message}")
        # 可以扩展为发送到其他渠道（如微信、钉钉等）
    
    def _check_work_summary(self):
        """检查工作总结"""
        today = datetime.date.today().isoformat()
        diary_file = f"data/diary/{today}.md"
        
        if os.path.exists(diary_file):
            with open(diary_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                return True, "今日工作总结已完成"
        
        return False, "今日工作总结尚未完成"
    
    def _reminder_loop(self):
        """提醒循环"""
        while self.running:
            try:
                now = datetime.datetime.now()
                
                # 检查是否下班时间
                end_time = datetime.datetime.strptime(self.work_end_time, "%H:%M").time()
                if now.time() >= end_time:
                    # 检查工作总结
                    completed, message = self._check_work_summary()
                    if not completed:
                        reminder_msg = f"提醒 {message}，请及时完成今日工作总结！"
                        self._send_reminder(reminder_msg)
                    else:
                        print(f"✅ {message}")
                
                time.sleep(self.reminder_interval)
                
            except Exception as e:
                print(f"错误 提醒循环出错: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续
    
    def _email_monitor_loop(self):
        """邮件监控循环 - 集成agent自动处理老板邮件"""
        from app.chat import Client
        
        # 初始化agent客户端
        client = Client()
        client.set_model(client.config["models"][0])
        
        # 记录已处理的邮件时间戳，避免重复处理
        processed_emails = set()
        
        while self.running:
            try:
                # 处理邮件并获取新邮件信息
                new_emails = process_once()
                
                # 如果有新邮件且来自老板，启动agent处理
                if new_emails and self.boss_email:
                    for email in new_emails:
                        email_key = f"{email.get('from', '')}_{email.get('subject', '')}_{email.get('timestamp', '')}"
                        
                        if (email.get('from') and 
                            self.boss_email in email['from'] and 
                            email_key not in processed_emails):
                            
                            print(f"收到老板邮件: {email.get('subject', '无主题')}")
                            processed_emails.add(email_key)
                            
                            # 使用agent处理邮件内容
                            email_content = f"发件人: {email.get('from', '未知')}\n"
                            email_content += f"主题: {email.get('subject', '无主题')}\n"
                            email_content += f"内容: {email.get('body', '无内容')}"
                            
                            prompt = f"请处理这封来自老板的邮件:\n{email_content}\n\n请分析邮件内容并给出合适的回复。"
                            
                            try:
                                # 显示老板的邮件内容（同时写入日志）
                                boss_message = f"老板: {email_content}"
                                print(boss_message)
                                # 写入日志文件
                                with open(f"logs/secretary_interaction.log", "a", encoding="utf-8") as log_file:
                                    log_file.write(f"{datetime.datetime.now()}: {boss_message}\n")
                                
                                # 获取agent回复并显示交互记录
                                response = client.send(prompt)
                                if response and response.get('content'):
                                    secretary_message = f"秘书: {response['content']}"
                                    print(secretary_message)
                                    # 写入日志文件
                                    with open(f"logs/secretary_interaction.log", "a", encoding="utf-8") as log_file:
                                        log_file.write(f"{datetime.datetime.now()}: {secretary_message}\n")
                                    
                                    # 自动发送回复邮件给老板
                                    reply_subject = f"Re: {email.get('subject', '您的邮件')}"
                                    _send_mail(
                                        self.boss_email,
                                        reply_subject,
                                        response['content']
                                    )
                                    success_message = "成功 已自动回复老板邮件"
                                    print(success_message)
                                    # 写入日志文件
                                    with open(f"logs/secretary_interaction.log", "a", encoding="utf-8") as log_file:
                                        log_file.write(f"{datetime.datetime.now()}: {success_message}\n")
                                    
                            except Exception as agent_error:
                                print(f"错误 Agent处理出错: {agent_error}")
                
                time.sleep(self.email_check_interval)
                
            except Exception as e:
                print(f"错误 邮件监控出错: {e}")
                time.sleep(60)  # 出错后等待1分钟再继续
    
    def start(self):
        """启动私人秘书服务"""
        if self.running:
            print("⚠️ 秘书服务已在运行中")
            return
        
        self.running = True
        
        # 启动提醒线程
        self.reminder_thread = threading.Thread(target=self._reminder_loop, daemon=True)
        self.reminder_thread.start()
        
        # 启动邮件监控线程
        self.email_thread = threading.Thread(target=self._email_monitor_loop, daemon=True)
        self.email_thread.start()
        
        print("私人秘书服务已启动")
        print(f"下班时间提醒: {self.work_end_time}")
        print(f"提醒间隔: {self.reminder_interval}秒")
        print(f"邮件检查间隔: {self.email_check_interval}秒")
        if self.boss_email:
            print(f"老板邮箱: {self.boss_email}")
    
    def stop(self):
        """停止私人秘书服务"""
        if not self.running:
            print("⚠️ 秘书服务未在运行")
            return
        
        self.running = False
        
        if self.reminder_thread:
            self.reminder_thread.join(timeout=5)
        if self.email_thread:
            self.email_thread.join(timeout=5)
        
        print("🛑 私人秘书服务已停止")
    
    def status(self):
        """查看服务状态"""
        status = "运行中" if self.running else "已停止"
        
        completed, message = self._check_work_summary()
        summary_status = "已完成" if completed else "未完成"
        
        print(f"秘书服务状态: {status}")
        print(f"今日工作总结: {summary_status}")
        print(f"下班时间: {self.work_end_time}")
        print(f"提醒间隔: {self.reminder_interval}秒")
        print(f"邮件检查间隔: {self.email_check_interval}秒")

def start_secretary_service():
    """启动秘书服务"""
    secretary = PersonalSecretary()
    secretary.start()
    
    try:
        # 主线程保持运行
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n停止信号 接收到中断信号，停止服务...")
        secretary.stop()

if __name__ == "__main__":
    start_secretary_service()