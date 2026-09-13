# -*- coding: utf-8 -*-
"""
main.py —— stage11 交互入口（python src/main.py）

菜单：
  1. 跑 v1 基线
  2. 跑 v2 迭代版
  3. 回归对比 v1 vs v2（评测驱动开发的核心动作）
  4. 查看用例集
命令行另有 CI 门槛模式：python src/run_eval.py --gate
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

from llm import check_ready, get_client  # noqa: E402
from targets import TARGETS              # noqa: E402
import runner                            # noqa: E402

MENU = """
════════════════════════════════════════════════════════════
 stage11 · 评测 harness —— 程序判分 / LLM 裁判 / 回归 / 门槛
════════════════════════════════════════════════════════════
  1) 跑 v1 基线（target A）
  2) 跑 v2 迭代版（target B）
  3) 回归对比 v1 vs v2
  4) 查看用例集
  q) 退出
CI 门槛模式另见：python src/run_eval.py --gate
────────────────────────────────────────────────────────────
"""


def show_cases(cases):
    for c in cases:
        n_checks = len(c.get("checks") or [])
        n_judge = "＋裁判" if c.get("judge") else ""
        print(f"  · {c['id']:<26} 程序判据×{n_checks}{n_judge}  {c['task']}")


def main():
    print(MENU)
    if not check_ready():
        sys.exit(1)
    client = get_client()
    cases = runner.load_cases()

    while True:
        try:
            choice = input("选择> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice == "q":
            print("再见！")
            break
        if choice == "1":
            print("▶ 跑 v1 基线")
            s = runner.run_suite(client, cases, TARGETS["a（v1 基线）"],
                                 label="v1")
            runner.print_summary(s)
        elif choice == "2":
            print("▶ 跑 v2 迭代版")
            s = runner.run_suite(client, cases, TARGETS["b（v2 迭代）"],
                                 label="v2")
            runner.print_summary(s)
        elif choice == "3":
            runner.compare("v1", "v2")
        elif choice == "4":
            show_cases(cases)
        else:
            print(MENU)


if __name__ == "__main__":
    main()
