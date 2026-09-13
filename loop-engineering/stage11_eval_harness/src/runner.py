# -*- coding: utf-8 -*-
"""
runner.py —— 评测执行器（stage11 的主角）

一条用例的判分流水线：
    跑被测系统（一次 LLM 调用，温度固定保证可复现）
      → 程序判分（contains / not_contains / regex，快、免费、确定）
      → LLM-as-judge（可选：rubric 清单 + min_score，管"程序写不出的对"）
      → 汇总 pass/fail + 聚合通过率

设计决策：
  · 程序判分优先——确定、零成本，能程序写就别叫裁判
  · 裁判用温度 0 + JSON 输出 + 容错解析——判分要可复现
  · 裁判故障不连坐（judge_error 单独标记，不计入 fail）
"""
import json
import re
from pathlib import Path

from llm import chat, judge_chat, MODEL

CASES_DIR = Path(__file__).resolve().parent / "cases"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def load_cases() -> list:
    """加载 cases/ 下全部 YAML 用例。"""
    try:
        import yaml
    except ImportError:
        raise SystemExit("缺少依赖 PyYAML：pip install PyYAML")
    cases = []
    for f in sorted(CASES_DIR.glob("*.yaml")):
        for c in yaml.safe_load(f.read_text(encoding="utf-8")):
            c["suite"] = f.stem
            cases.append(c)
    return cases


# ── 程序判分 ─────────────────────────────────────────────
def run_checks(answer: str, checks: list) -> list:
    """返回 [(名称, 是否通过)] 列表。"""
    results = []
    for c in checks or []:
        for kind, arg in c.items():
            if kind == "contains":
                ok = str(arg) in answer
                results.append((f"contains「{arg}」", ok))
            elif kind == "not_contains":
                ok = str(arg) not in answer
                results.append((f"not_contains「{arg}」", ok))
            elif kind == "regex":
                ok = bool(re.search(str(arg), answer))
                results.append((f"regex「{arg}」", ok))
    return results


# ── LLM-as-judge ─────────────────────────────────────────
JUDGE_PROMPT = """\
你是评测裁判。根据评分标准（rubric）给下面的回答打分。

【评分标准】
{rubric}

【用户问题】
{task}

【被评回答】
{answer}

输出 JSON（不要输出其他内容）：
{{"score": 0.0到1.0的数字, "reasons": "一句话理由"}}"""


def run_judge(task: str, answer: str, judge_cfg: dict) -> dict:
    prompt = JUDGE_PROMPT.format(rubric=judge_cfg.get("rubric", "").strip(),
                                 task=task, answer=answer)
    raw = judge_chat([{"role": "user", "content": prompt}])
    lo, hi = raw.find("{"), raw.rfind("}")
    if lo == -1 or hi <= lo:
        return {"score": None, "reasons": f"裁判输出无法解析：{raw[:80]}"}
    try:
        data = json.loads(raw[lo:hi + 1])
        return {"score": float(data.get("score", 0)),
                "reasons": str(data.get("reasons", ""))}
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"score": None, "reasons": f"裁判 JSON 解析失败：{raw[:80]}"}


# ── 单条用例 ─────────────────────────────────────────────
def run_case(client, case: dict, system_prompt: str, use_judge: bool = True) -> dict:
    answer_msg = chat(client, [{"role": "system", "content": system_prompt},
                               {"role": "user", "content": case["task"]}])
    answer = answer_msg.content or ""
    answer = str(answer).strip()

    checks = run_checks(answer, case.get("checks"))
    checks_pass = all(ok for _, ok in checks) if checks else True

    judge_result = None
    judge_pass = True
    if use_judge and case.get("judge"):
        judge_result = run_judge(case["task"], answer, case["judge"])
        if judge_result["score"] is None:
            judge_pass = None               # 裁判故障：不连坐
        else:
            judge_pass = (judge_result["score"]
                          >= float(case["judge"].get("min_score", 0.7)))

    passed = checks_pass and (judge_pass is not False)
    return {"id": case["id"], "task": case["task"], "answer": answer,
            "checks": checks, "checks_pass": checks_pass,
            "judge": judge_result, "judge_pass": judge_pass,
            "passed": passed}


# ── 整套执行 ─────────────────────────────────────────────
def run_suite(client, cases: list, system_prompt: str, use_judge: bool = True,
              label: str = "run") -> dict:
    results = []
    for case in cases:
        r = run_case(client, case, system_prompt, use_judge)
        results.append(r)
        mark = "✅" if r["passed"] else "❌"
        extra = ""
        if r["judge"] and r["judge"]["score"] is not None:
            extra = f" · judge {r['judge']['score']:.2f}"
        print(f"  {mark} {r['id']}{extra}"
              + ("" if r["passed"] else f"\n      回答：{r['answer'][:60]}…"))
    n_pass = sum(1 for r in results if r["passed"])
    summary = {"label": label, "model": MODEL,
               "total": len(results), "passed": n_pass,
               "pass_rate": n_pass / len(results) if results else 0,
               "results": results}
    # 结果落盘（回归对比的原料）
    out = RESULTS_DIR / f"{label}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    return summary


def print_summary(s: dict):
    print(f"\n┈┈┈ {s['label']} ┈┈┈")
    print(f"  模型 {s['model']} · 通过 {s['passed']}/{s['total']}"
          f" · 通过率 {s['pass_rate']:.0%}")


def compare(label_a: str, label_b: str):
    """对比两次结果：回归的核心动作。"""
    fa = RESULTS_DIR / f"{label_a}.json"
    fb = RESULTS_DIR / f"{label_b}.json"
    if not fa.exists() or not fb.exists():
        print("  找不到结果文件（先跑一遍 A 和 B）")
        return
    a = json.loads(fa.read_text(encoding="utf-8"))
    b = json.loads(fb.read_text(encoding="utf-8"))
    ra = {r["id"]: r for r in a["results"]}
    rb = {r["id"]: r for r in b["results"]}
    print(f"\n┈┈┈ 回归对比 {label_a} vs {label_b} ┈┈┈")
    for cid in ra:
        pa, pb = ra[cid]["passed"], rb[cid]["passed"]
        delta = "→" if pa == pb else ("↑ 修复" if pb and not pa else "↓ 退化")
        print(f"  {cid:<26} {'✅' if pa else '❌'} → {'✅' if pb else '❌'}  {delta}")
    print(f"  通过率 {a['pass_rate']:.0%} → {b['pass_rate']:.0%}"
          f"（{'迭代有效' if b['pass_rate'] > a['pass_rate'] else '未见提升'}）")
