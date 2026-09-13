# -*- coding: utf-8 -*-
"""
tools.py —— stage04 工具集：三个文件工具 + 显式记忆工具

工作笔记层 = agent 用 read/write/list 直接操作 notes/。
长期记忆层 = save_memory / recall_memory 显式接口（写 MEMORY.md）。
显式记忆工具的存在本身就是设计信号：让模型区分"写任务文件"和"存长期事实"。
"""
import subprocess
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
NOTES_DIR = STAGE_ROOT / "notes"
WORKSPACE.mkdir(exist_ok=True)
NOTES_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(STAGE_ROOT))
from memory import MemoryStore  # noqa: E402

_MEM = MemoryStore()


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
        return f"错误：{path} 不是 UTF-8 文本文件"


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
    return "\n".join(
        f"{'📁' if it.is_dir() else '📄'} {it.name}"
        for it in items)


def _save_memory(fact: str) -> str:
    """注意：写的是 memory/MEMORY.md，不在 workspace 沙盒内——记忆层是特权路径。"""
    n = _MEM.append_memory([fact.strip() for fact in fact.splitlines() if fact.strip()])
    return f"已存入长期记忆（{n} 条）。新会话开始时会自动看到。"


def _recall_memory() -> str:
    content = _MEM.load_memory()
    return content if content else "（长期记忆为空）"


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


def build_default_tools() -> list:
    return [
        Tool("read_file", "读取 workspace/ 下的文件（含 notes/ 工作笔记）。",
             {"type": "object",
              "properties": {"path": {"type": "string"}},
              "required": ["path"]},
             _read_file),
        Tool("write_file", "写入 workspace/ 下的文件（任务产物与中间笔记写这里，长期事实用 save_memory）。",
             {"type": "object",
              "properties": {"path": {"type": "string"},
                             "content": {"type": "string"}},
              "required": ["path", "content"]},
             _write_file),
        Tool("list_dir", "列出 workspace/ 下目录内容。",
             {"type": "object",
              "properties": {"path": {"type": "string"}},
              "required": []},
             _list_dir),
        Tool("save_memory",
             "保存值得跨会话记住的长期事实（用户偏好/项目约束/重要决定）。一行一条；临时状态不要存这里。",
             {"type": "object",
              "properties": {"fact": {"type": "string",
                                      "description": "一条或多条事实，用换行分隔"}},
              "required": ["fact"]},
             _save_memory),
        Tool("recall_memory", "读取全部长期记忆。",
             {"type": "object", "properties": {}, "required": []},
             lambda: _recall_memory()),
        Tool("run_python", "子进程执行 Python，返回输出。",
             {"type": "object",
              "properties": {"code": {"type": "string"}},
              "required": ["code"]},
             _run_python),
    ]
