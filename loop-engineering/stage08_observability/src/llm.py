# -*- coding: utf-8 -*-
"""llm.py —— LLM 客户端封装（stage08，同前形状）。"""
import sys
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = STAGE_ROOT.parent.parent    # 仓库根目录：全部 stage 共用根目录的 config.py
if str(STAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import API_KEY, BASE_URL, MODEL  # noqa: E402


def check_ready() -> bool:
    if API_KEY and BASE_URL and MODEL:
        return True
    print("⚠️  尚未配置 API —— 请打开仓库根目录的 config.py，填入三行后重跑。")
    return False


def get_client():
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def chat(client, messages: list, tools: list = None, temperature: float = 0.2,
         max_tokens: int = 2000):
    kwargs = dict(model=MODEL, messages=messages,
                  temperature=temperature, max_tokens=max_tokens)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message
