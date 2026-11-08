# Causal-IDFM：最小正确核心稳定化 P1（2026-10-18）

**版本身份**：`v2.9.2 Post-release Minimal Core Stabilization + Maintenance P1`，不发布 v2.9.3。**冻结** `pfn_pipeline/` 数学算法、A0 Gateway 和正式证书。此次只新增开发诊断工具、Golden 测试、CI 的快速核验与只读审计。

## 1. 与 是什么关系？

对比两个正式 ZIP（按路径忽略顶层压缩目录名称，SHA-256 逐文件比较）：

| 项目 | v2.9.1 → v2.9.2 Minimal Stabilization |
|---|---|
| 旧文件 | 962 个全部保留；948 个内容未变、14 个改变、0 个删除 |
| 新文件 | 46（含 v2.9.2 安全审核、业务基准、展示、Research-only PARTIAL、Golden） |
| `pfn_pipeline/` | 125/125 逐字节相同，R1a/R1b/R2/R3 定理及正式支持域未改 |
| `cfm_id_llm/` | 38/38 逐字节相同 |
| `cfm_id_bridge/` | 4 个旧文件更新、2 个新增：业务目标审核、A4/A5 证据绑定等 |
| 对 v2.9.1 旧审核资料的兼容性 | **有意收紧**：缺 `business_intent` 或 `evidence_manifest` 不得取得新 POINT |
| 研究性 PARTIAL | Star7 有界结果区间示例，**不是正式 R4** |

结论：**原有 POINT 数学能力没有删减**，但不能声称所有 v2.9.1 的旧 JSON/审核调用“功能完全一样”：新审核必填字段会阻断未补齐的新调用。这是安全门禁，不是识别定理失效。

## 2. 本轮只做两件事

**R3 同 Target / 不同 A4 表示的最小消融**：`3` 节点路径、E1 严格多数、**一个** R3 按观测律标准化 Direct 目标。分别声明 `FULL_JOINT_LAW`、`NODE_INDEPENDENT_BERNOULLI` 和 `ONE_COMPONENT_MIXTURE_BERNOULLI` 的同一完整处理律，经正式业务入口/原独立 verifier/replay；两个组成 arm 的精确支持分别为 `1/8`、`3/8`，且读-only Target A4 审计确认相同。只改变观测处理律则**不**合并；缺交换性或把总体信息替换为样本统计则拒绝。输入是假设性**符号总体声明**，不是实际业务数据。

**旧 PFN-smoke 的最小隔离诊断**：`scripts/diagnose_legacy_pfn_smoke.py` 在独立子进程中运行原有 checkpoint 测试；分阶段记录 `train_model` 和 `evaluate_checkpoint`，设置一次性堆栈定时输出和进程超时。**未改** smoke 正式断言、训练函数、模型参数或 Estimation。若超时，明确记为 `TIMEOUT` 并返回非零，不允许被解释成 `PASS`。

## 3. 本地隔离试验结果（不能证明偶发故障根因已解决）

- 原有 9 项 PFN smoke：隔离执行用时约 **11.21 秒**，`PASS`。其中训练阶段约 **2.30 秒**、checkpoint evaluation 阶段约 **0.039 秒**。
- 单独的 `test_migrated_checkpoint_evaluation`：约 **4.98 秒**、`PASS`，训练约 **2.29 秒**、evaluation 约 **0.039 秒**。
- 上述只证明*这一环境/这几次单独运行*没有重现卡顿。不能由此断定历史连续运行的超时原因；若再次卡顿，以日志和 faulthandler 堆栈定位具体阶段，再设计只改变单一条件的消融。

## 4. 七个 R3 模块的只读审计：保留还是收敛？

只读 AST 记录 `maintenance_evidence_p1/R3_READONLY_STRUCTURAL_AUDIT.json`，七个模块共 **2408 行**。

| 模块（省略前缀） | 行数 | 数学/信息职责 |
|---|---:|---|
| `identification_observational_effects.py` | 231 | 显式完整观测律下的 p-standardized arm/contrast |
| `identification_observational_factorized_a4.py` | 370 | 节点独立 Bernoulli A4 |
| `identification_observational_mixture_a4.py` | 344 | 有限 Bernoulli 混合 A4 |
| `identification_observational_exposure_adjustment.py` | 455 | **不同 Target**：共享分层 covariate-adjusted effect |
| `identification_observational_nodewise_adjustment.py` | 602 | **不同 Target**：nodewise-adjusted effect |
| `identification_observational_nodewise_mixture_a4.py` | 79 | Nodewise 调整路线的条件混合 A4 适配 |
| `identification_r3_target_a4_audit.py` | 327 | 只读跨表示核对，不生成新 POINT |

不能因为文件中均有 `verify` / `replay` / `support` 就把这些函数直接合并。`p`-standardized 与 adjusted 目标数学上不等价；多个计算表示即使给出同一 `p(T)`，独立重放仍应保留不同的概率算法，以保证交叉校验价值。

**本轮决定：不重构 R3。** 以后若确实识别出纯粹重复的字段检查，先给出严格输入/输出等价证明和正反例，再只抽取一个无状态辅助函数，并保留两个独立支持计算/验证实现。

## 5. 标准维护命令（源码根目录）

```bash
bash scripts/run_minimal_stabilization_checks.sh fast
bash scripts/run_minimal_stabilization_checks.sh r3-ablate
bash scripts/run_minimal_stabilization_checks.sh r3-audit /tmp/r3_structural.json
bash scripts/run_minimal_stabilization_checks.sh pfn-diagnose /tmp/pfn_checkpoint_report.json
bash scripts/run_minimal_stabilization_checks.sh core-split
bash scripts/run_minimal_stabilization_checks.sh gateway
bash scripts/run_minimal_stabilization_checks.sh pfn-smoke
```

- `fast` 是原来的三节点 R1a 黄金路径，**保持原样**。
- `r3-ablate` 是一个不同的三节点 R3 调整/总体算子消融，**不改变原先的 Golden**。
- `r3-audit` 是结构检查，不改动 Core 文件。`pfn-diagnose` 是有终止时间、可生成堆栈的诊断命令。
- `core-split` 避免旧测试连续执行时不明卡顿；远端 CI 是否通过仍需实际平台结果。

## 6. 下一阶段门槛

只有在 (i) Golden 均稳定、(ii) 发现具体重复逻辑有证据、(iii) 独立 verifier 和跨表示判据保留、(iv) 对小图所有正反例回归通过，才允许最小公共代码收敛。否则 **不重构、不新增新 Family/D/E**。这符合导师所说的“维护最简正确结构比无目标扩展更重要”。
