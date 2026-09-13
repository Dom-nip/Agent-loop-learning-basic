# -*- coding: utf-8 -*-
"""
checkpoint.py —— 每步检查点 + 崩溃恢复（stage09 组件一）

原则（教程第 25 章）：**持久化执行的单位不是进程，是状态**。
每完成一轮循环就落一次盘；进程无论怎么死，重启后从上一轮续跑——
已烧的钱不重烧，已完成的工作不重做。

注意 append-only 的历史在这里再次立功：检查点就是"把历史原样序列化"，
不需要任何额外的事务设计。
"""
import json
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
CKPT_FILE = STAGE_ROOT / "checkpoint.json"


def _to_jsonable(m):
    """openai SDK 的 message 是 pydantic 对象；dict 原样通过。"""
    if isinstance(m, dict):
        return m
    return m.model_dump()


def save_checkpoint(history: list, task: str, turn: int):
    data = {
        "task": task,
        "turn": turn,
        "ts": datetime.now().isoformat(timespec="seconds"),
        "history": [_to_jsonable(m) for m in history],
    }
    # 原子写：先写临时文件再替换，防止写一半崩溃留下残缺检查点
    tmp = CKPT_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(CKPT_FILE)


def load_checkpoint() -> dict:
    if not CKPT_FILE.exists():
        return None
    try:
        return json.loads(CKPT_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def clear_checkpoint():
    if CKPT_FILE.exists():
        CKPT_FILE.unlink()
