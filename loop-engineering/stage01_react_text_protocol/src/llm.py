# -*- coding: utf-8 -*-
"""
llm.py —— LLM 客户端封装（stage01）

唯一职责：把仓库根目录 config.py 的三行配置变成一个可调用的 chat()。
设计要点：
  · 统一配置：只读仓库根目录的 config.py（全部 stage 共用一份，改一处全局生效）
  · 未配置不崩溃：check_ready() 给出友好指引，main.py 据此优雅退出
  · 路径锚定：无论从哪个目录启动，都能找到本 stage 根目录与仓库根目录
"""
import sys
from pathlib import Path

# 本 stage 根目录（src/ 的上一级）与仓库根目录——config.py 在仓库根目录
STAGE_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = STAGE_ROOT.parent.parent    # 仓库根目录：全部 stage 共用根目录的 config.py
if str(STAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import API_KEY, BASE_URL, MODEL  # noqa: E402


def check_ready() -> bool:
    """配置检查：三项齐全返回 True，否则打印友好指引（供 main.py 决定是否退出）。"""
    if API_KEY and BASE_URL and MODEL:
        return True
    print("⚠️  尚未配置 API —— 请打开仓库根目录的 config.py，填入三行：")
    print('     API_KEY  = "sk-..."')
    print('     BASE_URL = "https://api.openai.com/v1"   # 或 DeepSeek/智谱/中转站/本地 vLLM')
    print('     MODEL    = "gpt-4o-mini"')
    print("   保存后重新运行：python src/main.py")
    return False


def get_client():
    """延迟创建 OpenAI 兼容客户端（不装 openai 包、不调用时零开销）。"""
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def chat(client, messages: list, temperature: float = 0.2, max_tokens: int = 2000) -> str:
    """最小对话封装：传入消息列表，返回模型回复文本。"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""
