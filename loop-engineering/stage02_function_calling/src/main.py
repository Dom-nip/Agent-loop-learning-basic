# -*- coding: utf-8 -*-
"""
main.py —— stage02 唯一入口

运行方式（在本 stage 文件夹下）：python src/main.py

与 stage01 同形状的交互 REPL，新增命令：
    /mode auto|required|none   切换 tool_choice 三模式（对照实验）
    /stats                     看轮次/调用/修复统计
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
from agent import ToolCallingAgent       # noqa: E402
from tools import build_default_tools    # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage02 · Function Calling —— 结构化工具调用
════════════════════════════════════════════════════════════
工具说明书下沉为 API 参数（tools=[schema]），模型返回结构化 tool_calls。
stage01 的文本解析器整个消失，schema 校验失败走 repair loop。
对照实验：
  · /mode required  强制调用工具（看模型如何"挤"出一个调用）
  · /mode none      收走全部工具（对比 stage01 的纯文本回答）
  · 一次说两件事："建 a.txt 写 hello，再建 b.txt 写 world" → 观察并行 tool_calls
命令：/tools /mode /stats /new /history /exit
────────────────────────────────────────────────────────────
"""


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    agent = ToolCallingAgent(get_client(), build_default_tools(), max_turns=15)
    print(f"✅ 已连接 {__import__('config').MODEL}（Function Calling 模式）\n")

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            s = agent.stats
            print(f"再见！轮次 {s['turns']} · 工具调用 {s['tool_calls']} 次 · "
                  f"schema 修复 {s['repairs']} 次")
            break
        if user == "/new":
            agent.reset()
            continue
        if user == "/tools":
            for t in agent.tools.values():
                print(f"  · {t.name}: {t.description}")
            continue
        if user == "/mode":
            try:
                spec = (input("  模式（auto/required/none）> ").strip()
                        if sys.stdin.isatty() else "auto")
            except (EOFError, KeyboardInterrupt):
                print("  （已取消）")
                continue
            if spec in ("auto", "required", "none"):
                agent.set_tool_choice(spec)
            else:
                print("  无效模式")
            continue
        if user == "/stats":
            print(f"  {agent.stats}")
            continue
        if user == "/history":
            print(f"  当前消息数：{len(agent.history)}")
            continue
        agent.run_task(user)
        print()


if __name__ == "__main__":
    main()
