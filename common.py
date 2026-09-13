# -*- coding: utf-8 -*-
"""
═════════════════════════════════════════════════════════════════
 Agent 教程共享工具（所有 notebook 都 import 这个模块）
═════════════════════════════════════════════════════════════════
设计原则（对应教程各章的教训）：
  · 零第三方依赖：openai 延迟到真正调用时才 import —— 不装包也能打开
  · 未配置不崩溃：NotConfiguredError + 友好提示，纯本地实验照常跑
  · 工具即教程：safe_execute 就是第 11/19 章讲的「源头截断 + 黑名单」实现
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SANDBOX = ROOT / "sandbox"   # 沙盒始终锚定仓库根目录——notebook 移入 chapters/ 子文件夹后依然正确


# ─────────────────────────────────────────────────────────────
# 1. 配置
# ─────────────────────────────────────────────────────────────
class NotConfiguredError(Exception):
    """config.py 还没填时的友好异常。"""


def _cfg():
    import config  # 延迟导入：保证 common 零依赖可用
    return config


def is_configured() -> bool:
    c = _cfg()
    return bool(c.API_KEY and c.BASE_URL and c.MODEL)


def how_to_configure() -> str:
    return (
        "⏭️  本 cell 需要调用大模型，尚未配置。\n"
        "   打开根目录 config.py，填入三行：\n"
        "     API_KEY  = \"sk-...\"\n"
        "     BASE_URL = \"https://api.openai.com/v1\"   # 或 DeepSeek/智谱/中转站\n"
        "     MODEL    = \"gpt-4o-mini\"\n"
        "   保存后重启本 cell 即可。纯本地的实验 cell 不受影响。"
    )


def print_status():
    """setup cell 调用：打印当前配置状态。"""
    c = _cfg()
    if is_configured():
        masked = c.API_KEY[:6] + "***" if len(c.API_KEY) > 6 else "***"
        print(f"✅ 已配置  model={c.MODEL}")
        print(f"   base_url={c.BASE_URL}")
        print(f"   api_key ={masked}")
    else:
        print("⚠️  config.py 尚未填写 —— 需要大模型的 cell 会提示跳过。")
        print("   纯本地的实验 cell 可以照常运行。")


def get_client(judge: bool = False):
    """返回 OpenAI 兼容 client。openai 延迟导入（不装包不报错）。"""
    c = _cfg()
    if judge:
        key, url = c.JUDGE_API_KEY or c.API_KEY, c.JUDGE_BASE_URL or c.BASE_URL
    else:
        key, url = c.API_KEY, c.BASE_URL
    if not (key and url):
        raise NotConfiguredError(how_to_configure())
    try:
        from openai import OpenAI
    except ImportError:
        raise NotConfiguredError(
            "缺少 openai 包，请先执行：pip install openai")
    return OpenAI(api_key=key, base_url=url)


def chat(messages, tools=None, tool_choice=None, model=None,
         temperature=0.2, max_tokens=None, judge=False, extra=None):
    """
    全教程统一的调用入口。
    返回 resp.choices[0].message 对象（.content / .tool_calls）。
    需要 usage 时用 chat_raw()。
    """
    return chat_raw(messages, tools, tool_choice, model, temperature,
                    max_tokens, judge, extra).choices[0].message


def chat_raw(messages, tools=None, tool_choice=None, model=None,
             temperature=0.2, max_tokens=None, judge=False, extra=None):
    c = _cfg()
    kwargs = dict(
        model=model or c.MODEL,
        messages=messages,
        temperature=temperature,
    )
    if max_tokens:
        kwargs["max_tokens"] = max_tokens
    if tools:
        kwargs["tools"] = tools
    if tool_choice:
        kwargs["tool_choice"] = tool_choice
    if extra:
        kwargs.update(extra)
    return get_client(judge=judge).chat.completions.create(**kwargs)


# ─────────────────────────────────────────────────────────────
# 2. Token 粗估（第 10、12 章预算计算器用）
# ─────────────────────────────────────────────────────────────
def estimate_tokens(text: str) -> int:
    """粗估：ASCII 约 4 字符/token，非 ASCII（中文等）约 1.33 字符/token。
    教学用途足够，真实计费以各平台 tokenizer 为准。"""
    ascii_n = sum(1 for ch in text if ord(ch) < 128)
    other_n = len(text) - ascii_n
    return int(ascii_n / 4 + other_n * 0.75)


# ─────────────────────────────────────────────────────────────
# 3. 沙盒执行器（第 11 章源头截断、第 20 章 agent loop 复用）
# ─────────────────────────────────────────────────────────────
DEFAULT_BLOCKLIST = ("rm -rf", "sudo", "mkfs", "> /dev/", "curl | sh",
                     "shutdown", "format ", "del /f")


def safe_execute(command: str, cwd: Path | str = None, timeout: int = 30,
                 max_chars: int = 2000, blocklist=DEFAULT_BLOCKLIST) -> str:
    """带黑名单/超时/输出截断的 shell 执行 —— 教程里的『工具实现规范』示范。"""
    if any(d in command for d in blocklist):
        return "BLOCKED: 该命令命中安全黑名单，已拦截。"
    cwd = cwd or SANDBOX
    cwd = Path(cwd)
    cwd.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(command, shell=True, capture_output=True,
                           text=True, timeout=timeout, cwd=str(cwd))
        out = (r.stdout + ("\n" + r.stderr if r.stderr else "")).strip()
    except subprocess.TimeoutExpired:
        return f"TIMEOUT: 命令超过 {timeout}s 未返回。"
    if len(out) > max_chars:  # 源头截断：保首尾、去中间
        out = out[: max_chars - 200] + "\n...(中略)...\n" + out[-150:]
    return out or "(无输出)"


# ─────────────────────────────────────────────────────────────
# 4. 小工具
# ─────────────────────────────────────────────────────────────
def ptext(s: str):
    """notebook 里打印等宽文本块。"""
    print(s)


def load_md(name: str) -> str:
    """读取各章文件夹中的 md 构建源原文（供对照）。按文件名在 chapters/*/ 中检索。"""
    for p in sorted((ROOT / "chapters").glob(f"*/{name}")):
        return p.read_text(encoding="utf-8")
    return "(未找到)"
