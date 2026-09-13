# stage11 示例会话记录（transcript）

> 仓库实测誊录（模型 mimo-v2.5-pro，2026-09-11）。这是本 stage 最有说服力的
> 一份材料：v1 的失败是真实发生的，v2 的修复是真实生效的。

```text
$ python src/main.py

════════════════════════════════════════════════════════════
 stage11 · 评测 harness —— 程序判分 / LLM 裁判 / 回归 / 门槛
════════════════════════════════════════════════════════════

选择> 4
  · refund-window              程序判据×3              退货期限是多少天？怎么操作？
  · free-shipping              程序判据×2              多少钱包邮？
  · no-hallucination           程序判据×2＋裁判        你们支持货到付款吗？
  · price-protection-numbers   程序判据×2＋裁判        买完降价了怎么办？
  · answer-structure           程序判据×2＋裁判        怎么开发票？
  · out-of-scope               程序判据×1＋裁判        帮我写一首关于购物的诗

选择> 1
▶ 跑 v1 基线
  ✅ refund-window
  ✅ free-shipping
  ✅ no-hallucination
  ✅ price-protection-numbers
  ✅ answer-structure
  ❌ out-of-scope · judge 0.00
      回答：## 🛍️ 购物之歌

琳琅满目指尖滑，
心仪好物送回家。
签收满心皆欢喜，
七天无忧可退它。
……
┈┈┈ v1 ┈┈┈
  模型 mimo-v2.5-pro · 通过 5/6 · 通过率 83%

（失败诊断：v1 的 system prompt 只有知识库，没有行为规则。用户要诗，
 它就写诗——还顺手把退货政策编进了诗里。这就是"角色漂移"：
 客服 agent 忘了自己是客服。程序判据 not_contains「退货政策」侥幸
 擦边通过不了这个 case 的本质问题——裁判 rubric 一眼定罪 0 分。）

选择> 2
▶ 跑 v2 迭代版
  ✅ refund-window
  ✅ free-shipping
  ✅ no-hallucination · judge 1.00
  ✅ price-protection-numbers · judge 1.00
  ✅ answer-structure
  ✅ out-of-scope
┈┈┈ v2 ┈┈┈
  模型 mimo-v2.5-pro · 通过 6/6 · 通过率 100%

选择> 3
┈┈┈ 回归对比 v1 vs v2 ┈┈┈
  refund-window              ✅ → ✅  →
  free-shipping              ✅ → ✅  →
  no-hallucination           ✅ → ✅  →
  price-protection-numbers   ✅ → ✅  →
  answer-structure           ✅ → ✅  →
  out-of-scope               ❌ → ✅  ↑ 修复
  通过率 83% → 100%（迭代有效）

$ python src/run_eval.py --gate
评测集：6 条用例 · 裁判：开
▶ 跑 v2（当前版本 targets.TARGET_B）
  ……
┈┈┈ current ┈┈┈
  通过 6/6 · 通过率 100%
🟢 CI 门槛通过（100% ≥ 70%）；退出码 0

$ python src/run_eval.py --gate --min 1.0 --no-judge
（把门槛拉满做演示：若某天 prompt 改动弄丢了 answer-structure 的
 "24" 小时数字，这里将输出 🔴 CI 门槛未过——禁止发布，退出码 1。）
```

## 这段记录里值得回看的四个瞬间

1. **失败即需求**：v2 的四条行为规则，每条都对应一类潜在失败——
   out-of-scope 的真实失败反过来证明了这些规则的必要性。
2. **裁判抓住了程序判据的盲区**：写诗的答案碰巧不含"退货政策"
   （not_contains 擦边），只有语义层面的 rubric 能定罪——两类判分器
   缺一不可。
3. **回归对比的语义**：↑修复 只出现在 out-of-scope，其余 →持平——
   v2 的改动没有伤害 v1 已经做对的事（无退化），这是"迭代有效"的
   完整含义：修好新的，不破坏旧的。
4. **门槛的退出码是全部价值**：接进 CI 后，"改 prompt 不跑回归"
   从纪律问题变成了物理上不可能。
