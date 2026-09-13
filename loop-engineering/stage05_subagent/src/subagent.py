# -*- coding: utf-8 -*-
"""
subagent.py —— 子代理：一个全新的、干净上下文的 agent 实例（stage05 核心）

核心思想（上下文隔离，教程第 7/15 章）：
  主 agent 不把高消耗任务（读大文件、逐项分析）做在自己的上下文里，而是把任务打包
  分派给子代理。子代理：
    · 从零开始：历史里只有 system prompt + 任务包（不继承主对话的任何消息）
    · 干完只交回一份最终报告（中间过程全部留在子代理的上下文里，随实例消亡）
  主 agent 上下文里只增加一段"报告"——这就是上下文的空间减法。

任务包五要素（缺一项，子代理就会"自信地错"）：
  ① goal        目标：要做什么、做到什么程度
  ② context     最小上下文：完成它需要知道什么（不要更多）
  ③ tools       工具集：只给必需的工具（最小权限）
  ④ boundaries  边界：不许做什么、不许碰哪里
  ⑤ output_fmt  输出格式：报告长什么样（便于 fan-in 合成）
"""
from llm import chat
from schema import parse_args, validate, repair_message

SUB_SYSTEM_TMPL = """\
你是一个专注的子代理（subagent），独立完成一个被分派的任务，然后交回报告。
规则：
  · 只做任务包里写的事，不要展开新任务
  · {boundaries}
  · 文件操作只允许 workspace/ 内部
  · 达到输出格式要求后立即用中文交出最终报告，不要寒暄"""


class SubAgent:
    """单次任务子代理：跑完即弃，报告是唯一出口。"""

    def __init__(self, client, all_tools, package: dict, max_turns: int = 10,
                 verbose: bool = True, tag: str = "sub"):
        self.client = client
        self.max_turns = max_turns
        self.verbose = verbose
        self.tag = tag

        # ③ 工具集：只装配任务包点名的工具（缺省给只读的三个文件工具）
        allowed = package.get("tools") or ["read_file", "list_dir"]
        self.tools = {t.name: t for t in all_tools if t.name in allowed}
        self.specs = [t.openai_spec() for t in self.tools.values()]

        system = SUB_SYSTEM_TMPL.format(
            boundaries=package.get("boundaries", "只操作任务包描述范围内的数据"))
        task_text = (f"【目标】{package.get('goal', '')}\n"
                     f"【背景上下文】{package.get('context', '无')}\n"
                     f"【输出格式】{package.get('output_format', '中文简要报告')}")
        # 干净的历史：system + 任务包，仅此而已——隔离的意义就在这一行
        self.history = [{"role": "system", "content": system},
                        {"role": "user", "content": task_text}]

    def run(self) -> str:
        for turn in range(1, self.max_turns + 1):
            msg = chat(self.client, self.history, tools=self.specs)
            self.history.append(msg)

            calls = list(msg.tool_calls or [])
            if calls:
                for c in calls:
                    result = self._execute(c)
                    self.history.append({"role": "tool", "tool_call_id": c.id,
                                         "content": result})
                    self._say(f"      [{self.tag} t{turn}] 🔧 {c.function.name}")
                continue
            if msg.content:
                return msg.content
        return f"（子代理 {self.tag} 达到最大轮数，未能给出报告）"

    def _execute(self, call) -> str:
        try:
            args = parse_args(call.function.arguments)
        except ValueError as e:
            return f"❌ {e}"
        tool = self.tools.get(call.function.name)
        if tool is None:
            return f"错误：子代理没有被授权工具 {call.function.name}"
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


def run_parallel(client, all_tools, packages: list, max_turns: int = 10,
                 verbose: bool = True, max_workers: int = 4) -> list:
    """并行分派多个子代理（fan-out），收集全部报告（fan-in 的原料）。

    真并行用 ThreadPoolExecutor——LLM 调用是 IO 密集，线程即可。
    """
    from concurrent.futures import ThreadPoolExecutor

    def one(i_pkg):
        i, pkg = i_pkg
        sub = SubAgent(client, all_tools, pkg, max_turns=max_turns,
                       verbose=verbose, tag=pkg.get("name", f"sub{i + 1}"))
        report = sub.run()
        return {"name": pkg.get("name", f"sub{i + 1}"), "report": report}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return list(pool.map(one, enumerate(packages)))
