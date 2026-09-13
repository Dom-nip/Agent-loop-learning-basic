# -*- coding: utf-8 -*-
"""
main.py —— stage01 唯一入口

运行方式（在本 stage 文件夹下）：
    python src/main.py

进入交互式多轮对话：
    你> 任务描述
    agent 打印 Thought/Action/Observation 全过程，最后给出 Final Answer
    你> 下一个任务（可引用上一个任务的结论——对话历史连续）

内置命令：/tools 看工具、/new 清空对话、/history 看消息数、/exit 退出
"""
import sys
from pathlib import Path

# 路径锚定：以本 stage 文件夹为根（config.py 在那里），src/ 为模块目录
SRC = Path(__file__).resolve().parent
STAGE_ROOT = SRC.parent
for p in (str(SRC), str(STAGE_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Windows 控制台中文输出兜底（GBK → UTF-8）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from llm import check_ready, get_client  # noqa: E402
from agent import ReActAgent             # noqa: E402
from tools import build_default_tools    # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage01 · ReAct 文本协议 —— Thought / Action / Observation
════════════════════════════════════════════════════════════
模型用纯文本协议调用工具：Thought(想) → Action(做) → Observation(看)。
试试：
  · "在 workspace 里建一个 todo.md，写上三件今天要做的事"
  · "用 run_python 算一下 2 的 100 次方有多少位"
  · "看看 workspace 里有什么文件，然后写一段读后感到 notes.md"
命令：/tools /new /history /exit
────────────────────────────────────────────────────────────
"""


def main():
    print(BANNER)
    if not check_ready():          # 配置未填：友好指引后退出，不崩溃
        sys.exit(1)

    agent = ReActAgent(get_client(), build_default_tools(), max_turns=15)
    print(f"✅ 已连接 {__import__('config').MODEL}，workspace 就绪，开始对话。\n")

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            print(f"再见！本会话共执行 {agent.total_turns} 个循环轮次。")
            break
        if user == "/new":
            agent.reset()
            continue
        if user == "/tools":
            for t in agent.tools.values():
                print(f"  · {t.name}: {t.description}")
            continue
        if user == "/history":
            print(f"  当前消息数：{len(agent.history)}，累计轮次：{agent.total_turns}")
            continue
        agent.run_task(user)       # 一个任务 = 一段完整 ReAct 循环
        print()


if __name__ == "__main__":
    main()
