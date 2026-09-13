# -*- coding: utf-8 -*-
"""
memory.py —— 文件系统记忆库（stage04 的主角）

三层记忆，各就各位（对应教程第 12/13 章）：
  ┌──────────────┬────────────────────────┬──────────────────┐
  │ 层           │ 位置                   │ 特性             │
  ├──────────────┼────────────────────────┼──────────────────┤
  │ 会话历史     │ 进程内消息列表         │ 上下文窗口内，   │
  │              │                        │ 会话结束即逝     │
  │ 工作笔记     │ notes/*.md（agent 自己 │ 确定性路径寻址， │
  │              │ 用文件工具读写）       │ 任务中间状态     │
  │ 长期记忆     │ memory/MEMORY.md       │ 跨会话；启动时   │
  │              │ + sessions/*.md        │ 注入，结束前沉淀 │
  └──────────────┴────────────────────────┴──────────────────┘

为什么是文件系统而不是向量数据库？——"我知道状态在哪"永远比
"我猜相关的在哪"可靠：记忆条目有确定路径、可 git、可人工编辑、
可 grep。向量检索管知识召回，不管状态存取（AutoGPT 的历史遗留影响就是
拿向量库存任务状态——时序错乱、新旧混杂）。
"""
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = STAGE_ROOT / "memory"
NOTES_DIR = STAGE_ROOT / "notes"
SESSIONS_DIR = STAGE_ROOT / "sessions"
MEMORY_FILE = MEMORY_DIR / "MEMORY.md"

for d in (MEMORY_DIR, NOTES_DIR, SESSIONS_DIR):
    d.mkdir(exist_ok=True)

EMPTY_MEMORY = "（记忆为空——本文件由会话结束时自动沉淀，也可手工编辑）\n"


class MemoryStore:
    """长期记忆与会话归档的文件系统实现。"""

    # ── 长期记忆（MEMORY.md）──────────────────────────────
    def load_memory(self) -> str:
        if not MEMORY_FILE.exists():
            return ""
        return MEMORY_FILE.read_text(encoding="utf-8")

    def append_memory(self, facts: list) -> int:
        """把若干条事实追加进 MEMORY.md（带日期戳）。返回追加条数。"""
        if not facts:
            return 0
        if not MEMORY_FILE.exists():
            MEMORY_FILE.write_text("# 长期记忆\n\n", encoding="utf-8")
        stamp = datetime.now().strftime("%Y-%m-%d")
        block = "".join(f"- [{stamp}] {f}\n" for f in facts)
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(block)
        return len(facts)

    def clear_memory(self):
        MEMORY_FILE.write_text(EMPTY_MEMORY, encoding="utf-8")

    # ── 会话归档（sessions/*.md）──────────────────────────
    def save_session_summary(self, summary: str, meta: dict) -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = SESSIONS_DIR / f"{stamp}.md"
        head = (f"# 会话摘要 {stamp}\n\n"
                f"- 任务数：{meta.get('tasks', 0)}\n"
                f"- 循环轮次：{meta.get('turns', 0)}\n"
                f"- 工具调用：{meta.get('tool_calls', 0)}\n\n"
                f"## 摘要\n\n{summary}\n")
        path.write_text(head, encoding="utf-8")
        return path

    def list_sessions(self) -> list:
        return sorted(SESSIONS_DIR.glob("*.md"))

    def read_session(self, name: str) -> str:
        p = SESSIONS_DIR / name
        if p.exists():
            return p.read_text(encoding="utf-8")
        return f"（找不到会话 {name}）"


# ── 会话收尾的两个 LLM 步骤（沉淀流程）───────────────────────
SUMMARY_PROMPT = (
    "你是会话归档员。把以下 agent 会话压缩成一篇归档摘要（中文，≤300 字）：\n"
    "① 用户做了什么（任务清单）；② 关键结论与产出文件；③ 未完成事项。\n"
    "只写事实，不写寒暄。\n\n会话记录：\n")

MEMORY_PROMPT = (
    "你是记忆筛选员。从以下会话记录中提炼**值得跨会话记住的长期事实**：\n"
    "用户的偏好、项目的长期约束、重要的决定。临时性内容（本次任务的中间状态、\n"
    "已经写进文件的正文）不要。每条一行、独立成立、精确具体。\n"
    "输出 JSON 数组（字符串数组）；没有值得记的就输出 []。\n\n会话记录：\n")


def distill_session(client, chat_fn, transcript_text: str):
    """收尾两步：返回 (会话摘要 str, 长期事实 list)。"""
    import json as _json
    msgs = [{"role": "user", "content": SUMMARY_PROMPT + transcript_text}]
    summary = chat_fn(client, msgs, max_tokens=800)
    summary = summary.content or ""

    msgs = [{"role": "user", "content": MEMORY_PROMPT + transcript_text}]
    resp = chat_fn(client, msgs, max_tokens=600, temperature=0)
    raw = (resp.content or "").strip()
    # 容错解析：截取第一个 [ 到最后一个 ] 之间的内容
    lo, hi = raw.find("["), raw.rfind("]")
    facts = []
    if lo != -1 and hi > lo:
        try:
            facts = [str(x) for x in _json.loads(raw[lo:hi + 1])]
        except _json.JSONDecodeError:
            facts = []
    return summary, facts
