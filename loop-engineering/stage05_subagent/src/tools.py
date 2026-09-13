# -*- coding: utf-8 -*-
"""
tools.py —— stage05 工具集：三个文件工具 + run_python + spawn_subagents

spawn_subagents 是本 stage 的灵魂工具：主 agent 用它发起分派。
注意它的参数 schema 本身就是"任务包五要素"的合同——schema 即接口文档。
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


def build_default_tools(client=None) -> list:
    """client 必传以装配 spawn_subagents（它要发起 LLM 调用）。"""
    from subagent import run_parallel

    def _spawn(packages: list) -> str:
        if not packages:
            return "错误：packages 为空"
        if len(packages) > 4:
            return "错误：一次最多并行 4 个子代理（预算护栏）"
        reports = run_parallel(client, ALL_TOOLS_REF, packages, verbose=True)
        lines = []
        for r in reports:
            lines.append(f"━━ 子代理【{r['name']}】的报告 ━━\n{r['report']}")
        return "\n\n".join(lines)

    tools = [
        Tool("read_file", "读取 workspace/ 下的文本文件。",
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
    ]
    spawn = Tool(
        name="spawn_subagents",
        description=(
            "并行分派 1-4 个子代理执行独立子任务，返回各子代理的最终报告。"
            "适合可分解、彼此独立、产出明确的高消耗任务（逐文件分析、逐项调研）。"
            "每个任务包必须完整：goal 目标 / context 最小背景 / tools 工具集 / "
            "boundaries 边界 / output_format 报告格式。"),
        parameters={
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "description": "任务包列表，每包含五要素",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "子代理名字"},
                            "goal": {"type": "string", "description": "目标：做什么、做到什么程度"},
                            "context": {"type": "string", "description": "最小必要背景"},
                            "tools": {"type": "array",
                                      "items": {"type": "string"},
                                      "description": "授权工具名列表，如 [\"read_file\",\"run_python\"]"},
                            "boundaries": {"type": "string", "description": "边界：不许做什么"},
                            "output_format": {"type": "string", "description": "报告格式要求"},
                        },
                        "required": ["name", "goal", "context", "boundaries", "output_format"],
                    },
                },
            },
            "required": ["packages"],
        },
        run=_spawn)
    tools.append(spawn)
    return tools


# spawn 内部要访问全部工具（给子代理按需装配），模块级引用
ALL_TOOLS_REF = None


def bind_tools(client):
    """构建工具集并完成 spawn 的自引用。"""
    global ALL_TOOLS_REF
    tools = build_default_tools(client)
    ALL_TOOLS_REF = tools
    return tools
