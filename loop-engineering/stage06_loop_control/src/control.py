# -*- coding: utf-8 -*-
"""
control.py —— 循环控制器（stage06 的主角）

AutoGPT 的败因复盘（教程第 4 章）：无界循环 + 大计划不回头 + 错误级联。
本文件把"保证它停"做成四道显式机制：

  ① 硬上限    max_turns 轮数上限 + token_budget 预算上限——
              触线强制停止，返回结构化 stop_reason（绝不"祈祷它自己停"）
  ② 确认门    危险工具执行前必须人工确认（human-in-the-loop gate）——
              拒绝的调用不执行，把"用户拒绝"作为工具结果喂回
  ③ stall 检测 连续重复同一（工具，参数）签名 → 注入提醒；
              屡教不改 → 强制计划重写
  ④ 短计划    任务开始先立 ≤5 步短计划；stall 重写时带着已获得的观察修订
              ——计划是消耗品，不是宪法
"""
from tokens import estimate_messages

STILL_NUDGE = (
    "⚠️ [harness] 检测到重复动作（stall）：你已经连续执行了相同的调用。"
    "重复不会产生新信息。请换一个方法推进，或说明为什么必须重试。")

STILL_REWRITE = (
    "⚠️ [harness] 多次 stall。请先重写计划：用 PLAN: 开头，"
    "结合已获得的观察（哪些路不通），给出不超过 5 步的新计划，再继续执行。")

PLAN_PROMPT = (
    "[harness] 开始前请先给出简短计划：以 PLAN: 开头，不超过 5 步，"
    "每步一行。计划是初稿，执行中会随观察修订。")


class LoopController:
    """四道机制的载体。每个任务开始时 reset。"""

    def __init__(self, max_turns: int = 12, token_budget: int = 30000,
                 dangerous_tools: set = None, gate_enabled: bool = True):
        self.max_turns = max_turns
        self.token_budget = token_budget
        self.dangerous_tools = dangerous_tools or set()
        self.gate_enabled = gate_enabled

        # 运行时状态
        self.turns = 0
        self.tokens_used = 0
        self.last_sig = None          # 上一轮动作签名
        self.stall_count = 0          # 连续重复计数
        self.rewrites = 0             # 计划重写次数
        self.stop_reason = None

    def reset(self):
        self.turns = 0
        self.tokens_used = 0
        self.last_sig = None
        self.stall_count = 0
        self.rewrites = 0
        self.stop_reason = None

    # ── ① 硬上限 ─────────────────────────────────────────
    def before_llm(self, history) -> bool:
        """每轮调用模型前检查。返回 False = 必须停止。"""
        self.turns += 1
        self.tokens_used = estimate_messages(history)   # 累计上下文规模
        if self.turns > self.max_turns:
            self.stop_reason = (f"达到轮数上限 {self.max_turns}")
            return False
        if self.tokens_used > self.token_budget:
            self.stop_reason = (f"超出 token 预算 {self.tokens_used}"
                                f"/{self.token_budget}")
            return False
        return True

    # ── ② 确认门 ─────────────────────────────────────────
    def confirm(self, tool_name: str, args: dict) -> bool:
        """危险操作请求人工确认。返回 False = 用户拒绝。"""
        if tool_name not in self.dangerous_tools or not self.gate_enabled:
            return True
        print(f"\n🚦 [确认门] agent 请求执行危险操作：{tool_name}")
        print(f"   参数：{args}")
        try:
            ans = input("   允许执行？(y=允许 / 其他=拒绝) > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False
        return ans == "y"

    # ── ③ stall 检测 ─────────────────────────────────────
    def note_action(self, tool_name: str, args: dict) -> str:
        """记录本轮动作。返回 "rewrite" / "nudge" / ""。"""
        import json
        sig = (tool_name, json.dumps(args, sort_keys=True, ensure_ascii=False))
        if sig == self.last_sig:
            self.stall_count += 1
        else:
            self.stall_count = 0
            self.last_sig = sig
        if self.stall_count >= 2:
            self.rewrites += 1
            return "rewrite"
        if self.stall_count == 1:
            return "nudge"
        return ""

    def status_line(self) -> str:
        return (f"轮 {min(self.turns, self.max_turns)}/{self.max_turns}"
                f" · 预算≈{self.tokens_used}/{self.token_budget}"
                f" · 重写{self.rewrites}次")
