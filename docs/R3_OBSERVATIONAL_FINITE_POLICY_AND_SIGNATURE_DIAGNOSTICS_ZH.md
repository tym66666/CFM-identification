# Causal-IDFM Identification v2.3：有限观测网络 R3 POINT / D2-E1 Signature Support 诊断

当前接入状态：共同业务入口已连接固定W的 **R3_FULL_ASSIGNMENT**，显式签名读取配置另接 **R3_MEAN_SIGNATURE**，见 [接入合同](R3_POLICY_ENTRY_CONTRACT_ZH.md)。下文保留原生数学定义与历史批次说明，不代表其他R3目标已全部接入。

**研究版严格增量；正式基线 v2.2。日期：2026-10-17。** 不修改 Estimation / Policy / 旧的正式 R1a/R1b/R2 后端，保留 v2.2 原 32 张业务卡。

## 0. 已实现与未实现

新增两条有共同 A5 但不同 A6 的 **Observational Network 固定政策 POINT route**：

- **R3-Full**：完整观测 assignment cell 有正支持时识别固定政策值；不要求 exposure-sufficiency。
- **R3-Signature**：完整观测 assignment cell 零支持时，另外接受全域均值签名充分性，并在所有有正政策权重的节点上检查目标签名的观测支持。

额外增加 **D2/E1 Signature Quota Diagnostics**，它只是支持条件解释器而不是新识别定理，精确解释某节点为什么 support=0，并使用独立组合计数核对。

限制非常明确：已知固定简单无向网络；单时点二元 treatment；固定给定的完整前处理条件 `W=w`；输入严格为 **总体分布** `P_obs(T=t|W=w)` 和由**同一 A4 声明**覆盖的 node-assignment 条件均值符号算子；最多 12 个节点、最多 4096 个显式列出的正质量 assignment cell。**不把经验频数估计作为总体律；不处理连续 W 的积分、现实 A5 真实性检验、观测网络的 Direct/Spillover contrast 或 ER300 通用 observational policy。**

R3 与 R1b 的区别：观测分配律 `P_obs(T|W)` **不是**随机化设计 `q(T|W)`；观察到 propensity 严格不能产生因果许可。只有**额外、单独**接受的条件交换性才能使用 R3。

## 1. 明确的数学定理

给定固定处理前图 `G`、完整向量二元处理 `T∈{0,1}^N`、前处理完整信息 `W=w`，以及条件总体潜在均值

\[
m_i(\mathbf t,w)=\mathbb E[Y_i(\mathbf t)\mid W=w].
\]

固定政策目标为

\[
V(\mathbf z\mid w)=\sum_i\omega_i\,m_i(\mathbf z,w), \quad \omega_i\ge0,\ \sum_i\omega_i=1.
\]

**基础 A5：**（1）consistency：`Y_i^obs=Y_i(T)`；（2）全部潜在结果与实际完整处理向量 **full-vector conditional exchangeability**：`{Y_i(t):i,t} ⟂ T | W=w`；（3）固定处理前图；（4）有限一阶矩。

交换性一般**不能从数据中检验或自动推导**，只接受人类确认/领域依据/明确合成研究规范，有证据来源与 status。人口记录 `P_obs(T=t|W=w)` 只是 A4，不能替代 A5。

### R3-Full

如果在 A4 总体观测分配中 `P_obs(T=z|W=w)>0`，consistency + full-vector conditional exchangeability 给出

\[
V(\mathbf z\mid w)=\sum_i\omega_i\mathbb E[Y_i^{obs}\mid\mathbf T=\mathbf z,W=w].
\]

本公式不涉及 exposure mapping，不需要 mean-signature sufficiency。

### R3-Signature

额外、必须单独明确接受的**条件均值结构充分性**：对所有完整向量 `t`，

\[
\mathbb E[Y_i(\mathbf t)\mid W=w]
=h_i(t_i,g_i(\mathbf t,G),w).
\]

其中 `g` 目前可为已审核的 E1/E2/E3，来源和网络签名身份必须一致。若所有正权重节点均有

\[
\rho_i(a_i,s_i\mid w):=P_{obs}(T_i=a_i,g_i(\mathbf T,G)=s_i\mid W=w)>0,
\quad (a_i,s_i)=(z_i,g_i(\mathbf z,G)),
\]

则

\[
V(\mathbf z\mid w)=\sum_i\omega_i\,
\mathbb E[Y_i^{obs}\mid T_i=z_i, g_i(\mathbf T,G)=g_i(\mathbf z,G), W=w].
\]

**推导关键：**对每个实际赋值 `u`，consistency 把 `Yobs|T=u` 换为 `Y(u)|T=u`；交换性将其条件均值换为 `E[Y(u)|W=w]`；均值签名充分性将同签名各 `u` 的均值固定为 `h_i`；对正支持的签名条件集合求混合，即目标均值。无需声称个体级 potential outcomes 相等。

如果 `P_obs(T=z|W)=0` 且缺少结构充分性，只能报告当前 R3-Full 路线不适用，**不能声称已证明 causal target nonidentified**。

## 2. A4/A5/A6 Software Contract

- `NetworkStudyContextV17.observation_regime` 必须为 `observational`，不得声明随机化设计。
- `ObservationalFinitePopulationV23`：单个 admitted A4 source 同时声明完整的条件 assignment 分布与所有正质量 assignment 的 node-conditional mean 符号算子；所有概率是 canonical `Fraction`，正且精确合计 1。source 必须对应研究网络、节点顺序、条件 W、outcome 和 protocol digest。`FINITE_SAMPLE_ESTIMATE` 不能替代总体算子。
- `Assumption`：明确要求 `full_vector_conditional_exchangeability`, `consistency`, `fixed_pretreatment_network`, `finite_conditional_first_moments`；A5 未确认、来自 LLM proposal、缺少 evidence 一律拒绝。交换性不能通过 deterministic derivation 自行确认。
- Signature 路线还需 `SignatureSpecV20` 与 `MeanSignatureSufficiencyV20`，明确 A5 admittance，检查被目标正权重覆盖的全部节点。
- `identify_observational_policy_v23` 输出固定条件 W 的 POINT **符号**识别公式和独立 replay 证书；没有估计值或 PFN adapter。`replay_observational_policy_v23` 重新推导并使用第二套直接枚举/独立 exposure 判别进行支持概率对拍。
- `ObservationalPolicyInquiryV23` 接到已有 `identify_network_business_query()` 统一业务入口；原类型及路由优先级未改变，原受控实验路线保持独立。

科学身份 `target_fingerprint` 采用 v1.9/v2.0 固定完整分配政策目标身份合同，不把观测 vs 实验 protocol 当作 causal target 的一部分。A4 source/protocol 信息进入独立证书，不能混用另一研究的观测律。

### N≤12 是软件计算域，不是因果定理条件

有限 allocation-law 枚举只是本版本为严格检查和独立 replay 选择的**工程限制**。大网络观测分配需要新压缩算子/图概率模型/条件支持验证和新的相应证书机制；不能把 12 节点演示冒充 ER300 观测能力。

## 3. D2/E1 解释为什么 support=0

固定 `N=7, m=3`，目标全员处理，`E1` 严格多数（孤立节点按 E1 旧定义标为低暴露）。有邻居的节点 `i` 在目标签名 `(1,1)` 下需要至少

\[
K_i^{\min}=\lfloor d_i/2\rfloor+1
\]

个 treated 邻居；因为自己先占一个名额，实验最多允许 `m-1=2` 个 treated 邻居。因此当 `d_i≥4`，`P_q(T_i=1,S_i=1)=0`。这是 Star 中心、Complete 每个节点等支持不足的直接原因。

对本案例更一般的判据（d_i>0，D2 对 m 的完全随机化）：

\[
P_q(T_i=1,S_i=1)>0
\iff m\ge 2+\lfloor d_i/2\rfloor,
\]

假定其余 D2 基本配额可行 `0≤m≤N`。新诊断器对每个节点核验该阈值，还直接计算组合数：

\[
\pi_i^q(a,s)=\frac{\sum_{k:\,\text{E1}(k,d_i)=s}
\binom{d_i}{k}\binom{N-1-d_i}{m-a-k}}{\binom Nm}.
\]

将此与正式 `SupportEngine` 计算逐个核对，输出失败原因，如 `INSUFFICIENT_QUOTA_FOR_MAJORITY_SIGNATURE`。这是**A6 诊断，不会自动确认 R2 所需的因果充分性假设**。

## 4. 可复现命令

仓库根目录：

```bash
python -B -m unittest tests.test_observational_r3_and_signature_diagnostics -v
python -B -m unittest discover -s tests -q
python -B -m examples.run_observational_r3_and_signature --output-dir showcase_v23
python -B -m examples.run_business_coverage_delta --output-dir showcase_v23
```

打开 `showcase_v23/CFM_ID_v2_3_R3_and_Signature_Support.html`，对应同名 JSON 为机器可读执行记录。还有 `CFM_ID_v2_3_Business_Coverage_Delta_32plus5.json`。

**v2.2 原始 32 张业务卡逐项保持不变，另增加 C33–C37 五张观测固定政策卡。B24 是 observational DIRECT effect，R3-Full / R3-Signature 本版只实现 FIXED POLICY VALUE，所以 B24 仍是 `NO_REGISTERED_THEOREM`，不能偷换 Target 后计为 POINT。**

## 5. 后续优先级（未完成）

1. Observational R3：从有限显式 assignment table 推进到可验证的低维 conditional `P_obs(T_i,S_i|W)` + A4 node signature law、分组 W 标准化、合法 direct/spillover contrasts。必须明确局部 exchangeability 和 mean-sufficiency 的识别条件，不能降级为简单回归。
2. Randomized D4 Cluster（包括簇间干扰和簇内干扰、分配单位声明），以及 D5 任意多组固定 quota，需要新的精确支持与**独立 verifier**。
3. E4 Exact Treated-neighbor Count、E5 Any Treated Neighbor 作为可声明 exposure 规则接入现有 Randomized R1a 和 R2，尤其检查 isolated nodes 与 target-state 定义。
4. 导师 Demo：保持 v2.1 ER300 与 v2.2 32 卡看板，增加 v2.3 R3 的有限观测政策与 quota 零支持解释；对每张案例并列显示 L0/L1/L2/L3，不夸大市场覆盖。

**正确性警告：** replay、哈希和 A5 metadata 无法在真实世界证明交换性或签名充分性为真。只有在明确声明的总体算子与外部因果假设成立的条件下，才有 population-level POINT 识别结论。
