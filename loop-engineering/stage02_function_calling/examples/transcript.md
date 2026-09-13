# stage02 示例会话记录（transcript）

> 真实运行的节选誊录。重点观察：并行 tool_calls、schema repair loop、
> tool_choice 三模式的行为差异。

```text
════════════════════════════════════════════════════════════
 stage02 · Function Calling —— 结构化工具调用
════════════════════════════════════════════════════════════
✅ 已连接 mimo-v2.5-pro（Function Calling 模式）

你> 建两个文件：a.txt 写 hello，b.txt 写 world
┌─ 任务：建两个文件：a.txt 写 hello，b.txt 写 world   [tool_choice=auto]
│ [turn 1] 🔧 write_file({"path": "a.txt", "content": "hello"})
│           → 已写入 workspace/a.txt（5 字符）
│           🔧 write_file({"path": "b.txt", "content": "world"})
│           → 已写入 workspace/b.txt（5 字符）
│ [turn 2] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
两个文件已创建完成：a.txt（hello）和 b.txt（world）。
（对照 stage01：同一任务要 4 轮 Thought/Action 交替；这里 2 轮结束——
 并行调用把两个写操作合并进一条消息。）

你> 写一段内容到 quote.txt：他说："结构化调用救了所有解析器维护者"
┌─ 任务：写一段内容到 quote.txt：他说："结构化调用救了所有解析器维护者"
│ [turn 1] 🔧 write_file({"path": "quote.txt", "content": "他说：\"结构化调用救了所有解析器维护者\""})
│           → 已写入 workspace/quote.txt（25 字符）
│ [turn 2] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
已写入 quote.txt。注意 arguments 里的引号由 SDK 层转义，模型只管内容本身——
stage01 里这个场景是 bad_json 修复提示的高发区。

你> /mode required
🔧 tool_choice = required
   （模型将被迫调用工具——观察它如何「挤」出一个调用）

你> 1+1 等于几？
┌─ 任务：1+1 等于几？   [tool_choice=required]
│ [turn 1] 🔧 run_python({"code": "print(1 + 1)"})
│           → 2
│ [turn 2] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
1 + 1 = 2。
（被迫调用时模型选了最无害的工具执行了一次无意义计算——required 会扭曲行为，
 适合调试工具链，不适合当生产默认。）

你> /mode none
🔧 tool_choice = none
   （工具被彻底收走——模型只能用文本回答）

你> workspace 里现在有哪些文件？
┌─ 任务：workspace 里现在有哪些文件？   [tool_choice=none]
│ [turn 1] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
根据我们之前的对话记录，workspace 里应该有：a.txt、b.txt、quote.txt。
但当前模式下我无法实际查看目录——如果需要确认，请切换回 auto 模式。
（诚实的模型会声明"看不到"；不诚实的模型会编造——收走工具是检验模型
 "知道自己不知道"的关键手段。）

你> /mode auto
🔧 tool_choice = auto

你> 把 quote.txt 的内容改成单引号版本，再新建 empty.md 空文件
┌─ 任务：把 quote.txt 的内容改成单引号版本，再新建 empty.md 空文件
│ [turn 1] 🔧 read_file({"path": "quote.txt"})
│           → 他说："结构化调用救了所有解析器维护者"
│ [turn 2] 🔧 write_file({"path": "quote.txt", "content": "他说：'结构化调用救了所有解析器维护者'"})
│           🔧 write_file({"path": "empty.md", "content": ""})
│           → 已写入 workspace/quote.txt（25 字符）
│           → 已写入 workspace/empty.md（0 字符）
│ [turn 3] 💬（无工具调用，直接回答）
└─ ✅ Final Answer:
quote.txt 已改为单引号版本；empty.md 已创建（空文件）。

你> /stats
  {'turns': 9, 'tool_calls': 9, 'repairs': 0}

你> /exit
再见！轮次 9 · 工具调用 9 次 · schema 修复 0 次
```

## 这段记录里值得回看的四个瞬间

1. **并行 tool_calls 省了一半轮次**：两个独立写操作合并进一条 assistant 消息。
2. **required 模式的行为扭曲**：模型为"满足合同"发起无意义计算——约束改变行为，
   这是做工具链调试时的有用技巧、生产环境的危险默认。
3. **none 模式的诚实度测试**：模型承认看不见目录。给它工具它才会去看——
   "能力"与"工具在不在场"直接绑定。
4. **repairs = 0 不是运气**：schema 清晰 + SDK 层转义，让参数错误从"常见病"
   变成"罕见病"。但 description 写得含糊时它立刻回升——工具说明书是合同，
   措辞的模糊会被模型放大成行动的偏离。
