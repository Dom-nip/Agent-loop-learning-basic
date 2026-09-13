# -*- coding: utf-8 -*-
"""
main.py —— stage08 唯一入口

交互模式：python src/main.py
回放模式：python src/main.py --replay logs/trace-<时间戳>.jsonl

会话内命令：/trace（看轨迹树+汇总） /cost（只看成本） /new /exit
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
from agent import InstrumentedAgent      # noqa: E402
from tools import build_default_tools    # noqa: E402
from trace import Tracer, replay         # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage08 · 可观测性 —— 轨迹树 / 计时 / 成本 / 回放
════════════════════════════════════════════════════════════
每个动作都在 span 里：task → llm → tool 父子成树，实时落 JSONL。
  · /trace   看轨迹树与汇总（谁、多久、多少 token、多少钱）
  · 退出后用回放模式离线复盘：python src/main.py --replay logs/trace-xxx.jsonl
命令：/trace /cost /new /exit
────────────────────────────────────────────────────────────
"""


def main():
    # 回放模式
    if len(sys.argv) >= 3 and sys.argv[1] == "--replay":
        replay(sys.argv[2])
        return

    print(BANNER)
    if not check_ready():
        sys.exit(1)

    tracer = Tracer()
    agent = InstrumentedAgent(get_client(), build_default_tools(), tracer)
    print(f"✅ 就绪。轨迹日志：{tracer.log_file.name}\n")

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            tracer.report()
            print(f"\n轨迹已存盘：{tracer.log_file}")
            print(f"回放：python src/main.py --replay {tracer.log_file.name}")
            break
        if user == "/trace":
            tracer.report()
            continue
        if user == "/cost":
            t = tracer.totals()
            print(f"  累计成本 ¥{t['cost_yuan']}"
                  f"（in {t['tokens_in']} + out {t['tokens_out']} token）")
            continue
        if user == "/new":
            agent.history = [{"role": "system",
                              "content": agent.history[0]["content"]}]
            print("🧹 对话已重置")
            continue
        agent.run_task(user)
        print()


if __name__ == "__main__":
    main()
