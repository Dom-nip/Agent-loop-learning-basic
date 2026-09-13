# -*- coding: utf-8 -*-
"""
main.py —— stage10 唯一入口（python src/main.py）

启动时：加载技能元数据（第一层）+ 拉起 MCP server 并桥接工具。
试试：
  · "帮我写本周周报：完成了 A/B/C 三件事" → 看它先 load_skill 再动笔
  · "统计这段文字：……" → 看它调用 MCP 工具 mcp_word_count（来自另一个进程）
  · "现在几点了" → mcp_now（无参数 MCP 工具）
命令：/skills /mcp /new /exit
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
from agent import SkillMcpAgent          # noqa: E402
from tools import (build_default_tools, bridge_mcp_tools,  # noqa: E402
                   set_skills, set_mcp)
from skills import SkillLoader           # noqa: E402
from mcp_client import McpStdioClient    # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage10 · Skill 与 MCP —— 能力按需加载 + 工具跨进程接入
════════════════════════════════════════════════════════════
三层渐进披露：元数据常驻（~50 token/技能）→ load_skill 读正文
            → read_skill_ref 读参考。技能库越大，省得越多。
MCP：mini server 是独立进程（src/mcp_server.py），宿主经 stdio
    JSON-RPC 调用；工具桥接后与本地工具无差别。
命令：/skills /mcp /new /exit
────────────────────────────────────────────────────────────
"""


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    loader = SkillLoader()
    set_skills(loader)
    mcp = McpStdioClient()
    try:
        mcp.start()
        mcp_tools = bridge_mcp_tools(mcp)
    except Exception as e:
        print(f"⚠️ MCP server 启动失败（{e}）——仅用本地工具继续")
        mcp_tools = []

    tools = build_default_tools() + mcp_tools
    agent = SkillMcpAgent(get_client(), tools, loader)

    print("✅ 技能元数据已注入（第一层）：")
    for line in loader.metadata_block().splitlines():
        print(f"   {line}")
    print(f"✅ MCP 工具已桥接：{[t.name for t in mcp_tools] or '（无）'}\n")

    try:
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
            if user == "/skills":
                for name, s in loader.skills.items():
                    refs = loader.list_references(name)
                    print(f"  · {name}: {s['description']}"
                          + (f"（参考文件 {len(refs)} 个）" if refs else ""))
                continue
            if user == "/mcp":
                for t in mcp_tools:
                    print(f"  · {t.name}: {t.description}")
                continue
            if user == "/new":
                agent.history = [{"role": "system",
                                  "content": agent._system_prompt()}]
                print("🧹 对话已重置")
                continue
            agent.run_task(user)
            print()
    finally:
        mcp.stop()


if __name__ == "__main__":
    main()
