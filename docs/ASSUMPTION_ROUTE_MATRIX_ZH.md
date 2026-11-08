# Causal-IDFM Post-release P0：假设类型、适用定理与覆盖边界

> 状态：**针对已实现 POINT 识别路线的可机读要求目录与科学解释**。它不是新增假设验证器、不是现实世界假设的统计检验，也不是新 Family。源代码：`pfn_pipeline/identification_assumption_inventory.py`；独立测试：`tests/test_postrelease_assumptions_handoff.py`。

## 1. “假设是有限的”应该怎么理解？

- **有限**：目前正式网络 POINT 定理所显式使用的、可复用的顶层假设名称是有限的；本目录记录 **8 项**（其中 `known_assignment_law` 按代码约定保留名称，实质上是 A4/实验设计信息，不是独立的科学因果排除假设）。
- **不保证有限**：所有可能的因果研究假设并不存在由本系统已列举完毕的有限清单；每种网络映射、节点范围、目标总体、干预版本、W 条件层及假设参数，都可能产生不同的科学断言。
- **不等于可检验**：`CERTIFIED` / `ADMITTED` / `DERIVED` 是**来源与工作流状态**。即使独立 verifier 全绿，也仅表示「如果假设成立、A4/A6 合法，则 POINT 数学公式正确」，绝不是软件以数据证明假设成立。

## 2. 八个已实现的必要前提名称

| 名称（源码） | 层级 | 含义与注意事项 |
|---|---|---|
| `known_assignment_law` | **A4/Design** | 已知完整实验分配律 `q(T\|W)`，不能用观察到的样本频率替代；当前 D1–D6 |
| `full_vector_randomization` | A5 | 实验完整处理向量与所有相关潜在结果在条件 `W` 下独立 |
| `consistency` | A5 | 真实观察到的 `Y_i^{obs}` 与实际完整干预版本对应的潜在结果一致 |
| `fixed_pretreatment_network` | A3/A5 | 图结构、暴露参考集合及处理前定义的网络坐标稳定 |
| `finite_conditional_first_moments` | A5/分析条件 | 各目标总体条件均值存在且有限 |
| `mean_signature_sufficiency` | A5/结构 | **仅 R2、R3-Signature 政策**；均值取决于 `(t_i,g_i(t,W),W)`，需绑具体签名与节点；不要求逐点潜在结果相等 |
| `full_vector_conditional_exchangeability` | A5/观测 | R3 要求给定 `W` 时，非随机的完整 treatment 向量与完整潜在结果条件独立；很强的科学假设 |
| `first_stage_profile_no_direct_outcome_effect` | A5/D6 | D6 第一阶段配额或公告 `U` 不能在固定最终 `T` 外直接影响结果；否则应建模 `Y_i(T,U)` |

**其它门禁不应塞进这个目录：** `A4` 的 typed population outcome 观测算子必须足够精细，`A6` 必须逐查询检验正支持、实验配额、孤立节点 exposure 定义等。支持概率是数学/分配律条件，不是一个可以点击「接受」的无混杂假设。

## 3. 正式业务 Route 所要求的组合

| Route | 数学目标 | 共同许可 | 额外 A5 | A4 粒度 / A6 支持 |
|---|---|---|---|---|
| `R1A_RANDOMIZED_ARM` | `q`-standardized node arm | `known q + full-vector randomization + consistency + stable graph + moments` | **不需要 exposure sufficiency** | typed arm / 合法强算子，joint arm 正支持 |
| `R1A_COMPOSITION` | 同一 q/g/W 下的 Direct、Spillover、Total、加权平均 | 与 R1a 相同 | **不需要 exposure sufficiency** | 每个非零线性项有 A4 且正支持 |
| `R1B_FULL_ASSIGNMENT` | 真实完整政策 `V(z)` | 与 R1a 相同 | **不需要 exposure sufficiency** | assignment-level A4，`q(z)>0` |
| `R1B_FINITE_POLICY` | 有限多个已认证 R1b 政策的正权混合 | 各 R1b 分量均合格 | **不需要 exposure sufficiency** | 每个非零分量的完整支持与 A4 |
| `R2_MEAN_SIGNATURE` | 完整政策 `V(z)`，允许 `q(z)=0` | 与 R1a 相同 | **另需签名均值充分性** | 目标节点签名 A4 与逐节点正支持 |
| `R3_FULL_ASSIGNMENT` | 观测完整政策 `V(z)` | full-vector conditional exchangeability + consistency + stable graph + moments | 不需要 exposure sufficiency | 有限明确 `p_obs`、assignment-level A4 与 `p_obs(z)>0` |
| `R3_MEAN_SIGNATURE` | 观测完整政策 `V(z)`，可 off-support | R3 交换性基础 | **另需签名均值充分性** | 目标签名正支持与匹配 A4 |
| `R3_P_STANDARDIZED_EFFECTS` | 观测 `p`-standardized Direct/Spillover/Total | R3 交换性基础 | **不需要 exposure sufficiency** | 支持 arm 的观测均值与正支持；现有软件仍要求显式完整 `p_obs` |

**D6 条件附加**：若使用 `two_stage_quota_mixture_binary_v2_7`，R1a/R1b/R2 还必须单独接受 `first_stage_profile_no_direct_outcome_effect`。不是 R3 的假设，也不是从 D6 概率法则自然推出的属性。

## 4. 三个容易弄错的科学问题

1. **随机化不等于无干扰**：R1a 可以在完全一般的跨节点干扰潜在结果下识别设计标准化 arm，且**不要求**均值暴露充分性；定义 E1/E5 并不说明潜在结果只受该暴露影响。
2. **更粗的 exposure 能增加支持，但未必科学合理**：例如 E5 Any-treated 的支持较 E4 Exact Count 宽，也意味着在 R2 中接受了**另一种可能更强的均值等同性断言**；不可自动把 E4 的 A5 许可换成 E5。
3. **R3 观测交换性 ≠ 已观测所有相关变量就自然成立**：即使 `p_obs(T|W)` 与 node outcomes 的总体算子全部声明合法，交换性仍是需独立审查的外生科学主张。

## 5. 还没有正式实现的主要假设/识别机制

- 局部或弱于完整向量的观测均值交换性；不可测网络共同原因的调整；有选择偏差/缺失数据的条件。
- 一般变量 DAG 的 backdoor/frontdoor；IV 的独立性、排除、相关性、单调性或 completeness 等；代理变量识别。
- 动态/处理诱发网络、第一阶段公告直接效应 `Y_i(t,u)`、多值连续处理、跨企业的 transportability 与跨 W 层总体标准化。
- 真实业务中有系统根据有限样本**证明** A5 成立、输出一般网络 PARTIAL sharp bounds，或自动训练覆盖所有 route 的 PFN estimator。

**结论**：继续维护有限、版本化的 **数学机制目录**，但允许每项假设对研究总体/暴露签名/节点/干预版本进行参数化。新增一种类别不是「写一个 Python 名字」就算覆盖，必须有 A1–A6 数学合同、反例、独立 verifier 和正反验收。
