# -*- coding: utf-8 -*-
"""
tools.py —— stage09 工具集：三个文件工具 + 三个任务队列工具

submit_job / poll_jobs / cancel_job 把"长活"交后台线程——agent 的主循环
不被阻塞，用户可以继续对话，稍后轮询收结果。
"""
import subprocess
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = STAGE_ROOT / "workspace"
WORKSPACE.mkdir(exist_ok=True)

_queue = None    # main.py 注入


def set_queue(q):
    global _queue
    _queue = q


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


def _submit_job(description: str, total_steps: int = 5) -> str:
    job_id = _queue.submit(description, total_steps)
    return (f"已提交异步任务 {job_id}（{total_steps} 步，每步约 2 秒，后台执行）。"
            f"稍后用 poll_jobs 查询进度；完成后结果在 jobs/{job_id}.md。")


def _poll_jobs() -> str:
    jobs = _queue.poll()
    if not jobs:
        return "（队列里没有任务）"
    lines = [f"- {j['id']} [{j['status']}] 进度 {j['progress']} —— {j['desc']}"
             for j in jobs]
    return "\n".join(lines)


def _cancel_job(job_id: str) -> str:
    return _queue.cancel(job_id)


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
        Tool("submit_job",
             "提交长任务到后台异步队列（提交后立即可继续其他工作，不阻塞）。",
             {"type": "object",
              "properties": {"description": {"type": "string",
                                             "description": "任务描述"},
                             "total_steps": {"type": "integer",
                                             "description": "总步数（每步约2秒）"}},
              "required": ["description"]}, _submit_job),
        Tool("poll_jobs", "查询全部后台任务的状态与进度。",
             {"type": "object", "properties": {}, "required": []}, _poll_jobs),
        Tool("cancel_job", "请求取消某个后台任务（当前步完成后生效）。",
             {"type": "object", "properties": {"job_id": {"type": "string"}},
              "required": ["job_id"]}, _cancel_job),
    ]
