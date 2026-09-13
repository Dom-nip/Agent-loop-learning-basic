# stage02 · Function Calling —— 工具协议下沉为基础设施

> 第一幕 · 可运行（2/3）。同一个 agent（stage01 的循环保持原样），把文本协议换成
> **API 级结构化调用**——这是 2023 年 6 月 OpenAI 发布 Function Calling 之后，
> 整个行业一次性完成的迁移。

## 1. 本阶段目标

**使"模型如何调用工具"从 prompt 工程变为 API 合同**：工具说明书（JSON Schema）
作为 `tools` 参数随请求发送，模型以结构化 `tool_calls` 字段返回调用意图——
解析器、格式修复提示这些 stage01 的"协议税"从此消失。

## 2. 前置知识

| 来源 | 内容 |
|---|---|
| stage01 | ReAct 循环形状、文本协议的脆弱性（本 stage 针对其缺陷而设计） |
| 正文第 3 章 | 文本协议 → Function Calling 的完整演进、解析失败率数据 |
| 正文第 11 章 | description 三原则（本 stage 的 schema 写法直接受益） |

## 3. 原理与设计决策

**协议下沉换来了什么？**

| stage01（文本协议） | stage02（Function Calling） |
|---|---|
| 格式规则写进 system prompt，每轮重发 | schema 走 API 参数，由服务商侧注入训练分布 |
| 正则解析 Action 行，失败率随轮数上升 | SDK 直接给 `message.tool_calls` 结构体 |
| JSON 转义靠模型自觉，含引号内容频繁出错 | arguments 是独立 JSON 字段，引号无须模型操心 |
| 格式错误 → 回传规则重试（纯协议税） | schema 校验失败 → 错误作为 tool result 喂回（repair loop 只管内容） |

**本 stage 的关键实现决策：**

1. **schema 与实现同源**（`tools.py` 的 `Tool` 类）：description、parameters、run
   写在同一个对象里。接口文档漂移是工具层的首要风险——同源设计使一处定义
   服务于三处使用（API 参数、校验、执行）。
2. **description 按三原则写**：何时不用（"只用于读小文件"）、参数语义、失败先验。
   stage01 的工具说明面向开发者自身；自本 stage 起，它是面向模型的接口合同。
3. **自建极简校验器**（`schema.py`）：type/required/enum/items 四件事够了，
   零依赖。校验失败**不执行**，把错误列表渲染成修复指令当 tool result 喂回——
   模型下一轮自己改。这是 repair loop（修复循环）在结构化时代的形态。
4. **tool_choice 三模式做进交互**（`/mode` 命令）：`auto`（模型自主）、`required`
   （强制至少一次调用）、`none`（彻底不传 tools）。这是调试与评测时最常用的
   三个开关。
5. **并行工具调用**：一条 assistant 消息可携带多个 tool_calls，harness 依次执行、
   逐个以 `role="tool"` 回填。减少往返轮次即降低延迟与成本。
6. **system prompt 精简**：工具说明书移出 system prompt 后，此处仅保留身份、
   边界、语言三件事——为 stage03 的上下文分区做好铺垫。

## 4. 运行方式

```bash
cd loop-engineering/stage02_function_calling
pip install -r requirements.txt
# 填仓库根目录 config.py 三行后：
python src/main.py
```

示例交互（节选，完整见 `examples/transcript.md`）：

```
你> 建两个文件：a.txt 写 hello，b.txt 写 world
┌─ 任务：建两个文件：a.txt 写 hello，b.txt 写 world   [tool_choice=auto]
│ [turn 1] 🔧 write_file({"path": "a.txt", "content": "hello"})
│           → 已写入 workspace/a.txt（5 字符）
│           🔧 write_file({"path": "b.txt", "content": "world"})
│           → 已写入 workspace/b.txt（5 字符）
│ [turn 2] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
两个文件已创建完成……
```

## 5. 观察点

- **并行调用**：让模型一次处理两件不相关的事，观察是否一条消息携带两个
  tool_calls（轮次从 4 降到 2）。
- **repair loop**：临时把某个参数改成 `required` 但 description 含糊，观察校验
  失败 → 喂回 → 自我修正的全过程（`/stats` 里 repairs 计数）。
- **`/mode required`**：问一个不需要工具的问题（"1+1 等于几"），模型被迫产生
  一次调用——强制约束会扭曲模型行为，这正是它适合作调试工具而非生产默认值
  的原因。
- **`/mode none`**：同一问题让它纯文本回答——与 stage01 的行为对照，理解
  "工具可用性"本身就是一种上下文信息。
- **枚举参数**：本 stage 未内置 enum 工具；可为 list_dir 增加 `sort_by` 枚举
  参数并检验模型是否遵守——枚举是最易被模型违反的约束。

## 6. 设计权衡

| 优势 | 代价 |
|---|---|
| 解析税归零，失败率大幅下降（第 3 章数据） | 依赖服务商实现质量（各家 schema 遵守度参差） |
| schema 校验可程序化，repair loop 只管内容 | 多工具（50+）时 tools 参数本身消耗 token |
| 并行调用降低轮次与延迟 | 不同能力模型的遵守度差异大，需评测（stage11） |
| 工具说明书与代码同源，不漂移 | 工具数量一多，选错率上升（stage10 渐进披露解） |

## 7. 同期竞争方案的淘汰原因

- **文本协议 patch 库**（stage01 时代的延续）：社区为 ReAct 解析器积累了大量
  补丁（容错正则、few-shot 修复示例、重试上限）。Function Calling 发布后，
  这些补丁库迅速过时——**在 API 层解决的问题不该在 prompt 层修**。
- **纯 JSON mode**：`response_format={"type": "json_object"}` 保证输出是合法
  JSON，但不保证是"哪个工具的合法参数"——工具选择与参数结构仍要自己在
  prompt 里约定、自己解析分发。它是 function calling 普及前的过渡方案，
  如今仅用于"模型不支持 tools 参数"的兼容场景。
- **微调专用工具模型**：为自家工具集微调调用能力，被通用模型的 tools 接口
  取代——更新工具集从"重新训练"变为"修改一个 JSON"。

## 8. 与下一个 stage 的衔接

stage02 解决了"怎么调"，但没解决"调多少次上下文装得下"：tools 参数、多轮
tool results、长文件内容都在持续占用 context window（上下文窗口）。stage03
开始上下文工程：token 记账、工具结果截断、历史压缩、上下文分区——**协议稳定
之后，上下文成为新的胜负手**。
