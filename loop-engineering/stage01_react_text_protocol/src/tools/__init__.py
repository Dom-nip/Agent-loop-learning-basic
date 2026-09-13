# -*- coding: utf-8 -*-
"""
tools 包 —— stage01 的工具箱

工具即一个简单约定（dataclass Tool）：
  · name / description / params：给模型看的"说明书"（stage02 会升级为 JSON Schema）
  · run(**kwargs) -> str：真正的执行体，永远返回字符串（ Observation 的原料）

安全约定（这里先立规矩，stage07 会展开成完整权限体系）：
  · 所有文件操作锚定 workspace/ 沙盒根，路径越界一律拒绝
  · run_python 在子进程中执行、带超时、工作目录限定为 workspace/
"""
from pathlib import Path

from .files import read_file, write_file, list_dir
from .python_tool import run_python

WORKSPACE = Path(__file__).resolve().parent.parent.parent / "workspace"
WORKSPACE.mkdir(exist_ok=True)


class Tool:
    """最小工具抽象：说明书三要素 + 执行体。"""

    def __init__(self, name: str, description: str, params: dict, run):
        self.name = name
        self.description = description
        self.params = params          # {参数名: 类型说明}，仅供展示
        self.run = run

    def doc(self) -> str:
        """渲染成注入 system prompt 的工具说明（协议的一部分）。"""
        p = ", ".join(f"{k}({v})" for k, v in self.params.items())
        return f"- {name_line(self.name)}: {self.description} 参数: {p}"


def name_line(n: str) -> str:
    return n


def sandbox_path(rel: str) -> Path:
    """把模型给的相对路径约束进 workspace/ 沙盒（防 ../ 越界）。"""
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE.resolve())):
        raise ValueError(f"路径越界：{rel} 只允许访问 workspace/ 内部")
    return p


def build_default_tools() -> list:
    """stage01 的默认四件工具。"""
    return [
        Tool(
            name="read_file",
            description="读取 workspace/ 下某个文本文件的全部内容。",
            params={"path": "相对 workspace/ 的路径"},
            run=lambda **kw: read_file(sandbox_path(kw["path"])),
        ),
        Tool(
            name="write_file",
            description="把 content 写入 workspace/ 下的文件（覆盖写）。",
            params={"path": "相对路径", "content": "要写入的全文"},
            run=lambda **kw: write_file(sandbox_path(kw["path"]), kw["content"]),
        ),
        Tool(
            name="list_dir",
            description="列出 workspace/ 下某目录的文件与子目录。",
            params={"path": "相对路径，\".\" 表示根"},
            run=lambda **kw: list_dir(sandbox_path(kw.get("path", "."))),
        ),
        Tool(
            name="run_python",
            description="在 workspace/ 下以子进程执行一段 Python 代码，返回 stdout/stderr（30 秒超时）。",
            params={"code": "要执行的 Python 源码"},
            run=lambda **kw: run_python(kw["code"], WORKSPACE),
        ),
    ]
