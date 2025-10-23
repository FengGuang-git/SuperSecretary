#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置文件加载模块
负责加载和解析config.json配置文件
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

# 加载.env文件中的环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✅ .env文件已加载")
except ImportError:
    print("⚠️  python-dotenv未安装，跳过.env文件加载")
except Exception as e:
    print(f"⚠️  加载.env文件失败: {e}")


class ConfigLoader:
    """配置加载器类"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """设置日志记录器"""
        logger = logging.getLogger(__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger
    
    @staticmethod
    def _resolve_env_vars(config_data: Any) -> Any:
        """
        递归解析配置中的环境变量（静态方法）
        
        Args:
            config_data: 配置数据
            
        Returns:
            解析后的配置数据
        """
        if isinstance(config_data, dict):
            return {key: ConfigLoader._resolve_env_vars(value) for key, value in config_data.items()}
        elif isinstance(config_data, list):
            return [ConfigLoader._resolve_env_vars(item) for item in config_data]
        elif isinstance(config_data, str):
            # 处理 ${VAR_NAME} 格式的环境变量
            if config_data.startswith('${') and config_data.endswith('}'):
                var_name = config_data[2:-1]
                env_value = os.getenv(var_name)
                if env_value is not None:
                    return env_value
                # 如果环境变量未设置，返回空字符串而不是占位符
                return ''
        return config_data
    
    @staticmethod
    def load_config(config_path: str = "config.json") -> Dict[str, Any]:
        """加载配置文件（静态方法）"""
        try:
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"配置文件不存在: {config_path}")
            
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            # 解析环境变量
            config = ConfigLoader._resolve_env_vars(raw_config)
            
            # 验证必要配置
            ConfigLoader._validate_config(config)
            
            # 提取老板邮箱列表
            config['boss_emails'] = ConfigLoader._extract_boss_emails(config)
            
            print("✅ 配置文件解析成功")
            return config
            
        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            raise
    
    @staticmethod
    def _validate_config(config: Dict[str, Any]):
        """验证配置文件完整性"""
        required_sections = ['main_prompts', 'model_default_params', 'mcpServers']
        
        for section in required_sections:
            if section not in config:
                raise ValueError(f"配置文件缺少必要部分: {section}")
        
        # 验证main_prompts结构（支持数组或字典格式）
        main_prompts = config['main_prompts']
        if not isinstance(main_prompts, (dict, list)):
            raise ValueError("main_prompts必须是字典或数组类型")
        
        # 验证mcpServers配置
        mcp_servers = config['mcpServers']
        if 'zerolib-email' not in mcp_servers:
            raise ValueError("mcpServers必须包含zerolib-email配置")
    
    @staticmethod
    def _extract_boss_emails(config: Dict[str, Any]) -> List[str]:
        """
        从配置中提取老板邮箱列表
        
        Args:
            config: 配置字典
            
        Returns:
            老板邮箱列表
        """
        boss_emails = []
        
        # 从main_prompts中提取老板邮箱
        main_prompts = config.get('main_prompts', {})
        
        # 检查是否有明确的老板邮箱配置
        if isinstance(main_prompts, dict) and 'boss_email' in main_prompts:
            boss_email = main_prompts['boss_email']
            if isinstance(boss_email, str) and boss_email:
                boss_emails.append(boss_email)
        
        # 如果main_prompts是数组，从文本内容中提取邮箱
        elif isinstance(main_prompts, list):
            import re
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            for item in main_prompts:
                if isinstance(item, str):
                    # 查找邮箱地址
                    emails = re.findall(email_pattern, item)
                    for email in emails:
                        # 只添加18696133867@163.com这个老板邮箱
                        if email == '18696133867@163.com' and email not in boss_emails:
                            boss_emails.append(email)
        
        # 从环境变量或默认配置中获取
        import os
        env_boss_email = os.getenv('BOSS_EMAIL')
        if env_boss_email:
            boss_emails.append(env_boss_email)
        
        # 如果没有配置老板邮箱，使用默认值
        if not boss_emails:
            boss_emails = ['18696133867@163.com']  # 默认老板邮箱
        
        return boss_emails
    
    @staticmethod
    def get_boss_emails(config: Dict[str, Any]) -> List[str]:
        """
        获取老板邮箱列表（静态方法）
        
        Args:
            config: 配置字典
            
        Returns:
            老板邮箱列表
        """
        # 如果配置中已经有boss_emails字段，直接返回
        if 'boss_emails' in config:
            return config['boss_emails']
        
        # 否则提取老板邮箱
        return ConfigLoader._extract_boss_emails(config)
    
    @staticmethod
    def get_email_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取邮件服务配置
        
        Args:
            config: 配置字典
            
        Returns:
            邮件服务配置
        """
        mcp_servers = config.get('mcpServers', {})
        email_config = mcp_servers.get('zerolib-email', {})
        
        # 提取环境变量配置
        env_config = email_config.get('env', {})
        
        return {
            'command': email_config.get('command', 'uvx'),
            'args': email_config.get('args', ['mcp-email-server@latest', 'stdio']),
            'env': env_config
        }
    
    @staticmethod
    def get_ai_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取AI模型配置
        
        Args:
            config: 配置字典
            
        Returns:
            AI模型配置
        """
        model_params = config.get('model_default_params', {})
        models_config = config.get('models', {})
        
        return {
            'model': model_params.get('model', 'gpt-4'),
            'temperature': model_params.get('temperature', 0.7),
            'max_tokens': model_params.get('max_tokens', 2000),
            'api_key': models_config.get('openai', {}).get('api_key'),
            'base_url': models_config.get('openai', {}).get('base_url')
        }
    
    @staticmethod
    def get_prompt_config(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取提示词配置
        
        Args:
            config: 配置字典
            
        Returns:
            提示词配置
        """
        main_prompts = config.get('main_prompts', {})
        
        # 如果main_prompts是数组，将其转换为字典格式
        if isinstance(main_prompts, list):
            # 将数组内容合并为一个字符串作为角色描述
            role_description = '\n'.join([str(item) for item in main_prompts if item])
            return {
                'role_description': role_description,
                'core_responsibilities': [],
                'important_rules': [],
                'time_greeting_templates': {},
                'schedule_communication_logic': {},
                'hard_constraints': []
            }
        else:
            # 如果是字典格式，按原逻辑处理
            return {
                'role_description': main_prompts.get('role_description', ''),
                'core_responsibilities': main_prompts.get('core_responsibilities', []),
                'important_rules': main_prompts.get('important_rules', []),
                'time_greeting_templates': main_prompts.get('time_greeting_templates', {}),
                'schedule_communication_logic': main_prompts.get('schedule_communication_logic', {}),
                'hard_constraints': main_prompts.get('hard_constraints', [])
            }


if __name__ == "__main__":
    # 测试代码
    try:
        config = ConfigLoader.load_config("config.json")
        print("配置加载测试成功")
        print(f"老板邮箱: {config.get('boss_emails', [])}")
    except Exception as e:
        print(f"配置加载测试失败: {e}")