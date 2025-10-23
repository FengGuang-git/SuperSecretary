#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
超级秘书AI服务程序 - 主入口模块
为丰光提供专属的AI秘书服务，基于zerolib-email MCP实现邮件交互
"""

import argparse
import logging
import sys
import os
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 加载.env文件（如果存在）
from dotenv import load_dotenv
load_dotenv()

from app.super_secretary import SuperSecretary


def setup_logging():
    """配置日志系统"""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "supersecretary_debug.log", encoding='utf-8')
        ]
    )


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='超级秘书AI服务程序')
    parser.add_argument('action', choices=['start', 'stop', 'status'], 
                       help='服务操作: start(启动), stop(停止), status(状态)')
    
    args = parser.parse_args()
    
    # 配置日志
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        secretary = SuperSecretary()
        
        if args.action == 'start':
            logger.info("正在启动超级秘书服务...")
            secretary.start()
            logger.info("超级秘书服务启动成功")
            
            # 保持主线程运行，等待服务运行
            try:
                while secretary.is_running():
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号，正在停止服务...")
                secretary.stop()
                logger.info("超级秘书服务已停止")
            
        elif args.action == 'stop':
            logger.info("正在停止超级秘书服务...")
            secretary.stop()
            logger.info("超级秘书服务已停止")
            
        elif args.action == 'status':
            status = secretary.get_status()
            logger.info(f"超级秘书服务状态: {status}")
            
    except Exception as e:
        logger.error(f"服务操作失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()