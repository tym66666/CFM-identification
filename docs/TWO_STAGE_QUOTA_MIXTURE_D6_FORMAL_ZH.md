# Causal-IDFM — D6 Two-stage Quota-Mixture Randomization 正式数学合同

**状态：正式有限 POINT Identification 设计子域（不是新 Family）。** 以 v2.6 + pre-v2.7 P0 为基线，保留 R1a/R1b/R2 的识别目标、生产级 A4、A5 独立来源以及 A6 精确 verifier。本文只对**已知固定处理前无向图、二元单时点处理、条件层 W=w、有限 profile 组内固定配额**适用；不能以“Two-stage”名称暗示所有两阶段、饱和度或动态干扰设计已实现。

## 1. A1–A3：设计、潜在结果和目标

- 固定节点 `V`，处理前已知简单无向网络 `G`。`C_1,...,C_H` 为节点的已知、无重叠、非空**分配分组**，不是干扰独立的连通分量；允许跨组边。
- 第一阶段随机选择完整配额向量 `U=(m_1,...,m_H)`，取自有限 profile 集 `\mathcal U`，`\pi(u\mid w)>0` 且 `\sum_u\pi(u\mid w)=1`；各组配额可以相关，不假定各组第一阶段选择独立。
- 给定 `U=u`，第二阶段在每个组 `C_h` 中均匀、无放回选出恰好 `m_h(u)` 个 treated，给定完整 profile 时各组第二阶段独立。
- 第一阶段配额公告或 profile 选择**不得在固定完整处理向量之外直接影响潜在结果**。这条 `first_stage_profile_no_direct_outcome_effect` 必须在 A5 中由领域研究者另行接受。否则一般应写成 `Y_i(t,u)`，原 R1a/R1b/R2 的 `Y_i(t)` 目标不具备这些证明所用的版本一致性。即使假设被软件记录为 admitted，也不代表科学上已得到证实。
- 假设 full-vector randomization `T \perp \{Y_i(t):i,t\}\mid W`、consistency、固定处理前图与有限所需一阶矩。A4 中相关节点的总体条件结果均值必须独立提供；有限样本不代替总体算子。

## 2. D6 精确的完整分配律

设 `n_h=|C_h|`, `S_h(t)=\sum_{j\in C_h}t_j`，则

\[
q(t\mid w)=\sum_{u\in\mathcal U}\pi(u\mid w)
\prod_{h=1}^{H}\frac{\mathbf1\{S_h(t)=m_h(u)\}}{\binom{n_h}{m_h(u)}}.
\]

有了已知的 `q` 和完整随机化，D6 不是新识别定理：它将已有 R1a 标准化 arm、R1b 完整政策概率，以及 R2 签名支持的基础设计律扩展为一个新的经验证分配机制。只有当 `q(z)>0` 且 A4 足够精细，R1b 才能识别固定政策 `V(z\mid W)=\sum_i\omega_i E[Y_i(z)\mid W]`。有限固定政策随机混合仍按原 R1b 逐分量审核，不等价于任意 stochastic policy kernel。

## 3. A6：节点自己的 treatment 与 reference-neighbor 的联合概率

令 `R_i` 是合法的、处理前确定的 exposure reference 集合（E1/E2/E4/E5 取完整一跳邻居；E3 为明确声明的核心合作者子集），`d_{ih}=|R_i\cap C_h|`，目标节点属于 `C_{h_*}`。给定第一阶段 profile `u`，有

\[
p_i(a\mid u)=P(T_i=a\mid U=u,W)=\begin{cases}m_{h_*}(u)/n_{h_*},&a=1,\\1-m_{h_*}(u)/n_{h_*},&a=0.\end{cases}
\]

当 `p_i(a|u)>0`，每个组的 treated reference 邻居人数服从独立超几何分布：

\[
K_{ih}\mid U=u,T_i=a \sim
\operatorname{Hypergeom}(n_h-1_{h=h_*},\ m_h(u)-a1_{h=h_*},\ d_{ih}).
\]

按组卷积 `\ast_h` 后，完整联合质量为

\[
P_q(T_i=a,K_i=k\mid W)=\sum_u\pi(u\mid W)p_i(a\mid u)
\left[\mathop{\ast}_h\operatorname{Hypergeom}(n_h-1_{h=h_*},m_h(u)-a1_{h=h_*},d_{ih})\right](k).
\]

`p_i(a|u)=0` 的 profile 对该联合分布贡献 0，不允许对其计算不存在的条件超几何分布。令 `P(T_i=a)=\sum_k P(T_i=a,K_i=k)`，只有当它为正时才能归一化得到 `P(K_i=k\mid T_i=a)`。

**尤其不能采用** `\sum_u\pi(u)P(K_i=k\mid T_i=a,U=u)` 直接平均条件律；正确的第一阶段条件权重必须与 `\pi(u) P(T_i=a\mid U=u)` 成正比。

### 独立 verifier（不复用 proposer）

对于固定 profile `u` 和组 `h`，在原完整分配空间中，将节点自己固定为 `a` 后，恰好 `k_h` 个 reference 节点 treated 的合法完整分配数为

\[
N_{h,u}(k_h)=\binom{d_{ih}}{k_h}
\binom{n_h-1_{h=h_*}-d_{ih}}{m_h(u)-a1_{h=h_*}-k_h}.
\]

把 `\prod_h\sum_{k_h}N_{h,u}(k_h)x^{k_h}` 的第 `k` 项系数除以原始分母 `\prod_h\binom{n_h}{m_h(u)}`，再按 `\pi(u)` 混合，得到 `P(T_i=a,K_i=k)`。这与 proposer 的**条件超几何卷积**是不同的代码路径；在小图上还与 `2^N` 完整分配穷举独立对拍。

## 4. 三条正式路线的适用条件

| Route | 数学目标 | 额外必要条件 | D6 的支持核对 |
|---|---|---|---|
| R1a / Composition | `\mu_i^q(a,s)=E[Y_i^obs\mid T_i=a,S_i=s,W]` 与合法线性组合 | 各目标 arm A4 充分；不要求 exposure sufficiency | 目标 `(a,s)` 联合支持正数；Batch 逐节点核验 |
| R1b | `V(z\mid W)=\sum_i\omega_i E[Y_i(z)\mid W]` | assignment-level A4，完整分配 support 正数 | `q(z)>0`，独立完整组合分母检查 |
| R2 | 同一真实固定政策价值 | 研究者额外明确接受已绑定 signature 的**mean-signature sufficiency**，A4 对应签名均值 | 所有非零加权节点的目标签名支持正数；`q(z)` 可以为 0 |

**不得混淆** R1a 的“设计标准化 Direct/Spillover/Total”和 R1b/R2 的“固定政策潜在结果”。R2 不可从 majority、exact-count、any-treated 的 mapping 定义自动推导 mean sufficiency；不同 mapping 的充分性许可也不可互换。

## 5. A4/A5/A6 正式门禁及 fail-closed

- A4：必须声明原 D6 协议和可用于 query 的 typed population outcome observable。R1b 不得以四臂总体均值代替 assignment-level outcome；R2 不得借其他 signature 的 outcome 算子通过。
- A5：`known_assignment_law`, `full_vector_randomization`, `consistency`, `fixed_pretreatment_network`, `finite_conditional_first_moments` 均须满足；D6 额外的 `first_stage_profile_no_direct_outcome_effect` 不可默许。缺少/未确认 → NEEDS_INPUT；明确 contradict → UNSUPPORTED。软件不能检验这些现实世界假设。
- A6：不合法配额、重复 profile、权重不精确或未归一化、组不构成网络节点分区、E2 孤立节点、查询 arm 零支持，均不能产生 POINT。独立 verifier 需验证原 assignment 法与支持并能拒绝 certificate 篡改。
- 当前软件域：**2–64 个分组、1–64 个第一阶段 profiles**，每个组的 quota 在 `[0,n_h]`，全部概率是正的、总和严格为 1 的有理字符串。R1a 使用历史 N≤4096、degree≤4096 的运行约束及 D6 的精确卷积预算；超出域只能报告不可处理，不能猜测 support。

## 6. 正式代码与可复现的证据

- 公共 `TwoStageQuotaMixtureDesignV27` 与 `make_two_stage_quota_arm_task()`，统一 `identify_network_business_query()`；完整 `AssignmentSpec`、`SupportEngine` 与 E1–E5。
- proposer 为 `randomized_arm_family/assignment.py` 的 stage-one posterior weighted hypergeometric；独立 verifier 为 `randomized_arm_family/two_stage_verifier.py` 原分配整数生成多项式。
- `identification_batch.py`、`identification_policy_r1b.py`、`identification_policy_r2.py`、`identification_support_diagnostics.py` 接入 D6；各正式路线调用原 theorem 的 replay。
- `tests/test_two_stage_quota_mixture.py` 中有完整小图穷举对拍、E1–E5、D5 退化、A5 阻断、R1a/Batch/Composition、R1b、R2、业务入口与证书篡改。`tests/test_two_stage_showcase.py` 独立重新生成 HTML/JSON。
- `python -B -m examples.run_two_stage --output-dir showcase_v27` 会真正调用公开 API 创建 11 张合成业务卡，并检查每张成功结果的 theorem replay；包括非 ER Ring300 上 3 个指定 arm（**不是 300 节点全部 arm**）。

## 7. 明确未支持

任何 `Y_i(t,u)` 第一阶段直接结果效应、先宣布 saturation 导致行为变化、两阶段非均匀组内分配、随机化配额依赖中间 outcome 的 adaptive 设计、任意 stage-one quota kernel、动态/未知图、非二元处理、多阶段时序干预、通用 R3 observational 条件分解，以及数值 PFN Estimation，**都没有被 v2.7 本合同证明或实现**。

本文件是受限的识别结果数学合同，不是关于实证随机化协议可靠性、真实业务假设或具体销售效应的声明。
