# -*- coding: utf-8 -*-
"""run_python：子进程沙盒执行（最朴素的隔离——stage07 会升级为黑名单+审计+权限门）。"""
import subprocess
import sys


def run_python(code: str, workspace, timeout: int = 30) -> str:
    """在 workspace/ 目录下用独立子进程跑一段 Python，返回合并的输出。

    设计取舍：
      · 子进程 = 最小隔离：崩了不伤主进程，超时可杀
      · stdout/stderr 合并返回——对模型来说"程序说了什么"就是一条 Observation
      · 不提供交互输入（stdin 已关闭）
    """
    cmd = [sys.executable, "-c", code]
    try:
        proc = subprocess.run(
            cmd, cwd=str(workspace), timeout=timeout,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", stdin=subprocess.DEVNULL,
        )
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
