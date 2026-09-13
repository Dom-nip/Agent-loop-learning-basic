# stage01 示例会话记录（transcript）

> 真实运行的节选誊录（模型为 OpenAI 兼容接口，输出细节因模型而异）。
> 重点观察：Thought → Action → Observation 的交织、修复提示的触发、连续任务的上下文延续。

```text
════════════════════════════════════════════════════════════
 stage01 · ReAct 文本协议 —— Thought / Action / Observation
════════════════════════════════════════════════════════════

✅ 已连接 mimo-v2.5-pro，workspace 就绪，开始对话。

你> 看看 workspace 里有什么
┌─ 任务：看看 workspace 里有什么
│ [turn 1] Thought: 用户想知道 workspace 里有什么文件，使用 list_dir 工具查看根目录
│           Action: list_dir  Input: {'path': '.'}
│           Observation: （目录为空）
│ [turn 2] Thought: workspace 目前为空，可以直接告知用户
└─ ✅ Final Answer:
workspace 目前是空的，还没有任何文件。需要我帮你创建点什么吗？

你> 那帮我建一个 todo.md，写上三件今天要做的事，主题是"学习 agent 开发"
┌─ 任务：那帮我建一个 todo.md，写上三件今天要做的事，主题是"学习 agent 开发"
│ [turn 1] Thought: 需要创建 todo.md 并写入三件与学习 agent 开发相关的待办事项
│           Action: write_file  Input: {'path': 'todo.md', 'content': '# 今天的待办\n\n1. 复习 ReAct 循环的三个组成部分\n2. 跑通 stage01 并观察格式漂移\n3. 预习 Function Calling 与 JSON Schema\n'}
│           Observation: 已写入 workspace/todo.md（112 字符）
│ [turn 2] Thought: 文件已成功写入，任务完成，可以收尾
└─ ✅ Final Answer:
已在 workspace/todo.md 写入三件今天要做的事：
1. 复习 ReAct 循环的三个组成部分
2. 跑通 stage01 并观察格式漂移
3. 预习 Function Calling 与 JSON Schema

你> 读一下刚写的文件，确认内容完整
┌─ 任务：读一下刚写的文件，确认内容完整
│ [turn 1] Thought: 用户想确认刚才写入的 todo.md 内容，使用 read_file 读取
│           Action: read_file  Input: {'path': 'todo.md'}
│           Observation: # 今天的待办

1. 复习 ReAct 循环的三个组成部分
2. 跑通 stage01 并观察格式漂移
3. 预习 Function Calling 与 JSON Schema
│ [turn 2] Thought: 内容与刚才写入的一致，三条待办完整无缺
└─ ✅ Final Answer:
已读取确认，todo.md 内容完整，三条待办事项都在（共 112 字符）。
注意这里没有重新调用工具问"上一轮写了什么"——对话历史保留了上一任务的结论。

你> 用 run_python 算一下 2 的 100 次方等于多少
┌─ 任务：用 run_python 算一下 2 的 100 次方等于多少
│ [turn 1] Thought: 需要 Python 的大数运算，调用 run_python
│           Action: run_python  Input: {'code': 'print(2 ** 100)'}
│           Observation: 1267650600228229401496703205376
│ [turn 2] Thought: 得到结果，向用户报告
└─ ✅ Final Answer:
2 的 100 次方 = 1267650600228229401496703205376（约 1.27 × 10^30）。

你> 现在写一段含双引号的句子到 quote.txt，比如：他说："格式漂移是文本协议的原罪"
┌─ 任务：现在写一段含双引号的句子到 quote.txt，比如：他说："格式漂移是文本协议的原罪"
│ [turn 1] Thought: 内容包含双引号，JSON 里必须转义。我小心地写
│           Action: write_file  Input: {'path': 'quote.txt', 'content': '他说："格式漂移是文本协议的原罪"'}
│           Observation: 已写入 workspace/quote.txt（22 字符）
│ [turn 2] Thought: 写入成功
└─ ✅ Final Answer:
已写入 quote.txt：他说："格式漂移是文本协议的原罪"
（这次 JSON 转义侥幸写对了——换更小的模型，这里常常触发 bad_json 修复提示，
 这就是 README 观察点里说的"JSON 转义崩溃"实验。）

你> /history
  当前消息数：14，累计轮次：8

你> /exit
再见！本会话共执行 8 个循环轮次。
```

## 这段记录里值得回看的四个瞬间

1. **turn 1 永远是"想清楚再动手"**：每个任务的第一个 Thought 都在陈述意图——
   这是协议强制显式思考的价值。
2. **第三个任务没有重读文件的必要却读了**：模型选择用工具确认而不是相信记忆——
   行动验证优于自信，这是 ReAct 的精神；但每一步都要花真金白银。
3. **`/history` 显示 14 条消息**：只干了 3 件小事，历史已经 14 条——stage03 的
   上下文工程就是为了对付这条曲线。
4. **含引号的写入是赌博**：文本协议下 JSON 转义靠模型自觉，失败时靠修复提示兜底
   ——stage02 的 Function Calling 会把这整类问题从"概率问题"变成"不存在的问题"。
