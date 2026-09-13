# -*- coding: utf-8 -*-
"""
main.py —— stage09 唯一入口（python src/main.py）

崩溃恢复演示：
  1. 给一个多轮任务，看到 [轮 N] 在推进（每轮都在落检查点）
  2. 中途 Ctrl+C 杀掉进程
  3. 重新运行 python src/main.py → 检测到 checkpoint.json → 询问是否续跑
  4. 续跑：从上次中断的轮次继续，历史完整，不重复烧钱

异步队列演示：
  · 让它"提交一个 10 步的批处理任务"→ submit_job 立即返回
  · "/jobs" 或让它 poll_jobs → 看后台进度逐步增长
  · "/cancel job-001" → 当前步完成后生效（取消传播）
命令：/jobs /cancel <id> /checkpoint /drop /exit
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
from agent import ResumableAgent         # noqa: E402
from tools import build_default_tools, set_queue  # noqa: E402
from queue_manager import TaskQueue      # noqa: E402
import checkpoint as ckpt                # noqa: E402

BANNER = """
════════════════════════════════════════════════════════════
 stage09 · 长时任务 —— 检查点恢复 / 异步队列 / 取消传播
════════════════════════════════════════════════════════════
崩溃恢复：每轮循环落 checkpoint.json，进程死了重启续跑。
异步队列：submit_job 交后台线程，poll_jobs 查进度，cancel_job 请求取消
         （当前步完成后生效——分布式取消语义）。
试试：
  · 多轮任务做到一半 Ctrl+C → 重启本程序 → 按提示续跑
  · "提交一个 8 步的批量分析任务" → /jobs 看进度 → /cancel job-001
命令：/jobs /cancel <id> /checkpoint /drop /exit
────────────────────────────────────────────────────────────
"""


def maybe_resume(agent) -> bool:
    """启动时检查检查点，询问是否续跑。返回是否已恢复。"""
    ck = ckpt.load_checkpoint()
    if not ck:
        return False
    print(f"🔍 发现未完成任务的检查点：")
    print(f"   任务：{ck['task']}")
    print(f"   中断于：第 {ck['turn']} 轮（{ck['ts']}）")
    try:
        ans = input("   续跑该任务？(y=续跑 / 其他=丢弃检查点从头开始) > ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        ans = ""
    if ans == "y":
        agent.restore(ck)
        agent.run_task(ck["task"], resume=True)
        ckpt.clear_checkpoint()          # 跑完清检查点
        return True
    ckpt.clear_checkpoint()
    print("   🗑️ 检查点已丢弃")
    return False


def main():
    print(BANNER)
    if not check_ready():
        sys.exit(1)

    queue = TaskQueue()
    set_queue(queue)
    agent = ResumableAgent(get_client(), build_default_tools())

    if maybe_resume(agent):
        pass  # 续跑已完成

    while True:
        try:
            user = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C 不再是"丢一切"：历史已每轮落盘，下次启动可续跑
            print("\n（已退出。未完成任务有检查点，重启可续跑。）")
            break
        if not user:
            continue
        if user == "/exit":
            ck = ckpt.load_checkpoint()
            print("再见！" + ("（无未完成检查点）" if not ck else
                             "（有未完成检查点，重启可续跑）"))
            break
        if user == "/jobs":
            for j in queue.poll():
                print(f"  {j['id']} [{j['status']}] {j['progress']} —— {j['desc']}")
            continue
        if user.startswith("/cancel"):
            parts = user.split()
            if len(parts) > 1:
                print(f"  {queue.cancel(parts[1])}")
            else:
                print("  用法：/cancel job-001")
            continue
        if user == "/checkpoint":
            ck = ckpt.load_checkpoint()
            if ck:
                print(f"  任务「{ck['task']}」第 {ck['turn']} 轮（{ck['ts']}），"
                      f"历史 {len(ck['history'])} 条消息")
            else:
                print("  （无检查点）")
            continue
        if user == "/drop":
            ckpt.clear_checkpoint()
            print("  🗑️ 检查点已清除")
            continue
        agent.run_task(user)
        ckpt.clear_checkpoint()          # 任务正常完成即清检查点
        print()


if __name__ == "__main__":
    main()
