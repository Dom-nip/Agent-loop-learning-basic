# -*- coding: utf-8 -*-
"""
main.py —— stage05 唯一入口（python src/main.py）

/flooddata 生成三个门店的销售 CSV（制造"可分解的高消耗任务"），然后试试：
    "对比三个门店的销售情况，给出综合结论"
观察主代理如何拆分 → 并行分派 → fan-in 合成。
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
from agent import LeadAgent              # noqa: E402
from tools import bind_tools, WORKSPACE  # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage05 · Subagent —— 分派、并行隔离与 fan-in 合成
════════════════════════════════════════════════════════════
主代理只做拆分与合成；高消耗任务（读大文件、逐项分析）外包给从零开始
的子代理——它们的中间过程不会污染主对话的上下文。

演示路径：
  · /flooddata  生成三个门店的销售数据（store_a/b/c.csv）
  · "对比三个门店的销售情况，给出综合结论"
  → 观察任务包五要素、并行执行、报告合成
命令：/flooddata /stats /new /exit
────────────────────────────────────────────────────────────
"""


def flooddata():
    """生成三份风格不同的门店销售 CSV（每份 ~120 行）。"""
    import random
    random.seed(7)
    profiles = {
        "store_a.csv": ("东区店", 0.92, 180),
        "store_b.csv": ("南区店", 1.00, 150),
        "store_c.csv": ("西区店", 0.75, 220),
    }
    products = ["键盘", "鼠标", "显示器", "耳机", "摄像头", "USB集线器"]
    for fname, (label, factor, base) in profiles.items():
        rows = ["date,product,quantity,unit_price,revenue"]
        for day in range(1, 121):
            prod = random.choice(products)
            qty = max(0, int(random.gauss(base / 30 * factor, 3)))
            price = random.choice([99, 149, 199, 299, 399])
            rows.append(f"2026-05-{(day - 1) % 30 + 1:02d},{prod},{qty},{price},{qty * price}")
        (WORKSPACE / fname).write_text("\n".join(rows), encoding="utf-8")
        print(f"  📄 已生成 workspace/{fname}（{label}，120 行）")


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    client = get_client()
    agent = LeadAgent(client, bind_tools(client))
    print("✅ 就绪。子代理将获得干净上下文，只带回报告。\n")

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            print(f"再见！{agent.stats}")
            break
        if user == "/flooddata":
            flooddata()
            continue
        if user == "/stats":
            print(f"  {agent.stats}")
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
