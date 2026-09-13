# -*- coding: utf-8 -*-
"""
agent.py —— 主代理（Lead）循环（stage05）

主 agent 的 system prompt 承担"分派纪律"：
  · 先判断任务是否值得分派（独立子任务 ≥2 个才分派；顺手的事自己做）
  · 任务包五要素必须完整（要素缺失的任务包会产生"自信地错"的子代理）
  · 报告回来后自己合成（fan-in synthesis），而不是把子报告原样堆给用户
"""
from llm import chat
from schema import parse_args, validate, repair_message

LEAD_SYSTEM = """\
你是主代理（Lead agent），通过函数调用使用工具，并可以把独立子任务分派给子代理。

〖分派纪律〗
  · 可分解为 ≥2 个互不依赖的子任务时，用 spawn_subagents 并行分派；
    顺手就能做的小事不要分派（分派有成本）
  · 每个任务包五要素必须完整：goal（目标）/ context（最小背景）/
    tools（最小工具集）/ boundaries（边界）/ output_format（报告格式）
  · 子代理看不到我们的对话——它们只知道任务包里写的内容
  · 收到全部报告后，由你合成最终结论（对比、汇总、指出冲突），不要原样转贴

〖通用规则〗
  · 文件操作只允许 workspace/ 内部；不要编造工具结果
  · 最终回答用中文"""


class LeadAgent:
    def __init__(self, client, tools, verbose: bool = True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.verbose = verbose
        self.history = [{"role": "system", "content": LEAD_SYSTEM}]
        self.stats = {"turns": 0, "tool_calls": 0, "spawned": 0}

    def run_task(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        self._say(f"\n┌─ 任务：{task}")

        for turn in range(1, 20):
            self.stats["turns"] += 1
            msg = chat(self.client, self.history, tools=self.specs)
            self.history.append(msg)

            calls = list(msg.tool_calls or [])
            if calls:
                for c in calls:
                    result = self._execute(c)
                    if c.function.name == "spawn_subagents":
                        # 数一下分派了几个（观察点）
                        try:
                            import json as _json
                            pkgs = _json.loads(c.function.arguments).get("packages", [])
                            self.stats["spawned"] += len(pkgs)
                        except Exception:
                            pass
                    self.history.append({"role": "tool", "tool_call_id": c.id,
                                         "content": result})
                    self.stats["tool_calls"] += 1
                continue

            if msg.content:
                self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                return msg.content

        msg = "⚠️ 已达单任务最大轮数，强制停止。"
        self.history.append({"role": "assistant", "content": msg})
        self._say(f"└─ {msg}")
        return msg

    def _execute(self, call) -> str:
        try:
            args = parse_args(call.function.arguments)
        except ValueError as e:
            return f"❌ {e}"
        tool = self.tools.get(call.function.name)
        if tool is None:
            return f"错误：未知工具 {call.function.name}"
        errors = validate(args, tool.parameters)
        if errors:
            return repair_message(call.function.name, errors)
        try:
            return str(tool.run(**args))
        except Exception as e:
            return f"错误：{type(e).__name__}: {e}"

    def _say(self, s: str):
        if self.verbose:
            print(s)
