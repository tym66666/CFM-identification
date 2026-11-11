# Causal-IDFM — Task 1 网络拓展 / POINT 拓展 正式数学合同

**状态：有限网络干扰下的 POINT Identification 拓展（不等概率固定名额、重随机化、加权暴露、分组暴露 + 四类目标）。** 以 D1–D6 × E1–E5 既有 arm-mean / 政策值识别为基线，复用其推理、求解与验证流程。本文只对**已知固定处理前无向图、二元单时点处理、固定条件层 W=w、精确有理概率**适用；不主张任意动态图、多值处理或数值估计。

## 1. A1–A3：网络、暴露、潜在结果与目标

- 固定节点 `V`（`N=|V|`），处理前已知简单无向网络 `G`，`N(i)` 为一跳邻居，`d_i=|N(i)|`。
- 处理向量 `T=(T_1,...,T_N)\in\{0,1\}^N`，`q(t\mid w)=P(T=t\mid W=w)` 为已知的完整分配律（不依据结果数据推断）。
- 暴露映射 `S_i(t)=g_i(t)` 将完整处理向量映射到节点的暴露状态。设计标准化 arm 均值 `\mu_i^q(a,s\mid w)` 是暴露格上的条件均值，其 POINT 识别只需原设计律 + `full_vector_randomization` + `consistency` + 目标 arm 正支持，**不**依赖 exposure sufficiency。把 `\mu_i(1,s)-\mu_i(0,s)` 解释为「暴露的因果效应」是**额外**采用 exposure sufficiency 后的更强解释；核对工具以 `interpretation` 字段区分 `design_standardized_contrast` 与 `causal_effect_under_exposure_sufficiency`。未采用充分性不拒绝该设计标准化对比——**不能把充分的解释层当作结论成立的前提，也不能用它混同「按原设计平均」与「暴露充分性效应」**。
- 潜在结果 `Y_i(t)`；观测 `Y_i^{obs}=Y_i(T)`（consistency）。假设 full-vector randomization `T\perp\{Y_i(t):i,t\}\mid W`、固定处理前图、以及相关条件一阶矩有限。

## 2. 一般 POINT 识别（Aronow–Samii 2017）

对目标节点 `i`、自身处理 `a\in\{0,1\}`、暴露状态 `s`，定义联合支持质量

\[
\pi_i(a,s\mid w)=P(T_i=a,\,S_i=s\mid w)
=\sum_{t:\,t_i=a,\;S_i(t)=s} q(t\mid w).
\]

当 `\pi_i(a,s\mid w)>0`，设计标准化 arm 均值可唯一写为观测总体条件均值：

\[
\mu_i^q(a,s\mid w)
=\sum_{t:\,t_i=a,\,S_i(t)=s}\frac{q(t\mid w)}{\pi_i(a,s\mid w)}\,E[Y_i(t)\mid w]
=E[Y_i^{obs}\mid W=w,\,T_i=a,\,S_i=s],
\]

其中第二个等号由 consistency 与 full-vector randomization 给出。因此只要 `\pi_i>0`，目标就由可观测总体分布唯一决定，即 POINT。**本文的四项功能都不是新识别定理**，而是把 `q` 的支撑结构扩展为新的、经验证的分配机制与暴露映射；POINT 的充分条件始终是「`q` 已知 + 全向量随机化 + consistency + 目标 arm 正支持」。

## 3. 四项新功能的精确定义

### 3.1 ① 不等概率固定名额

恰选 `m` 个 treated，但各完整名单概率不等。支持两种输入方式：任意合法完整名单概率表，以及更受限的单位权重乘积族。它们并不等价；后者可展开为概率表，任意概率表未必可写成单位权重乘积：

\[
q(A)=\begin{cases}
p_A, & A\in\mathcal A,\ \sum_{A\in\mathcal A}p_A=1,\ |A|=m,\\[4pt]
\dfrac{\prod_{i\in A}w_i}{\sum_{|B|=m}\prod_{j\in B}w_j}, & w_i\ge 0,\ \sum_{|B|=m}\prod_{j\in B}w_j>0.
\end{cases}
\]

例如四节点恰选两人时，乘积族必须满足 `q(ab)q(cd)=q(ac)q(bd)=q(ad)q(bc)`，任意名单概率表没有该限制。

其余 `|A|\ne m` 的名单 `q=0`。**关键查找**：`\sum_A q(A)=1`；不在 `\mathcal A`（或权重为零组合）的名单概率严格为 0；条件于 `T_i=a` 后仅保留含/不含 `i` 的名单重新归一。

### 3.2 ② 按平衡规则重随机化（Morgan–Rubin 2012）

设基础律 `q(A)` 与处理前平衡事件 `B(A)`（如各协变量 treated 与 untreated 均值差的绝对值不超过容差 `\delta`），重随机化后的律为拒绝抽样：

\[
q_B(A)=\frac{q(A)\,\mathbf1\{B(A)\}}{P_q(B)},\qquad
P_q(B)=\sum_{A}q(A)\,\mathbf1\{B(A)}>0.
\]

`q_B` 是 `q` 在平衡事件上的条件分布；每个平衡名单按原概率比例放大 `1/P_q(B)`，不满足 `B` 的名单概率为 0。平衡规则只依赖处理前协变量，不引入任何结果信息。

### 3.3 ③ 固定权重暴露

对每个节点 `i` 给定处理前非负权重 `w_{ij}\ge 0`（`j\in N(i)`），暴露状态为

\[
S_i(t)=\sum_{j\in N(i)}w_{ij}t_j \quad(\text{sum}),\qquad\text{或}\qquad
S_i(t)=\frac{\sum_{j\in N(i)}w_{ij}t_j}{\sum_{j\in N(i)}w_{ij}} \quad(\text{proportion}).
\]

业务读取字段目前只接受每个邻居一个全局权重 `w_j`；原生数学对象另可表达逐边 `w_ij`。不能把原生接口的逐边能力宣称为已通过自然语言入口验收。

proportion 模式下要求权重和非零（零权重节点该状态无定义）。状态是 `\mathbb Q` 上的精确值，不合并不同加权和。

### 3.4 ④ 分组暴露

给定处理前不相交的邻居分组 `G_1,\dots,G_K\subseteq N(i)`，暴露状态为逐组 treated 邻居人数的元组

\[
S_i(t)=\Big(\sum_{j\in G_1}t_j,\ \dots,\ \sum_{j\in G_K}t_j\Big),
\]

标签按稳定（字典）序排列。不同分组结构不可合并为同一状态；元组保留各组标签与联合概率。

## 4. 联合支持的计算与独立 verifier

**解析路径（D1–D6 × E1–E5）**：对每个 `a` 计算条件邻居计数律 `P(K_i=k\mid T_i=a)`（超几何 / Poisson-binomial / 簇 DP / 两阶段卷积），再按暴露分组 `\text{classify}(k,d_i)=s` 累加。这条路径避免 `2^N` 穷举。

**穷举路径（新设计 ① ② 与 加权/分组暴露）**：新设计无解析计数律，采用精确 `2^N` 全排列枚举，`N\le 8`；逐 `t` 累加 `q(t)` 到 `(t_i,S_i(t))`，再校验 `\sum\pi_i=1`。超出 `N\le 8` 只能报告不可处理，不猜测支持。

**独立 oracle**：`randomized_arm_family/support_verifier.py` 用自己的 `2^N` 循环独立复算联合支持，**不调用** `SupportEngine`、也不调用求解器的 `assignment_probability`/`statistic`/`classify`/平衡公式，在小图上与 proposer 对拍。这满足「证明重放 = 验证器检查数学证书与目标绑定」，而非复用同一计算函数。

## 5. 四类目标

以下是本次接入的目标与各路线所需支持。条件未审核、缺失和方法适用性失败由业务入口分别报告；原生路线的 `UNSUPPORTED` 不等于已证明目标不可识别。

| 目标 | 数学定义 | 正支持条件 |
|---|---|---|
| `local_direct_mean` | `sum_i omega_i [mu_i^q(1,s|w)-mu_i^q(0,s|w)]` | 每个非零权重评价节点的 `(0,s)` 与 `(1,s)` 正支持 |
| `peer_spillover_mean` | `sum_i omega_i [mu_i^q(a,s_1|w)-mu_i^q(a,s_0|w)]` | 每个非零权重评价节点的两个暴露格正支持 |
| `policy_mean` | `V(z|w)=sum_i omega_i E[Y_i(z)|W=w]` | R1b 要求完整政策 `q(z|w)>0`；R2 另需均值签名充分性及各目标签名正支持 |
| `policy_contrast` | `V(z_1|w)-V(z_0|w)` | 两端分别满足所用路线条件，保持比较方向与共同评价范围 |

其中 `omega_i` 是已审核的评价权重，和为 1。局部效应默认是按原设计 `q` 平均的 arm 均值之差；未采用额外充分性时不能把它写成只由 `(a,s)` 决定的潜在结果 `Y_i(a,s)`。固定政策 `z` 是要评价的安排，不是生成试验处理的分配律 `q`。

有限政策混合另以明确给定的权重 `rho_k` 组合 `sum_k rho_k V(z_k|w)`；它不等于自动按试验律 `q` 平均，也不构成任意策略函数的识别。完整政策与 arm 目标的充分性条件不得互换。上述支持是各路线的充分条件；支持失败只说明该路线不能给出结论，不是一般非点识别证明。

## 6. A4/A5/A6 门禁（fail-closed）

- **A5**：`known_assignment_law`、`full_vector_randomization`、`consistency`、`fixed_pretreatment_network`、`finite_conditional_first_moments` 均须确认。`exposure_sufficiency` **不是**设计标准化 arm 均值的形式识别条件；若另行采用它，只是把对比升级为「暴露的因果效应」解释，不能当作形式识别已完成的前提或结论。缺少/明确拒绝 A5 条件 → `UNSUPPORTED`。
- **A4**：目标单元格的总体条件均值必须由声明信息独立提供；有限样本不代替总体算子。
- **A6**：不等概率律概率和须为 1、重随机化平衡事件须正概率、权重须非负、分组须不相交、查询 arm 须正支持；不满足即 `UNSUPPORTED`，不得回退为 PARTIAL 猜测。

## 7. 正式代码与可复现证据

- 公共 wire 设计 `UnequalProbabilityFixedQuotaDesignV1`、`RerandomizedBalancedDesignV1`、`CovariateBalanceRuleV1`；内部精确层 `randomized_arm_family/`（`assignment_extensions.py`、`exposure_extensions.py`、`support_verifier.py`）。
- 任务接口 `cfm_id/network_design_adapter.py`（`task1_design`、`make_arm` 路由）与读取层 `cfm_id_llm/network_design_reading.py`、`network_policy_reading.py`。
- 正式识别与证书：`identification.py`（`make_*_arm_task` + `identify`）、`randomized_network_arm.py`（单臂）、`identification_batch.py`（批量，含 `_compute_wg`）、`identification_composition.py`（效应组合，含 W/G 坐标解析）、`identification_policy_r1b.py`（固定政策值/两政策差值）、`identification_policy_r2.py`（均值签名充分性政策值与两政策端点，D7/D8 走精确枚举 + 独立 oracle）；W/G 走单臂/批量/组合与业务派单（合同 `exposure_weights`/`exposure_groups` 字段，见 §3）。
- 组合查找表 `docs/task1_combination_lookup.md` 由 `examples/generate_task1_combination_lookup.py` 可复现生成；业务案例 `examples/task1_business_case_reference.py` 走完整派单链。
- **核对工具（非识别）**：`tests/task1_target_helpers.py` 给定各安排结果再算四类目标期望，仅作手算对照/组合表，**不构成正式识别**；`rule.py` 现为**正式识别规则入口**（`rule.identify` 转发证书路径、`rule.replay` 证明重放），包 `__init__` 不再导出核对目标。
- 测试：`tests/test_task1_*.py` 含小图 `2^N` 穷举对拍、正支持/零支持、四类目标手算核对、验证器独立性、W/G 证书与证书篡改拒绝；`tests_gateway/test_task1_weighted_grouped_business_case.py` 覆盖 W/G 业务派单。

## 8. 三条文献依据

- **Morgan, K. L., & Rubin, D. B. (2012).** *Rerandomization to Improve Covariate Balance in Experiments.* The Annals of Statistics 40(2), 1263–1282. doi:10.1214/12-AOS1008 —— 平衡规则下拒绝抽样的思想来源，对应 ② 重随机化。
- **Hájek, J. (1964).** *Asymptotic Theory of Rejective Sampling with Varying Probabilities from a Finite Population.* The Annals of Mathematical Statistics 35(4), 1491–1523. doi:10.1214/aoms/1177700375 —— rejective sampling 的 `q_B(A)=q(A)1\{B\}/P_q(B)` 精确形式。
- **Aronow, P. M., & Samii, C. (2017).** *Estimating Average Causal Effects Under General Interference, with Application to a Social Network Experiment.* The Annals of Applied Statistics 11(4), 1912–1947. doi:10.1214/16-AOAS1005 —— 一般暴露映射下 `\pi_i(t,s)=\sum_{u\in U_{i,t,s}}q(u)` 与 POINT 识别的框架，对应 ③ ④ 暴露与四类目标。

文献卡与"依据→推导→实现→测试"映射见 `literature_support/catalog.json`（`aronow_samii2017_interference`、`morgan_rubin2012_rerandomization`、`hajek1964_rejective_sampling`）与 `literature_support/routes/task1_network_point_extension.json`；文献只提供概念依据，项目推导与证书独立（未把任何原论文逐字作为本项目定理）。

## 9. 识别范围与明确未支持

按当前代码与本合同一致：

- **识别什么**：设计标准化条件 arm 均值 `\mu_i^q(a,s)=E[Y_i^{obs}\mid T_i=a,S_i=s]`（`\pi_i(a,s)>0`）；直接/溢出效应为 arm mean 对比；政策值与两政策差值在已知完整分配律下（R1B），或显式采用均值签名充分性时经 R2。
- **需要哪些条件**：`known_assignment_law`、`full_vector_randomization`、`consistency`、`fixed_pretreatment_network`、`finite_conditional_first_moments`、目标 arm 正支持；新设计精确支持依赖 `N\le 8` 全排列枚举。`exposure_sufficiency` **不是**设计标准化对比的条件（见 §1、§6）。
- **已完成**：① 不等概率固定名额、② 重随机化、③ 加权暴露、④ 分组暴露，均接入正式流程——单臂证书（`rule.identify`）、批量 `identification_batch`（W/G 按节点可达状态并集，非矩形，不可达格 pad UNSUPPORTED）、组合 `identification_composition`（W/G 坐标解析 + 独立 oracle）、效应业务派单、扩展 R1A 路由（D1–D8）；新设计的政策均值/两政策差值走 R1B（固定政策值，含有限政策混合）与 R2（均值签名充分性，含两政策端点）。
- **未完成**：`N>8` 解析推广（U1）；数值 PFN Estimation（U2）；R2 的 W/G 签名（U3，W/G 走 R1B/效应路线）；默认优先 R2（U5）；任意 stochastic policy kernel、动态/未知图、多值或连续处理、R3 观测条件分解（U6）。详见缺项/限制表。

本文件是受限的识别结果数学合同，不是关于真实业务假设成立、实证随机化协议可靠或具体效应大小的声明。

维护者补充（2026-11-11）：D4–D6 的分配质量现由验证器分别从簇、组内配额和两阶段混合概率独立复算；故障注入测试要求共享求解计算被破坏后仍拒绝错误证书。已有业务入口验收使用固定读取样例，不能代替真实 LLM 或网页自然语言验收。
