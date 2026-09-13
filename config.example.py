# -*- coding: utf-8 -*-
"""
═════════════════════════════════════════════════════════════════
 Agent 教程统一配置模板 —— 复制本文件为 config.py 后填写
═════════════════════════════════════════════════════════════════

    cp config.example.py config.py        # macOS / Linux
    copy config.example.py config.py      # Windows

config.py 已被 .gitignore 排除，不会被提交；本模板不含任何真实密钥。

三行全部留空时：所有文档照常阅读，纯本地的实验代码照常运行，
需要调用大模型的入口会打印友好提示并跳过（不报错）。

接口形态统一为「OpenAI 兼容协议」(openai SDK + base_url)，
以下服务商都适用，只需要换三个值：
  · OpenAI 官方     BASE_URL = "https://api.openai.com/v1"
  · DeepSeek        BASE_URL = "https://api.deepseek.com/v1"
  · 智谱 GLM        BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
  · 阿里百炼        BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
  · 各类中转站       BASE_URL = "<中转站给你的地址，通常以 /v1 结尾>"
  · 本地 vLLM/Ollama BASE_URL = "http://localhost:8000/v1" (Ollama 为 11434/v1)

安全提示：密钥等同于账户凭证。不要提交进任何仓库、不要写进截图或
聊天记录；生产环境建议改从环境变量读取（见正文第 26 章）。
"""

# ═══════════════ 在下面填入你的配置 ═══════════════

API_KEY  = ""    # 必填：你的 API 密钥，例如 "sk-xxxxxxxx"

BASE_URL = ""    # 必填：OpenAI 兼容接口地址，例如 "https://api.openai.com/v1"（见上方对照表）

MODEL    = ""    # 必填：模型名，例如 "gpt-4o-mini"、"deepseek-chat"、"glm-4-flash"
# ═══════════════ 填到这里为止 ═══════════════

# 以下为可选：某些章节实验需要第二把"裁判"钥匙（第 20 章 LLM-as-judge 交叉验证）
# 不填则自动复用上面的主配置。
JUDGE_API_KEY  = ""
JUDGE_BASE_URL = ""
JUDGE_MODEL    = ""
