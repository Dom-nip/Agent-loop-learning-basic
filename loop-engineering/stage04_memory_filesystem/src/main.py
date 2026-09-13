# -*- coding: utf-8 -*-
"""
main.py —— stage04 唯一入口（python src/main.py）

跨会话记忆演示路径：
  会话 1：告诉它你的偏好 → 让它 save_memory → /exit 触发沉淀
  会话 2：重新启动 → 它开口就"记得你"（MEMORY.md 注入 system prompt）

命令：/memory（看 MEMORY.md）/sessions（列归档）/forget（清空记忆）/exit
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

from llm import check_ready, get_client, chat  # noqa: E402
from agent import MemoryAgent                  # noqa: E402
from tools import build_default_tools          # noqa: E402
from memory import MemoryStore, distill_session  # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage04 · 记忆与文件系统 —— 跨会话的三层记忆
════════════════════════════════════════════════════════════
  会话历史  → 进程内（本窗口内有效）
  工作笔记  → notes/*.md（agent 用文件工具自己读写）
  长期记忆  → memory/MEMORY.md + sessions/*.md（跨会话持久）
试试：
  · "记住：我在做电商后台项目，偏好 Python，不用 Docker"
  · "把这个任务的分析写到 notes/analysis.md"（工作笔记层）
  · /exit 退出 → 观察沉淀流程；再启动 → 观察它记得你
命令：/memory /sessions /forget /exit
────────────────────────────────────────────────────────────
"""


def end_of_session(agent, store):
    """会话收尾沉淀：① 会话摘要落盘 ② 长期事实入 MEMORY.md。"""
    print("\n🧹 会话收尾：正在沉淀记忆……")
    text = agent.transcript_text()
    if len(text) < 80:
        print("   （本次会话内容太少，跳过沉淀）")
        return
    try:
        summary, facts = distill_session(agent.client, chat, text)
    except Exception as e:
        print(f"   ⚠️ 沉淀失败（{e}）——不影响退出。")
        return

    path = store.save_session_summary(summary, agent.stats)
    print(f"   📄 会话摘要已归档：{path.name}")
    if facts:
        n = store.append_memory(facts)
        print(f"   🧠 新增长期记忆 {n} 条：")
        for f in facts:
            print(f"      · {f}")
    else:
        print("   🧠 没有值得写入长期记忆的新事实")


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    store = MemoryStore()
    client = get_client()
    agent = MemoryAgent(client, build_default_tools(), store)

    mem = store.load_memory().strip()
    n_sessions = len(store.list_sessions())
    if mem:
        print(f"✅ 已加载长期记忆（{len(mem)} 字符）+ {n_sessions} 份历史会话归档。")
        print("   开口试试：\"还记得我的项目偏好吗？\"")
    else:
        print("✅ 长期记忆为空（首次会话）。告诉它一些值得记住的事。")
    print()

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            user = "/exit"
        if not user:
            continue
        if user == "/exit":
            end_of_session(agent, store)
            print("\n再见！")
            break
        if user == "/memory":
            content = store.load_memory().strip() or "（空）"
            print(f"── memory/MEMORY.md ──\n{content}")
            continue
        if user == "/sessions":
            sessions = store.list_sessions()
            if not sessions:
                print("  （还没有会话归档）")
            for s in sessions:
                print(f"  · {s.name}")
            continue
        if user == "/forget":
            store.clear_memory()
            print("🗑️ 长期记忆已清空（会话归档保留）")
            continue
        agent.run_task(user)
        print()


if __name__ == "__main__":
    main()
