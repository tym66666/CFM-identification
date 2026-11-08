# Post-release P1：R3 有限混合观测处理分配律的正式数学合同

> 状态：**新 A4 计算子域**，复用 `R3_P_STANDARDIZED_EFFECTS`，非新的 theorem route，也不是新 A5 因果假设。先验证必要数学合同、正反例与独立 verifier；不改变 R1a/R1b/R2、旧 R3 policy 和 Estimation 的目标或输出。

## 1. 对象与有效域

- 研究固定、处理前、简单无向网络 `G`，单时点二元处理 `T_i∈{0,1}`，固定背景条件 `W=w`。
- 明确接受观测总体分配律的有限混合表示，其中 `H≤16`，每个分量内节点独立，但**给定 W 的边际分配一般是相关的**：

\[
 p_{\rm obs}(\mathbf t\mid w)
 =\sum_{h=1}^{H}\pi_h\prod_{j=1}^{N}
 r_{hj}^{t_j}(1-r_{hj})^{1-t_j},\quad
 \pi_h>0,\ \sum_h\pi_h=1,\ 0\le r_{hj}\le1.
\]

- 混合变量 `h` 是数学表示中的潜在类别，**不是**实验第一阶段的已随机化 treatment，也不能因为其存在就断言 `(T_i)` 因果随机。
- `π_h` 与全部 `r_hj` 为精确有理数的已批准**总体**信息；不接受浮点近似来虚构数学零支持，也不接受仅提供的有限样本频率。
- A4 同时提供查询中每一个非零线性项所需的 `E[Y_i^obs|T_i=a,S_i=s,W=w]` **总体符号条件均值算子**；本模块不提供这类均值的估计数值。
- 可用 E1–E5（E3 需要单独预先规定的核心协作者集合），网络最多 2000 节点，每个查询的参考集合规模至多 600（工程 guard），不是普遍数学上限。

## 2. 因果目标与识别定理

定义 `A_i(a,s)={t:t_i=a,g_i(t,G)=s}` 与联合 arm support：

\[
\rho_i^p(a,s\mid w)=\sum_{\mathbf t\in A_i(a,s)}p_{\rm obs}(\mathbf t\mid w).
\]

在以下**另行确认**的 A5 成立时：`full_vector_conditional_exchangeability`、`consistency`、`fixed_pretreatment_network`、`finite_conditional_first_moments`，以及目标所需 `ρ_i^p(a,s|w)>0`、相应 A4 总体条件均值存在，则

\[
\begin{aligned}
\mu_i^p(a,s\mid w)
&:=\frac{\displaystyle\sum_{\mathbf t\in A_i(a,s)}
 p_{\rm obs}(\mathbf t\mid w)\,\mathbb E[Y_i(\mathbf t)\mid W=w]}
 {\rho_i^p(a,s\mid w)}\\
&=\mathbb E[Y_i^{\rm obs}\mid T_i=a,S_i=s,W=w].
\end{aligned}
\]

可复用 R1a 的 `EffectQueryV18` 线性组合，识别观测律标准化的 Direct、Spillover、Total、预先指定节点加权平均。**不需要 exposure sufficiency**。这些值不自动等于控制所有其他人的 `T_{-i}` 不变时的因果效应，也不自动等于固定全局政策价值。

## 3. 精确 support 算法（A6）

令 `R_i` 为 exposure 参考邻居（E3 用 pre-treatment core）。每个分量的 Poisson-binomial 邻居处理数生成多项式：

\[
 F_{i,h}(x)=\prod_{j\in R_i}[(1-r_{hj})+r_{hj}x].
\]

若第 `k` 个邻居处理数归于暴露状态 `s`，则

\[
\rho_i^p(a,s\mid w)
=\sum_h\pi_h\,r_{hi}^a(1-r_{hi})^{1-a}
\sum_{k:g_i(k,G)=s}[x^k]F_{i,h}(x).
\]

主计算由精确有理数多项式卷积计算；**独立 verifier** 倒序使用稀疏计数递推，并使用手写 E1–E5 分类复核每个正权重项。小图另有完全独立的完整二元 treatment 向量枚举 oracle，覆盖 E1–E5。

**为什么不能对混合分量的节点 propensity 先平均再乘？** 通常
\(\sum_h\pi_h r_{hi}r_{hj}\neq(\sum_h\pi_h r_{hi})(\sum_h\pi_h r_{hj})\)。
例如 \(\pi=(1/3,2/3),\ r_h=(1/4,3/4)\) 时，任意两节点 \(P(T_i=T_j=1)=19/48\)，而 \(P(T_i=1)P(T_j=1)=49/144\)，不相等。

## 4. A4/来源/目标同一性

- `source_id`、来源、完整节点顺序、研究 scope、protocol、outcome、W、signature 全部绑定 typed A4。
- 分量概率向量排序、重复向量合并；精确 `π` 正且总和为 1。混合分量的重排不改变其 canonically-declared model fingerprint。
- **小图 ≤12 节点**：跨独立 Bernoulli、有限 mixture、完整赋值总体表，以完整二元分配枚举证明 `p_obs` 是否精确一致。
- **大图**：完全相同的规范化混合模型及同一 Target 可以认证声明模型同一；不同的混合模型不能仅凭相似名称、相同一阶 marginals，或 `marginal_law_fingerprint=None` 宣称相同目标。
- `replay` 独立检查结果包、全文证书 hash、全定理再算、support 对拍，不证明 A4 来源内容在真实世界成立。

## 5. 重要反例与安全拒绝

1. `p_obs` 存在相关性并不自动意味着 A5 交换性：如果 latent mixture class 同时影响 `Y_i(t)`，full-vector conditional exchangeability 可能失败；必须另行科学论证。
2. `PROPOSED` 或只有 `FINITE_SAMPLE_ESTIMATE` 的 A4，不可以返回 POINT。
3. 某个非零项的 arm 联合 support = 0，不能把该概率改为小正数；当前这条 theorem 拒绝。
4. 即使概率支持 >0，缺少 typed arm 总体均值仍被拒绝。
5. 已声明但无数学定义的 exposure cells，即使本次业务查询未使用，也被拒绝。
6. 大图混合律与另一 A4 表示缺乏等价证明时，不允许下游合并；现有 estimation 仍 `NO_ADAPTER`。

## 6. 独立复验与交付边界

- 源码：`pfn_pipeline/identification_observational_mixture_a4.py`。
- 路由：在旧 `ObservationalEffectsInquiryV26` 中 opt-in 注入新 typed source，**仍为 R3_P_STANDARDIZED_EFFECTS**。
- 测试：`tests/test_r3_mixture_correlated_a4.py`（独立全赋值 oracle、反例、证书）和 `tests/test_r3_mixture_showcase_and_inventory.py`。
- 演示：`examples/run_r3_correlated_mixture.py`，300 节点 Ring，9 个合成符号业务查询。
- **不支持**任意相关的 `p_obs(T|X,W)`、一般 Forastiere GPS、任意 nodewise multivariate adjustment、Network Auto-G、固定政策 R3 的大图改造、数值 estimation，或将 A5 由机器自动证实。

本阶段 A0 由另一开发线推进，R4/R5、DAG/PARTIAL 暂不纳入。
