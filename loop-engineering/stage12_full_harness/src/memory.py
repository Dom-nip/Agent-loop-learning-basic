# -*- coding: utf-8 -*-
"""
【L7 记忆层】memory.py —— MEMORY.md 长期记忆 + 会话归档
（stage12，stage04 的集成精简版：记忆注入宪法、退出沉淀摘要）。
"""
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = STAGE_ROOT / "memory"
SESSIONS_DIR = STAGE_ROOT / "sessions"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"
for d in (MEMORY_DIR, SESSIONS_DIR):
    d.mkdir(exist_ok=True)


def load_memory() -> str:
    if not MEMORY_FILE.exists():
        return ""
    return MEMORY_FILE.read_text(encoding="utf-8").strip()


def append_memory(facts: list) -> int:
    facts = [f.strip() for f in facts if f.strip()]
    if not facts:
        return 0
    if not MEMORY_FILE.exists():
        MEMORY_FILE.write_text("# 长期记忆\n\n", encoding="utf-8")
    stamp = datetime.now().strftime("%Y-%m-%d")
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write("".join(f"- [{stamp}] {x}\n" for x in facts))
    return len(facts)


def save_session_summary(summary: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = SESSIONS_DIR / f"{stamp}.md"
    path.write_text(f"# 会话摘要 {stamp}\n\n{summary}\n", encoding="utf-8")
    return path
