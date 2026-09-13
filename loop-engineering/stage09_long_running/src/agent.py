# -*- coding: utf-8 -*-
"""
agent.py —— 可恢复的循环（stage09）

与之前所有 stage 的差别：每一轮结束都 save_checkpoint；
崩溃/重启后由 main.py 加载检查点续跑——循环的进度活在磁盘上，
不活在进程里。
"""
from llm import chat
from schema import parse_args, validate, repair_message
from checkpoint import save_checkpoint

SYSTEM_PROMPT = """\
你是一个严谨的助手，可以通过函数调用使用工具。规则：
  · 文件操作只允许 workspace/ 内部；不要编造工具结果
  · 耗时的批量工作用 submit_job 交给后台队列，不要自己一步步磨
  · 任务完成后用中文给出面向用户的最终回答"""

MAX_TURNS = 15


class ResumableAgent:
    def __init__(self, client, tools, verbose=True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.verbose = verbose
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.current_task = None
        self.turn_in_task = 0

    # ── 恢复 ─────────────────────────────────────────────
    def restore(self, ckpt: dict):
        """从检查点恢复：历史 + 任务 + 轮次。"""
        self.history = ckpt["history"]
        self.current_task = ckpt["task"]
        self.turn_in_task = ckpt["turn"]
        self._say(f"♻️ 已恢复检查点：任务「{self.current_task}」"
                  f"（中断在第 {self.turn_in_task} 轮）")

    # ── 执行 ─────────────────────────────────────────────
    def run_task(self, task: str, resume: bool = False) -> str:
        if not resume:
            self.current_task = task
            self.turn_in_task = 0
            self.history.append({"role": "user", "content": task})
            self._say(f"\n┌─ 任务：{task}")
        else:
            self._say(f"\n┌─ 续跑任务：{task}")

        while self.turn_in_task < MAX_TURNS:
            self.turn_in_task += 1
            msg = chat(self.client, self.history, tools=self.specs)
            self.history.append(msg)

            calls = list(msg.tool_calls or [])
            if calls:
                for c in calls:
                    result = self._execute(c)
                    self.history.append({"role": "tool", "tool_call_id": c.id,
                                         "content": result})
                    self._say(f"│ [轮 {self.turn_in_task}/{MAX_TURNS}] "
                              f"🔧 {c.function.name}")
                # ★ 每轮落检查点（崩溃恢复的锚点）
                save_checkpoint(self.history, self.current_task,
                                self.turn_in_task)
                continue

            if msg.content:
                self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                return msg.content

        final = "⚠️ 达到最大轮数，强制停止。"
        self.history.append({"role": "assistant", "content": final})
        self._say(f"└─ {final}")
        return final

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
