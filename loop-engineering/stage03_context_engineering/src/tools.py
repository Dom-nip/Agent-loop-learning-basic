# -*- coding: utf-8 -*-
"""
tools.py —— stage03 工具集（schema 同源，同 stage02 形状）

刻意保留了会"产出大结果"的工具（read_file / run_python）——没有它们，
就没有需要截断的对象。观察实验：先 /flood 生成一个大日志文件，再让 agent 读它。
"""
import subprocess
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)


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
        + ("" if it.is_dir() else f"  {it.stat().st_size}B")
        for it in items)


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
    if proc.returncode != 0:
        out.append(f"[进程退出码 {proc.returncode}]")
    return "\n".join(out) if out else "（无输出，退出码 0）"


def build_default_tools() -> list:
    return [
        Tool("read_file", "读取 workspace/ 下的文本文件。大文件会被 harness 截断，重要内容请分段用 run_python 提取。",
             {"type": "object",
              "properties": {"path": {"type": "string", "description": "相对路径"}},
              "required": ["path"]},
             _read_file),
        Tool("write_file", "写入文本到 workspace/ 下的文件（覆盖写）。",
             {"type": "object",
              "properties": {"path": {"type": "string"},
                             "content": {"type": "string"}},
              "required": ["path", "content"]},
             _write_file),
        Tool("list_dir", "列出 workspace/ 下某目录的内容。",
             {"type": "object",
              "properties": {"path": {"type": "string", "description": "默认 \".\""}},
              "required": []},
             _list_dir),
        Tool("run_python", "子进程执行 Python，返回输出。精确计算与大文件抽样分析用它。",
             {"type": "object",
              "properties": {"code": {"type": "string"},
                             "timeout": {"type": "integer"}},
              "required": ["code"]},
             lambda code, timeout=30: _run_python(code, timeout)),
    ]
