import os
import json
from openai import OpenAI
import importlib
import pkgutil
import inspect
from types import ModuleType
from typing import List, Tuple, Iterator
import atexit
import tiktoken
from app.mcp.mcp_remote import MCPBridge
import re
import dataclasses
from enum import Enum
import os, json
from pathlib import Path
from dotenv import load_dotenv

# ========== 配置 ==========
MAX_TOOL_ROUNDS = 1000

# 根据 deepseek-reasoner API 文档调整最大上下文长度（仅用于提示，不做自动修剪）
MAX_CONTEXT_LENGTH = 65536  # 64K tokens
TOKEN_BUFFER = 2048
ENCODER_NAME = "cl100k_base"

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

# ========== 轻量压缩（不改变语义，不截断） ==========
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

BASE_DIR = Path(__file__).resolve().parents[1]  # 项目根目录 SuperSecretary/
CONFIG_PATH = Path(os.getenv("CONFIG_PATH", BASE_DIR / "config.json"))


class Client:
    def __init__(self):
        # 加载.env文件的环境变量
        load_dotenv()
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as file:
            self.config = json.load(file)

        # 保存远程 MCP 桥接实例，保证全局只启一次
        self._mcp_bridges = []
        self.tools, self.funcDict = self.get_mcp_tools()
        # 初始化编码器
        self.encoder = tiktoken.get_encoding(ENCODER_NAME)

        # 退出时清理
        atexit.register(self._shutdown_mcp)

    # ========== JSON 解析工具 ==========
    def _iter_json_objects(self, s: str):
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

    def safe_json_loads(self, s: str):
        """返回最后一个合法 JSON（通常是模型最终覆写的参数）。"""
        last = None
        for obj in self._iter_json_objects(s):
            last = obj
        if last is None:
            return {}
        if not isinstance(last, dict):
            if isinstance(last, list) and last and isinstance(last[0], dict):
                return last[0]
            return {"_value": last}
        return last

    # ========== 模型与消息 ==========
    def set_model(self, model):
        self.model = model
        # 处理环境变量替换
        api_key = os.getenv("OPENAI_API_KEY", "") if "${OPENAI_API_KEY}" in self.model["key"] else self.model["key"]
        base_url = os.getenv("OPENAI_BASE_URL", "") if "${OPENAI_BASE_URL}" in self.model["url"] else self.model["url"]
        print("==DEBUG== model.name:", self.model.get("name"), "url:", base_url)
        
        self.instance = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        print("设置模型：" + self.model["name"])
        self.rest_message()

    def rest_message(self):
        self.messages = [{"role": "system", "content": '\n'.join(self.config["main_prompts"])}]
        print("消息已经重置")

    def _count_tokens(self, messages):
        """计算消息列表的token数量（仅用于提示，不做自动修剪）"""
        total_tokens = 0
        for message in messages:
            for key, value in message.items():
                if isinstance(value, str):
                    total_tokens += len(self.encoder.encode(value))
                elif isinstance(value, dict):
                    total_tokens += len(self.encoder.encode(json.dumps(value, ensure_ascii=False)))
                elif isinstance(value, list):
                    total_tokens += len(self.encoder.encode(json.dumps(value, ensure_ascii=False)))
        return total_tokens

    def _trim_context(self):
        """禁用上下文修剪：不做任何事，确保发给模型的消息完全保留。"""
        return

    def send(self, user_input, step_msg_func=None):
        clean_input = _squeeze_text(user_input)
        self.messages.append({"role": "user", "content": clean_input})

        step_msg = ""
        step_count = 0

        def step_msg_handler(msg):
            nonlocal step_msg
            if step_msg_func:
                step_msg_func(step_msg)
            step_msg += msg
            if step_msg_func:
                step_msg_func(step_msg)

        # 最大工具调用轮次限制，避免无限循环
        round_idx = 1
        while round_idx <= MAX_TOOL_ROUNDS:
            print(f"\n=== 🔄 第 {round_idx} 轮 ===", flush=True)
            print("—— 思考 / 回答流 ——", flush=True)

            # 不再自动修剪上下文
            self._trim_context()

            # 额外提示：若明显超限，提前打印提醒（不自动删减）
            current_tokens = self._count_tokens(self.messages)
            max_tokens = MAX_CONTEXT_LENGTH - TOKEN_BUFFER
            if current_tokens > max_tokens:
                print(f"⚠️ 预计上下文 {current_tokens} tokens 已超过模型建议上限 {max_tokens}，"
                      f"如出现API报错请手动减少历史或清空对话。", flush=True)

            try:
                resp = self.instance.chat.completions.create(
                    model=self.model["name"],
                    messages=self.messages,
                    tools=self.tools,
                    **self.config["model_default_params"]
                ).choices[0]
            except Exception as e:
                # 禁止自动裁剪，直接抛出带指引的错误
                if "maximum context length" in str(e).lower() or "context_length" in str(e).lower():
                    raise RuntimeError(
                        "上下文超过模型最大限制。为保证消息完整性，已禁用自动修剪。\n"
                        "请清空历史或减少输入后重试。"
                    ) from e
                else:
                    raise

            resp_message = resp.message.to_dict()
            self.messages.append(resp_message)
            if resp.finish_reason == 'stop':
                print("—— 最终答复 ——", flush=True)
                if resp_message.get("content"):
                    print(resp_message["content"], flush=True)
                resp_message["cards"] = [{"title": "🔍 详细分析", "content": step_msg, "expanded": False}]
                if step_msg_func:
                    step_msg_func(step_msg)
                return resp_message

            step_count += 1
            step_msg_handler("第 %d 步\n\n" % step_count)
            if resp_message.get("content"):
                step_msg_handler("内容：%s\n\n" % resp_message["content"])
                print(resp_message["content"], end="", flush=True)

            if resp.message.tool_calls:
                print("\n—— 工具调用 ——", flush=True)
                for call in resp.message.tool_calls:
                    raw_args = call.function.arguments
                    args = self.safe_json_loads(raw_args)
                    func_name = call.function.name

                    step_msg_handler(
                        "函数执行准备, 函数名:%s, 参数:%s\n\n" % (call.function.name, call.function.arguments))
                    service_name = self._tool_to_service_map.get(func_name, "未知服务")
                    print(f"▶ 调用 {func_name} [{service_name}] 参数: {json.dumps(args, ensure_ascii=False)}",
                          flush=True)

                    try:
                        result = self.funcDict[func_name](**args)
                    except Exception as e:
                        result = f"[工具执行异常: {e}]\n请尝试使用不同的参数或换一个工具来完成任务"

                    # 工具结果：仅做轻量压缩，不截断
                    content = json.dumps(result, ensure_ascii=False, default=_json_default)
                    if _is_json_like(content):
                        content = _minify_json_str(content)
                    else:
                        content = _squeeze_text(content)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "name": func_name,
                        "content": content
                    })
                    step_msg_handler("函数执行结果：%s\n\n" % content)

            step_msg_handler("")
            round_idx += 1

        # 兜底返回
        print("—— 最终答复 ——", flush=True)
        print("[超出最大工具轮次]", flush=True)
        fail_message = {"role": "assistant", "content": "[超出最大工具轮次]"}
        fail_message["cards"] = [{"title": "🔍 详细分析", "content": step_msg, "expanded": False}]
        self.messages.append(fail_message)
        if step_msg_func:
            step_msg_func(step_msg)
        return fail_message

    # ========== MCP 工具加载 ==========
    def iter_package_modules(self, package_name: str) -> Iterator[ModuleType]:
        package = importlib.import_module(package_name)
        if not hasattr(package, '__path__'):
            raise ValueError(f"{package_name} is not a package")
        for importer, modname, ispkg in pkgutil.walk_packages(path=package.__path__,
                                                              prefix=package.__name__ + ".",
                                                              onerror=lambda x: None):
            try:
                module = importlib.import_module(modname)
                yield module
            except ImportError as e:
                print(f"无法导入模块 {modname}: {e}")

    def get_module_global_functions(self, module: ModuleType) -> List[Tuple[str, callable]]:
        functions = inspect.getmembers(module, inspect.isfunction)
        return functions

    def extract_all_functions_from_package(self, package_name: str) -> dict:
        all_functions = {}
        for module in self.iter_package_modules(package_name):
            module_name = module.__name__
            functions = self.get_module_global_functions(module)
            if functions:
                all_functions[module_name] = functions
            all_functions[module_name] = functions
        return all_functions

    def get_mcp_tools(self):
        mcp_tools = []
        mcp_funcDict = {}

        servers = self.config.get("mcpServers", {})
        mcp_service_info = {}

        for name, cfg in servers.items():
            # 跳过被禁用的服务
            if cfg.get("disabled", False):
                print(f"⏭️ 跳过已禁用服务: {name}", flush=True)
                continue

            cmd = cfg.get("command")
            args = cfg.get("args", [])
            cwd = cfg.get("workingDirectory") or cfg.get("working_directory") or os.getcwd()

            try:
                bridge = MCPBridge(command=cmd, args=args, cwd=cwd, timeout=30.0)
                self._mcp_bridges.append(bridge)

                # 远程工具的 schema 直接并入
                tools = bridge.get_tools()

                # 获取服务详细信息
                service_info = bridge.get_service_info()

                # 为每个工具添加服务信息到描述中，帮助模型理解工具来源
                for tool in tools:
                    function_info = tool["function"]
                    original_description = function_info["description"]
                    function_info["description"] = f"[{name}服务] {original_description}"

                mcp_tools.extend(tools)

                mcp_service_info[name] = {
                    "tools": service_info["tools"],
                    "working_directory": service_info["service"]["working_directory"]
                }

                # 远程工具的调用分发函数也并入
                mcp_funcDict.update(bridge.get_func_map())

                print(f"MCP 已就绪: {name}", flush=True)
            except Exception as e:
                print(f"MCP 启动失败: {name} - {e}", flush=True)
                continue

        # 保存服务信息供后续使用
        self._mcp_service_info = mcp_service_info
        # 创建工具到服务的映射
        self._tool_to_service_map = {}
        for service_name, service_info in mcp_service_info.items():
            for tool_name in service_info["tools"]:
                self._tool_to_service_map[tool_name] = service_name

        print(f"可用工具总数: {len(mcp_funcDict)}", flush=True)

        # ===== 本地批量执行工具（把多次同名调用收敛到同一轮）=====
        def _local_batch_exec(tool: str, args_list: list, mode: str = "sequential", max_concurrency: int = 4):
            """
            对同一工具进行批量调用：把多组参数一次性提交，按顺序返回结果。
            默认顺序执行；如需并发，可自行扩展。
            """
            if tool not in mcp_funcDict:
                return {"ok": False, "error": f"unknown tool '{tool}'"}
            fn = mcp_funcDict[tool]
            results = []
            for i, a in enumerate(args_list or []):
                try:
                    if not isinstance(a, dict):
                        raise ValueError("each args in args_list must be an object")
                    data = fn(**a)
                    results.append({"i": i, "ok": True, "data": data})
                except Exception as e:
                    results.append({"i": i, "ok": False, "error": str(e)})
            return {"ok": True, "results": results}

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

        mcp_tools.append(batch_tool_schema)
        mcp_funcDict["batch_exec"] = _local_batch_exec
        self._tool_to_service_map["batch_exec"] = "local-batch"

        return mcp_tools, mcp_funcDict

    def _shutdown_mcp(self):
        for b in getattr(self, "_mcp_bridges", []):
            try:
                b.stop()
            except Exception:
                pass

if __name__ == "__main__":
    try:
        client = Client()
        client.set_model(client.config["models"][0])

        print("进入问答模式（Ctrl+C 退出）", flush=True)
        while True:
            try:
                q = input("你：").strip()
                if not q:
                    continue
                resp = client.send(q)
                print("\n助手：", (resp.get("content") or "").strip(), "\n")
            except KeyboardInterrupt:
                print("\n已退出。")
                break
            except Exception as e:
                print(f"错误：{e}")
    except Exception as e:
        print(f"启动失败：{e}")
