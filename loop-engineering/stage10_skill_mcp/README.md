# stage10 · Skill 与 MCP —— 能力按需加载 + 工具跨进程接入

> 第四幕 · 可扩展（1/3）。前九个 stage 将单 agent 打磨完整，本 stage 处理
> "规模化"的两个瓶颈：**知识增多后 prompt 无法容纳**（Skill 渐进披露）与
> **工具增多后宿主无法承载**（MCP 协议）。二者均为 2025 年确立的行业标准。

## 1. 本阶段目标

**掌握两个能力生态标准**：
- Agent Skills：SKILL.md 三层渐进式披露——元数据常驻、正文按需、参考深读；
- MCP（Model Context Protocol）：最小 stdio client/server，工具跨进程
  标准化接入，宿主对第三方工具零实现成本。

## 2. 前置知识

| 来源 | 内容 |
|---|---|
| 正文第 14 章 | 三层加载的 token 账本、Anthropic Skills 设计 |
| 正文第 17 章 | MCP 的 USB-C 类比、五个攻击面 |
| stage02 | tools 参数的 JSON Schema（MCP 的 inputSchema 与它同构） |

## 3. 原理与设计决策

**组件一：三层渐进披露（`skills.py` + `skills/*/SKILL.md`）**

| 层 | 内容 | 加载时机 | token 量级 |
|---|---|---|---|
| 一 | frontmatter 的 name + description | 常驻 system prompt | ~50/技能 |
| 二 | SKILL.md 正文 | 模型调 load_skill | 几百 |
| 三 | references/*.md | 正文指路，模型调 read_skill_ref | 更深 |

关键决策：
- **元数据里写清"何时加载"**（"用户要求清洗数据时加载"）——模型依靠它
  判断是否需要，这条描述的质量直接决定技能的命中率；
- **正文里显式指路第三层**（"更细的边界案例见参考文件"）——渐进披露
  的每一层都要为下一层留入口；
- **只用正则解析 frontmatter**，不引 yaml 依赖——教学实现保持零强依赖。

**组件二：MCP stdio 最小实现（`mcp_server.py` / `mcp_client.py`）**

- JSON-RPC 2.0 over stdio，三个方法：`initialize`（握手）/ `tools/list` /
  `tools/call`。这是 MCP 协议的教学子集（官方还有 resources/prompts/
  通知与 `mcp` SDK，见第 17 章）；
- server 是**独立进程**：崩溃隔离（server 崩溃不影响宿主存活）、语言无关
  （任何语言编写的 server 都能接入）、权限边界清晰（工具代码不在宿主内
  运行）；
- **桥接层**（`tools.py` 的 `bridge_mcp_tools`）：把 server 的
  inputSchema 直接转成宿主 Tool——宿主没有为 MCP 工具编写一行实现。
  这就是 M×N 困境（M 个宿主 × N 个工具的私有集成）的解法：协议双方
  各只需实现一次。

## 4. 运行方式

```bash
cd loop-engineering/stage10_skill_mcp
pip install -r requirements.txt
# 填仓库根目录 config.py 三行后：
python src/main.py
```

```
✅ 技能元数据已注入（第一层）：
   - data-cleanup: 清洗与整理 CSV/文本数据集时使用。……
   - weekly-report: 撰写规范周报时使用。……
✅ MCP 工具已桥接：['mcp_word_count', 'mcp_now']

你> 帮我写本周周报：完成订单导出功能、修复了3个线上bug、下周做性能优化
│ [turn 1] 🔧 load_skill({"name": "weekly-report"})   ← 先读指南再动笔
│ [turn 2] 🔧 read_skill_ref({"skill": "weekly-report",
│            "filename": "style-guide.md"})           ← 深读范例
│ [turn 3] 💬（按模板输出周报）
└─ ✅ Final Answer:
**本周结论**：订单导出上线，线上稳定性修复完毕。……
```

完整示例见 `examples/transcript.md`。

## 5. 观察点

- **load_skill 的触发**：不提"周报"只说"帮我写本周总结"，它是否加载？
  元数据的 description 写"周报/周总结/进展汇报"正是为此。
- **第三层是否被读**：写完周报后它读取 style-guide 了吗？读取参考文件
  说明正文里的指路生效——三层缺一层就断链。
- **token 账本对比**：/skills 查看元数据（~100 token 常驻）；手动加载两个
  技能全文对比（~4000 token）——技能越多差距指数级扩大。
- **MCP 透明性**：从对话看，模型完全不知道 mcp_word_count 来自另一个
  进程——桥接的抽象是完整的。
- **server 隔离**：手动终止 server 进程，再调用 MCP 工具观察宿主反应
  （本教学版会报错返回；生产版应自动重启 server）。

## 6. 设计权衡

| 优势 | 代价 |
|---|---|
| 知识成本从 O(全量) 降到 O(元数据) + O(用到) | 模型可能该加载时不加载（元数据质量决定） |
| 技能即文件：可 git、可分享、可人工审 | 三层设计要维护一致性（正文与参考不同步） |
| 工具跨进程：隔离、语言无关、即插即用 | stdio 往返有延迟（本机 ~1ms，可忽略） |
| MCP 一次实现，任意 server 接入 | 教学子集不含 resources/prompts/鉴权 |

## 7. 同期竞争方案的淘汰原因

- **全量塞 prompt**（"反正窗口大"）：每个领域的全部知识都常驻。成本尚在
  其次，更严重的是知识相互干扰——写作指南与清洗规则同时在场时，模型
  可能在撰写周报的过程中混入"先探查再动手"的清洗流程话术。知识按需
  加载同时解决了成本与干扰两类问题。
- **RAG 当知识管理**：检索适合"找事实"，不适合承载"程序性知识"——
  周报结构、清洗红线这类知识是整份使用的，切片检索反而将其切碎。
  Skills 的单位是"技能"（完整文档），不是"片段"。
- **M×N 私有集成**（每个宿主为每个工具写适配器）：OpenAI/Anthropic/
  各家 agent 框架各自定义工具格式，工具开发者要维护 N 份适配。MCP
  把 N 降到 1（工具方实现一次 server），M 降到 1（宿主实现一次
  client）——其胜出并非源于技术优越性，而是同时大幅压低了双方的成本
  曲线。
- **Function Calling 即生态**（把"注册进我家的工具列表"当生态位）：
  工具与宿主绑定（失败模式 #18），更换宿主需全部重写。MCP 使工具归属于
  中立的第三方协议。

## 8. 与下一个 stage 的衔接

能力生态解决了"可扩展"，但规模化的系统如何**保证质量**？stage11
（eval harness）把测试用例集、程序判分、LLM-as-judge、回归对比、
CI 门槛做成一个可运行的最小评测体系——评测先于迭代。
