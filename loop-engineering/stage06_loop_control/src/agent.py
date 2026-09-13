# -*- coding: utf-8 -*-
"""
agent.py —— 受控循环（stage06）

在 stage02 形状的循环里插入 LoopController 的四道机制。
每个关键节点都打印控制状态，让"控制"本身可见。
"""
from llm import chat
from schema import parse_args, validate, repair_message
from control import LoopController, PLAN_PROMPT, STILL_NUDGE, STILL_REWRITE

SYSTEM_PROMPT = """\
你是一个严谨的助手，可以通过函数调用使用工具。规则：
  · 文件操作只允许 workspace/ 内部；不要编造工具结果
  · 收到 [harness] 开头的系统消息时，那是循环控制器在提醒你——照做
  · 同一操作失败后不要原样重试，先换方法收集信息
  · 任务完成后用中文给出面向用户的最终回答"""


class ControlledAgent:
    def __init__(self, client, tools, controller: LoopController, verbose=True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.ctrl = controller
        self.verbose = verbose
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]

    def run_task(self, task: str) -> str:
        self.ctrl.reset()
        self.history.append({"role": "user", "content": task})
        # ④ 短计划：任务开始先立计划（消耗品，不是宪法）
        plan_msg = chat(self.client, self.history + [
            {"role": "user", "content": PLAN_PROMPT}], max_tokens=300)
        plan = (plan_msg.content or "").strip()
        self.history.append({"role": "assistant",
                             "content": f"{plan}\n（计划已记录，开始执行）"})
        self._say(f"\n┌─ 任务：{task}\n│ 📋 计划:\n"
                  + "\n".join(f"│    {ln}" for ln in plan.splitlines()[:6]))

        while True:
            if not self.ctrl.before_llm(self.history):        # ① 硬上限
                break

            msg = chat(self.client, self.history, tools=self.specs)
            self.history.append(msg)

            calls = list(msg.tool_calls or [])
            if not calls:
                if msg.content:                               # 最终回答
                    self._say(f"└─ ✅ {self.ctrl.status_line()}\n"
                              f"   Final Answer:\n{msg.content}")
                    return msg.content
                continue

            for c in calls:
                try:
                    args = parse_args(c.function.arguments)
                except ValueError as e:
                    result = f"❌ {e}"
                    args = {}
                else:
                    result = self._execute(c.function.name, args)

                # ③ stall 检测（只对真实工具动作计）
                if not result.startswith(("❌", "错误：")):
                    verdict = self.ctrl.note_action(c.function.name, args)
                else:
                    verdict = ""
                self.history.append({"role": "tool", "tool_call_id": c.id,
                                     "content": result})
                self._say(f"│ [{self.ctrl.status_line()}] 🔧 {c.function.name}"
                          f"({self._clip(str(args), 80)})")
                self._say(f"│     → {self._clip(result, 110)}")

                if verdict == "nudge":
                    self.history.append({"role": "user", "content": STILL_NUDGE})
                    self._say(f"│ ⚠️ stall 检测：已注入提醒")
                elif verdict == "rewrite":
                    self.history.append({"role": "user", "content": STILL_REWRITE})
                    self._say(f"│ ⚠️ 多次 stall：要求重写计划（第 {self.ctrl.rewrites} 次）")

        self._say(f"└─ 🛑 强制停止：{self.ctrl.stop_reason}"
                  f"（{self.ctrl.status_line()}）")
        final = f"⚠️ 任务被循环控制器中止：{self.ctrl.stop_reason}。"
        self.history.append({"role": "assistant", "content": final})
        return final

    def _execute(self, name: str, args: dict) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return f"错误：未知工具 {name}。可用：{', '.join(self.tools)}"
        errors = validate(args, tool.parameters)
        if errors:
            return repair_message(name, errors)
        if not self.ctrl.confirm(name, args):                 # ② 确认门
            return "用户拒绝执行此危险操作。请改用其他方案，或向用户解释为什么需要它。"
        try:
            return str(tool.run(**args))
        except Exception as e:
            return f"错误：{type(e).__name__}: {e}"

    def _say(self, s: str):
        if self.verbose:
            print(s)

    @staticmethod
    def _clip(s: str, limit: int = 160) -> str:
        s = str(s).replace("\n", " ⏎ ")
        return s if len(s) <= limit else s[:limit] + f"…（共 {len(s)} 字符）"
