# -*- coding: utf-8 -*-
"""
agent.py —— Function Calling 循环核心（stage02）

与 stage01 循环形状相同，但三个部件换成了基础设施：
  · 协议说明 → tools=[...] API 参数（协议下沉，system prompt 里不再有格式宪法）
  · 文本解析器 → SDK 直接给 message.tool_calls（结构化，零解析税）
  · 格式修复提示 → schema 校验失败把错误当 tool result 喂回（repair loop 只管内容）

新能力：**并行工具调用**——模型可以在一条 assistant 消息里同时给出多个 tool_calls，
harness 依次执行、逐个以 role="tool" 消息回填。
"""
from llm import chat
from schema import parse_args, validate, repair_message


class ToolCallingAgent:
    """基于 Function Calling 的 agent，支持跨任务连续对话与 tool_choice 切换。"""

    def __init__(self, client, tools, max_turns: int = 15, verbose: bool = True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.max_turns = max_turns
        self.verbose = verbose
        self.tool_choice = "auto"      # 可经 /mode 命令切换：auto / required / none
        self.history = [{"role": "system", "content": self._system_prompt()}]
        self.stats = {"turns": 0, "tool_calls": 0, "repairs": 0}

    def _system_prompt(self) -> str:
        # 注意：这里没有工具说明书——schema 已由 API 参数提供。
        # system prompt 只保留身份、语言、沙盒边界这类"宪法"层内容。
        return (
            "你是一个严谨的助手，可以通过函数调用使用工具。规则：\n"
            "  · 需要工具就用工具，不要凭空编造工具结果\n"
            "  · 文件操作只允许 workspace/ 目录内部\n"
            "  · 任务完成后用中文给出面向用户的最终回答\n"
            "  · 多个互不依赖的操作可以在同一条消息里并行发起多个函数调用"
        )

    def run_task(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        self._say(f"\n┌─ 任务：{task}   [tool_choice={self.tool_choice}]")

        for turn in range(1, self.max_turns + 1):
            self.stats["turns"] += 1
            if self.tool_choice == "none":
                # tool_choice="none" 的彻底形态：干脆不传 tools
                msg = chat(self.client, self.history, tools=None)
            else:
                msg = chat(self.client, self.history, tools=self.specs,
                           tool_choice=self.tool_choice)

            self.history.append(msg)                       # assistant 消息原样入历史

            calls = list(msg.tool_calls or [])
            if calls:                                      # 行动：执行全部 tool_calls
                for c in calls:
                    result = self._execute(c)
                    self.history.append({"role": "tool",
                                         "tool_call_id": c.id,
                                         "content": result})
                    self.stats["tool_calls"] += 1
                    self._say(f"│ [turn {turn}] 🔧 {c.function.name}"
                              f"({self._clip(c.function.arguments, 120)})")
                    self._say(f"│           → {self._clip(result)}")
                continue                                   # 工具结果回填完毕，继续循环

            if msg.content:                                # 无行动、有文本 = 最终回答
                self._say(f"│ [turn {turn}] 💬（无工具调用，直接回答）")
                self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                return msg.content

            self._say(f"│ [turn {turn}] ⚠️ 空响应（既无 tool_calls 也无文本），重试")

        msg = f"⚠️ 已达单任务最大轮数（{self.max_turns}），强制停止。"
        self.history.append({"role": "assistant", "content": msg})
        self._say(f"└─ {msg}")
        return msg

    # ── 单次 tool_call：解析 → 校验 → 执行，失败不抛异常只喂回 ──
    def _execute(self, call) -> str:
        name = call.function.name
        try:
            args = parse_args(call.function.arguments)
        except ValueError as e:
            self.stats["repairs"] += 1
            return f"❌ {e}。请修正 arguments 后重新调用 {name}。"

        if name not in self.tools:
            return f"错误：未知工具 {name}。可用：{', '.join(self.tools)}"

        tool = self.tools[name]
        errors = validate(args, tool.parameters)
        if errors:                                         # schema repair loop
            self.stats["repairs"] += 1
            return repair_message(name, errors)

        try:
            return str(tool.run(**args))
        except TypeError as e:
            return f"错误：参数不匹配（{e}）"
        except Exception as e:
            return f"错误：{type(e).__name__}: {e}"

    def set_tool_choice(self, mode: str):
        assert mode in ("auto", "required", "none")
        self.tool_choice = mode
        print(f"🔧 tool_choice = {mode}")
        if mode == "required":
            print("   （模型将被迫调用工具——观察它如何「挤」出一个调用）")
        elif mode == "none":
            print("   （工具被彻底收走——模型只能用文本回答）")

    def reset(self):
        self.history = [{"role": "system", "content": self._system_prompt()}]
        print("🧹 对话历史已清空（新会话）")

    def _say(self, s: str):
        if self.verbose:
            print(s)

    @staticmethod
    def _clip(s: str, limit: int = 160) -> str:
        s = str(s).replace("\n", " ⏎ ")
        return s if len(s) <= limit else s[:limit] + f"…（共 {len(s)} 字符）"
