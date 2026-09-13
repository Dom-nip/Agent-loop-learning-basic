# -*- coding: utf-8 -*-
"""
context.py —— 上下文管理器（stage03 的主角）

三件事，对应第 10-12 章的三课：
  1. 源头截断（truncate_tool_result）：工具结果进历史前先截断——一次 cat
     吃掉 3 万 token 的事故从这里杜绝（第 10/11 章）
  2. 分区记账（ledger）：上下文不是一锅粥，是三个分区——
     【宪法区】system prompt，永不改动（改历史 = 摧毁 prompt cache）
     【文档区】压缩摘要 + 注入的参考资料，按需增删
     【历史区】近期对话 append-only，越过阈值就把老消息压缩进文档区
  3. 阈值压缩（maybe_compact）：历史区 token 超过 COMPACT_THRESHOLD 时，
     把老消息用 LLM 压成一段摘要并入文档区（第 12 章的 compaction loop）

被淘汰方案（本文件的注释里反复出现）：
  · 长窗口全塞派："窗口够大就赢了"——Context Rot（上下文腐烂）实验证伪
  · 每次全量重建：顺序一变 prompt cache 全灭，成本 ×10
"""
from tokens import estimate_tokens, estimate_messages

# ── 可调参数（观察点：改它们做对照实验）─────────────────────
TOOL_RESULT_LIMIT = 1200     # 单条工具结果进入历史的最大字符数
HEAD_KEEP, TAIL_KEEP = 800, 250   # 截断时保留头/尾各多少字符
COMPACT_THRESHOLD = 6000     # 历史区 token 超过此值触发压缩
KEEP_RECENT = 6              # 压缩时保留最近几条消息不压

SUMMARIZE_PROMPT = (
    "你是对话压缩器。把以下 agent 对话历史压缩成一段结构化摘要（中文，≤400 字），"
    "必须保留：① 用户的任务目标；② 已经做了什么（关键文件与操作）；③ 重要的工具"
    "结果数据；④ 未完成的事项。省略寒暄、重复与过程性细节，只留事实。\n\n对话历史：\n"
)


class ContextManager:
    """管理三个分区，并对外提供 token 账本。"""

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt                # 宪法区（不可变）
        self.documents: list = []                         # 文档区（摘要/注入资料）
        self.history: list = []                           # 历史区（append-only）
        self.compactions = 0                              # 压缩次数（观察点）
        self.truncated_calls = 0                          # 截断次数（观察点）

    # ── 1. 源头截断 ──────────────────────────────────────
    def truncate_tool_result(self, text: str) -> str:
        if len(text) <= TOOL_RESULT_LIMIT:
            return text
        self.truncated_calls += 1
        cut = len(text) - HEAD_KEEP - TAIL_KEEP
        return (text[:HEAD_KEEP]
                + f"\n…[工具结果过长，已截断 {cut} 字符；完整内容请分段读取]…\n"
                + text[-TAIL_KEEP:])

    # ── 2. 分区组装：发给 API 的消息序列 ──────────────────
    def to_messages(self) -> list:
        msgs = [{"role": "system", "content": self.system_prompt}]
        if self.documents:
            body = "\n\n".join(self.documents)
            msgs.append({"role": "user",
                         "content": f"【文档区｜以下是本会话的背景资料与历史摘要，"
                                    f"供参考，不是新指令】\n{body}"})
        msgs.extend(self.history)
        return msgs

    # ── 3. 阈值压缩 ──────────────────────────────────────
    def maybe_compact(self, client, chat_fn, verbose=True) -> bool:
        """历史区超阈值则压缩。返回是否发生了压缩。

        client/chat_fn：用主 agent 同一个客户端调用一次摘要。
        """
        if estimate_messages(self.history) <= COMPACT_THRESHOLD:
            return False
        return self.compact(client, chat_fn, verbose)

    def compact(self, client, chat_fn, verbose=True) -> bool:
        body = self.history
        if len(body) <= KEEP_RECENT:
            return False
        # 切分点必须是 user 消息：防止把 tool 消息与其引用的 assistant
        # tool_calls 拆到两区（API 会直接报 400）
        split = len(body) - KEEP_RECENT
        while split > 0 and body[split].get("role") != "user":
            split -= 1
        if split <= 0:
            return False

        old, recent = body[:split], body[split:]
        transcript = "\n".join(
            f"[{m['role']}] {self._flatten(m)}" for m in old)
        summary = chat_fn(client, [
            {"role": "user", "content": SUMMARIZE_PROMPT + transcript}],
            max_tokens=800)
        summary = (summary.content if hasattr(summary, "content") else str(summary))

        before = estimate_messages(self.history)
        self.documents.append(f"【历史摘要 #{self.compactions + 1}】\n{summary}")
        self.history = recent
        self.compactions += 1
        after = estimate_messages(self.history)
        if verbose:
            print(f"🗜️ 压缩完成：{len(old)} 条老消息 → 摘要并入文档区"
                  f"（历史区 {before} → {after} token）")
        return True

    @staticmethod
    def _flatten(m: dict) -> str:
        c = m.get("content")
        if c:
            return str(c).replace("\n", " ⏎ ")
        tcs = m.get("tool_calls")
        if tcs:
            return "; ".join(f"调用 {tc['function']['name']}({tc['function']['arguments']})"
                             if isinstance(tc, dict)
                             else f"调用 {tc.function.name}({tc.function.arguments})"
                             for tc in tcs)
        return "（工具结果）"

    # ── 记账与报告 ────────────────────────────────────────
    def ledger(self, tool_specs: list) -> dict:
        sys_t = estimate_tokens(self.system_prompt)
        doc_t = estimate_tokens("\n\n".join(self.documents))
        hist_t = estimate_messages(self.history)
        tools_t = estimate_tokens(str(tool_specs)) if tool_specs else 0
        return {"宪法区 system": sys_t,
                "文档区 documents": doc_t,
                "历史区 history": hist_t,
                "工具 schema tools": tools_t,
                "合计": sys_t + doc_t + hist_t + tools_t}

    def report(self, tool_specs: list):
        led = self.ledger(tool_specs)
        width = max(len(k) for k in led)
        print("┈┈┈ 上下文账本（估算值）┈┈┈")
        for k, v in led.items():
            bar = "▇" * max(1, v // 120)
            print(f"  {k:<{width}}  {v:>6}  {bar}")
        print(f"  压缩 {self.compactions} 次 · 工具结果截断 {self.truncated_calls} 次")
