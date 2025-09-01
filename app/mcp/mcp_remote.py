# tools/mcp_remote.py
# -*- coding: utf-8 -*-
import asyncio
import atexit
import re
import json
from threading import Thread
from typing import Dict, List, Any
from fastmcp import Client as FastMCPClient
from fastmcp.exceptions import ToolError


class MCPBridge:
    """
    MCP桥接器类，用于与MCP(Model Context Protocol)服务器进行通信
    封装了异步MCP客户端，提供同步接口以便在普通Python代码中使用
    """
    
    def __init__(
        self,
        command: str = None,
        args: List[str] = None,
        cwd: str = None,
        config: Dict[str, Any] = None,
        timeout: float = 30.0,
    ):
        """
        初始化MCP桥接器
        
        Args:
            command: 启动MCP服务器的命令
            args: 命令行参数列表
            cwd: 工作目录
            config: MCP服务器配置
            timeout: 操作超时时间（秒）
        """
        if config:
            # 如果提供了配置，则使用配置中的MCP服务器信息
            self._source = {"mcpServers": config["mcpServers"]} if "mcpServers" in config else config
        elif command:
            # 如果提供了命令，则构建本地MCP服务器配置
            self._source = {
                "mcpServers": {
                    "local": {
                        "transport": "stdio",  # 使用标准输入输出传输
                        "command": command,    # 启动命令
                        "args": args or [],    # 命令行参数
                        "cwd": cwd or None,    # 工作目录
                    }
                }
            }
        else:
            # 如果既没有提供配置也没有提供命令，则抛出错误
            raise ValueError("需提供 config 或 command/args/cwd")

        self._timeout = timeout  # 设置超时时间
        self._loop = asyncio.new_event_loop()  # 创建新的异步事件循环
        # 创建并启动守护线程来运行事件循环
        self._thread = Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

        # 创建MCP客户端并连接到服务器
        self._client = FastMCPClient(self._source)
        asyncio.run_coroutine_threadsafe(self._client.__aenter__(), self._loop).result(timeout=self._timeout)

        self._stopped = False  # 幂等关停标记，防止重复停止
        atexit.register(self.stop)  # 注册程序退出时的清理函数

    def _run(self, coro):
        """
        在事件循环中运行协程并获取结果
        
        Args:
            coro: 要运行的协程
            
        Returns:
            协程的执行结果
        """
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout=self._timeout)

    def get_tools(self) -> List[dict]:
        """
        获取MCP服务器上所有可用工具的信息
        
        Returns:
            工具信息列表，每个工具信息包括名称、描述和参数
        """
        tools = self._run(self._client.list_tools())  # 获取工具列表
        out = []
        for t in tools:
            # 获取工具的输入参数模式，如果没有则使用默认值
            params = getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}
            out.append({
                "type": "function",
                "function": {
                    "name": t.name,                      # 工具名称
                    "description": (t.description or "")[:1024],  # 工具描述（限制长度）
                    "parameters": params,                # 工具参数
                }
            })
        return out

    def get_service_info(self) -> dict:
        """
        获取MCP服务的详细信息
        
        Returns:
            包含服务名称和工具信息的字典
        """
        tools = self._run(self._client.list_tools())
        tool_names = [t.name for t in tools]
        
        # 获取服务配置信息
        service_config = {}
        if hasattr(self, '_source') and 'mcpServers' in self._source:
            # 如果是通过配置启动的，获取第一个服务的信息
            for service_name, config in self._source['mcpServers'].items():
                service_config = {
                    'name': service_name,
                    'working_directory': config.get('cwd', config.get('workingDirectory', '')),
                    'command': config.get('command', ''),
                    'args': config.get('args', [])
                }
                break
        else:
            # 如果是通过命令行参数启动的
            service_config = {
                'name': 'local',
                'working_directory': getattr(self, '_source', {}).get('mcpServers', {}).get('local', {}).get('cwd', ''),
                'command': getattr(self, '_source', {}).get('mcpServers', {}).get('local', {}).get('command', ''),
                'args': getattr(self, '_source', {}).get('mcpServers', {}).get('local', {}).get('args', [])
            }
        
        return {
            'service': service_config,
            'tools': tool_names
        }

    def get_func_map(self):
        """
        获取工具名称到调用函数的映射
        
        Returns:
            字典，键为工具名称，值为对应的调用函数
        """
        tools = self._run(self._client.list_tools())  # 获取工具列表
        # 为每个工具创建调用函数并返回映射
        return {t.name: self._make_caller(t.name) for t in tools}

    def _make_caller(self, tool_name: str):
        """
        创建指定工具的调用函数
        
        Args:
            tool_name: 工具名称
            
        Returns:
            可调用的函数，用于执行该工具
        """
        def _call(**kwargs):
            """
            调用指定工具的内部函数
            
            Args:
                **kwargs: 传递给工具的参数
                
            Returns:
                工具执行结果
            """
            try:
                # 尝试调用工具
                res = self._run(self._client.call_tool(tool_name, kwargs))
            except ToolError as e:
                # 兼容服务端 schema 校验失败但实际有内容返回（如 State-Tool 返回 list[str]）
                msg = str(e)
                m = re.search(r'(\[.*\])', msg, re.S)
                if m:
                    try:
                        arr = json.loads(m.group(1))
                        text_parts = [x for x in arr if isinstance(x, str)]
                        if text_parts:
                            return "\n".join(text_parts)
                    except Exception:
                        pass
                return msg  # 最后兜底：返回报错文本，避免对话中断

            # 正常返回路径
            if getattr(res, "data", None) is not None:
                # 如果结果有data属性，则返回data
                return res.data
            # 遍历结果的内容列表，返回第一个有文本内容的部分
            for c in getattr(res, "content", []) or []:
                if hasattr(c, "text") and c.text:
                    return c.text
            return None  # 如果没有找到有效内容，则返回None
        return _call

    def stop(self):
        """
        停止MCP桥接器，释放资源
        这是一个幂等操作，可以安全地多次调用
        """
        # 幂等检查，如果已经停止则直接返回
        if getattr(self, "_stopped", False):
            return
        self._stopped = True  # 设置停止标记

        try:
            # 如果事件循环正在运行且未关闭，则尝试正常退出客户端
            if self._loop and self._loop.is_running() and not self._loop.is_closed():
                try:
                    fut = asyncio.run_coroutine_threadsafe(
                        self._client.__aexit__(None, None, None), self._loop
                    )
                    # 退出时限小一点，避免阻塞进程
                    fut.result(timeout=1.0)
                except Exception:
                    pass
        finally:
            # 尝试停止事件循环
            try:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
            # 尝试等待线程结束
            try:
                if self._thread and self._thread.is_alive():
                    self._thread.join(timeout=1.0)
            except Exception:
                pass


if __name__ == "__main__":
    import json, traceback


    CONFIG = {
        "mcpServers": {
            "nx-mcp": {
                "transport": "stdio",
                "command": r".conda/ocr311/python.exe",
                "args": [r"mcp_server/nx_mcp/main_nx_mcp.py"],
                "cwd":  r".",
                "disabled": False
            }
        }
    }

    try:
        bridge = MCPBridge(config=CONFIG, timeout=60.0)
        print("已连接 nx-mcp")

        tools = bridge.get_tools()
        names = [t["function"]["name"] for t in tools]
        print("工具清单：", names)

        func_map = bridge.get_func_map()

        # --- 手动调用 create_new_part ---

        cam_env_path  = r"E:\Workspace\MySolution\NXCopilotPrototype\test\_model6_setup_1.prt"
        master_name   = "_model6"
        r = func_map["switch_to_manufacturing"](args={})
        print(json.dumps(r, ensure_ascii=False, indent=2))

    except Exception as e:
        print("自测异常：", e)
        traceback.print_exc()
    finally:
        try:
            bridge.stop()
        except Exception:
            pass
