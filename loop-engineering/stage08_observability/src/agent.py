# -*- coding: utf-8 -*-
"""
agent.py —— 全程插桩的循环（stage08）

每个动作都在 span 里：任务(task) → 每轮 LLM(llm) → 每次工具(tool)，
父子关系构成轨迹树；每条 span 实时落 JSONL。
LLM 调用按"请求消息估算输入 token、回复估算输出 token"计量，
配合 trace.py 的 PRICE 表折算成本。
"""
from llm import chat
from schema import parse_args, validate, repair_message
from tokens import estimate_messages, estimate_tokens
from trace import Tracer

SYSTEM_PROMPT = """\
你是一个严谨的助手，可以通过函数调用使用工具。规则：
  · 文件操作只允许 workspace/ 内部；不要编造工具结果
  · 任务完成后用中文给出面向用户的最终回答"""


class InstrumentedAgent:
    def __init__(self, client, tools, tracer: Tracer = None, verbose=True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.tracer = tracer or Tracer()
        self.verbose = verbose
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def run_task(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        self._say(f"\n┌─ 任务：{task}")

        with self.tracer.span("task", task[:30]) as task_span:
            for turn in range(1, 16):
                with self.tracer.span("llm", f"turn{turn}") as sp:
                    sp.tokens_in = estimate_messages(self.history)
                    msg = chat(self.client, self.history, tools=self.specs)
                    sp.tokens_out = estimate_tokens(msg.content or "")
                    if msg.tool_calls:
                        sp.tokens_out += sum(
                            estimate_tokens(c.function.arguments)
                            for c in msg.tool_calls)
                self.history.append(msg)

                calls = list(msg.tool_calls or [])
                if calls:
                    for c in calls:
                        result = self._instrumented_execute(c)
                        self.history.append({"role": "tool",
                                             "tool_call_id": c.id,
                                             "content": result})
                    continue
                if msg.content:
                    self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                    return msg.content

        final = "⚠️ 达到最大轮数，强制停止。"
        self.history.append({"role": "assistant", "content": final})
        self._say(f"└─ {final}")
        return final

    def _instrumented_execute(self, call) -> str:
        name = call.function.name
        try:
            args = parse_args(call.function.arguments)
        except ValueError as e:
            return f"❌ {e}"
        tool = self.tools.get(name)
        if tool is None:
            return f"错误：未知工具 {name}"
        errors = validate(args, tool.parameters)
        if errors:
            return repair_message(name, errors)

        with self.tracer.span("tool", name) as sp:
            sp.meta = {"args": args}
            sp.tokens_in = estimate_tokens(str(args))
            try:
                result = str(tool.run(**args))
            except Exception as e:
                sp.status = "error"
                sp.error = f"{type(e).__name__}: {e}"
                result = f"错误：{sp.error}"
            sp.tokens_out = estimate_tokens(result)
            self._say(f"│ 🔧 {name}({self._clip(str(args), 70)}) → "
                      f"{self._clip(result, 90)}")
            return result

    def _say(self, s: str):
        if self.verbose:
            print(s)

    @staticmethod
    def _clip(s: str, limit: int = 160) -> str:
        s = str(s).replace("\n", " ⏎ ")
        return s if len(s) <= limit else s[:limit] + f"…（共 {len(s)} 字符）"
