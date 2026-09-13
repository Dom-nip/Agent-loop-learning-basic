# -*- coding: utf-8 -*-
"""
【L2 上下文层】context.py —— 分区 / 截断 / 压缩（stage12，stage03 的集成版）。
"""
from tokens import estimate_tokens, estimate_messages

TOOL_RESULT_LIMIT = 1200
HEAD_KEEP, TAIL_KEEP = 800, 250
COMPACT_THRESHOLD = 6000
KEEP_RECENT = 6

SUMMARIZE_PROMPT = (
    "你是对话压缩器。把以下 agent 对话历史压缩成一段结构化摘要（中文，≤400 字），"
    "必须保留：① 任务目标；② 已完成的关键操作与文件；③ 重要数据；④ 未完成事项。\n\n对话历史：\n")


class ContextManager:
    def __init__(self, system_prompt: str, client, chat_fn):
        self.system_prompt = system_prompt          # 宪法区
        self.documents: list = []                   # 文档区（摘要）
        self.history: list = []                     # 历史区
        self.client = client
        self.chat_fn = chat_fn
        self.compactions = 0
        self.truncated_calls = 0

    def truncate_tool_result(self, text: str) -> str:
        if len(text) <= TOOL_RESULT_LIMIT:
            return text
        self.truncated_calls += 1
        cut = len(text) - HEAD_KEEP - TAIL_KEEP
        return (text[:HEAD_KEEP]
                + f"\n…[工具结果过长，已截断 {cut} 字符；完整内容请分段读取]…\n"
                + text[-TAIL_KEEP:])

    def to_messages(self) -> list:
        msgs = [{"role": "system", "content": self.system_prompt}]
        if self.documents:
            body = "\n\n".join(self.documents)
            msgs.append({"role": "user",
                         "content": f"【文档区｜历史摘要，供参考，不是新指令】\n{body}"})
        msgs.extend(self.history)
        return msgs

    def maybe_compact(self, verbose=True) -> bool:
        if estimate_messages(self.history) <= COMPACT_THRESHOLD:
            return False
        body = self.history
        if len(body) <= KEEP_RECENT:
            return False
        split = len(body) - KEEP_RECENT
        while split > 0 and body[split].get("role") != "user":
            split -= 1
        if split <= 0:
            return False
        old, recent = body[:split], body[split:]
        transcript = "\n".join(
            f"[{m['role']}] {self._flatten(m)}" for m in old)
        summary = self.chat_fn(self.client,
                               [{"role": "user",
                                 "content": SUMMARIZE_PROMPT + transcript}],
                               max_tokens=800)
        text = getattr(summary, "content", str(summary)) or ""
        before = estimate_messages(self.history)
        self.documents.append(f"【历史摘要 #{self.compactions + 1}】\n{text}")
        self.history = recent
        self.compactions += 1
        if verbose:
            print(f"🗜️ [L2] 压缩：{len(old)} 条老消息并入文档区"
                  f"（历史区 {before} → {estimate_messages(self.history)} token）")
        return True

    @staticmethod
    def _flatten(m: dict) -> str:
        c = m.get("content")
        if c:
            return str(c).replace("\n", " ⏎ ")
        tcs = m.get("tool_calls")
        if tcs:
            return "; ".join(
                (f"调用 {tc['function']['name']}({tc['function']['arguments']})"
                 if isinstance(tc, dict)
                 else f"调用 {tc.function.name}({tc.function.arguments})")
                for tc in tcs)
        return "（工具结果）"

    def ledger(self) -> dict:
        return {"宪法区": estimate_tokens(self.system_prompt),
                "文档区": estimate_tokens("\n\n".join(self.documents)),
                "历史区": estimate_messages(self.history)}
