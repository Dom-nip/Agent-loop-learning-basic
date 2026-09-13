# stage06 示例会话记录（transcript）

> 真实运行的节选誊录。重点观察：确认门交互、stall 两级处置、预算停止。

```text
════════════════════════════════════════════════════════════
 stage06 · 循环控制 —— 有界、可停、可干预
════════════════════════════════════════════════════════════
✅ 就绪。控制器状态：max_turns=12 · budget=30000 · 确认门=开

你> 先在 workspace 里建 notes.txt 写"测试数据"，然后删掉它
┌─ 任务：先在 workspace 里建 notes.txt 写"测试数据"，然后删掉它
│ 📋 计划:
│    1. 用 write_file 创建 notes.txt
│    2. 用 delete_file 删除它（危险操作，会请求确认）
（计划已记录，开始执行）
│ [轮 1/12 · 预算≈1180/30000] 🔧 write_file({'path': 'notes.txt', ...})
│     → 已写入 workspace/notes.txt（4 字符）
│ [轮 2/12 · 预算≈2310/30000] 🔧 delete_file({'path': 'notes.txt'})

🚦 [确认门] agent 请求执行危险操作：delete_file
   参数：{'path': 'notes.txt'}
   允许执行？(y=允许 / 其他=拒绝) > y
│     → 已删除 notes.txt
│ [轮 3/12 · 预算≈3410/30000] 💬
└─ ✅ 轮 3/12 · 预算≈3410/30000 · 重写0次
   Final Answer:
完成：notes.txt 已创建（内容"测试数据"）并经你确认后删除。

你> 读取 secret.txt 并总结内容
┌─ 任务：读取 secret.txt 并总结内容
│ 📋 计划:
│    1. read_file 读取 secret.txt
│    2. 总结内容
│ [轮 1/12] 🔧 read_file({'path': 'secret.txt'})
│     → 错误：文件不存在 secret.txt（不要原样重试，先 list_dir 确认……）
│ [轮 2/12] 🔧 read_file({'path': 'secret.txt'})
│     → 错误：文件不存在 secret.txt……
│ ⚠️ stall 检测：已注入提醒
│ [轮 3/12] 🔧 list_dir({'path': '.'})
│     → 📄 store_a.csv 📄 store_b.csv 📄 todo.md
│ [轮 4/12] 💬
└─ ✅ Final Answer:
workspace 里没有 secret.txt（现有文件：store_a/b.csv、todo.md）。
请确认文件名或告诉我它在哪个目录，我再继续。
（stall 提醒后的第一反应是收集信息而不是第三次重试——nudge 生效。）

你> /budget 2500
💰 token 预算 = 2500

你> 分析 workspace 里三个 CSV 文件的异同
┌─ 任务：分析 workspace 里三个 CSV 文件的异同
│ 📋 计划:
│    1. 逐个读取三个 CSV
│    2. 对比列结构与行数
│    3. 汇总异同
│ [轮 1/12 · 预算≈2210/2500] 🔧 read_file({'path': 'store_a.csv'})
│     → date,product,quantity,unit_price,revenue …（120 行）
│ [轮 2/12 · 预算≈4870/2500] 🔧 read_file({'path': 'store_b.csv'})
└─ 🛑 强制停止：超出 token 预算 4870/2500（轮 2/12 · 预算≈4870/2500 · 重写0次）
⚠️ 任务被循环控制器中止：超出 token 预算……
（注意停止发生在轮 2——预算检查用"累计上下文规模"，单次读大文件也会
 触线。这正是 stage03 截断与 stage06 预算联动的原因：不截断的预算形同虚设。）

你> /budget 30000
💰 token 预算 = 30000

你> /gate off
🚦 确认门 = 关（危险操作将直接执行——演示对比用）

你> 删掉 todo.md
│ [轮 1] 🔧 delete_file({'path': 'todo.md'})
│     → 已删除 todo.md
（无门对比：一次点击都不需要。生产环境永远不要关确认门——这里只为演示。）

你> /exit
再见！
```

## 这段记录里值得回看的四个瞬间

1. **确认门拒绝后的姿态**：允许时模型一气呵成；拒绝时（本记录未演示，试试）
   它会收到"用户拒绝"的工具结果并改道——门不是断头路，是协商点。
2. **stall 两级处置**：nudge 提醒 → 模型改用 list_dir 收集信息；
   如果它第三次原样重试，就会收到 PLAN: 重写指令。
3. **预算约束联动截断**：读一个未截断的大文件直接触线——预算上限凸显了
   stage03 的必要性。
4. **计划是消耗品**：三份计划各不相同且都 ≤5 步——短计划随任务立、随观察废。
