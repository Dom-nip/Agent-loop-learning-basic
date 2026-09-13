# -*- coding: utf-8 -*-
"""
【L3 工具层】tools.py —— 干净的工具实现（防御在 L4，执行编排在 agent）。
"""
import subprocess
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)
sys.path.insert(0, str(STAGE_ROOT))
from memory import append_memory, load_memory  # noqa: E402


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


def _delete_file(path: str) -> str:
    p = sandbox_path(path)
    if not p.exists():
        return f"错误：文件不存在 {path}"
    p.unlink()
    return f"已删除 {path}"


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


def _save_memory(fact: str) -> str:
    n = append_memory(fact.splitlines())
    return f"已存入长期记忆（{n} 条）"


def _recall_memory() -> str:
    return load_memory() or "（长期记忆为空）"


DANGEROUS_TOOLS = {"delete_file"}


def build_default_tools() -> list:
    return [
        Tool("read_file", "读取 workspace/ 下的文本文件。",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": ["path"]}, _read_file),
        Tool("write_file", "写入 workspace/ 下的文件。",
             {"type": "object", "properties": {"path": {"type": "string"},
                                               "content": {"type": "string"}},
              "required": ["path", "content"]}, _write_file),
        Tool("delete_file", "删除 workspace/ 下的单个文件。危险操作。",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": ["path"]}, _delete_file),
        Tool("list_dir", "列出 workspace/ 目录内容。",
             {"type": "object", "properties": {"path": {"type": "string"}},
              "required": []}, _list_dir),
        Tool("run_python", "子进程执行 Python 并返回输出。",
             {"type": "object", "properties": {"code": {"type": "string"}},
              "required": ["code"]}, _run_python),
        Tool("save_memory", "保存值得跨会话记住的长期事实（一行一条）。",
             {"type": "object", "properties": {"fact": {"type": "string"}},
              "required": ["fact"]}, _save_memory),
        Tool("recall_memory", "读取全部长期记忆。",
             {"type": "object", "properties": {}, "required": []},
             _recall_memory),
    ]
