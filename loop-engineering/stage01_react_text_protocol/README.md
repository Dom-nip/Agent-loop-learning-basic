# stage01 · ReAct 文本协议 —— 最小可用的 agent loop

> 第一幕 · 可运行（1/3）。这是全书实战册的起点：一个用**纯文本协议**驱动工具的 agent，
> 大约 300 行 Python。之后 11 个 stage 的所有机制，都是为了修补它暴露出来的问题。

## 1. 本阶段目标

**使一个 while 循环具备"边想边做"的能力**：模型在循环里写出 Thought（思考）→
Action（调用哪个工具）→ 等待 Observation（工具结果），直到它认为可以给出
Final Answer。这就是 ReAct（Reasoning + Acting）模式，2022 年提出、至今仍是
几乎所有 agent harness 的骨架。

## 2. 前置知识

| 来源 | 内容 |
|---|---|
| 正文第 2 章 | ReAct 的提出背景、格式漂移问题、Toolformer 败因 |
| 正文第 4 章 | 无界循环的灾难（本 stage 已埋下 max_turns 兜底） |
| 前序 stage | 无——这是起点 |

## 3. 原理与设计决策

**为什么行动必须与推理交织？** 单纯 Chain-of-Thought（思维链）只能"想"，想法对不对
没有现实校验；单纯行动（直接输出工具调用）又没有"想"的缓冲。ReAct 要求每一步
行动前先落一个 Thought，即强制模型显式声明其行动依据——既提升单步质量，也为
调试保留第一现场。

**本 stage 的关键实现决策：**

1. **协议即 system prompt**（`protocol.py`）：格式规则（三行式）+ 工具说明书，每次
   请求都随历史发给模型。协议的定义、解析与违规处置三段逻辑都写在这一个文件里。
2. **Action Input 用 JSON**：原版 ReAct 用自由文本参数，实践中很快发现写文件这类
   多参数工具无法表达，于是退到"单行 JSON 对象"。这一妥协正是文本协议
   开始失效的第一个缺口——stage02 将以 Function Calling 从协议层面消除该问题。
3. **解析失败 → 修复重试，而不是崩溃**（`protocol.py` 的 `REPAIR_HINTS`）：模型忘了
   写 Action 行、或 JSON 没写对时，harness 将规则以修复提示的形式回传，要求模型
   重新生成。这一"修理循环"是文本协议时代最重要的工程发明之一，也是 token
   成本中第一笔"纯协议税"。
4. **一切工具结果都是 Observation 字符串**：成功是结果、错误也是结果——错误信息
   作为 Observation 回传、由模型自行调整，优于以异常终止循环。
5. **append-only 历史**：assistant 原文和 Observation 都只追加、不修改。stage03 会
   讲为什么改动历史会摧毁 prompt cache 和行为一致性。
6. **有界循环**：`max_turns=15` 触顶强制停止。这个参数在 stage06 会升级为完整的
   循环控制体系，但该约束自第一个循环起就必须存在。

**目录结构：**

```
stage01_react_text_protocol/
├── src/                    # 代码目录（API 配置统一放仓库根目录 config.py）
│   ├── main.py             # 交互入口：python src/main.py
│   ├── agent.py            # ReAct 循环核心（本 stage 的核心模块）
│   ├── llm.py              # OpenAI 兼容客户端封装
│   ├── protocol.py         # 文本协议：立法/解析/修复
│   └── tools/              # read_file / write_file / list_dir / run_python
├── workspace/              # agent 的沙盒工作区（文件工具只许碰这里）
└── examples/transcript.md  # 一段真实示例会话
```

## 4. 运行方式

```bash
cd loop-engineering/stage01_react_text_protocol
pip install -r requirements.txt        # 只有 openai
# 1) 填仓库根目录 config.py 三行（API_KEY / BASE_URL / MODEL，全部 stage 通用）
# 2) 启动
python src/main.py
```

示例交互（节选，完整见 `examples/transcript.md`）：

```
你> 在 workspace 里建一个 todo.md，写上三件今天要做的事
┌─ 任务：在 workspace 里建一个 todo.md，写上三件今天要做的事
│ [turn 1] Thought: 需要创建文件，使用 write_file 工具
│           Action: write_file  Input: {'path': 'todo.md', 'content': '...'}
│           Observation: 已写入 workspace/todo.md（58 字符）
│ [turn 2] Thought: 文件已写好，可以收尾了
└─ ✅ Final Answer:
已在 workspace/todo.md 写入三件待办事项……
```

## 5. 观察点

- **Thought 的质量**：格式强制下的"想"是否构成真实推理，还是模板化措辞？
  （第 19 章：推理模型会把这层显式思考内化）
- **协议税**：统计每个任务消耗的轮数，以及其中用于"格式修正"的比例——
  这是文本协议的真实成本。
- **JSON 转义崩溃**：构造一段含引号的写入任务，观察 `bad_json` 修复重试是否触发。
- **长任务格式漂移**：连续 10+ 轮后，模型开始跳过 Thought 行或虚构 Observation
  ——第 2 章所述的"格式漂移"将再次出现。
- **`/history` 看消息数**：历史线性膨胀，为 stage03 的上下文工程埋下伏笔。

## 6. 设计权衡

| 优势 | 代价 |
|---|---|
| 零特殊 API，任何聊天模型均可运行 | 解析脆弱：格式漂移、JSON 转义、虚构 Observation |
| Thought 显式可见，调试直观 | 每轮都要重发协议说明（token 税） |
| 约 300 行实现全部核心机制 | 多参数工具表达受限（JSON 需嵌入文本行） |
| 协议可自由定制（仅需修改 prompt） | 修复重试产生额外成本，失败率随工具数上升 |

## 7. 同期竞争方案的淘汰原因

- **纯 Chain-of-Thought（无行动）**：推理再充分也缺乏事实校验，幻觉无法被外部
  反馈纠正。其被淘汰的原因不是推理质量不足，而是缺失外部反馈回路。
- **AutoGPT 式预规划再执行**：先让模型产出完整计划再逐步执行，形式上更
  "工程化"，但计划与现实的偏差无从修正——位列第 4 章五大失败模式之首。
  ReAct 以"每步都对照现实校验"最终胜出，而 AutoGPT 的教训（无界循环、
  无验证）也反过来催生了本 stage 的 `max_turns` 与 stage06 的完整循环控制。
- **微调模型内化工具调用（Toolformer 路线）**：为每个工具微调的成本高、
  更新慢，被通用模型的工具调用接口（stage02）取代。但其核心洞察——模型
  可以自行学会何时调用何种工具——被 Function Calling 的训练目标继承。

## 8. 与下一个 stage 的衔接

stage02 移除以下两项，代之以更严格的协议：

1. `protocol.py` 整个消失——Action/Action Input 变成 API 的 `tools` 参数与
   `tool_calls` 返回值；
2. `REPAIR_HINTS` 换成 schema 校验-重试（repair loop 只管参数内容，不再管格式）。

agent.py 的循环形状不变：**循环结构保持稳定，协议层可整体替换**——这是本 stage 旨在
呈现的核心事实。
