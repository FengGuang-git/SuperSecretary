#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
邮件服务模块
基于zerolib-email MCP实现邮件收发功能
"""

import logging
import time
from typing import Dict, Any, List, Optional

from .mcp.mcp_bridge import MCPBridge


class EmailService:
    """邮件服务类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化邮件服务
        
        Args:
            config: 配置字典
        """
        self.logger = logging.getLogger(__name__)
        self.config = config
        
        # MCP桥接器
        self.mcp_bridge = None
        self.email_tools = None
        
        # 邮件处理状态
        self.last_check_time = None
        self.processed_emails = set()
        
        # 初始化邮件服务
        self._init_email_service()
    
    def _init_email_service(self):
        """初始化邮件服务"""
        try:
            # 创建MCP桥接器
            self.mcp_bridge = MCPBridge(config=self.config)
            
            # 获取邮件工具
            self.email_tools = self.mcp_bridge.get_func_map()
            
            # 验证邮件工具可用性
            self._validate_email_tools()
            
            self.logger.info("邮件服务初始化成功")
            
        except Exception as e:
            self.logger.error(f"邮件服务初始化失败: {e}")
            raise
    
    def _validate_email_tools(self):
        """验证邮件工具是否可用"""
        # 邮件MCP服务实际提供的工具名称
        actual_tools = ['send_email', 'page_email', 'list_available_accounts']
        
        # 检查是否至少有一个邮件工具可用
        available_tools = [tool for tool in actual_tools if tool in self.email_tools]
        if not available_tools:
            raise ValueError(f"缺少必要的邮件工具，期望的工具: {actual_tools}")
        
        self.logger.info(f"可用的邮件工具: {available_tools}")
    
    def check_new_emails(self) -> List[Dict[str, Any]]:
        """
        检查新邮件
        
        Returns:
            新邮件列表
        """
        try:
            # 使用page_email工具获取最新邮件元数据
            result = self.email_tools['page_email'](
                account_name="default",
                page=1,
                page_size=10,
                order="desc"
            )
            
            # 解析邮件结果
            emails = self._parse_email_result(result)
            
            # 过滤已处理的邮件
            new_emails = []
            for email in emails:
                email_id = email.get('id')
                if email_id and email_id not in self.processed_emails:
                    new_emails.append(email)
                    self.processed_emails.add(email_id)
            
            self.logger.info(f"发现 {len(new_emails)} 封新邮件")
            return new_emails
            
        except Exception as e:
            self.logger.error(f"检查新邮件失败: {e}")
            return []
    
    def send_email(self, to: List[str], subject: str, body: str, 
                   cc: Optional[List[str]] = None, 
                   bcc: Optional[List[str]] = None) -> bool:
        """
        发送邮件
        
        Args:
            to: 收件人列表
            subject: 邮件主题
            body: 邮件正文
            cc: 抄送列表
            bcc: 密送列表
            
        Returns:
            发送是否成功
        """
        try:
            # 使用send_email工具发送邮件
            result = self.email_tools['send_email'](
                account_name="default",
                recipients=to,
                subject=subject,
                body=body,
                cc=cc or [],
                bcc=bcc or []
            )
            
            self.logger.info(f"邮件发送成功: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"邮件发送失败: {e}")
            return False
    
    def _parse_email_result(self, result: Any) -> List[Dict[str, Any]]:
        """
        解析邮件工具返回结果
        
        Args:
            result: 邮件工具返回结果
            
        Returns:
            邮件列表
        """
        emails = []
        
        # 处理不同类型的返回结果
        if isinstance(result, list):
            # 直接返回邮件列表
            emails = result
        elif isinstance(result, dict):
            # 包含分页信息的返回结果
            if 'emails' in result:
                emails = result['emails']
            elif 'data' in result:
                emails = result['data']
        elif hasattr(result, 'emails'):
            # 对象类型的返回结果
            emails = result.emails
        
        # 标准化邮件格式
        standardized_emails = []
        for email in emails:
            if isinstance(email, dict):
                standardized_emails.append(self._standardize_email_format(email))
        
        return standardized_emails
    
    def _standardize_email_format(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化邮件格式
        
        Args:
            email: 原始邮件数据
            
        Returns:
            标准化后的邮件数据
        """
        standardized = {
            'id': email.get('id') or email.get('message_id') or str(hash(str(email))),
            'from': email.get('from') or email.get('sender') or '',
            'to': email.get('to') or email.get('recipients') or [],
            'subject': email.get('subject') or '',
            'body': email.get('body') or email.get('content') or email.get('text') or '',
            'date': email.get('date') or email.get('timestamp') or ''
        }
        
        # 确保to字段是列表
        if isinstance(standardized['to'], str):
            standardized['to'] = [standardized['to']]
        
        return standardized
    
    def get_email_accounts(self) -> List[Dict[str, Any]]:
        """
        获取配置的邮件账户列表
        
        Returns:
            邮件账户列表
        """
        try:
            if 'list_available_accounts' in self.email_tools:
                result = self.email_tools['list_available_accounts']()
                return result if isinstance(result, list) else []
            else:
                self.logger.warning("list_available_accounts工具不可用")
                return []
                
        except Exception as e:
            self.logger.error(f"获取邮件账户列表失败: {e}")
            return []
    
    def stop(self):
        """停止邮件服务"""
        if self.mcp_bridge:
            try:
                self.mcp_bridge.stop()
                self.logger.info("邮件服务已停止")
            except Exception as e:
                self.logger.error(f"停止邮件服务时发生错误: {e}")


if __name__ == "__main__":
    # 测试代码
    import json
    
    # 加载测试配置
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    email_service = EmailService(config)
    print("邮件服务初始化测试成功")
    
    # 测试获取邮件账户
    accounts = email_service.get_email_accounts()
    print(f"邮件账户: {accounts}")
    
    email_service.stop()