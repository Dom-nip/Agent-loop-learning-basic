# -*- coding: utf-8 -*-
"""
llm.py —— LLM 客户端封装（stage11）

多一个 judge_chat()：裁判模型。config.py 里的 JUDGE_* 三项
（异族裁判——不同厂商的模型）填了就用，没填则回落主配置。
"裁判模型随意选择"是失败模式 #26——异族 + 清单 rubric 是对策。
"""
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = STAGE_ROOT.parent.parent    # 仓库根目录：全部 stage 共用根目录的 config.py
if str(STAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import (API_KEY, BASE_URL, MODEL,           # noqa: E402
                    JUDGE_API_KEY, JUDGE_BASE_URL, JUDGE_MODEL)


def check_ready() -> bool:
    if API_KEY and BASE_URL and MODEL:
        return True
    print("⚠️  尚未配置 API —— 请打开仓库根目录的 config.py，填入三行后重跑。")
    return False


def get_client():
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def _judge_config():
    if JUDGE_API_KEY and JUDGE_BASE_URL and JUDGE_MODEL:
        return JUDGE_API_KEY, JUDGE_BASE_URL, JUDGE_MODEL
    return API_KEY, BASE_URL, MODEL     # 回落主配置（真实系统强烈建议异族）


def chat(client, messages: list, temperature: float = 0.2,
         max_tokens: int = 2000):
    resp = client.chat.completions.create(
        model=MODEL, messages=messages,
        temperature=temperature, max_tokens=max_tokens)
    return resp.choices[0].message


def judge_chat(messages: list, temperature: float = 0) -> str:
    """用裁判模型跑一条判分请求（温度 0：判分要可复现）。"""
    from openai import OpenAI
    key, url, model = _judge_config()
    client = OpenAI(api_key=key, base_url=url)
    resp = client.chat.completions.create(
        model=model, messages=messages,
        temperature=temperature, max_tokens=600)
    return resp.choices[0].message.content or ""
