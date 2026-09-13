# -*- coding: utf-8 -*-
"""
agent.py —— 带技能与 MCP 工具的循环（stage10）

system prompt 只带技能的**第一层元数据**（每技能约 50 token）；
正文与参考文件由模型按需经 load_skill / read_skill_ref 加载。
MCP 工具已在启动时桥接进工具表，模型看不出它们来自另一个进程。
"""
from llm import chat
from schema import parse_args, validate, repair_message

SYSTEM_TMPL = """\
你是一个严谨的助手，可以通过函数调用使用工具。

〖可用技能（渐进式披露：先 load_skill 读指南，再动手）〗
{skill_metadata}

〖通用规则〗
  · 做专门工作（写周报/清洗数据）前，先加载对应技能
  · 文件操作只允许 workspace/ 内部；不要编造工具结果
  · 任务完成后用中文给出面向用户的最终回答"""


class SkillMcpAgent:
    def __init__(self, client, tools, skill_loader, verbose=True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.skill_loader = skill_loader
        self.verbose = verbose
        self.history = [{"role": "system",
                         "content": self._system_prompt()}]
        self.stats = {"turns": 0, "tool_calls": 0,
                      "skill_loads": 0, "ref_reads": 0}

    def _system_prompt(self) -> str:
        return SYSTEM_TMPL.format(
            skill_metadata=self.skill_loader.metadata_block())

    def run_task(self, task: str) -> str:
        self.history.append({"role": "user", "content": task})
        self._say(f"\n┌─ 任务：{task}")

        for turn in range(1, 16):
            self.stats["turns"] += 1
            msg = chat(self.client, self.history, tools=self.specs)
            self.history.append(msg)

            calls = list(msg.tool_calls or [])
            if calls:
                for c in calls:
                    result = self._execute(c)
                    if c.function.name == "load_skill":
                        self.stats["skill_loads"] += 1
                    elif c.function.name == "read_skill_ref":
                        self.stats["ref_reads"] += 1
                    self.history.append({"role": "tool",
                                         "tool_call_id": c.id,
                                         "content": result})
                    self.stats["tool_calls"] += 1
                    self._say(f"│ [turn {turn}] 🔧 {c.function.name}"
                              f"({self._clip(c.function.arguments, 80)})")
                    self._say(f"│     → {self._clip(result, 100)}")
                continue

            if msg.content:
                self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                return msg.content

        final = "⚠️ 达到最大轮数，强制停止。"
        self.history.append({"role": "assistant", "content": final})
        self._say(f"└─ {final}")
        return final

    def _execute(self, call) -> str:
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
