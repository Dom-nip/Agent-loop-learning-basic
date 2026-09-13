# -*- coding: utf-8 -*-
"""
llm.py —— LLM 客户端封装（stage02）

与 stage01 的差别：chat() 不再返回纯文本，而是返回**完整的 message 对象**——
因为 Function Calling 下模型的"行动"是结构化的 tool_calls 字段，文本只是附带。
"""
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
    print("⚠️  尚未配置 API —— 请打开仓库根目录的 config.py，填入三行：")
    print('     API_KEY  = "sk-..."')
    print('     BASE_URL = "https://api.openai.com/v1"')
    print('     MODEL    = "gpt-4o-mini"')
    print("   保存后重新运行：python src/main.py")
    return False


def get_client():
    from openai import OpenAI
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def chat(client, messages: list, tools: list = None, tool_choice: str = "auto",
         temperature: float = 0.2, max_tokens: int = 2000):
    """返回 resp.choices[0].message 完整对象。

    - tools=None 时不传工具参数（等价 tool_choice="none" 的彻底版）
    - tool_choice 三模式："auto"（模型自己决定）/ "required"（必须调用某工具）/
      "none"（禁止调用，只许文本回答）
    """
    kwargs = dict(model=MODEL, messages=messages,
                  temperature=temperature, max_tokens=max_tokens)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message
