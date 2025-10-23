#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI代理模块 - 对话机器人版本
处理与AI模型的交互、工具调用和自然语言对话
"""

import json
import logging
import time
import re
import sys
import os
from typing import Dict, Any, List, Optional, Union
import dataclasses
from enum import Enum

# ========== 工具函数（参照chat.py实现） ==========
_DECODER = json.JSONDecoder()

def _json_default(o):
    if hasattr(o, "model_dump"):           # Pydantic v2
        return o.model_dump()
    if hasattr(o, "dict"):                 # Pydantic v1
        return o.dict()
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if isinstance(o, Enum):
        return o.value
    if hasattr(o, "__dict__"):             # 普通对象兜底
        return {k: v for k, v in o.__dict__.items()
                if not callable(v) and not k.startswith("_")}
    return str(o)

def _minify_json_str(s: str) -> str:
    """尽量把JSON字符串压成最短（去空格/换行），失败则原样返回。"""
    try:
        obj = json.loads(s)
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        return s

def _squeeze_text(s: str) -> str:
    """对非JSON文本进行轻量压缩：去两端空白、折叠多余换行与空格（不截断、不改语义）。"""
    if not isinstance(s, str):
        return s
    s = s.strip()
    # 连续换行压成单个换行
    s = re.sub(r"\n{2,}", "\n", s)
    # 每行内部多空格折叠为单空格（不触碰代码块语义）
    lines = []
    for line in s.split("\n"):
        if line.startswith("    ") or line.startswith("\t") or line.strip().startswith("```"):
            lines.append(line.rstrip())
        else:
            lines.append(re.sub(r"[ \t]{2,}", " ", line).rstrip())
    return "\n".join(lines)

def _is_json_like(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s2 = s.lstrip()
    return s2.startswith("{") or s2.startswith("[")

def _iter_json_objects(s: str):
    """从字符串中依次提取一个或多个 JSON 对象/数组（容错串流/NDJSON）。"""
    if not isinstance(s, str):
        yield s
        return
    i, n = 0, len(s)
    while i < n:
        # 跳过空白
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        try:
            obj, end = _DECODER.raw_decode(s, i)
            yield obj
            i = end
        except json.JSONDecodeError:
            j1 = s.find('{', i + 1)
            j2 = s.find('[', i + 1)
            cand = [x for x in (j1, j2) if x != -1]
            if not cand:
                break
            i = min(cand)

def safe_json_loads(s: str):
    """返回最后一个合法 JSON（通常是模型最终覆写的参数）。"""
    last = None
    for obj in _iter_json_objects(s):
        last = obj
    if last is None:
        return {}
    if not isinstance(last, dict):
        if isinstance(last, list) and last and isinstance(last[0], dict):
            return last[0]
        return {"_value": last}
    return last

# 修复相对导入问题
# 当直接运行文件时，需要添加父目录到Python路径
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 确保site-packages中的mcp包优先于本地mcp目录
# 移除本地mcp目录的路径，避免与site-packages中的mcp包冲突
local_mcp_path = os.path.join(parent_dir, 'app', 'mcp')
if local_mcp_path in sys.path:
    sys.path.remove(local_mcp_path)
    print(f"已移除本地mcp路径: {local_mcp_path}")

# 确保site-packages路径在最前面
site_packages_paths = [p for p in sys.path if 'site-packages' in p]
for sp_path in site_packages_paths:
    if sp_path in sys.path:
        sys.path.remove(sp_path)
        sys.path.insert(0, sp_path)

# 检查mcp包是否可用
try:
    import mcp
    
    # 检查mcp.types是否可用
    try:
        import mcp.types
    except ImportError as e:
        # 只在调试模式下输出警告
        if os.getenv('DEBUG_MODE'):
            print(f"Warning: mcp.types import failed: {e}")
        
except ImportError as e:
    # 只在调试模式下输出错误
    if os.getenv('DEBUG_MODE'):
        print(f"Error: mcp import failed: {e}")
    raise

# 使用绝对导入
from app.mcp.mcp_bridge import MCPBridge



class AIAgent:
    """AI对话机器人类 - 支持自然语言交互和MCP工具调用"""
    

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化AI对话机器人
        
        Args:
            config: 配置字典，如果为None则内部自动加载配置
        """
        self.logger = logging.getLogger(__name__)
        
        # 如果未提供配置，则内部自动加载
        if config is None:
            self.config = self._load_config()
        else:
            self.config = config
        
        # AI模型配置
        self.model_config = self._get_model_config()
        
        # MCP桥接器
        self.mcp_bridge = None
        self.available_tools = {}
        self.tool_descriptions = {}
        
        # 对话历史
        self.conversation_history = []
        
        # 工具调用历史
        self.tool_call_history = []
        
        # 对话机器人配置
        self.enable_tool_calls = True  # 是否启用工具调用
        self.max_tool_calls_per_message = 3  # 每条消息最大工具调用次数
        
        # 初始化AI对话机器人
        self._init_ai_agent()
    
    def _load_config(self) -> Dict[str, Any]:
        """内部加载配置文件"""
        try:
            # 导入配置加载器
            from app.config_loader import ConfigLoader
            
            # 加载配置
            config = ConfigLoader.load_config()
            self.logger.info("配置加载成功")
            return config
            
        except Exception as e:
            self.logger.error(f"配置加载失败: {e}")
            # 返回空配置作为兜底
            return {}
    
    def _get_model_config(self) -> Dict[str, Any]:
        """获取模型配置 - 优先使用环境变量配置"""
        models_config = self.config.get('models', {})
        model_default_params = self.config.get('model_default_params', {})
        
        # 从环境变量获取配置，如果环境变量未设置则使用配置中的默认值
        model_name = os.getenv('BFM_MODLE_NAME', os.getenv('MODEL_NAME', 'DeepSeek-V3.1'))
        api_key = os.getenv('BFM_API_KEY', os.getenv('OPENAI_API_KEY', ''))
        base_url = os.getenv('BFM_BASE_URL', os.getenv('OPENAI_BASE_URL', ''))
        
        # 如果配置中有模型配置，优先使用配置中的值
        if models_config:
            # 尝试获取指定模型的配置
            model_config = models_config.get(model_name, {})
            if not model_config:
                # 如果指定模型不存在，使用第一个模型配置
                first_model_name = next(iter(models_config.keys()), model_name)
                model_config = models_config.get(first_model_name, {})
            
            # 使用配置中的值覆盖环境变量
            model_name = model_config.get('model', model_name)
            api_key = model_config.get('api_key', api_key)
            base_url = model_config.get('base_url', base_url)
        
        # 解析环境变量占位符
        api_key = self._resolve_env_vars(api_key)
        base_url = self._resolve_env_vars(base_url)
        
        return {
            'model': model_name,
            'api_key': api_key,
            'base_url': base_url,
            'temperature': model_default_params.get('temperature', 0.2),
            'max_tokens': model_default_params.get('max_tokens', 1500)
        }
    
    def _init_ai_agent(self):
        """初始化AI对话机器人"""
        try:
            # 创建MCP桥接器
            self.mcp_bridge = MCPBridge(config=self.config)
            
            # 获取可用工具
            self.available_tools = self.mcp_bridge.get_func_map()
            
            # 获取工具描述信息
            self._init_tool_descriptions()
            
            # 初始化服务信息映射
            self._init_service_mapping()
            
            # 添加批量工具调用支持
            self._add_batch_tool_support()
            
            # 初始化对话历史
            self._init_conversation_history()
            
            self.logger.info("AI对话机器人初始化成功")
            self.logger.info(f"可用工具数量: {len(self.available_tools)}")
            
            # 打印大模型配置信息到控制台
            model_config = self._get_model_config()
            model_name = model_config.get('model', '未知模型')
            base_url = model_config.get('base_url', '未知地址')
            
            print("=== AI Agent 大模型配置信息 ===")
            print(f"大模型名称: {model_name}")
            print(f"访问地址: {base_url}")
            print("=" * 40)
            
        except Exception as e:
            self.logger.error(f"AI对话机器人初始化失败: {e}")
            raise
    
    def _init_tool_descriptions(self):
        """初始化工具描述信息"""
        try:
            tools_info = self.mcp_bridge.get_tools()
            for tool_info in tools_info:
                func_info = tool_info.get('function', {})
                tool_name = func_info.get('name', '')
                tool_description = func_info.get('description', '')
                tool_parameters = func_info.get('parameters', {})
                
                if tool_name:
                    self.tool_descriptions[tool_name] = {
                        'description': tool_description,
                        'parameters': tool_parameters
                    }
        except Exception as e:
            self.logger.warning(f"获取工具描述信息失败: {e}")
    
    def _init_service_mapping(self):
        """初始化服务信息映射"""
        try:
            # 获取MCP服务信息
            service_info = self.mcp_bridge.get_service_info()
            
            # 创建工具到服务的映射
            self.tool_to_service_map = {}
            
            # 正确解析服务信息结构
            service_name = service_info.get('service', {}).get('name', 'unknown')
            tools = service_info.get('tools', [])
            
            # 建立工具映射
            for tool_name in tools:
                self.tool_to_service_map[tool_name] = service_name
            
            self.logger.info(f"服务信息映射初始化完成，服务: {service_name}, 映射工具数量: {len(self.tool_to_service_map)}")
            
        except Exception as e:
            self.logger.warning(f"初始化服务信息映射失败: {e}")
            self.tool_to_service_map = {}
    
    def _add_batch_tool_support(self):
        """添加批量工具调用支持"""
        try:
            # 定义批量执行工具函数
            def _batch_exec(tool: str, args_list: list, mode: str = "sequential", max_concurrency: int = 4):
                """
                对同一工具进行批量调用：把多组参数一次性提交，按顺序返回结果。
                默认顺序执行；如需并发，可自行扩展。
                """
                if tool not in self.available_tools:
                    return {"ok": False, "error": f"未知工具 '{tool}'"}
                
                fn = self.available_tools[tool]
                results = []
                
                for i, args in enumerate(args_list or []):
                    try:
                        if not isinstance(args, dict):
                            raise ValueError("args_list中的每个参数必须是字典对象")
                        
                        data = fn(**args)
                        results.append({"i": i, "ok": True, "data": data})
                        
                    except Exception as e:
                        results.append({"i": i, "ok": False, "error": str(e)})
                
                return {"ok": True, "results": results}
            
            # 创建批量工具的描述
            batch_tool_schema = {
                "type": "function",
                "function": {
                    "name": "batch_exec",
                    "description": "对同一工具进行批量调用：提供目标工具名 tool 以及参数数组 args_list，一次性执行并按输入顺序返回结果。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tool": {"type": "string", "description": "要批量调用的工具名（必须是已有工具）"},
                            "args_list": {
                                "type": "array",
                                "items": {"type": "object"},
                                "description": "每次调用的一组参数对象，顺序即执行顺序"
                            },
                            "mode": {"type": "string", "enum": ["sequential", "parallel"], "default": "sequential"},
                            "max_concurrency": {"type": "integer", "minimum": 1, "default": 4}
                        },
                        "required": ["tool", "args_list"]
                    }
                }
            }
            
            # 将批量工具添加到可用工具中
            self.available_tools["batch_exec"] = _batch_exec
            
            # 将批量工具添加到服务映射中
            self.tool_to_service_map["batch_exec"] = "local-batch"
            
            # 获取当前工具列表并添加批量工具
            tools_info = self.mcp_bridge.get_tools()
            tools_info.append(batch_tool_schema)
            
            self.logger.info("批量工具调用支持已添加")
            
        except Exception as e:
            self.logger.warning(f"添加批量工具调用支持失败: {e}")
    
    def _init_conversation_history(self):
        """初始化对话历史"""
        # 从配置中加载初始提示词
        main_prompts = self.config.get('main_prompts', {})
        
        # 构建系统提示词
        system_prompt = self._build_system_prompt(main_prompts)
        
        # 添加系统消息到对话历史
        self.conversation_history = [
            {
                "role": "system",
                "content": system_prompt
            }
        ]
        
        # 添加欢迎消息
        welcome_message = """你好！我是你的超级秘书AI助手。我可以帮助你处理各种任务，包括发送邮件、搜索信息、管理项目等。

请告诉我你需要什么帮助？"""
        
        self.conversation_history.append({
            "role": "assistant",
            "content": welcome_message
        })
    
    def _build_system_prompt(self, main_prompts: Any) -> str:
        """构建对话机器人系统提示词"""
        # 直接返回main_prompts中的所有内容
        if isinstance(main_prompts, list):
            # 如果是数组，过滤掉空字符串并合并内容
            filtered_prompts = [str(item) for item in main_prompts if item]
            return "\n".join(filtered_prompts)
        else:
            # 如果是字典，转换为字符串返回
            return str(main_prompts)
    
    def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        处理用户消息 - 支持工具调用和智能对话
        
        Args:
            message: 用户消息
            context: 上下文信息
            
        Returns:
            AI回复
        """
        try:
            # 添加上下文信息
            enriched_message = self._add_context_to_message(message, context)
            
            # 分析用户意图，判断是否需要工具调用
            intent_analysis = self._analyze_user_intent(message)
            
            # 如果需要工具调用，准备工具调用信息
            tool_calls_info = ""
            if intent_analysis.get('needs_tools', False) and self.enable_tool_calls:
                tool_calls_info = self._prepare_tool_calls_info(intent_analysis)
            
            # 构建完整的对话消息
            full_message = self._build_conversation_message(enriched_message, tool_calls_info)
            
            # 添加用户消息到对话历史
            self.conversation_history.append({
                "role": "user",
                "content": full_message,
                "timestamp": time.time(),
                "message_id": f"user_{int(time.time() * 1000)}"
            })
            
            # 类似chat.py的多次工具调用循环逻辑
            
            current_round = 0
            final_response = ""
            MAX_TOOL_ROUNDS = 10  # 最大工具调用轮次
            while current_round < MAX_TOOL_ROUNDS:
                current_round += 1
                
                # 打印当前轮次信息
                print(f"=== 🔄 第 {current_round} 轮 ===", flush=True)
                
                # 尝试调用AI模型，如果失败则使用本地智能回复
                try:
                    # 使用新的标准工具调用流程，获取响应内容、finish_reason和工具调用
                    response_content, finish_reason, tool_calls = self._get_intelligent_response(full_message)
                    
                except Exception as api_error:
                    self.logger.warning(f"AI API调用失败，将使用本地智能回复: {api_error}")
                    response_content, finish_reason, tool_calls = self._get_intelligent_response(full_message)
                
                # 关键修复：检查finish_reason，如果为'stop'则立即退出循环（类似chat.py的逻辑）
                if finish_reason == 'stop':
                    print("—— 最终答复 ——", flush=True)
                    if response_content:
                        print(response_content, flush=True)
                    final_response = response_content
                    break
                
                # 检查是否有工具调用需要处理
                if self._has_pending_tool_calls(response_content):
                    # 如果有待处理的工具调用，继续下一轮
                    full_message = response_content  # 将当前响应作为下一轮的输入
                    continue
                else:
                    # 没有待处理的工具调用，结束循环
                    final_response = response_content
                    break
            
            # 如果达到最大轮次仍未完成，使用最后一次响应
            if not final_response:
                final_response = response_content
                print(f"⚠️ 达到最大工具调用轮次 ({MAX_TOOL_ROUNDS} 轮)，使用最后一次响应", flush=True)
            
            # 添加AI回复到对话历史
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response,
                "timestamp": time.time(),
                "message_id": f"assistant_{int(time.time() * 1000)}"
            })
            
            # 修剪对话历史（防止过长）
            self._trim_conversation_history()
            
            # 记录对话统计
            self._log_conversation_stats()
            
            return final_response
            
        except Exception as e:
            self.logger.error(f"处理消息失败: {e}")
            # 出现其他错误时，也尝试返回本地智能回复
            try:
                fallback_response = self._get_intelligent_response()
                return fallback_response
            except:
                return f"抱歉，处理消息时出现错误: {str(e)}"
    
    def _analyze_user_intent(self, message: str) -> Dict[str, Any]:
        """分析用户意图，判断是否需要工具调用"""
        intent = {
            'needs_tools': False,
            'suggested_tools': [],
            'intent_type': 'conversation'
        }
        
        # 关键词匹配，判断是否需要工具调用
        tool_keywords = [
            '发送邮件', '发邮件', 'email', 'mail',
            '搜索', '查找', 'search', 'find',
            '创建', '新建', 'create', 'make',
            '获取', '查看', 'get', 'check',
            '更新', '修改', 'update', 'modify',
            '删除', 'remove', 'delete'
        ]
        
        message_lower = message.lower()
        
        # 检查是否包含工具相关关键词
        for keyword in tool_keywords:
            if keyword in message_lower:
                intent['needs_tools'] = True
                break
        
        # 根据关键词推荐具体工具
        if '邮件' in message_lower or 'email' in message_lower or 'mail' in message_lower:
            intent['suggested_tools'].extend(['send_email', 'page_email', 'list_available_accounts'])
        
        if '搜索' in message_lower or 'search' in message_lower or '查找' in message_lower:
            intent['suggested_tools'].extend(['web_search'])
        
        if '创建' in message_lower or '新建' in message_lower or 'create' in message_lower:
            intent['suggested_tools'].extend(['mcp_gitee_create_issue', 'mcp_gitee_create_pull'])
        
        return intent
    
    def _prepare_tool_calls_info(self, intent_analysis: Dict[str, Any]) -> str:
        """准备工具调用相关信息"""
        tool_info = """

## 可用工具信息
你可以调用以下工具来帮助完成任务：
"""
        
        # 添加推荐的工具
        suggested_tools = intent_analysis.get('suggested_tools', [])
        if suggested_tools:
            tool_info += "推荐工具：\n"
            for tool_name in suggested_tools:
                if tool_name in self.tool_descriptions:
                    desc = self.tool_descriptions[tool_name].get('description', '无描述')
                    tool_info += f"- {tool_name}: {desc}\n"
        
        # 添加所有可用工具
        tool_info += "\n所有可用工具：\n"
        for tool_name, tool_desc in self.tool_descriptions.items():
            if tool_name not in suggested_tools:
                desc = tool_desc.get('description', '无描述')
                tool_info += f"- {tool_name}: {desc}\n"
        
        tool_info += """

## 工具调用说明
- 如果需要调用工具，请在回复中明确说明要调用的工具名称和参数
- 每条消息最多可以调用{max_tools}个工具
- 工具调用结果会自动展示给用户
""".format(max_tools=self.max_tool_calls_per_message)
        
        return tool_info
    
    def _build_conversation_message(self, message: str, tool_info: str = "") -> str:
        """构建完整的对话消息"""
        # 添加对话历史上下文
        history_context = self._get_conversation_context()
        
        # 构建完整消息
        full_message = f"""{history_context}

## 当前用户消息
{message}
{tool_info}

请根据以上信息，为用户提供有帮助的回复。"""
        
        return full_message
    
    def _get_conversation_context(self) -> str:
        """获取对话历史上下文"""
        if not self.conversation_history:
            return "这是本次对话的开始。"
        
        context = "## 对话历史\n"
        # 获取最近的对话记录（排除系统消息）
        recent_messages = []
        for msg in self.conversation_history[-10:]:  # 最多取最近10条
            if msg["role"] in ["user", "assistant"]:
                recent_messages.append(msg)
        
        # 构建对话历史文本
        for i, msg in enumerate(recent_messages[-5:], 1):  # 显示最近5条
            role = "用户" if msg["role"] == "user" else "AI"
            context += f"第{i}轮:\n"
            context += f"{role}: {msg['content']}\n\n"
        
        return context
    
    def _has_pending_tool_calls(self, response_content: str = None) -> bool:
        """检查是否有待处理的工具调用"""
        # 如果提供了响应内容，检查响应中是否包含工具调用指令
        if response_content:
            tool_calls = self._parse_tool_calls(response_content)
            if tool_calls:
                return True
        
        # 检查对话历史中是否有工具调用结果等待处理
        if not self.conversation_history:
            return False
        
        # 检查最后一条消息是否是工具调用结果
        last_message = self.conversation_history[-1]
        if last_message.get("role") == "tool":
            return True
        
        # 检查是否有未完成的工具调用
        return False
    
    def _handle_tool_calls_in_response(self, response: str) -> str:
        """处理响应中的工具调用"""
        try:
            # 解析响应中的工具调用指令
            tool_calls = self._parse_tool_calls(response)
            
            if not tool_calls:
                return response
            
            # 执行工具调用
            tool_results = []
            for tool_call in tool_calls[:self.max_tool_calls_per_message]:
                # 记录工具调用信息到日志（不打印到控制台）
                tool_name = tool_call['tool_name']
                parameters = tool_call['parameters']
                service_name = self.tool_to_service_map.get(tool_name, "未知服务")
                
                self.logger.info(f"执行工具调用: {tool_name} [{service_name}] with {parameters}")
                
                result = self._execute_tool_call(tool_call)
                tool_results.append(result)
                
                # 记录工具调用历史
                self.tool_call_history.append({
                    'tool_name': tool_call['tool_name'],
                    'parameters': tool_call['parameters'],
                    'result': result,
                    'timestamp': time.time()
                })
            
            # 将工具调用结果整合到响应中
            if tool_results:
                enhanced_response = self._enhance_response_with_tool_results(response, tool_results)
                return enhanced_response
            
            return response
            
        except Exception as e:
            self.logger.error(f"处理工具调用失败: {e}")
            return f"{response}\n\n[工具调用处理失败: {str(e)}]"
    
    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """解析响应中的工具调用指令"""
        tool_calls = []
        
        # 快速检查是否包含工具调用关键词
        if "调用工具" not in response and "{" not in response:
            return tool_calls
        
        # 使用预编译的正则表达式提高性能
        if not hasattr(self, '_tool_pattern1'):
            self._tool_pattern1 = re.compile(r'\[调用工具:\s*([^(]+)\(([^)]+)\)\]')
            self._tool_pattern2 = re.compile(r'(\w+):\s*\{([^}]+)\}')
        
        # 模式1: [调用工具: 工具名(参数1=值1, 参数2=值2)]
        matches1 = self._tool_pattern1.findall(response)
        
        for tool_name, params_str in matches1:
            tool_name = tool_name.strip()
            if tool_name in self.available_tools: 
                parameters = self._parse_parameters(params_str)
                tool_calls.append({
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'type': 'explicit'
                })
        
        # 模式2: 工具名: {参数1: 值1, 参数2: 值2}
        matches2 = self._tool_pattern2.findall(response)
        
        for tool_name, params_str in matches2:
            tool_name = tool_name.strip()
            if tool_name in self.available_tools:
                parameters = self._parse_json_parameters(params_str)
                tool_calls.append({
                    'tool_name': tool_name,
                    'parameters': parameters,
                    'type': 'json'
                })
        
        return tool_calls
    
    def _parse_parameters(self, params_str: str) -> Dict[str, Any]:
        """解析参数字符串"""
        parameters = {}
        
        # 分割参数对
        param_pairs = params_str.split(',')
        
        for pair in param_pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                key = key.strip()
                value = value.strip()
                
                # 处理引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                
                parameters[key] = value
        
        return parameters
    
    def _parse_json_parameters(self, params_str: str) -> Dict[str, Any]:
        """解析JSON格式的参数"""
        try:
            # 尝试解析为JSON
            json_str = '{' + params_str + '}'
            parameters = json.loads(json_str)
            return parameters
        except:
            # 如果JSON解析失败，使用简单解析
            return self._parse_parameters(params_str)
    
    def _execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """执行工具调用 - 优化错误处理和结果压缩"""
        try:
            tool_name = tool_call['tool_name']
            parameters = tool_call['parameters']
            
            # 获取服务信息
            service_name = self.tool_to_service_map.get(tool_name, "未知服务")
            
            # 记录工具调用信息到日志（不打印到控制台）
            self.logger.info(f"执行工具调用: {tool_name} [{service_name}] with {parameters}")
            
            # 调用工具
            result = self.call_tool(tool_name, **parameters)
            
            # 压缩工具结果
            compressed_result = self._compress_tool_result(result)
            
            return {
                'tool_name': tool_name,
                'service_name': service_name,
                'success': True,
                'result': compressed_result,
                'original_result': result,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"工具执行异常: {e}"
            
            # 提供更友好的错误提示
            if "参数" in str(e) or "argument" in str(e).lower():
                error_msg += "\n💡 **提示**: 请检查参数格式是否正确，或尝试使用不同的参数"
            elif "连接" in str(e) or "connection" in str(e).lower():
                error_msg += "\n🔌 **提示**: 请检查网络连接或服务是否正常运行"
            elif "权限" in str(e) or "permission" in str(e).lower():
                error_msg += "\n🔐 **提示**: 请检查是否有足够的权限执行此操作"
            else:
                error_msg += "\n🔄 **提示**: 请稍后重试或联系技术支持"
            
            # 记录错误信息到日志（不打印到控制台）
            self.logger.error(f"工具调用失败: {tool_call['tool_name']} - {e}")
            
            return {
                'tool_name': tool_call['tool_name'],
                'service_name': self.tool_to_service_map.get(tool_call['tool_name'], "未知服务"),
                'success': False,
                'result': None,
                'error': error_msg
            }
    
    def _compress_tool_result(self, result: Any) -> Any:
        """压缩工具执行结果 - 避免返回过长的内容"""
        if result is None:
            return None
            
        # 如果是字符串，进行压缩
        if isinstance(result, str):
            return _squeeze_text(result)
            
        # 如果是字典或列表，转换为JSON并压缩
        if isinstance(result, (dict, list)):
            try:
                json_str = json.dumps(result, ensure_ascii=False, default=self._json_default)
                if self._is_json_like(json_str):
                    return self._minify_json_str(json_str)
                else:
                    return _squeeze_text(json_str)
            except:
                return str(result)[:500]  # 截断过长的内容
                
        # 其他类型直接转换为字符串并压缩
        result_str = str(result)
        if len(result_str) > 500:
            return result_str[:500] + "..."
            
        return result_str
    
    def _handle_standard_tool_calls(self, message) -> str:
        """处理标准OpenAI工具调用格式 - 优化交互流程"""
        try:
            if not hasattr(message, 'tool_calls') or not message.tool_calls:
                return message.content if hasattr(message, 'content') else str(message)
            
            # 处理每个工具调用
            tool_results = []
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments or "{}")
                
                # 获取服务信息
                service_name = self.tool_to_service_map.get(tool_name, "未知服务")
                
                # 记录工具调用信息到日志（不打印到控制台）
                self.logger.info(f"执行标准工具调用: {tool_name} [{service_name}] with {tool_args}")
                
                # 执行工具调用
                try:
                    result = self.call_tool(tool_name, **tool_args)
                    
                    # 压缩工具结果
                    compressed_result = self._compress_tool_result(result)
                    
                    # 将工具执行结果添加到对话历史
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": json.dumps(compressed_result, ensure_ascii=False)
                    })
                    
                    tool_results.append({
                        'tool_name': tool_name,
                        'service_name': service_name,
                        'success': True,
                        'result': compressed_result,
                        'original_result': result,
                        'error': None
                    })
                    
                except Exception as e:
                    error_msg = f"工具执行异常: {e}"
                    
                    # 提供更友好的错误提示
                    if "参数" in str(e) or "argument" in str(e).lower():
                        error_msg += "\n💡 **提示**: 请检查参数格式是否正确，或尝试使用不同的参数"
                    elif "连接" in str(e) or "connection" in str(e).lower():
                        error_msg += "\n🔌 **提示**: 请检查网络连接或服务是否正常运行"
                    elif "权限" in str(e) or "permission" in str(e).lower():
                        error_msg += "\n🔐 **提示**: 请检查是否有足够的权限执行此操作"
                    else:
                        error_msg += "\n🔄 **提示**: 请稍后重试或联系技术支持"
                    
                    self.logger.error(f"工具调用失败: {tool_name} - {e}")
                    
                    # 添加错误信息到对话历史
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_name,
                        "content": f"Error: {error_msg}"
                    })
                    
                    tool_results.append({
                        'tool_name': tool_name,
                        'service_name': service_name,
                        'success': False,
                        'result': None,
                        'error': error_msg
                    })
            
            # 重新调用AI模型处理工具执行结果
            ai_response = self._call_ai_model()
            
            # 检查是否需要用户确认或继续操作
            if tool_results and hasattr(ai_response, 'choices') and len(ai_response.choices) > 0:
                final_message = ai_response.choices[0].message
                response_content = final_message.content if hasattr(final_message, 'content') else str(final_message)
                
                # 检查是否需要进一步工具调用
                has_further_tool_calls = hasattr(final_message, 'tool_calls') and final_message.tool_calls
                
                # 添加工具调用结果摘要
                if tool_results:
                    response_content = self._enhance_response_with_tool_results(response_content, tool_results)
                
                # 添加明确的继续操作提示
                if not has_further_tool_calls:
                    # 根据工具调用结果提供不同的提示
                    successful_tools = [r for r in tool_results if r['success']]
                    failed_tools = [r for r in tool_results if not r['success']]
                    
                    if successful_tools and not failed_tools:
                        response_content += "\n\n🎉 **任务完成！** 所有工具调用成功执行。"
                    elif failed_tools:
                        response_content += "\n\n⚠️ **部分操作失败**，请检查错误信息并告诉我如何继续。"
                    else:
                        response_content += "\n\n💡 **提示**: 如果您需要继续操作或查看详细信息，请告诉我下一步的需求。"
                else:
                    response_content += "\n\n🔄 **系统**: 正在继续处理后续工具调用..."
                
                return response_content
            
            return ai_response
            
        except Exception as e:
            self.logger.error(f"处理标准工具调用失败: {e}")
            return f"抱歉，处理工具调用时出现错误: {str(e)}"
    
    def _enhance_response_with_tool_results(self, original_response: str, tool_results: List[Dict[str, Any]]) -> str:
        """将工具调用结果整合到响应中 - 优化结果展示"""
        # 确保original_response不是None
        enhanced_response = original_response if original_response is not None else ""
        
        # 添加工具调用结果摘要
        if tool_results:
            # 统计成功和失败的工具调用
            successful_tools = [r for r in tool_results if r['success']]
            failed_tools = [r for r in tool_results if not r['success']]
            
            result_summary = "\n\n--- 🔧 工具调用结果摘要 ---\n"
            
            if successful_tools:
                result_summary += f"✅ **成功执行 {len(successful_tools)} 个工具**:\n"
                for tool in successful_tools:
                    # 显示服务信息
                    service_info = f" [{tool.get('service_name', '未知服务')}]"
                    result_summary += f"   • **{tool['tool_name']}**{service_info}\n"
                    
                    # 显示简要结果（如果结果不是太大）
                    if tool.get('result'):
                        result_data = tool['result']
                        if isinstance(result_data, (dict, list)):
                            result_str = str(result_data)
                            if len(result_str) < 100:
                                result_summary += f"     结果: {result_str}\n"
                        elif isinstance(result_data, str):
                            if len(result_data) < 50:
                                result_summary += f"     结果: {result_data}\n"
            
            if failed_tools:
                result_summary += f"\n❌ **失败 {len(failed_tools)} 个工具**:\n"
                for tool in failed_tools:
                    service_info = f" [{tool.get('service_name', '未知服务')}]"
                    result_summary += f"   • **{tool['tool_name']}**{service_info}: {tool['error']}\n"
            
            # 添加总体统计
            total_tools = len(tool_results)
            success_rate = len(successful_tools) / total_tools * 100 if total_tools > 0 else 0
            
            result_summary += f"\n📊 **总体统计**: {len(successful_tools)}/{total_tools} 成功 ({success_rate:.1f}%)"
            
            # 根据成功率添加不同的提示
            if success_rate == 100:
                result_summary += " 🎉 所有工具调用成功！"
            elif success_rate >= 80:
                result_summary += " 👍 大部分工具调用成功"
            elif success_rate >= 50:
                result_summary += " ⚠️ 部分工具调用失败，请检查参数"
            else:
                result_summary += " ❗ 多数工具调用失败，可能需要调整策略"
            
            enhanced_response += result_summary
        
        return enhanced_response
    
    def _add_context_to_message(self, message: str, context: Optional[Dict[str, Any]]) -> str:
        """添加上下文信息到消息中"""
        if not context:
            return message
        
        context_parts = []
        
        # 添加时间信息
        if 'current_time' in context:
            context_parts.append(f"当前时间: {context['current_time']}")
        
        # 添加邮件信息
        if 'email_info' in context:
            email_info = context['email_info']
            context_parts.append(f"邮件主题: {email_info.get('subject', '无主题')}")
            context_parts.append(f"发件人: {email_info.get('from', '未知发件人')}")
        
        # 构建完整消息
        if context_parts:
            context_str = "\n".join(context_parts)
            return f"{context_str}\n\n{message}"
        
        return message
    
    def _call_ai_model(self):
        """调用AI模型 - 使用动态配置和标准工具调用模式"""
        try:
            import openai
            
            # 获取动态模型配置
            model_config = self._get_model_config()
            
            # 检查API密钥是否有效
            if not model_config.get('api_key'):
                self.logger.warning("API密钥未配置，使用本地智能回复")
                return "抱歉，API密钥未配置，无法调用AI服务。"
            
            # 配置OpenAI客户端
            client = openai.OpenAI(
                api_key=model_config['api_key'],
                base_url=model_config['base_url'],
                timeout=30.0,  # 添加超时设置
                max_retries=2   # 添加重试机制
            )
            
            # ✅ 关键修复：清理消息格式，只保留OpenAI API需要的字段
            cleaned_messages = []
            for msg in self.conversation_history:
                cleaned_msg = {
                    'role': msg['role'],
                    'content': msg['content']
                }
                cleaned_messages.append(cleaned_msg)
            
            # 准备请求参数
            params = {
                'model': model_config['model'],
                'messages': cleaned_messages,
                'temperature': model_config.get('temperature', 0.2),
                'max_tokens': model_config.get('max_tokens', 1500),
                'stream': False  # 禁用流式响应以提高性能
            }
            
            # ✅ 关键修复：添加工具参数（标准OpenAI工具调用模式）
            if self.enable_tool_calls and self.mcp_bridge:
                tools = self.mcp_bridge.get_tools()
                if tools:
                    params['tools'] = tools
                    params['tool_choice'] = 'auto'  # 允许AI自动选择工具
            
            # 调用API
            response = client.chat.completions.create(**params)
            
            return response
                
        except ImportError:
            self.logger.warning("OpenAI库未安装")
            raise Exception("OpenAI库未安装，无法调用AI服务")
        except openai.APITimeoutError:
            self.logger.warning("AI API调用超时")
            raise Exception("AI服务响应超时，请稍后重试")
        except openai.RateLimitError:
            self.logger.warning("AI API调用频率限制")
            raise Exception("AI服务暂时繁忙，请稍后重试")
        except openai.APIError as e:
            self.logger.error(f"AI API调用错误: {e}")
            raise Exception(f"AI服务暂时不可用: {str(e)}")
        except Exception as e:
            self.logger.error(f"调用AI模型失败: {e}")
            raise Exception(f"调用AI服务时出现错误: {str(e)}")
    
    def _resolve_env_vars(self, value: str) -> str:
        """解析环境变量占位符 - 支持多种格式"""
        import os
        import re
        
        if not value:
            return value
        
        # 处理 ${VAR_NAME} 格式的环境变量
        if value.startswith('${') and value.endswith('}'):
            var_name = value[2:-1]
            env_value = os.getenv(var_name, '')
            if env_value:
                return env_value
            # 如果环境变量未设置，返回原始值
            return value
        
        # 处理 $VAR_NAME 格式的环境变量
        elif value.startswith('$') and len(value) > 1:
            var_name = value[1:]
            env_value = os.getenv(var_name, '')
            if env_value:
                return env_value
            # 如果环境变量未设置，返回原始值
            return value
        
        # 处理包含环境变量的字符串（如 "prefix_${VAR_NAME}_suffix"）
        if '${' in value and '}' in value:
            # 使用正则表达式匹配所有 ${VAR_NAME} 格式的占位符
            pattern = r'\$\{([^}]+)\}'
            matches = re.findall(pattern, value)
            
            for var_name in matches:
                env_value = os.getenv(var_name, '')
                if env_value:
                    value = value.replace(f'${{{var_name}}}', env_value)
                else:
                    # 如果环境变量未设置，保留占位符
                    value = value.replace(f'${{{var_name}}}', var_name)
        
        # 处理包含 $VAR_NAME 格式的字符串
        if '$' in value and len(value) > 1:
            # 使用正则表达式匹配所有 $VAR_NAME 格式的占位符
            pattern = r'\$([A-Za-z_][A-Za-z0-9_]*)'
            matches = re.findall(pattern, value)
            
            for var_name in matches:
                env_value = os.getenv(var_name, '')
                if env_value:
                    value = value.replace(f'${var_name}', env_value)
                else:
                    # 如果环境变量未设置，保留占位符
                    value = value.replace(f'${var_name}', var_name)
        
        return value
    
    def _get_intelligent_response(self, user_message: str) -> tuple:
        """获取智能响应，使用标准OpenAI工具调用流程
        
        Returns:
            tuple: (response_content, finish_reason, tool_calls)
        """
        try:
            # 使用标准工具调用流程
            response = self._call_ai_model()
            
            # 检查是否有工具调用
            if hasattr(response, 'choices') and len(response.choices) > 0:
                message = response.choices[0].message
                finish_reason = response.choices[0].finish_reason if hasattr(response.choices[0], 'finish_reason') else None
                
                # 如果有工具调用，处理工具调用
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_calls = message.tool_calls
                    response_content = self._handle_standard_tool_calls(message)
                    return response_content, finish_reason, tool_calls
                else:
                    # 没有工具调用，直接返回内容
                    response_content = message.content if hasattr(message, 'content') else str(message)
                    return response_content, finish_reason, None
            else:
                return "抱歉，未能获取到有效的响应", None, None
                
        except Exception as e:
            self.logger.error(f"获取智能响应失败: {e}")
            return f"抱歉，处理您的请求时出现错误: {str(e)}", None, None
    

    
    def _log_conversation_stats(self):
        """记录对话统计信息"""
        user_messages = [msg for msg in self.conversation_history if msg["role"] == "user"]
        ai_messages = [msg for msg in self.conversation_history if msg["role"] == "assistant"]
        
        self.logger.info(f"对话统计 - 用户消息: {len(user_messages)}, AI回复: {len(ai_messages)}")
        
        # 记录工具调用统计
        if self.tool_call_history:
            self.logger.info(f"工具调用统计 - 总调用次数: {len(self.tool_call_history)}")
            
            # 按工具类型统计
            tool_stats = {}
            for call in self.tool_call_history:
                tool_name = call['tool_name']
                tool_stats[tool_name] = tool_stats.get(tool_name, 0) + 1
            
            for tool_name, count in tool_stats.items():
                self.logger.info(f"  {tool_name}: {count}次")
    
    def _ensure_email_html_format(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """
        确保邮件内容符合HTML格式要求
        
        Args:
            kwargs: 邮件发送参数
            
        Returns:
            处理后的邮件参数
        """
        if 'body' not in kwargs:
            return kwargs
        
        body = kwargs['body']
        
        # 检查内容是否已经是HTML格式
        if self._is_html_content(body):
            return kwargs
        
        # 将纯文本转换为HTML格式
        html_body = self._convert_text_to_html(body)
        kwargs['body'] = html_body
        
        self.logger.info("已将纯文本邮件内容转换为HTML格式")
        return kwargs
    
    @staticmethod
    def _is_html_content(content: str) -> bool:
        """
        检测内容是否为HTML格式
        
        Args:
            content: 要检测的内容
            
        Returns:
            如果是HTML格式返回True，否则返回False
        """
        if not content:
            return False
        
        # HTML标签检测模式
        html_patterns = [
            r'<[a-z][\\s\\S]*?>',  # 基本HTML标签
            r'<\\/?[a-z]+\\s*[^>]*>',  # 带属性的HTML标签
            r'<\\!DOCTYPE\\s+html>',  # HTML文档类型声明
            r'<html[\\s>]',  # html标签
            r'<head[\\s>]',  # head标签
            r'<body[\\s>]',  # body标签
            r'<div[\\s>]',  # div标签
            r'<p[\\s>]',  # p标签
            r'<br\\s*\\/?>',  # br标签
            r'<img[\\s>]',  # img标签
            r'<a[\\s>]',  # a标签
            r'<span[\\s>]',  # span标签
            r'<table[\\s>]',  # table标签
            r'<tr[\\s>]',  # tr标签
            r'<td[\\s>]',  # td标签
            r'<ul[\\s>]',  # ul标签
            r'<ol[\\s>]',  # ol标签
            r'<li[\\s>]',  # li标签
        ]
        
        # 检查是否包含常见的HTML标签
        for pattern in html_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        
        # 检查是否包含HTML实体
        html_entities = [
            '&nbsp;', '&lt;', '&gt;', '&amp;', '&quot;', '&apos;',
            '&copy;', '&reg;', '&trade;', '&euro;', '&pound;', '&yen;', '&cent;'
        ]
        
        for entity in html_entities:
            if entity in content:
                return True
        
        return False
    
    def _convert_text_to_html(self, text: str) -> str:
        """
        将纯文本转换为HTML格式
        
        Args:
            text: 纯文本内容
            
        Returns:
            HTML格式的内容
        """
        # 基本HTML模板
        html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>邮件内容</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }
        .email-content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .email-header {
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .email-body {
            font-size: 16px;
        }
        .email-footer {
            margin-top: 30px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            font-size: 14px;
            color: #666;
        }
        p {
            margin-bottom: 15px;
        }
        .signature {
            font-style: italic;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="email-content">
        <div class="email-body">
            {content}
        </div>
        <div class="email-footer">
            <p class="signature">此邮件由AI超级秘书自动生成</p>
        </div>
    </div>
</body>
</html>"""
        
        # 处理文本内容
        # 1. 将换行符转换为段落
        paragraphs = text.strip().split('\\n\\n')
        html_paragraphs = []
        
        for paragraph in paragraphs:
            if paragraph.strip():
                # 将单行换行转换为<br>
                paragraph = paragraph.replace('\\n', '<br>')
                html_paragraphs.append(f'<p>{paragraph}</p>')
        
        # 2. 如果没有段落，则直接包装
        if not html_paragraphs:
            content = f'<p>{text.replace("\\n", "<br>")}</p>'
        else:
            content = '\\n'.join(html_paragraphs)
        
        # 3. 插入到HTML模板中
        return html_template.replace('{content}', content)
    
    def _trim_conversation_history(self, max_tokens: int = 4000):
        """智能修剪对话历史"""
        if len(self.conversation_history) <= 10:
            return
            
        # 计算当前对话历史的近似token数
        total_chars = sum(len(msg["content"]) for msg in self.conversation_history)
        approx_tokens = total_chars // 4  # 粗略估算：1个token约等于4个字符
        
        # 如果token数超过限制，进行修剪
        if approx_tokens > max_tokens:
            self.logger.info(f"对话历史过长 ({approx_tokens} tokens)，开始修剪")
            
            # 保留系统消息
            system_message = self.conversation_history[0]
            
            # 智能保留策略：保留最近的对话和重要的工具调用结果
            important_messages = []
            recent_messages = []
            
            # 从后往前遍历，保留最近的对话
            for msg in reversed(self.conversation_history[1:]):  # 跳过系统消息
                if len(recent_messages) < 8:  # 保留最近的8条消息
                    recent_messages.insert(0, msg)
                elif "工具调用结果" in msg.get("content", ""):
                    # 保留重要的工具调用结果
                    important_messages.insert(0, msg)
                
                # 检查是否达到token限制
                current_chars = sum(len(m["content"]) for m in [system_message] + important_messages + recent_messages)
                if current_chars // 4 <= max_tokens * 0.8:  # 保留20%的缓冲空间
                    break
            
            # 构建新的对话历史
            self.conversation_history = [system_message] + important_messages + recent_messages
            self.logger.info(f"对话历史修剪完成，保留 {len(self.conversation_history)} 条消息")
        else:
            # 简单的实现：保留最近的10条消息
            system_message = self.conversation_history[0]
            recent_messages = self.conversation_history[-9:]
            self.conversation_history = [system_message] + recent_messages
    
    def get_available_tools(self) -> Dict[str, Any]:
        """获取可用工具列表"""
        return self.available_tools.copy()
    
    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数
            
        Returns:
            工具执行结果
        """
        try:
            if tool_name not in self.available_tools:
                raise ValueError(f"工具 '{tool_name}' 不存在")
            
            # 特殊处理邮件发送工具，确保HTML格式
            if tool_name == "send_email":
                kwargs = self._ensure_email_html_format(kwargs)
            
            tool_func = self.available_tools[tool_name]
            result = tool_func(**kwargs)
            
            self.logger.info(f"工具调用成功: {tool_name}")
            return result
            
        except Exception as e:
            self.logger.error(f"工具调用失败: {tool_name}, 错误: {e}")
            raise
    
    def reset_conversation(self):
        """重置对话历史"""
        self._init_conversation_history()
        self.logger.info("对话历史已重置")
    
    def stop(self):
        """停止AI代理"""
        if self.mcp_bridge:
            try:
                self.mcp_bridge.stop()
                self.logger.info("AI代理已停止")
            except Exception as e:
                self.logger.error(f"停止AI代理时发生错误: {e}")


if __name__ == "__main__":
    # 循环对话功能
    import json
    
    # 加载测试配置
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    ai_agent = AIAgent(config)
    print("AI代理初始化测试成功")
    print("=== AI超级秘书对话系统 ===")
    print("输入 '退出' 或 'quit' 结束对话")
    print("-" * 50)
    
    # 循环对话
    while True:
        try:
            # 获取用户输入
            user_input = input("\n你: ").strip()
            
            # 检查退出条件
            if user_input.lower() in ['退出', 'quit', 'exit', 'bye']:
                print("AI: 再见！感谢使用超级秘书服务。")
                break
            
            # 处理空输入
            if not user_input:
                print("AI: 请输入您的问题或需求。")
                continue
            
            # 处理用户消息
            response = ai_agent.process_message(user_input)
            print(f"AI: {response}")
            
        except KeyboardInterrupt:
            print("\n\nAI: 检测到中断信号，正在退出...")
            break
        except Exception as e:
            print(f"AI: 处理消息时出现错误: {e}")
            continue
    
    ai_agent.stop()