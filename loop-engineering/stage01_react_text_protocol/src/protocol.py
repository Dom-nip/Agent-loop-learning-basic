# -*- coding: utf-8 -*-
"""
protocol.py —— ReAct 文本协议的定义与解析（stage01 的主角）

ReAct（Reasoning + Acting, Yao et al. 2022）的核心思想：让模型把「思考（Thought）」
和「行动（Action）」交替写出来，harness 执行行动后把结果作为「观察（Observation）」
喂回去——推理与行动由此交织，直到模型写出「Final Answer」。

这个文件就是这个"协议"的全部：
  1. 协议说明（注入 system prompt，教模型怎么写）
  2. 解析器（从模型输出的自由文本里抠出 Action / Action Input）
  3. 修复提示（解析失败时把规则再念一遍——文本协议最著名的软肋）

之所以说文本协议"脆弱"，是因为 1 和 2 都建立在"模型恰好按格式写"的假设上。
stage02 会用 Function Calling 把这套协议下沉为 API 参数，届时本文件的解析器
与修复提示将整个消失。
"""
import json
import re

# ─────────────────────────────────────────────────────────────
# 1. 协议说明：每轮都注入 system prompt 的"格式宪法"
# ─────────────────────────────────────────────────────────────
PROTOCOL_INSTRUCTIONS = """\
你是一个能使用工具的助手。你必须严格按照以下格式回应（每次只走一步）：

Thought: 用一两句中文说明当前该怎么想、下一步做什么
Action: 工具名（必须是下方工具清单中的名字，一字不差）
Action Input: 一个合法的 JSON 对象，键为该工具的参数名

执行后你会收到 Observation: 开头的工具结果。基于它继续下一轮 Thought/Action。
多次使用工具时，每轮只调用一个工具，等待 Observation 后再继续。
当你已经能回答用户时，改用如下格式收尾：

Thought: 说明为什么现在可以回答了
Final Answer: 面向用户的最终回答（中文）

铁律：
  · 绝不编造 Observation——结果只能来自外部输入
  · 绝不在 Action 之外的位置发明新工具名
  · Action Input 必须是单行合法 JSON（例如 {"path": "notes.md"}）
"""

TOOLS_USAGE_TMPL = """\

可用工具清单：
{tool_docs}"""

# ─────────────────────────────────────────────────────────────
# 2. 解析器：从自由文本里抠出结构（这是文本协议的"税"）
# ─────────────────────────────────────────────────────────────
_FINAL_RE = re.compile(r"^\s*Final\s*Answer\s*[:：]", re.M)
_ACTION_RE = re.compile(r"^\s*Action\s*[:：]\s*(\S+)\s*$", re.M)
_INPUT_RE = re.compile(r"^\s*Action\s*Input\s*[:：]\s*(.+)$", re.M | re.S)
_THOUGHT_RE = re.compile(r"^\s*Thought\s*[:：]\s*(.+)$", re.M | re.S)


def parse(text: str) -> dict:
    """解析模型输出。返回四种结果之一：

    - {"type": "final",    "answer": str, "thought": str}   正常收尾
    - {"type": "act",      "tool": str, "input": dict, "thought": str}  正常行动
    - {"type": "bad_json", "tool": str, "raw": str, "error": str}  Action 对但参数不是合法 JSON
    - {"type": "bad_format"}                                              什么都没解析出来
    """
    thought_m = _THOUGHT_RE.search(text)

    # 情况一：Final Answer 收尾（Final Answer 之后的全部文本作为回答）
    fm = _FINAL_RE.search(text)
    if fm:
        answer = text[fm.end():].strip()
        return {"type": "final", "answer": answer or "（空回答）",
                "thought": (thought_m.group(1).strip() if thought_m else "")}

    # 情况二：Action 行动
    am = _ACTION_RE.search(text)
    if not am:
        return {"type": "bad_format"}
    tool = am.group(1)

    # Action Input：从 Action Input: 到文本结束（若有下一段协议关键词则截断，
    # 防止模型一口气幻觉出 Observation —— 长循环里最常见的格式漂移）
    im = _INPUT_RE.search(text)
    raw = ""
    if im:
        raw = im.group(1)
        for stop in ("Observation", "观察", "\nThought", "Thought:", "Final Answer"):
            idx = raw.find(stop)
            if idx != -1:
                raw = raw[:idx]
        raw = raw.strip()

    try:
        arg = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        return {"type": "bad_json", "tool": tool, "raw": raw, "error": str(e)}

    if not isinstance(arg, dict):
        return {"type": "bad_json", "tool": tool, "raw": raw,
                "error": "Action Input 应为 JSON 对象（花括号包裹）"}
    return {"type": "act", "tool": tool, "input": arg,
            "thought": (thought_m.group(1).strip() if thought_m else "")}


# ─────────────────────────────────────────────────────────────
# 3. 修复提示：解析失败时把规则念一遍，给模型一次重来的机会
# ─────────────────────────────────────────────────────────────
REPAIR_HINTS = {
    "bad_format": (
        "⚠️ 你上一条回复不符合 ReAct 协议（缺少 Action: 行）。请重新输出，"
        "必须包含 Thought: / Action: / Action Input: 三行（或用 Final Answer: 收尾）。"
    ),
    "bad_json": (
        "⚠️ 上一条 Action Input 不是合法的 JSON 对象（错误：{error}）。\n"
        "   你写的是：{raw}\n"
        "   请重新输出同一行动，Action Input 换成单行合法 JSON，"
        "例如 {{\"path\": \"notes.md\"}}。注意 JSON 字符串内部的双引号要转义。"
    ),
}


def repair_hint(kind: str, detail: dict = None) -> str:
    """生成对应的修复提示。"""
    detail = detail or {}
    return REPAIR_HINTS[kind].format(**detail)
