# -*- coding: utf-8 -*-
"""
main.py —— stage03 唯一入口（python src/main.py）

对照实验命令：
    /flood          在 workspace 生成一个 ~40KB 日志文件（制造待截断的长输出）
    /context        打印上下文账本（三分区 token 分布）
    /compact        手动触发一次压缩
    /load <文件>    把 workspace 文件注入文档区（按需加载演示）
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
from agent import ManagedAgent           # noqa: E402
from tools import build_default_tools, WORKSPACE  # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage03 · 上下文工程 —— 记账 / 截断 / 分区 / 压缩
════════════════════════════════════════════════════════════
上下文是注意力预算，不是内存。本 stage 三道防线：
  1. 工具结果先截断再进历史（源头截断）
  2. system / documents / history 三分区记账（/context 看账本）
  3. 历史区超 6000 token 自动压缩成摘要（并入文档区）
对照实验：
  · /flood 生成大日志 → "读一下 big.log 然后总结" → 看截断发生
  · 连续聊 10+ 个任务 → 看 /context 里历史区增长与自动压缩
命令：/flood /context /compact /load /new /exit
────────────────────────────────────────────────────────────
"""


def flood():
    """生成一个 ~40KB 的伪访问日志（每行一条，含时间戳/状态码/URL）。"""
    import random
    random.seed(42)
    lines = []
    urls = ["/api/v1/agent/run", "/api/v1/tools/list", "/health",
            "/api/v1/context/compact", "/static/app.js"]
    for i in range(800):
        ts = f"2026-09-{1 + i // 80:02d} {(i // 60) % 24:02d}:{i % 60:02d}:13"
        code = random.choice([200, 200, 200, 201, 404, 429, 500])
        latency = random.randint(12, 950)
        lines.append(f'{ts} {code} {latency}ms {random.choice(urls)} '
                     f'client-{random.randint(1, 40)}')
    (WORKSPACE / "big.log").write_text("\n".join(lines), encoding="utf-8")
    print(f"🌊 已生成 workspace/big.log（{len(chr(10).join(lines))} 字符，800 行）")


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    agent = ManagedAgent(get_client(), build_default_tools())

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user == "/exit":
            agent.ctx.report(agent.specs)
            print("再见！")
            break
        if user == "/flood":
            flood()
            continue
        if user == "/context":
            agent.ctx.report(agent.specs)
            continue
        if user == "/compact":
            ok = agent.ctx.compact(agent.client, __import__("llm").chat)
            if not ok:
                print("（历史区太短，无需压缩）")
            continue
        if user == "/load":
            try:
                rel = input("  workspace 内文件名 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("  （已取消）")
                continue
            p = WORKSPACE / rel
            if p.exists() and p.is_file():
                agent.load_document(rel, p.read_text(encoding="utf-8")[:4000])
            else:
                print("  文件不存在")
            continue
        if user == "/new":
            agent.ctx = __import__("context").ContextManager(agent.ctx.system_prompt)
            print("🧹 上下文已重置")
            continue
        agent.run_task(user)
        print()


if __name__ == "__main__":
    main()
