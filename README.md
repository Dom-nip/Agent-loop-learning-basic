# Agent 开发教程

This tutorial was developed with GLM-5.3-Flash, and its main content is originally written by GLM-5.3-Flash. The special-issue sections reproduce publicly available material from Anthropic and OpenAI; the accompanying commentaries are original to this project. The tutorial inevitably contains imperfections and is intended solely for personal learning, as supplementary material for foundational agent development.

> 一份以「问题驱动」为主线的 Agent 开发教程

Agent 技术是**由一连串公开失败累积而成**：AutoGPT 的失败确立了 agent loop 的基本形态；LangChain 因过度抽象受到的批评促成了"裸 API 优先"的工程共识；多智能体"AI 软件公司"的失败留下了 subagent 上下文隔离模式。不理解这些失败，便难以理解当前各项"理所当然"的设计为何如此。

---

## 快速开始

```bash
# 1. 阅读：直接打开 chapters/book.md
#    工程一手文献 → chapters/special-issue-openai-anthropic-engineering/README.md
#    动手实践     → loop-engineering/README.md，从任一 stage 开始

# 2. 环境要求：Python ≥ 3.8（开发实测环境为 Python 3.13）
#    安装依赖：
pip install -r requirements.txt          # openai 必需；PyYAML 供 stage11、mcp 供第 17 章（可选）

# 3. 配置：
#    复制 config.example.py 为 config.py 并填写三项（兼容任何 OpenAI 兼容服务）
#    API_KEY  = "sk-..."            # 生产环境应改为从环境变量读取
#    BASE_URL = "https://api.openai.com/v1"   # 或 DeepSeek/智谱/第三方代理/本地 vLLM
#    MODEL    = "gpt-4o-mini"

# 4. 运行（交互式多轮对话）：
cd loop-engineering/stage01_react_text_protocol
python src/main.py
```


## 仓库结构

```
├── README.md                ← 本文件
├── config.example.py        ← 配置模板：复制为 config.py 后填写（不含密钥）
├── config.py                ← 本地配置（已被 .gitignore 排除，不会上传）
├── common.py                ← 正文示教代码与实战册引用的共享工具：统一 chat()、token 粗估、沙盒执行器
├── requirements.txt         ← openai 必需；mcp 可选（第 17 章 MCP 演示需要）
├── chapters/
│   ├── book.md              ← 全书唯一正文档案：00 术语表 + 26 章正文 + 99 文献汇编
│   ├── images/              ← book.md 配图（34 张程序图）
│   └── special-issue-openai-anthropic-engineering/
│       ├── README.md            ← 导览：四组主题、两家共识与分歧、范式对照表
│       ├── commentary_figures/  ← 14 篇述评配图（28 张程序图）
│       └── 01…14 每篇一个文件夹 = original.md（英文全文）+ original.pdf + commentary.md（中文文献述评）
│                                    （8 篇另含 images/，为回填的原文插图）
├── loop-engineering/        ← 独立实战册：12 个 stage，从 ReAct 到 harness（见下文）
```

---

# 阅读指南

正文为单一档案 [chapters/book.md](./chapters/book.md)（自带全书目录，编辑器大纲可直接跳章）。以下按部分给出导读，链接直达正文中对应章节。

### 第零部分 · 手册（00 / 99）

| 册                                                                | 用途                                                                                |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| [00 术语表与缩略语](./chapters/book.md#00--术语表与缩略语glossary) | 108 条中英对照术语 + 发展时间线（2017→2026）——正文中术语标注存疑时可返回此处检索 |
| [99 参考文献与延伸阅读](./chapters/book.md#99--参考文献与延伸阅读) | 各章文献按十大主题汇编，供系统检索回溯                                              |

### 第一部分 · 认知地基（01-04）：Agent 从哪来

| 章节                                                                                                      | 回答的问题                       | 关键词                                        |
| --------------------------------------------------------------------------------------------------------- | -------------------------------- | --------------------------------------------- |
| [01 什么是 Agent](./chapters/book.md#01--什么是-agent为什么不是带插件的聊天机器人)                         | 与聊天机器人的本质区别是什么     | 循环、工具、workflow vs agent、自主性连续谱   |
| [02 ReAct：一切的原点](./chapters/book.md#02--react一切的原点)                                             | 模型如何学会"边想边做"           | 思考-行动-观察、轨迹格式漂移、Toolformer 败因 |
| [03 工具调用：从文本协议到 Function Calling](./chapters/book.md#03--工具调用从文本协议到-function-calling) | 调工具为什么变成 API 参数        | 文本协议、Function Calling、工具调用的契约观  |
| [04 AutoGPT：第一次自主浪潮的兴衰](./chapters/book.md#04--autogpt第一次自主浪潮的兴衰)                     | 最受瞩目的自主智能体为何迅速衰落 | AutoGPT 循环解剖、五大失败模式、错误级联      |

### 第二部分 · 路线之争（05-08）：组件如何选型

| 章节                                                                                                                | 回答的问题                    | 关键词                                          |
| ------------------------------------------------------------------------------------------------------------------- | ----------------------------- | ----------------------------------------------- |
| [05 记忆之争：RAG、长上下文与外部记忆](./chapters/book.md#05--记忆之争rag长上下文与外部记忆)                         | Agent 应如何实现记忆          | RAG、长上下文与外部记忆的分层取舍、"RAG 已死"论 |
| [06 框架大战与过度抽象](./chapters/book.md#06--框架大战与过度抽象)                                                   | 是否应使用 LangChain 这类框架 | 抽象税、框架厚度与模型能力成反比、裸 API 优先   |
| [07 多 Agent：从&#34;AI 软件公司&#34;到 subagent 隔离](./chapters/book.md#07--多-agent从ai-软件公司到-subagent-隔离) | 多 Agent 协作是否属于伪需求   | 「AI 软件公司」的失败、多 Agent 拓扑、一票判据  |
| [08 代码 Agent 与评测驱动](./chapters/book.md#08--代码-agent-与评测驱动agent-真正落地的第一站)                       | 代码 Agent 为何率先落地       | SWE-bench、Devin 教训、端到端通过率             |

### 第三部分 · 收敛（09）：行业祛魅

| 章节                                                                            | 回答的问题            | 关键词                                  |
| ------------------------------------------------------------------------------- | --------------------- | --------------------------------------- |
| [09 收敛：五种模式与简单性信条](./chapters/book.md#09--收敛五种模式与简单性信条) | 行业如何对 Agent 祛魅 | 五种积木的最小实现、workflow/agent 分界 |

### 第四部分 · 上下文工程六部曲（10-15）：2025 年的胜负手

| 章节                                                                                                                       | 回答的问题                   | 关键词                                        |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------- | --------------------------------------------- |
| [10 上下文工程 I：Context Rot 与注意力预算](./chapters/book.md#10--上下文工程-icontext-rot-与注意力预算attention-budget)    | 上下文过载为何损害模型性能   | Context Rot、注意力预算、上下文窗口的构成解剖 |
| [11 上下文工程 II：宪法式系统提示与工具层治理](./chapters/book.md#11--上下文工程-ii宪法式系统提示system-prompt与工具层治理) | 进入窗口前如何设防           | 宪法式系统提示、源头截断、工具层治理          |
| [12 上下文工程 III：压缩、笔记与文件系统记忆](./chapters/book.md#12--上下文工程-iii压缩笔记与文件系统记忆)                  | 窗口临近上限时如何治理       | 压缩与结构化笔记、KV 缓存经济学、文件系统记忆 |
| [13 上下文工程 IV：长期记忆与文件系统](./chapters/book.md#13--上下文工程-iv长期记忆与文件系统)                              | 会话结束后靠何种机制维持记忆 | 三层记忆、记忆的沉淀与遗忘、跨会话桥接        |
| [14 上下文工程 V：Agent Skills 与渐进式披露](./chapters/book.md#14--上下文工程-vagent-skills-与渐进式披露)                  | 领域知识放哪里               | Agent Skills、渐进式披露、SKILL.md 三层加载   |
| [15 上下文工程 VI：Sub-agent 与并行隔离](./chapters/book.md#15--上下文工程-visub-agent-与并行上下文隔离的工程学)            | 上下文的空间减法             | Sub-agent 并行隔离、干净上下文、任务包结构    |

### 第五部分 · 多智能体编排（16）：从概念到工程

| 章节                                                                                                                      | 回答的问题             | 关键词                                                      |
| ------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ----------------------------------------------------------- |
| [16 多智能体编排实战：任务分解、分派与并行回收](./chapters/book.md#16--多智能体编排实战任务分解分派与并行编排闭环的工程学) | 编排闭环如何工程化落地 | 分解校验器、ThreadPoolExecutor 并行、合成器、LangGraph 参照 |

### 第六部分 · 基础设施（17-18）：协议层

| 章节                                                                                | 回答的问题                   | 关键词                                   |
| ----------------------------------------------------------------------------------- | ---------------------------- | ---------------------------------------- |
| [17 协议层 I：MCP 深入](./chapters/book.md#17--协议层-imcp-深入)                     | 工具生态为何需要统一接入协议 | MCP 架构与握手、安全五攻击面、传输层演进 |
| [18 协议层 II：A2A 与完整协议栈](./chapters/book.md#18--协议层-iia2a-与完整的协议栈) | Agent 之间如何协作           | A2A 任务生命周期、Agent Card、四层协议栈 |

### 第七部分 · 模型与架构（19-22）：回到能力本身

| 章节                                                                                                                  | 回答的问题                   | 关键词                                     |
| --------------------------------------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------------------ |
| [19 推理模型：思考被内化之后](./chapters/book.md#19--推理模型agent-的思考被内化之后)                                   | o1/R1 改变了什么             | 测试时计算、思考预算、成本-质量-延迟三角   |
| [20 长时程任务：Deep Research 与 GUI 兜底](./chapters/book.md#20--长时程任务deep-research-的解剖与图形用户界面gui兜底) | 全自主长时程愿景为何二次兴起 | Deep Research 流水线、四因素乘积、GUI 兜底 |
| [21 2026 标准架构：七层全景与最小实现](./chapters/book.md#21--2026-年的标准架构七层全景与最小实现)                     | 当前的生产系统呈现何种形态   | 七层参考架构、最小实现、agent loop         |
| [22 评测驱动开发：给 Agent 建立质量体系](./chapters/book.md#22--评测驱动开发给-agent-建立质量体系)                     | 智能体质量保障体系如何构建   | 评测驱动开发、模型裁判、回归门与产品指标   |

### 第八部分 · 底线与生产化（23-26）：让它长期活着

| 章节                                                                                          | 回答的问题                 | 关键词                                                |
| --------------------------------------------------------------------------------------------- | -------------------------- | ----------------------------------------------------- |
| [23 Agent 安全：注入攻击与权限治理](./chapters/book.md#23--agent-安全注入攻击与权限治理)       | 攻击面为何转移到行为层     | 提示注入、通道清洗与权限治理、纵深防御                |
| [24 生产化可靠性：重试、降级与可观测性](./chapters/book.md#24--生产化可靠性重试降级与可观测性) | 原型如何演进为可上线系统   | 重试与退避、幂等与超时预算、可观测性                  |
| [25 服务化与持久化执行](./chapters/book.md#25--服务化与持久化执行把-agent-脚本变成可上线服务)  | 脚本形态如何演进为在线服务 | 检查点与恢复、持久化执行、LangGraph checkpointer 对照 |
| [26 治理：密钥、模型版本、成本与合规](./chapters/book.md#26--治理密钥模型版本成本与合规)       | 运维事故如何沉淀为工程纪律 | 密钥治理与扫描、版本治理与金丝雀、模型路由与成本工程  |

---

## 主线逻辑：演进脉络总览

```
问题：LLM 仅能生成文本——不能行动、不能多步推理、不能记忆
  │
  ├─ 如何使模型行动？ ─────────► ReAct 循环(02) → Function Calling(03)
  │
  ├─ 如何使其自主运行？ ───────► AutoGPT 全自主(04) → 失败 → 受约束循环+人机协作(08)
  │
  ├─ 如何赋予模型记忆？ ───────► RAG/长上下文/记忆系统的分层混合(05)
  │                            跨会话记忆(13)：写入-读取-遗忘三动作
  ├─ 如何组织复杂任务？ ──────► 框架(06)→过度抽象→回归简单代码
  │                            多 Agent(07)→传递损耗→orchestrator-worker
  ├─ 如何保障长任务质量？ ────► 上下文工程六部曲(10-15)：宪法/治理/压缩/
  │                            长期记忆/Skills/subagent 隔离
  ├─ 如何编排多 Agent？ ──────► 分解→分派→并行→回收→合成→验收(16)
  │                            框架参照：LangGraph StateGraph/checkpointer
  ├─ 如何接入协议生态？ ──────► MCP(17) → A2A(18) → 四层协议栈
  ├─ 如何守住底线？ ──────────► 安全与真隔离(23)；可靠性(24)
  │                            服务化与持久化执行(25)；治理三支柱(26)
  └─ 如何使质量可度量？ ──────► 评测驱动开发(22)：evals 先于智能；
                               产品指标与漂移金丝雀(22/26)
```

每一条分支的终点，均是某条更激进的路线失败之后沉淀下来的最小可行方案。逐年的分水岭事件见 [00 术语表 · 发展时间线](./chapters/book.md#00--术语表与缩略语glossary)；完整文献见 [99 参考文献与延伸阅读](./chapters/book.md#99--参考文献与延伸阅读)。

---

## 特别篇：OpenAI 与 Anthropic 的工程范式

主册论述"行业为何如此演进"，特别篇呈现"两大前沿实验室的一手工程文献"：
14 篇文献（2024-12 → 2026-03），范围从《Building Effective Agents》的五种工作流模式，
至 2026 年的 harness 工程前沿（Anthropic 长时程 harness 系列、OpenAI 零手写代码约束实验）。

---

## loop-engineering 实战册：12 个可交互运行的智能体项目

主册

实战册演示**如何实现**：12 个
**完全独立**的 stage 项目，从ReAct 文本协议到七层完整 harness，
每个 stage 都是可通过 `python src/main.py` 启动交互式对话的真实 agent 工程。

```
loop-engineering/
├── README.md                       ← 总教程：叙事四幕演进史 + 附录 A 决策树 + 附录 B 历史失败模式对照表
├── stage01_react_text_protocol/    ← 第一幕·可运行
├── stage02_function_calling/
├── stage03_context_engineering/
├── stage04_memory_filesystem/      ← 第二幕·可控
├── stage05_subagent/
├── stage06_loop_control/
├── stage07_guardrails_security/    ← 第三幕·可靠
├── stage08_observability/
├── stage09_long_running/
├── stage10_skill_mcp/              ← 第四幕·可扩展
├── stage11_eval_harness/
└── stage12_full_harness/           ← capstone：七层架构收官
```

| 幕 | Stage                  | 核心内容                                        | 教程锚点（book.md） |
| -- | ---------------------- | ----------------------------------------------- | ------------------- |
| 一 | 01_react_text_protocol | Thought/Action/Observation 文本协议 while 循环  | 第 02、04 章        |
| 一 | 02_function_calling    | 结构化工具调用、schema 校验-重试、并行调用      | 第 03 章            |
| 一 | 03_context_engineering | token 记账、工具结果截断、分区、阈值压缩        | 第 10-12 章         |
| 二 | 04_memory_filesystem   | 三层记忆、MEMORY.md、会话沉淀与读回             | 第 13 章            |
| 二 | 05_subagent            | 任务包五要素、并行隔离、fan-in 合成             | 第 07、15、16 章    |
| 二 | 06_loop_control        | max_turns/预算、危险确认门、stall 检测、短计划  | 第 04、09、21 章    |
| 三 | 07_guardrails_security | 通道清洗、三态权限、命令黑名单、审计日志        | 第 23 章            |
| 三 | 08_observability       | Span 轨迹树、成本计量、JSONL、回放              | 第 22、24 章        |
| 三 | 09_long_running        | 检查点崩溃恢复、异步任务队列、取消传播          | 第 20、25 章        |
| 四 | 10_skill_mcp           | SKILL.md 三层披露、最小 MCP stdio client/server | 第 14、17 章        |
| 四 | 11_eval_harness        | YAML 用例集、程序判分+LLM 裁判、回归、CI 门槛   | 第 08、22 章        |
| 四 | 12_full_harness        | 七层架构 capstone（集成以上全部机制）           | 第 21 章            |

**运行方法**（每个 stage 自包含，可从任意一个开始）：

```bash
cd loop-engineering/stage01_react_text_protocol
pip install -r requirements.txt
# 填根目录 config.py 三行
python src/main.py        # 进入交互式多轮对话
```

---

## 配置与密钥安全

- **`config.py`**：请从模板复制（`cp config.example.py config.py`）后填写三项配置。
  三项全部留空时程序不崩溃：需要调用模型的入口会打印配置指引并跳过，纯本地实验照常运行。

## 版权与免责声明

- **特别篇文献存档**：`chapters/special-issue-openai-anthropic-engineering/` 下的
  `original.md` 与 `original.pdf` 为 OpenAI / Anthropic 官方文章与报告的全文转载存档，
  **版权归原作者及相关权利方所有**。收录仅为个人学习与研究目的，并保留原文出处、作者
  与检索日期；如权利方认为不妥，请提交 issue，经确认后即移除相应内容。引用观点请回溯原文链接。
- **本仓库其余内容**（`chapters/book.md`、各篇 `commentary.md` 述评、`loop-engineering/`
  实战册代码、各 README）为本项目原创，**保留所有权利**：未附开源许可，
  默认适用版权法保护，转载或商用请先取得作者同意；学习与研究目的的个人使用不受限。
