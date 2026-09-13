# -*- coding: utf-8 -*-
"""
agent.py —— ReAct 循环核心（stage01）

整个 stage 的心脏只有 20 行逻辑：
    while 未到上限:
        text = LLM(历史消息)                 # 模型写 Thought/Action
        解析 text                            # 文本协议的"税"
        if Final Answer: 返回
        if 解析失败: 注入修复提示，重试
        obs = 执行工具(Action Input)
        Observation 喂回历史

注意它已经悄悄包含了 harness 的两粒种子（后面 stage 逐个展开）：
  · 有界循环（max_turns）——没有它就是 AutoGPT 式的无底洞
  · 失败重试（repair loop）——解析失败不崩，把规则再念一遍
"""
from llm import chat
import protocol


class ReActAgent:
    """基于文本协议的 ReAct agent，支持跨任务的连续多轮对话。"""

    def __init__(self, client, tools, max_turns: int = 15, verbose: bool = True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.max_turns = max_turns
        self.verbose = verbose
        # 对话历史跨任务保留——同一会话里的第 2 个任务能引用第 1 个任务的结论
        self.history = [{"role": "system",
                         "content": self._system_prompt(tools)}]
        self.total_turns = 0   # 本次会话累计轮数（观察点之一）

    # ── system prompt = 协议说明 + 工具说明书 ─────────────────
    def _system_prompt(self, tools) -> str:
        docs = "\n".join(t.doc() for t in tools)
        return protocol.PROTOCOL_INSTRUCTIONS + \
            protocol.TOOLS_USAGE_TMPL.format(tool_docs=docs)

    # ── 单个任务：跑到 Final Answer 或触顶 ───────────────────
    def run_task(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        if self.verbose:
            print(f"\n┌─ 任务：{task}")

        for turn in range(1, self.max_turns + 1):
            self.total_turns += 1
            text = chat(self.client, self.history)
            parsed = protocol.parse(text)

            if parsed["type"] == "final":                      # 收尾
                self.history.append({"role": "assistant", "content": text})
                self._say(f"│ Thought: {parsed['thought']}")
                self._say(f"└─ ✅ Final Answer:\n{parsed['answer']}")
                return parsed["answer"]

            if parsed["type"] == "bad_format":                 # 格式失败 → 修复重试
                self.history.append({"role": "assistant", "content": text})
                hint = protocol.repair_hint("bad_format")
                self.history.append({"role": "user", "content": hint})
                self._say(f"│ [turn {turn}] ⚠️ 格式解析失败，已注入修复提示")
                continue

            if parsed["type"] == "bad_json":                   # 参数不是合法 JSON → 修复重试
                self.history.append({"role": "assistant", "content": text})
                hint = protocol.repair_hint("bad_json", parsed)
                self.history.append({"role": "user", "content": hint})
                self._say(f"│ [turn {turn}] ⚠️ Action Input 不是合法 JSON，已注入修复提示")
                continue

            tool = self.tools.get(parsed["tool"])              # 工具不存在
            if tool is None:
                obs = (f"错误：未知工具 {parsed['tool']}。"
                       f"只能使用：{', '.join(self.tools)}")
            else:                                              # 正常执行
                try:
                    obs = tool.run(**parsed["input"])
                except TypeError as e:
                    obs = f"错误：参数不匹配（{e}）"
                except Exception as e:                         # 工具内部错误也作为 Observation
                    obs = f"错误：{type(e).__name__}: {e}"

            # 关键约定：assistant 原文与 Observation 都进历史（append-only）
            self.history.append({"role": "assistant", "content": text})
            self.history.append({"role": "user",
                                 "content": f"Observation: {obs}"})
            self._say(f"│ [turn {turn}] Thought: {parsed['thought']}")
            self._say(f"│           Action: {parsed['tool']}  "
                      f"Input: {parsed['input']}")
            self._say(f"│           Observation: {self._clip(obs)}")

        # 触顶兜底：有界循环的"界"发挥作用，而不是烧到天荒地老
        msg = f"⚠️ 已达单任务最大轮数（{self.max_turns}），强制停止。"
        self.history.append({"role": "assistant", "content": msg})
        self._say(f"└─ {msg}")
        return msg

    def reset(self):
        """清空对话（保留 system prompt）——/new 命令用。"""
        self.history = [{"role": "system",
                         "content": self._system_prompt(list(self.tools.values()))}]
        self.total_turns = 0
        print("🧹 对话历史已清空（新会话）")

    # ── 输出辅助 ─────────────────────────────────────────────
    def _say(self, s: str):
        if self.verbose:
            print(s)

    @staticmethod
    def _clip(s: str, limit: int = 160) -> str:
        s = s.replace("\n", " ⏎ ")
        return s if len(s) <= limit else s[:limit] + f"…（共 {len(s)} 字符）"
