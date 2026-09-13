# -*- coding: utf-8 -*-
"""
main.py —— stage06 唯一入口（python src/main.py）

四道控制机制的对照实验：
  ① 硬上限   "/budget 2000" 后让它做一件大事 → 看 token 预算强制停止
  ② 确认门   "删掉 workspace 里的 old.txt" → 看 🚦 确认门拦下危险操作
  ③ stall    "读取 secret.txt"（不存在）→ 看它是否反复重试、提醒是否生效
  ④ 短计划   每个任务开始时的 📋 计划，与 stall 后的重写
命令：/budget N /gate on|off /new /exit
"""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent
STAGE_ROOT = SRC.parent
for p in (str(SRC), str(STAGE_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from llm import check_ready, get_client  # noqa: E402
from agent import ControlledAgent        # noqa: E402
from tools import build_default_tools, WORKSPACE, DANGEROUS_TOOLS  # noqa: E402
from control import LoopController       # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage06 · 循环控制 —— 有界、可停、可干预
════════════════════════════════════════════════════════════
四道机制：① 硬上限（轮数+token 预算）② 危险操作确认门
        ③ stall 检测（重复动作提醒/强制重写计划）④ 短计划+计划重写
对照实验：
  · "删掉 workspace 里的 xx.txt"        → 🚦 确认门拦下
  · "读取 secret.txt 并总结"（不存在）   → stall 检测 / 自我修正
  · /budget 2500 后给个大任务            → 预算强制停止
命令：/budget N /gate on|off /new /exit
────────────────────────────────────────────────────────────
"""


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    ctrl = LoopController(max_turns=12, token_budget=30000,
                          dangerous_tools=DANGEROUS_TOOLS, gate_enabled=True)
    agent = ControlledAgent(get_client(), build_default_tools(), ctrl)
    print("✅ 就绪。控制器状态：max_turns=12 · budget=30000 · 确认门=开\n")

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            print("再见！")
            break
        if user == "/new":
            agent.history = [{"role": "system",
                              "content": agent.history[0]["content"]}]
            print("🧹 对话已重置")
            continue
        if user.startswith("/budget"):
            try:
                ctrl.token_budget = int(user.split()[1])
                print(f"💰 token 预算 = {ctrl.token_budget}")
            except (IndexError, ValueError):
                print("  用法：/budget 5000")
            continue
        if user.startswith("/gate"):
            arg = user.split()[-1].lower() if len(user.split()) > 1 else ""
            ctrl.gate_enabled = (arg != "off")
            print(f"🚦 确认门 = {'开' if ctrl.gate_enabled else '关'}"
                  + ("（危险操作将直接执行——演示对比用）" if not ctrl.gate_enabled else ""))
            continue
        agent.run_task(user)
        print()


if __name__ == "__main__":
    main()
