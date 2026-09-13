# -*- coding: utf-8 -*-
"""
【L6 观测层】trace.py —— span 轨迹 + 成本（stage12，stage08 的集成精简版）。
"""
import json
import time
import itertools
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = STAGE_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

PRICE = {"input": 2.0, "output": 8.0}    # 元/百万 token（示例价，按实价修改）
_ids = itertools.count(1)


class SpanCtx:
    def __init__(self, tracer, kind, name):
        self.t = tracer
        self.kind = kind
        self.name = name
        self.sp = None

    def __enter__(self):
        parent = self.t.stack[-1] if self.t.stack else None
        self.sp = {"id": next(_ids), "parent_id": parent,
                   "kind": self.kind, "name": self.name,
                   "ts": datetime.now().isoformat(timespec="seconds"),
                   "t0": time.perf_counter(), "tokens_in": 0,
                   "tokens_out": 0, "status": "ok", "error": None}
        self.t.stack.append(self.sp["id"])
        return self.sp

    def __exit__(self, exc_type, exc, tb):
        sp = self.sp
        sp["duration_ms"] = round((time.perf_counter() - sp.pop("t0")) * 1000, 1)
        self.t.stack.pop()
        if exc_type is not None:
            sp["status"] = "error"
            sp["error"] = f"{exc_type.__name__}: {exc}"
        sp["cost"] = round(sp["tokens_in"] / 1e6 * PRICE["input"]
                           + sp["tokens_out"] / 1e6 * PRICE["output"], 6)
        with open(self.t.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sp, ensure_ascii=False) + "\n")
        self.t.spans.append(sp)
        return False


class Tracer:
    def __init__(self):
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_file = LOGS_DIR / f"trace-{stamp}.jsonl"
        self.spans: list = []
        self.stack: list = []

    def span(self, kind: str, name: str) -> SpanCtx:
        return SpanCtx(self, kind, name)

    def report(self):
        tin = sum(s["tokens_in"] for s in self.spans)
        tout = sum(s["tokens_out"] for s in self.spans)
        cost = sum(s["cost"] for s in self.spans)
        errs = sum(1 for s in self.spans if s["status"] == "error")
        print("┈┈┈ [L6] 观测汇总 ┈┈┈")
        print(f"  span {len(self.spans)} 个 · 错误 {errs} · "
              f"token in {tin} / out {tout} · 成本 ¥{cost:.4f}")
        by_parent = {}
        for s in self.spans:
            by_parent.setdefault(s["parent_id"], []).append(s)
        ICON = {"task": "🎯", "llm": "🧠", "tool": "🔧"}

        def walk(pid, depth=0):
            for s in by_parent.get(pid, []):
                mark = "❌" if s["status"] == "error" else "✓"
                print(f"  {'    ' * depth}{ICON.get(s['kind'], '·')} "
                      f"{s['name']} {mark} {s['duration_ms']:.0f}ms "
                      f"in={s['tokens_in']} out={s['tokens_out']} ¥{s['cost']:.4f}")
                walk(s["id"], depth + 1)
        walk(None)
