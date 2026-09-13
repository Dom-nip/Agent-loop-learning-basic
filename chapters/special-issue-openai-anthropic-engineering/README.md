# 特别篇 · OpenAI 与 Anthropic 的工程范式

> 主册论述"今日 Agent 形态的由来"，本特别篇收录并以文献述评体评析**两大前沿实验室署名发布的工程文献群**——
> 它们既是模型供给方，又是工程方法论的输出方。

## 导读：四组主题，按需检索

| 组                                 | 主题       | 文献                                                                                                                                                                                                                                                                                                                                                                                                                                                     | 回答的问题                                                     |
| ---------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| **一 · 范式总纲**           | 方法论立场 | [01](./01-anthropic-building-effective-agents/commentary.md) Building Effective Agents（Anthropic, 2024-12）· [02](./02-openai-practical-guide-building-agents/commentary.md) A Practical Guide to Building Agents（OpenAI, 2025-01）                                                                                                                                                                                                                     | agent/workflow 的边界何在？何时应引入多 agent？                |
| **二 · 上下文、工具与技能** | 工程实现   | [03](./03-anthropic-context-engineering/commentary.md) Context Engineering（2025-09）· [04](./04-anthropic-writing-effective-tools/commentary.md) Writing Effective Tools（2025-09）· [05](./05-anthropic-agent-skills/commentary.md) Agent Skills（2025-10）· [06](./06-anthropic-claude-code-best-practices/commentary.md) Claude Code Best Practices（2025-04）· [07](./07-openai-gpt5-prompting-guide/commentary.md) GPT-5 Prompting Guide（2025-08） | 上下文预算如何治理？工具如何设计？知识如何存放？提示如何演进？ |
| **三 · 编排与多智能体**     | 协作编排   | [08](./08-anthropic-multi-agent-research-system/commentary.md) Multi-Agent Research System（2025-06）· [09](./09-anthropic-parallel-claudes-c-compiler/commentary.md) Parallel Claudes 造 C 编译器（2026-02）· [10](./10-openai-orchestrating-agents/commentary.md) Routines & Handoffs（2024-11）· [11](./11-openai-agents-sdk/commentary.md) Agents SDK 五原语（2025-03→）                                                                             | 多 agent 的收益与代价如何权衡？编排的最小原语是什么？          |
| **四 · Harness 与长时程**   | 长时程运行 | [12](./12-anthropic-effective-harnesses/commentary.md) Effective Harnesses（2025-11）· [13](./13-anthropic-harness-design-long-running-apps/commentary.md) Harness Design（2026-03）· [14](./14-openai-harness-engineering/commentary.md) Harness Engineering（OpenAI, 2026-02）                                                                                                                                                                          | 跨上下文窗口依靠何种机制延续？harness 的组件何时增减？         |

## 两家实验室的共识

分歧之下存在更深层的共识——以下五条已成为 2025-2026 年的行业事实标准：

1. **最简单方案优先**：workflow 优先于自主 agent，单 agent 优先于多 agent；复杂度必须被证明有回报后才允许引入（01、02 同句表述）。
2. **上下文是第一稀缺资源**：注意力预算、最小高信号 token 集合、"给地图不给说明书"（03、06、14 三篇一致）。
3. **护栏分层 + 人在环**：规则防线、分类器、工具风险分级、确认门，按失败阈值与动作危险度触发人工介入（02、06、07）。
4. **评测驱动一切**：prompt、工具、技能、harness 组件全部是"提示资产"，任何改动必须通过回归（04、08、13）。
5. **harness 为模型而设计**：从模型的失败模式出发设计环境（可运行的验证、防上下文污染的日志、可 grep 的错误），而非从人类使用习惯出发（06、09、12、14）。

## 两家实验室的分歧

| 维度          | Anthropic                                                               | OpenAI                                                                  |
| ------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| 组织形态偏好  | 组合式模式自由拼装（提供模式清单，harness 由使用者自行构建）            | 平台化原语一体交付（Agents SDK 五原语、Responses API 会话状态）         |
| 多 agent 立场 | 倡导 orchestrator-worker，量化其 15× token 代价，给出适用判据          | 保守：穷尽单 agent 方案后方考虑多 agent，Manager/Handoff 两型均视为后备 |
| 生态路线      | 开放协议（MCP、Agent Skills 开放标准）                                  | 自有平台纵深（Cookbook + SDK + 业务指南）                               |
| 提示层演进    | 提示退化成"配置"，重心移向环境与 harness                                | 提示仍是第一杠杆：训练模型适配 prompt 区块（`<persistence>` 等）      |
| 长时程叙事    | "harness 文学"系列：失败模式 → 双 agent → 对抗环 → 拆 harness 方法论 | "agent-first 组织"叙事：0 行手写代码的团队如何重构工程角色              |

## 范式 ↔ 本教程 ↔ 实战册 总对照表

| 范式要点                                        | 出处  | 主册章节 | 实战册 stage                    |
| ----------------------------------------------- | ----- | -------- | ------------------------------- |
| workflows/agents 分界                           | 01/02 | 01、09   | stage06 确认门                  |
| 五种模式（链/路由/并行/编排/评估）              | 01    | 09、16   | stage05                         |
| 三要素 + run loop                               | 02    | 21       | stage01                         |
| 注意力预算 / Context Rot                        | 03    | 10       | stage03                         |
| 最小高信号 token 集合                           | 03    | 10-12    | stage03 压缩                    |
| 工具 = 确定性↔非确定性契约                     | 04    | 03、11   | stage03 schema                  |
| 渐进式披露 / SKILL.md                           | 05/14 | 14       | stage10                         |
| CLAUDE.md ≈ 宪法式系统提示                     | 06    | 11       | stage03                         |
| eagerness 调节 / 早停判据                       | 07    | 19、21   | stage06                         |
| 任务包委派（目标/格式/边界）                    | 08    | 15、16   | stage05 五要素                  |
| LLM-as-judge（单裁判 0-1 分）                   | 08/13 | 20、22   | stage11                         |
| handoff 换提示不换历史                          | 10/11 | 07、18   | ——（对照 stage05 干净上下文） |
| 五原语（Agent/Handoff/Guardrail/Session/Trace） | 11    | 21-25    | stage07/08/09                   |
| 跨窗口延续（feature list/progress/git）         | 12    | 13、25   | stage09 检查点 + stage04 记忆   |
| generator-evaluator 对抗环 / 拆 harness         | 13    | 22、21   | stage11 / stage12               |
| 知识库即系统记录 + 机械不变量                   | 14    | 11、24   | stage07/08                      |

## original.pdf 与插图存档说明

- **original.pdf**：每篇原文的原版排版存档（检索日期 2026-09-12）。02 号为 OpenAI 官方 PDF 原文件（34 页）；其余为无头 Edge 打印的网页快照。
- **images/ + md 回填**：原文抓取时 9 篇共 48 处插图曾被替换为 `[图片省略]` 占位符，现已全部按原文位置回填——45 张正文插图下载至各篇 `images/`（md 以相对路径引用），09 号的 1 处为 YouTube 演示视频（静态存档无法承载，md 中为说明行）。
- 特殊处理三篇，均不影响文本完整性：07/10（cookbook 归档页，SPA 渲染后本地打印）；13（原页截图为轮播组件，PDF 按文档顺序全部展开）；14（Cloudflare 防护页，经真实浏览器会话取回，13 号同款轮播处理）。
- 14 号文末"Keep reading"推荐卡为动态轮换位：插图按卡片标题配对回填（GPT-5.6 卡经其原文页核实使用 `OAI_HabitatPT1` 资源）。
- PDF 与 md 同为个人学习存档，版权归原作者所有；13/14 号 PDF 的版式与在线页略有差异（轮播展开、系统字体回退）。

## 延伸阅读（未收录全文，供检索追溯）

- Anthropic：《Scaling Managed Agents: Decoupling the brain from the hands》（2026-04）、《How we contain Claude across products》（沙盒治理）、《The "think" tool》（2025-03）、《Code execution with MCP》（2025-11）、《Writing effective tools》的前身《Writing tools for agents》系列更新
- OpenAI：《Codex exec plans》文档、Realtime agents guidance、后续模型代际的 prompting guide
- 第三方：12-Factor Agents（HumanLayer）、Martin Fowler《Harness engineering for coding agent users》（2026-04）、Anthropic Cookbook 的 patterns-agents 示例库
