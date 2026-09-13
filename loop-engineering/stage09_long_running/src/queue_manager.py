# -*- coding: utf-8 -*-
"""
queue_manager.py —— 异步任务队列（stage09 组件二）

长任务的正确姿势不是"把交互循环卡住跑完"，而是：
    提交（submit）→ 干别的 → 轮询（poll）→ 完成（回调/结果文件）
这是教程第 25 章"异步任务收敛粒度"的最小实现——也是 AutoGPT 同时期
"同步阻塞脚本"路线被淘汰的原因：进程一死，一切归零。

实现：后台线程逐"步"执行；每步之间是取消检查点（cancel propagation
的落点）——取消请求不中断当前步，但在下一步前生效（与真实分布式
系统的取消语义一致）。

本实现里每步是 sleep(2) 模拟（零成本演示）；真实系统里这一步就是
一次 LLM 调用或一段真实处理。
"""
import threading
import time
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
JOBS_DIR = STAGE_ROOT / "jobs"
JOBS_DIR.mkdir(exist_ok=True)

STEP_SECONDS = 2          # 每步耗时（模拟）
_cancel_flags = {}        # job_id -> bool
_lock = threading.Lock()


class Job:
    def __init__(self, job_id: str, description: str, total_steps: int):
        self.id = job_id
        self.description = description
        self.total_steps = total_steps
        self.done_steps = 0
        self.status = "pending"           # pending/running/done/cancelled
        self.started_at = None
        self.finished_at = None

    def snapshot(self) -> dict:
        return {"id": self.id, "desc": self.description,
                "status": self.status,
                "progress": f"{self.done_steps}/{self.total_steps}",
                "started": self.started_at, "finished": self.finished_at}


class TaskQueue:
    def __init__(self):
        self.jobs: dict = {}
        self._counter = 0

    def submit(self, description: str, total_steps: int = 5) -> str:
        self._counter += 1
        job_id = f"job-{self._counter:03d}"
        job = Job(job_id, description, total_steps)
        self.jobs[job_id] = job
        t = threading.Thread(target=self._run, args=(job,), daemon=True)
        t.start()
        return job_id

    def poll(self) -> list:
        return [j.snapshot() for j in self.jobs.values()]

    def cancel(self, job_id: str) -> str:
        with _lock:
            if job_id not in self.jobs:
                return f"错误：找不到 {job_id}"
            if self.jobs[job_id].status in ("done", "cancelled"):
                return f"{job_id} 已是终态（{self.jobs[job_id].status}）"
            _cancel_flags[job_id] = True
            return f"已请求取消 {job_id}（当前步完成后生效）"

    # ── 后台执行体 ────────────────────────────────────────
    def _run(self, job: Job):
        job.status = "running"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        log = [f"# 任务 {job.id}：{job.description}\n"]
        for step in range(1, job.total_steps + 1):
            with _lock:
                if _cancel_flags.get(job.id):
                    job.status = "cancelled"
                    job.finished_at = datetime.now().isoformat(timespec="seconds")
                    log.append(f"\n## 在第 {step} 步前被取消")
                    self._write_result(job, log)
                    return
            time.sleep(STEP_SECONDS)          # 真实系统：这里调用 LLM / 处理数据
            job.done_steps = step
            log.append(f"- 步骤 {step}/{job.total_steps} 完成")
        job.status = "done"
        job.finished_at = datetime.now().isoformat(timespec="seconds")
        log.append(f"\n## 全部完成（{job.total_steps} 步）")
        self._write_result(job, log)

    def _write_result(self, job: Job, log: list):
        """完成/取消回调的模拟：结果落 jobs/<id>.md，轮询方可发现。"""
        path = JOBS_DIR / f"{job.id}.md"
        path.write_text("\n".join(log) + f"\n\n状态：{job.status}\n",
                        encoding="utf-8")
