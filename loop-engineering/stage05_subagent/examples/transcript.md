# stage05 示例会话记录（transcript）

> 真实运行的节选誊录。重点观察：任务包五要素、三路并行、fan-in 合成。

```text
════════════════════════════════════════════════════════════
 stage05 · Subagent —— 分派、并行隔离与 fan-in 合成
════════════════════════════════════════════════════════════

你> /flooddata
  📄 已生成 workspace/store_a.csv（东区店，120 行）
  📄 已生成 workspace/store_b.csv（南区店，120 行）
  📄 已生成 workspace/store_c.csv（西区店，120 行）

你> 对比三个门店的销售情况，给出综合结论
┌─ 任务：对比三个门店的销售情况，给出综合结论
│ [turn 1] 🔧 spawn_subagents({"packages": [
│     {"name": "东区店", "goal": "统计 store_a.csv 的总营收、最畅销产品、日均值",
│      "context": "CSV 列为 date,product,quantity,unit_price,revenue",
│      "tools": ["read_file", "run_python"],
│      "boundaries": "只分析 store_a.csv，不要读其他文件",
│      "output_format": "不超过 150 字的要点报告：总营收/最畅销产品/日均值"},
│     {"name": "南区店", ...}, {"name": "西区店", ...}]})
│      [东区店 t1] 🔧 run_python
│      [南区店 t1] 🔧 run_python      ← 三个子代理同时开跑（真并行）
│      [西区店 t1] 🔧 run_python
│           →（三份要点报告回流，各约 100 字）
│ [turn 2] 💬（合成）
└─ ✅ Final Answer:
三店对比：南区店总营收最高（约 28.6 万）；东区店次之但日均值最稳；
西区店明显落后（约为南区店的 62%），短板在显示器品类。
建议：西区店引入显示器促销；东区店保持节奏；南区店复盘高客单结构。
（三个 120 行的 CSV 没有进入主对话——主上下文只增加了任务包 + 三份报告。）

你> /stats
  {'turns': 2, 'tool_calls': 1, 'spawned': 3}

你> 只看看东区店卖得怎么样
┌─ 任务：只看看东区店卖得怎么样
│ [turn 1] 🔧 spawn_subagents({"packages": [{"name": "东区店复查", ...}]})
│      [东区店复查 t1] 🔧 run_python
│ [turn 2] 💬
└─ ✅ Final Answer:
东区店单店总营收约 26.4 万……（顺手的小任务它也分派了——分派纪律的
 "≥2 个子任务"判据没有约束住它，见 README 观察点：这条纪律靠 prompt
 约束，弱模型会过度分派。这是 subagent 方案的真实边界。）

你> /exit
再见！{'turns': 4, 'tool_calls': 2, 'spawned': 4}
```

## 这段记录里值得回看的四个瞬间

1. **schema 强制五要素**：spawn 的每个任务包都必须带 goal/context/tools/
   boundaries/output_format——要素缺失的任务包在 schema 层就被拦下。
2. **真并行**：三个子代理的 run_python 几乎同时出现，墙钟时间 ≈ 最慢者。
3. **主上下文零污染**：三个文件的分析过程（每个子代理 5-8 条消息）全部
   随实例消亡，主对话只见报告。
4. **分派判据靠 prompt 约束**：单店查询也被分派了——纪律写在 system prompt
   里不是硬闸门，stage06 的显式控制机制就是对这类"软约束失效"的补课。
