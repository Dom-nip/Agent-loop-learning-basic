# -*- coding: utf-8 -*-
"""
tokens.py —— 粗粒度 token 估算器（stage03）

真实工程里应当用模型对应的 tokenizer（tiktoken / 各家 SDK 自带）。为了让本 stage
零依赖可跑，这里用一条足够好的启发式：

    token ≈ 中日韩字符数 × 1.0 + 其余字符数 × 0.25

依据：主流 tokenizer 对中文约 1 字 ≈ 1 token（0.8~1.5 之间浮动），
英文约 4 字符 ≈ 1 token。误差 ±30%，但做"什么时候该压缩"的决策完全够用——
上下文工程要的不是精确会计，是数量级正确的仪表盘。
"""

# 混合文本里判断 CJK 的快速区间（含中文标点）
_CJK_RANGES = (
    (0x4E00, 0x9FFF),    # CJK 统一表意文字
    (0x3400, 0x4DBF),    # 扩展 A
    (0x3000, 0x303F),    # CJK 标点
    (0xFF00, 0xFFEF),    # 全角符号
)


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        cp = ord(ch)
        if any(lo <= cp <= hi for lo, hi in _CJK_RANGES):
            cjk += 1
        else:
            other += 1
    return max(1, int(cjk * 1.0 + other * 0.25))


def estimate_messages(messages: list) -> int:
    """对一整段消息列表估算 token（含每条约 4 token 的消息结构开销）。"""
    total = 0
    for m in messages:
        content = m.get("content") if isinstance(m, dict) else getattr(m, "content", "")
        if isinstance(content, list):          # 多模态 content 数组只算文本部分
            content = "".join(str(p) for p in content)
        total += estimate_tokens(content or "") + 4
        # tool_calls 的参数也算上下文
        tcs = (m.get("tool_calls") if isinstance(m, dict)
               else getattr(m, "tool_calls", None))
        for tc in tcs or []:
            fn = tc.get("function", {}) if isinstance(tc, dict) else tc.function
            total += estimate_tokens(fn.get("arguments", "")
                                     if isinstance(fn, dict) else fn.arguments)
    return total
