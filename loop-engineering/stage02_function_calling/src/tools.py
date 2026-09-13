# -*- coding: utf-8 -*-
"""
tools.py —— 带正式 JSON Schema 的工具定义（stage02）

与 stage01 的本质区别：工具说明书从 system prompt 里的自由文本，升级为 API 的
`tools` 参数（OpenAI Function Calling 格式）。schema 与实现写在同一个类里——
"接口文档与代码同源"，这是 Function Calling 时代最重要的工程惯例。

安全约定与 stage01 相同：路径全部锚定 workspace/ 沙盒（复用同一套 sandbox 逻辑）。
"""
import subprocess
import sys
from pathlib import Path
from json import dumps

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)


class Tool:
    """schema + 执行体同源的工具抽象。"""

    def __init__(self, name: str, description: str, parameters: dict, run):
        self.name = name
        self.description = description
        self.parameters = parameters   # 标准 JSON Schema
        self.run = run

    def openai_spec(self) -> dict:
        """渲染为 chat API 的 tools=[...] 条目。"""
        return {"type": "function",
                "function": {"name": self.name,
                             "description": self.description,
                             "parameters": self.parameters}}


# ── 沙盒路径收口（同 stage01）─────────────────────────────
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


# ── schema 定义：注意 description 的写法（何时不用/参数语义）──
def build_default_tools() -> list:
    """stage02 默认工具集：schema 是给模型看的合同，写错一个字模型就会跑偏。"""
    return [
        Tool(
            name="read_file",
            description="读取 workspace/ 下的文本文件。只用于读小文件；目录列举请用 list_dir。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string",
                                        "description": "相对 workspace/ 的路径，如 todo.md"}},
                "required": ["path"],
            },
            run=_read_file,
        ),
        Tool(
            name="write_file",
            description="写入文本到 workspace/ 下的文件（覆盖写）。内容含引号也无须转义处理。",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "相对路径"},
                    "content": {"type": "string", "description": "要写入的完整文本"},
                },
                "required": ["path", "content"],
            },
            run=_write_file,
        ),
        Tool(
            name="list_dir",
            description="列出 workspace/ 下某目录的内容。查看有哪些文件时优先用它，而不是猜测文件名。",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string",
                                        "description": "相对路径，默认 \".\" 表示根目录"}},
                "required": [],
            },
            run=_list_dir,
        ),
        Tool(
            name="run_python",
            description="在 workspace/ 下以子进程执行 Python 代码并返回输出。数学计算、文本处理等需要精确结果的场合使用；不要用它替代 read_file。",
            parameters={
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "完整 Python 源码，用 print() 输出结果"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认 30"},
                },
                "required": ["code"],
            },
            run=lambda code, timeout=30: _run_python(code, timeout),
        ),
    ]


if __name__ == "__main__":
    # 自检：打印 schema、跑一次沙盒冒烟测试
    for t in build_default_tools():
        print(dumps(t.openai_spec(), ensure_ascii=False, indent=2)[:200], "...")
    print(_run_python("print('sandbox ok')"))
