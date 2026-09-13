# -*- coding: utf-8 -*-
"""
trace.py —— 轨迹树与成本计量（stage08 的主角）

print 调试的三大局限：一闪而过、无法回放、没有结构。
本文件给出最小可用的观测方案：

  · Span      一次"有名字的工作"（LLM 调用 / 工具执行 / 整个任务），
              记录 谁干的(id)、父任务(parent_id)、起止与耗时、
              token 估算、成本、成功/失败
  · Tracer    span 的生命周期管理 + JSONL 结构化日志逐条落盘
              （logs/trace-<时间戳>.jsonl，append-only）
  · 回放      render_tree 把 JSONL 重建成树——跨进程、事后可查

成本计量：PRICE 表按"每百万 token 单价"配置（示例价格，请按你的
服务商实价修改）。成本 = 输入 token×输入价 + 输出 token×输出价。
"""
import json
import time
import itertools
from datetime import datetime
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = STAGE_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# 示例单价：元 / 百万 token（按你的服务商实价修改）
PRICE = {"input": 2.0, "output": 8.0}


class Span:
    _ids = itertools.count(1)

    def __init__(self, kind: str, name: str, parent_id=None):
        self.id = next(Span._ids)
        self.parent_id = parent_id
        self.kind = kind                      # task / llm / tool
        self.name = name
        self.t0 = time.perf_counter()
        self.t1 = None
        self.tokens_in = 0
        self.tokens_out = 0
        self.status = "ok"
        self.error = None
        self.meta = {}

    @property
    def duration_ms(self) -> float:
        return ((self.t1 or time.perf_counter()) - self.t0) * 1000

    @property
    def cost(self) -> float:
        return (self.tokens_in / 1e6 * PRICE["input"]
                + self.tokens_out / 1e6 * PRICE["output"])

    def to_dict(self) -> dict:
        return {"id": self.id, "parent_id": self.parent_id,
                "kind": self.kind, "name": self.name,
                "ts": datetime.now().isoformat(timespec="seconds"),
                "duration_ms": round(self.duration_ms, 1),
                "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "cost": round(self.cost, 6),
                "status": self.status, "error": self.error,
                **({"meta": self.meta} if self.meta else {})}


class Tracer:
    """span 生命周期 + JSONL 逐条落盘。"""

    def __init__(self, session_name: str = None):
        stamp = session_name or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_file = LOGS_DIR / f"trace-{stamp}.jsonl"
        self.spans: list = []
        self._stack: list = []

    def span(self, kind: str, name: str):
        """上下文管理器用法：

            with tracer.span("tool", "read_file") as sp:
                ...
                sp.tokens_in = n
        """
        return _SpanCtx(self, kind, name)

    def _start(self, kind, name) -> Span:
        parent = self._stack[-1] if self._stack else None
        sp = Span(kind, name, parent_id=parent)
        self._stack.append(sp.id)
        return sp

    def _end(self, sp: Span):
        sp.t1 = time.perf_counter()
        self._stack.pop()
        self.spans.append(sp)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sp.to_dict(), ensure_ascii=False) + "\n")

    # ── 汇总与渲染 ────────────────────────────────────────
    def totals(self) -> dict:
        tin = sum(s.tokens_in for s in self.spans)
        tout = sum(s.tokens_out for s in self.spans)
        cost = sum(s.cost for s in self.spans)
        n_llm = sum(1 for s in self.spans if s.kind == "llm")
        n_tool = sum(1 for s in self.spans if s.kind == "tool")
        errors = sum(1 for s in self.spans if s.status == "error")
        return {"llm_calls": n_llm, "tool_calls": n_tool, "errors": errors,
                "tokens_in": tin, "tokens_out": tout,
                "cost_yuan": round(cost, 4),
                "wall_ms": round(sum(s.duration_ms for s in self.spans), 1)}

    def report(self):
        t = self.totals()
        print("┈┈┈ 会话观测汇总 ┈┈┈")
        print(f"  LLM 调用 {t['llm_calls']} 次 · 工具调用 {t['tool_calls']} 次 · "
              f"错误 {t['errors']} 个")
        print(f"  tokens  输入 {t['tokens_in']} · 输出 {t['tokens_out']}")
        print(f"  估算成本 ¥{t['cost_yuan']}（单价表见 trace.py PRICE）")
        print(f"  累计耗时 {t['wall_ms']} ms")
        self.render_tree()

    def render_tree(self, spans: list = None):
        spans = spans if spans is not None else self.spans
        by_parent = {}
        for s in spans:
            by_parent.setdefault(s.parent_id, []).append(s)
        ICON = {"task": "🎯", "llm": "🧠", "tool": "🔧"}

        def walk(pid, depth=0):
            for s in by_parent.get(pid, []):
                mark = "❌" if s.status == "error" else "✓"
                print(f"  {'    ' * depth}{ICON.get(s.kind, '·')} "
                      f"[{s.id}] {s.name} {mark} "
                      f"{s.duration_ms:.0f}ms "
                      f"in={s.tokens_in} out={s.tokens_out} "
                      f"¥{s.cost:.4f}"
                      + (f" err={s.error}" if s.error else ""))
                walk(s.id, depth + 1)
        print("┈┈┈ 轨迹树 ┈┈┈")
        walk(None)


def replay(path: str):
    """从 JSONL 回放轨迹树（跨进程、事后排查）。"""
    p = Path(path)
    if not p.exists():
        print(f"找不到轨迹文件 {path}")
        return
    spans = []
    for line in p.read_text(encoding="utf-8").strip().splitlines():
        d = json.loads(line)
        sp = Span.__new__(Span)               # 重建而不执行计时器
        sp.__dict__.update({
            "id": d["id"], "parent_id": d["parent_id"], "kind": d["kind"],
            "name": d["name"], "t0": 0,
            # duration 为 0 时不能存 0.0——duration_ms 属性的 `or` 会回退到真实时钟
            "t1": (d["duration_ms"] / 1000) or 1e-9,
            "tokens_in": d["tokens_in"], "tokens_out": d["tokens_out"],
            "status": d["status"], "error": d.get("error"), "meta": d.get("meta", {})})
        # 让 duration_ms/cost 属性可用
        sp.__class__ = Span
        spans.append(sp)
    t = Tracer.__new__(Tracer)
    t.spans = spans
    t.log_file = p
    t.totals = Tracer.totals.__get__(t)
    t.report = Tracer.report.__get__(t)
    t.render_tree = Tracer.render_tree.__get__(t)
    print(f"📂 回放 {path}（共 {len(spans)} 个 span）")
    t.report()


class _SpanCtx:
    def __init__(self, tracer: Tracer, kind: str, name: str):
        self.tracer = tracer
        self.sp = None
        self._kind = kind
        self._name = name

    def __enter__(self) -> Span:
        self.sp = self.tracer._start(self._kind, self._name)
        return self.sp

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.sp.status = "error"
            self.sp.error = f"{exc_type.__name__}: {exc}"
        self.tracer._end(self.sp)
        return False
