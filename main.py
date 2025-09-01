#!/usr/bin/env python3
"""
SuperSecretary 主入口程序
整合邮件发送、接收、报告生成和私人秘书服务
"""
import os
import time
import argparse
from dotenv import load_dotenv
from app.email_gateway import process_once, _send_mail
from app.report_secretary import add_diary, gen_weekly
from app.personal_secretary import PersonalSecretary, start_secretary_service

load_dotenv()

def send_email_command(args):
    """发送邮件命令"""
    _send_mail(args.to, args.subject, args.body)
    print("✅ 邮件发送完成")

def receive_email_command(args):
    """接收邮件命令"""
    if args.once:
        process_once()
    else:
        print(f"📧 开始邮件监控，每 {args.interval} 秒检查一次...")
        try:
            while True:
                process_once()
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\n🛑 邮件监控已停止")

def diary_add_command(args):
    """添加日记命令"""
    path = add_diary(args.text, args.date)
    print(f"✅ 日记已记录: {path}")

def diary_report_command(args):
    """生成周报命令"""
    path = gen_weekly(args.start, args.end)
    print(f"✅ 周报已生成: {path}")

def secretary_command(args):
    """私人秘书服务命令"""
    secretary = PersonalSecretary()
    
    if args.action == "start":
        secretary.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 接收到中断信号，停止服务...")
            secretary.stop()
    elif args.action == "stop":
        secretary.stop()
    elif args.action == "status":
        secretary.status()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="SuperSecretary - 智能邮件秘书")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # 邮件发送
    send_parser = subparsers.add_parser("send", help="发送邮件")
    send_parser.add_argument("--to", required=True, help="收件人邮箱")
    send_parser.add_argument("--subject", required=True, help="邮件主题")
    send_parser.add_argument("--body", required=True, help="邮件内容")
    send_parser.set_defaults(func=send_email_command)
    
    # 邮件接收
    receive_parser = subparsers.add_parser("receive", help="接收邮件")
    receive_parser.add_argument("--once", action="store_true", help="只处理一次")
    receive_parser.add_argument("--interval", type=int, default=30, help="检查间隔(秒)，默认30秒")
    receive_parser.set_defaults(func=receive_email_command)
    
    # 日记管理
    diary_parser = subparsers.add_parser("diary", help="管理日记")
    diary_subparsers = diary_parser.add_subparsers(dest="subcommand", required=True)
    
    # 添加日记
    add_parser = diary_subparsers.add_parser("add", help="添加日记")
    add_parser.add_argument("--text", required=True, help="日记内容")
    add_parser.add_argument("--date", help="日期(YYYY-MM-DD)，默认为今天")
    add_parser.set_defaults(func=diary_add_command)
    
    # 生成周报
    report_parser = diary_subparsers.add_parser("report", help="生成周报")
    report_parser.add_argument("--start", help="开始日期(YYYY-MM-DD)")
    report_parser.add_argument("--end", help="结束日期(YYYY-MM-DD)")
    report_parser.set_defaults(func=diary_report_command)
    
    # 邮件网关（处理一次）
    gateway_parser = subparsers.add_parser("gateway", help="处理一次邮件")
    gateway_parser.set_defaults(func=lambda args: process_once())
    
    # 私人秘书服务
    secretary_parser = subparsers.add_parser("secretary", help="私人秘书服务")
    secretary_parser.add_argument("action", choices=["start", "stop", "status"], 
                                 help="服务操作: start-启动, stop-停止, status-状态")
    secretary_parser.set_defaults(func=secretary_command)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        process_once()

if __name__ == "__main__":
    main()