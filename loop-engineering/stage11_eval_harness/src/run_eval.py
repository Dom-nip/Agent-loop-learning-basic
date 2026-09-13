# -*- coding: utf-8 -*-
"""
run_eval.py —— CI 门槛模式的命令行入口（python src/run_eval.py）

    python src/run_eval.py                # 跑全部用例（程序判分+裁判）
    python src/run_eval.py --no-judge     # 只程序判分（省 token）
    python src/run_eval.py --gate         # CI 门槛：通过率 < 0.7 则退出码 1
    python src/run_eval.py --gate --min 0.9

退出码非 0 = 门槛未过——把它接进 CI，evals 就是发版闸门（失败模式 #25）。
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
from targets import TARGET_A, TARGET_B   # noqa: E402
import runner                            # noqa: E402


def main():
    args = sys.argv[1:]
    gate = "--gate" in args
    use_judge = "--no-judge" not in args
    min_rate = 0.7
    if "--min" in args:
        min_rate = float(args[args.index("--min") + 1])

    if not check_ready():
        sys.exit(1)
    client = get_client()
    cases = runner.load_cases()
    print(f"评测集：{len(cases)} 条用例 · 裁判：{'开' if use_judge else '关'}\n")

    print("▶ 跑 v2（当前版本 targets.TARGET_B）")
    summary = runner.run_suite(client, cases, TARGET_B,
                               use_judge=use_judge, label="current")
    runner.print_summary(summary)

    if gate:
        if summary["pass_rate"] >= min_rate:
            print(f"\n🟢 CI 门槛通过（{summary['pass_rate']:.0%} ≥ {min_rate:.0%}）")
            sys.exit(0)
        print(f"\n🔴 CI 门槛未过（{summary['pass_rate']:.0%} < {min_rate:.0%}）"
              f"——禁止发布")
        sys.exit(1)


if __name__ == "__main__":
    main()
