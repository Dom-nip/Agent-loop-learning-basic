# -*- coding: utf-8 -*-
"""
tools.py —— stage10 工具集：三个文件工具 + 技能两层加载工具 + MCP 桥接

亮点：
  · load_skill / read_skill_ref 把三层披露的后两层暴露给模型
  · bridge_mcp_tools 把 MCP server 的工具动态转成 Tool 对象——
    宿主没有为这些工具写一行实现代码，它们来自另一个进程
"""
import subprocess
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)

_skill_loader = None    # main.py 注入
_mcp_client = None


def set_skills(loader):
    global _skill_loader
    _skill_loader = loader


def set_mcp(client):
    global _mcp_client
    _mcp_client = client


class Tool:
    def __init__(self, name: str, description: str, parameters: dict, run):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.run = run

    def openai_spec(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description,
                             "parameters": self.parameters}}


def sandbox_path(rel: str) -> Path:
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f"路径越界：{rel} 只允许访问 workspace/ 内部")
    return p


def _read_file(path: str) -> str:
    p = sandbox_path(path)
    if not p.exists():
        return f"错误：文件不存在 {path}"
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"错误：{path} 不是文本文件"


def _write_file(path: str, content: str) -> str:
    p = sandbox_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 workspace/{path}（{len(content)} 字符）"


def _list_dir(path: str = ".") -> str:
    p = sandbox_path(path)
    if not p.exists():
        return f"错误：目录不存在 {path}"
    items = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
    if not items:
        return "（目录为空）"
    return "\n".join(f"{'📁' if it.is_dir() else '📄'} {it.name}" for it in items)


def _run_python(code: str, timeout: int = 30) -> str:
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code], cwd=str(WORKSPACE), timeout=timeout,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return f"错误：执行超过 {timeout} 秒，已被强制终止"
    out = []
    if proc.stdout:
        out.append(proc.stdout.rstrip())
    if proc.stderr:
        out.append("[stderr]\n" + proc.stderr.rstrip())
    return "\n".join(out) if out else "（无输出，退出码 0）"


def _load_skill(name: str) -> str:
    """第二层：加载技能正文（元数据已在 system prompt 里）。"""
    return _skill_loader.load_skill(name)


def _read_skill_ref(skill: str, filename: str) -> str:
    """第三层：读取技能的参考文件。"""
    return _skill_loader.read_reference(skill, filename)


def build_default_tools() -> list:
    return [
        Tool("read_file", "读取 workspace/ 下的文件。",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": ["path"]}, _read_file),
        Tool("write_file", "写入 workspace/ 下的文件。",
             {"type": "object", "properties": {"path": {"type": "string"},
                                               "content": {"type": "string"}},
              "required": ["path", "content"]}, _write_file),
        Tool("list_dir", "列出 workspace/ 目录内容。",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": []}, _list_dir),
        Tool("run_python", "子进程执行 Python 并返回输出。",
             {"type": "object", "properties": {"code": {"type": "string"}},
              "required": ["code"]}, _run_python),
        Tool("load_skill",
             "加载指定技能的完整指南（写周报、洗数据等专门工作的操作手册）。"
             "开始这类工作前先加载对应技能。",
             {"type": "object", "properties": {"name": {"type": "string",
              "description": "技能名，见系统提示中的可用技能列表"}},
              "required": ["name"]}, _load_skill),
        Tool("read_skill_ref",
             "读取技能的参考文件（更细的规则与范例）。技能正文中会指路。",
             {"type": "object",
              "properties": {"skill": {"type": "string"},
                             "filename": {"type": "string"}},
              "required": ["skill", "filename"]}, _read_skill_ref),
    ]


def bridge_mcp_tools(client) -> list:
    """把 MCP server 的工具动态转成宿主 Tool 对象（M×N 解耦的宿主侧）。"""
    tools = []
    for t in client.list_tools():
        name = t["name"]

        def make_run(n):
            def run(**kwargs):
                return _mcp_client.call_tool(n, kwargs)
            return run

        tools.append(Tool(
            name=f"mcp_{name}",
            description=f"[MCP] {t.get('description', '')}",
            parameters=t.get("inputSchema",
                             {"type": "object", "properties": {}}),
            run=make_run(name)))
    return tools
