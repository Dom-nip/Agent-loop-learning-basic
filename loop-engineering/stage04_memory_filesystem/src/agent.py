# -*- coding: utf-8 -*-
"""
agent.py —— 带三层记忆的 Function Calling 循环（stage04）

与 stage02/stage03 的差别在 system prompt 的组装：
  宪法层（身份与规则）
  + 记忆层（MEMORY.md 内容 + 上一次会话摘要——启动时从磁盘读入）
循环本体不变。记忆的"写入"交给模型经 save_memory 工具 + 会话收尾的
沉淀流程（main.py 的 /exit 里执行）。
"""
from llm import chat
from schema import parse_args, validate, repair_message
from memory import MemoryStore

SYSTEM_TMPL = """\
你是一个有长期记忆的助手，可以通过函数调用使用工具。

〖长期记忆〗（来自 memory/MEMORY.md，跨会话持久）
{memory_block}
{last_session_block}
〖记忆规则〗
  · 用户透露长期有效的偏好/约束时，主动调用 save_memory 存档
  · 任务中间状态写 notes/ 下的工作笔记（write_file），不要塞进长期记忆
  · 需要时用 recall_memory 核对记忆，不要凭印象编造

〖通用规则〗
  · 文件操作只允许 workspace/ 内部
  · 不要凭空编造工具结果
  · 任务完成后用中文给出面向用户的最终回答"""


class MemoryAgent:
    def __init__(self, client, tools, store: MemoryStore, verbose: bool = True):
        self.client = client
        self.tools = {t.name: t for t in tools}
        self.specs = [t.openai_spec() for t in tools]
        self.store = store
        self.verbose = verbose
        self.stats = {"turns": 0, "tool_calls": 0, "tasks": 0}
        self.history = [{"role": "system", "content": self._system_prompt()}]

    def _system_prompt(self) -> str:
        memory = self.store.load_memory().strip()
        memory_block = memory if memory else "（暂无长期记忆）"
        sessions = self.store.list_sessions()
        if sessions:
            last = sessions[-1].read_text(encoding="utf-8")
            # 只取摘要部分（元数据头之后），控制篇幅
            body = last.split("## 摘要", 1)
            last_block = (f"〖上次会话摘要〗（{sessions[-1].name}）\n"
                          + (body[1].strip() if len(body) > 1 else last.strip())
                          + "\n\n")
        else:
            last_block = ""
        return SYSTEM_TMPL.format(memory_block=memory_block,
                                  last_session_block=last_block)

    def run_task(self, task: str) -> str:
        self.stats["tasks"] += 1
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
                    self.history.append({"role": "tool",
                                         "tool_call_id": c.id,
                                         "content": result})
                    self.stats["tool_calls"] += 1
                    self._say(f"│ [turn {turn}] 🔧 {c.function.name}"
                              f"({self._clip(c.function.arguments, 100)})")
                    self._say(f"│           → {self._clip(result)}")
                continue

            if msg.content:
                self._say(f"└─ ✅ Final Answer:\n{msg.content}")
                return msg.content

        msg = "⚠️ 已达单任务最大轮数，强制停止。"
        self.history.append({"role": "assistant", "content": msg})
        self._say(f"└─ {msg}")
        return msg

    def _execute(self, call) -> str:
        name = call.function.name
        try:
            args = parse_args(call.function.arguments)
        except ValueError as e:
            return f"❌ {e}。请修正后重新调用 {name}。"
        if name not in self.tools:
            return f"错误：未知工具 {name}。可用：{', '.join(self.tools)}"
        tool = self.tools[name]
        errors = validate(args, tool.parameters)
        if errors:
            return repair_message(name, errors)
        try:
            return str(tool.run(**args))
        except Exception as e:
            return f"错误：{type(e).__name__}: {e}"

    def transcript_text(self) -> str:
        """把本会话压成纯文本，供收尾沉淀用（不含 system prompt）。"""
        lines = []
        for m in self.history:
            role = m.get("role", "?") if isinstance(m, dict) else m.role
            if role == "system":
                continue
            content = (m.get("content") if isinstance(m, dict) else m.content) or ""
            if content:
                lines.append(f"[{role}] {content}")
        return "\n".join(lines)

    def _say(self, s: str):
        if self.verbose:
            print(s)

    @staticmethod
    def _clip(s: str, limit: int = 160) -> str:
        s = str(s).replace("\n", " ⏎ ")
        return s if len(s) <= limit else s[:limit] + f"…（共 {len(s)} 字符）"
