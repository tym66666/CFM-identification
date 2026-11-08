# Post-release P2 | R3 观测网络分层 Exposure G-formula（正式有限子域）

> 状态：**已编码的 opt-in R3 theorem subroute，不是 v2.8，不是 Forastiere et al. (2021) 的通用实现。**
> 本文件只说明给定研究者**明确接受**的总体信息和因果假设时的数学结论，不断言真实公司数据满足这些假设。不包含有限样本估计、Policy 数值或通用 Network Auto-G。

## 1. 为什么需要新 Target，而不是修改原 R3 p-standardized

固定单时点、已知处理前简单无向图 `G`，二元完整向量 `T`，固定共同背景 `W=w`。令 `B` 为**全网共同的、离散处理前协变量层**，不是干预后变量，也不等同于任意节点个人/邻居高维 `X_i`。`B` 可能代表处理前登记的市场环境/业务时期等。

旧 R3 p-standardized：

\[
\mu_i^p(a,s\mid w)=\sum_{\mathbf t: (t_i,g_i(\mathbf t,G))=(a,s)}p(\mathbf t\mid T_i=a,S_i=s,w)\,\mathbb E[Y_i(\mathbf t)\mid W=w].
\]

它**不要求 exposure sufficiency**，但依赖完整向量条件交换性，其 Target 随观测 `p(T|W)` 改变。

**新 R3 Exposure Adjustment Target**：假定对许可节点存在完整的 exposure-potential-outcome 响应 `Y_i(a,s)`，定义

\[
\theta_i(a,s\mid w):=\mathbb E[Y_i(a,s)\mid W=w]
=\sum_{b\in\mathcal B}\rho_b\,\mathbb E[Y_i(a,s)\mid B=b,W=w], \quad \rho_b=P(B=b\mid W=w).
\]

对应 Direct/Spillover/Total 与预先登记节点权重，用现有 `EffectQueryV18` 线性组合。这里 **Target 与 `p(T|B,W)` 的 propensity 参数无关**，但依赖 `P(B|W)`、`g`、节点与权重。

## 2. 最小充分前提（A1–A6）

**A1/A2/A3：** 明确 `W=w`、B 定义、固定网络、明确 `g_i` 的 E1–E5 有效状态、以及具有科学定义的本人 treatment 和邻居 exposure。

**A5-I：个体潜在结果层 Exposure Sufficiency（强于均值充分性）**：

\[
Y_i(\mathbf t)=Y_i\big(t_i,g_i(\mathbf t,G)\big)
\quad \text{对所有完整 }\mathbf t,\text{许可的 }i\text{，几乎必然成立。}
\]

**不能将它换成** R2 的 `mean_signature_sufficiency`。这里选择强版本，是为了规避在观测 treatment 选择之下，先取条件均值再混合完整向量时的选择偏差。

**A5-II：Exposure-level *mean* conditional exchangeability（逐层）**：对每个相关 `(i,a,s)` 和所有正权重 `b`，

\[
\mathbb E[Y_i(a,s)\mid T_i=a,S_i=s,B=b,W=w]
=\mathbb E[Y_i(a,s)\mid B=b,W=w].
\]

这是直接面向个人处理与邻居 exposure 的无未观测混杂条件；**不要求**完整向量 `T` 与所有潜在结果独立。上述条件不是从独立 Bernoulli 形式自动推出来的。`B` 在真实业务中是否足以阻断隐藏混杂必须由领域专家论证；仅软件 admission 不构成科学证明。

**其余 A5：** consistency、固定处理前网络、有限条件一阶矩。这些分别使用 typed records。

**A4：** 必须有可用的**符号总体算子** `P(B=b|W)`, `E[Y_i^obs|T_i=a,S_i=s,B=b,W]`，并且绑定同一 scope/outcome/分层定义/Exposure 指纹。不能以 `finite sample estimates` 冒充 A4。

当前计算支持概率的**额外窄结构 A4** 是：

\[
p_{obs}(\mathbf T=\mathbf t\mid B=b,W=w)
=\prod_{j=1}^N (r_j^{(b)})^{t_j}(1-r_j^{(b)})^{1-t_j}.
\]

这个 conditional factorization 是需要单独科学接受的**观测总体律结构**，不是实验随机化或因果交换性。分层后**边际上** `T_i` 与 `T_j` 可以相关，因为共享 `B`。并未覆盖给定 `B` 仍然存在网络自选择依赖的业务。

**A6：** 对每个非零权重目标 `(i,a,s)`，每个 `ρ_b>0` 的 `b` 均要求

\[
P(T_i=a,S_i=s\mid B=b,W=w)>0.
\]

当前用精确有理数多项式卷积计算；独立 verifier 用相反方向递推与手写 E1–E5 判别重新校核。正支持且已登记总体条件均值方能发布 POINT。零支持是**本路线不适用**，不是任何意义的通用 non-ID 证明。

## 3. 证明

固定 `b`。Consistency 和 A5-I 使观测到的签名 `(a,s)` 结果等于 `Y_i(a,s)`。在 A6 正支持下，

\[
\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,B=b,W=w]
=\mathbb E[Y_i(a,s)\mid T_i=a,S_i=s,B=b,W=w].
\]

A5-II 把右端替换为 `E[Y_i(a,s)|B=b,W=w]`。再由 pre-treatment `P(B|W)` 做全概率标准化：

\[
\boxed{\theta_i(a,s\mid w)=\sum_b\rho_b\,
 \mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,B=b,W=w].}
\]

有限线性组合保持 POINT；但不能未经额外合同将它直接称为全局政策值或换成旧 R3 p-standardized Direct。

## 4. 一个重要的不可识别反例（为什么不能只靠 propensity）

令本节点 `T_i~Bernoulli(1/2)`，观察到 `Y_i^{obs}=T_i`，其他节点处理完全独立。**世界 A**：对所有人 `Y_i(1)=1, Y_i(0)=0`；**世界 B**：有潜在 `U=T_i`，且 `Y_i(1)=U,Y_i(0)=U`。两世界的观测 `p(T_i,Yobs)` 完全相同，处理向量分布也可以都完全因子化；但

\[
E_A[Y_i(1)]=1,\qquad E_B[Y_i(1)]=1/2.
\]

世界 B 违反曝光层交换性。这说明即使完整观测 treatment propensities 已知、support 正且 outcome 条件均值可用，没有 A5-II 仍不能据此识别目标。

另一个测试构造将远处节点 `T_k` 与 focal 结果共同依赖潜在 `U`，但 focal 的 `(T_i,S_i)` 独立 `U`：此时 exposure-level exchangeability 可以成立，完整向量交换性却失败，说明新路线在因果交换性上具有不同、可更弱的许可。

## 5. 代码/接口与限制

- `pfn_pipeline/identification_observational_exposure_adjustment.py`：typed A4、scoped A5、目标、算术、独立 replay。
- `ObservationalExposureAdjustedEffectsInquiryV27P2`：显式新业务查询（**不是** `ObservationalEffectsInquiryV26`）。正式业务路由 `R3_EXPOSURE_ADJUSTED_EFFECTS`。
- 可处理 E1–E5、Direct/Spillover/Total 与预设节点加权组合；允许最多 2000 节点、16 个 B 层、每目标参考节点最多 600（都是软件资源门禁，不是定理上限）。
- 输出 `NO_ADAPTER`，不生成 EstimationRequest 或真实效应数值。
- 假设与 A4 的真实性没有通过有限样本证明；仅检查声明的完整性、绑定与数学后果。
- **未支持**：节点特异的高维 `X_i`/邻居协变量 adjustment、一般非因子化观测律、Network Auto-G / chain graph、跨 W 的新目标总体、未观测混杂识别、稳定的一般 stochastic policy kernel、R4/R5。

## 6. 与文献的关系（明确不冒称复现）

1. Forastiere, Airoldi & Mealli (2021), *Identification and Estimation of Treatment and Interference Effects in Observational Studies on Networks*, JASA 116(534):901–918, DOI 10.1080/01621459.2020.1768100；研究本人+邻居 exposure 与个体/邻居协变量调整。本代码仅是**更窄的全网共同 B 分层**，未复现其个体级广义 propensity 方法。 https://arxiv.org/abs/1609.06245
2. Tchetgen Tchetgen, Fulcher & Shpitser (2021), *Auto-G-Computation of Causal Effects on a Network*, JASA 116(534):833–844；其 network joint law/chain-graph 识别与估计路线**尚未实现**。 https://pmc.ncbi.nlm.nih.gov/articles/PMC8345318/
3. Sävje (2024), *Causal inference with misspecified exposure mappings: separating definitions and assumptions*, Biometrika 111(1):1–15，提醒暴露的 Target 角色不能自动成为结构 sufficiency。 https://doi.org/10.1093/biomet/asad019
4. Bhadra & Schweinberger, *Causal Inference Under Network Interference*, arXiv:2508.06808v2（2026-08-09），强调固定/随机图与外推边界；本代码只条件于**一张固定处理前图**。 https://arxiv.org/abs/2508.06808v2
