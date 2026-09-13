# -*- coding: utf-8 -*-
"""
【L5 控制层】control.py —— 硬上限 / 确认门 / stall 检测
（stage12，stage06 的集成版：去掉了短计划轮——全 harness 里计划由
宪法层引导，控制层只管硬约束）。
"""
import json
from tokens import estimate_messages

STILL_NUDGE = ("⚠️ [控制层] 检测到重复动作。重复不会产生新信息——"
               "换方法推进，或先收集信息再行动。")


class LoopController:
    def __init__(self, max_turns: int = 12, token_budget: int = 30000,
                 dangerous_tools: set = None, gate_enabled: bool = True):
        self.max_turns = max_turns
        self.token_budget = token_budget
        self.dangerous_tools = dangerous_tools or set()
        self.gate_enabled = gate_enabled
        self.turns = 0
        self.tokens_used = 0
        self.last_sig = None
        self.stall_count = 0
        self.stop_reason = None

    def reset(self):
        self.turns = 0
        self.tokens_used = 0
        self.last_sig = None
        self.stall_count = 0
        self.stop_reason = None

    def before_llm(self, history) -> bool:
        self.turns += 1
        self.tokens_used = estimate_messages(history)
        if self.turns > self.max_turns:
            self.stop_reason = f"达到轮数上限 {self.max_turns}"
            return False
        if self.tokens_used > self.token_budget:
            self.stop_reason = f"超出 token 预算 {self.tokens_used}/{self.token_budget}"
            return False
        return True

    def confirm(self, tool_name: str, args: dict) -> bool:
        if tool_name not in self.dangerous_tools or not self.gate_enabled:
            return True
        print(f"\n🚦 [控制层] 危险操作确认：{tool_name} 参数 {args}")
        try:
            return input("   允许执行？(y=允许 / 其他=拒绝) > ").strip().lower() == "y"
        except (EOFError, KeyboardInterrupt):
            return False

    def note_action(self, tool_name: str, args: dict) -> bool:
        """返回 True = 检测到 stall（连续重复）。"""
        sig = (tool_name, json.dumps(args, sort_keys=True, ensure_ascii=False))
        if sig == self.last_sig:
            self.stall_count += 1
        else:
            self.stall_count = 0
            self.last_sig = sig
        return self.stall_count >= 1

    def status(self) -> str:
        return f"轮{self.turns}/{self.max_turns}·预算≈{self.tokens_used}"
