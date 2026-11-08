# R3 Nodewise Pretreatment Covariate & Neighbor Adjustment — 正式有限数学合同

**识别结论：有条件的 Population POINT；不是数据中自动证实的因果效应，不是任意高维 GPS，不是 Network Auto-G，不是有限样本 Estimation。**

## A1–A3：目标、变量和网络

固定背景 `W=w` 和**处理前固定无向图** `G=(V,E)`，每个节点有二元处理 `T_i`、结果 `Y_i`、处理前二元协变量 `X_i∈{0,1}`。 Exposure `S_i=g_i(T,G)` 可以是已有的 E1–E5（E3 使用预先确认的 core collaborators）。

第 `i` 个节点的**局部调整变量**定义为

\[
C_i=(X_i,K_i^X),\quad K_i^X=\sum_{j\in N_G(i)} X_j.
\]

`N_G(i)` 始终是完整无向图的一跳邻居，与 E3 `g_i` 的 core collaborators 子集可能不同。`K_i^X` 是**邻居的处理前协变量计数**，不是邻居使用 AI 的人数，也不是处理后变量。

目标：

\[
\theta_i(a,s\mid w)=E[Y_i(a,s)\mid W=w].
\]

目标可以经现有 `EffectQueryV18` 组合为 Direct、Spillover、Total 以及有处理前 cohort 证据的群体加权组合。**目标不是按观测 `p(T)` 标准化的旧 R3 设计混合均值，也不等于完整固定政策值。**

## A5：科学假设（不可由机器推断真实性）

1. **个体层 exposure potential-outcome sufficiency**：对所有完整处理向量 `t` 和许可节点，`Y_i(t)=Y_i(t_i,g_i(t,G))` 几乎处处；不能仅凭定义 `g_i` 或 R2 的 mean sufficiency 自动接受。
2. **节点局部调整的 exposure-level 均值条件交换性**：对于各个正质量局部层 `C_i=c` 和目标签名，

\[
E[Y_i(a,s)\mid T_i=a,S_i=s,C_i=c,W=w]=E[Y_i(a,s)\mid C_i=c,W=w].
\]

这是一条特定节点、特定结果与局部混杂调整集的科学假设；即使观测处理 `T` 给定完整 `X` 独立 Bernoulli，亦不推出这一因果交换性。共享处理前协变量或未观测混杂可能使它失败。软件只检查人工明示的**来源、确认状态、study scope、Exposure fingerprint、调整变量 schema 和 covered nodes**。
3. 一致性、固定处理前图、有限条件一阶矩。

## A4：可用的总体信息算子及粒度

使用有限个 `P(X-vector=x^k|W)=π_k>0`，`Σ_k π_k=1`，配置向量彼此不同，且给定每个配置明确声明总体律

\[
p_{obs}(T=t\mid X=x^k,W=w)=\prod_{j\in V}(r_j^k)^{t_j}(1-r_j^k)^{1-t_j}.
\]

这是一项**可选但很强的、已知总体处理律结构 A4**；不是实验随机化，也不是识别定理要求的最弱 A4。只有给定 `X-vector` 的分配可因子化，**给定局部 `C_i` 的处理分布一般是 profile 混合，不能再当成独立 Bernoulli**。明确提供 `E[Y_i^obs|T_i=a,S_i=s,C_i=c,W=w]` 的 typed 符号总体条件均值算子；任何有限样本估计值不能冒充它。

实现限制为最多 `MAX_NODE_COUNT`（上游限定为 2000）个节点、24 个不同的正质量完整预处理协变量配置、所需节点 Exposure 参考度数和局部一跳度数均不超过 600。属于软件精确核验资源上限，不是数学定理的上限。不能把这些限制解释为 `P(X)` 只允许全局 24 种的普遍科学假设。

## A6：局部调整层条件正支持

对每个目标 `(i,a,s)` 和所有 `P(C_i=c|W)>0` 的层，检查

\[
P_{obs}(T_i=a,S_i=s\mid C_i=c,W)>0.
\]

其中 `C_i(x^k)=(x_i^k,\sum_{j\in N_G(i)}x_j^k)`，

\[
\rho_{i,c}=\sum_{k:C_i(x^k)=c}\pi_k,\qquad
p_{i,c}(a,s)=\frac{1}{\rho_{i,c}}
\sum_{k:C_i(x^k)=c}\pi_k\;P(T_i=a,S_i=s\mid X=x^k,W).
\]

后一项通过独立 Bernoulli 邻居计数多项式精确计算，**不能省去 profile 混合项**。实现采用 `Fraction` 精确支持和反方向递推独立 verifier；对 E1–E5 另在小图下与完整向量枚举对拍。注意**不要求每个完整 `X=x^k` 配置各自支持正**；只需要总体 `C_i=c` 调整层有正支持。

## 识别证明

固定 `C_i=c`，由 consistency 和个体 exposure sufficiency：

\[
E[Y_i^{obs}\mid T_i=a,S_i=s,C_i=c,W]
=E[Y_i(a,s)\mid T_i=a,S_i=s,C_i=c,W].
\]

由所接受的局部 exposure-level 均值交换性，上式等于 `E[Y_i(a,s)|C_i=c,W]`。再对处理前 `C_i` 的总体分布标准化：

\[
\boxed{E[Y_i(a,s)\mid W=w]=\sum_{c:\rho_{i,c}>0}\rho_{i,c}
E[Y_i^{obs}\mid T_i=a,S_i=s,C_i=c,W=w].}
\]

有限精确线性组合继承 POINT。**此结论只对本研究条件层、已接受的 A5 和信息 A4 及正支持的目标成立。**

## 负例与可识别性边界

即使所有 `T_j|X` 节点独立且 support 严格正，仍可能存在未观测 `U_i` 同时决定 treatment 和 outcome。令 observed `Yobs_i=T_i` 且 `P(T_i=1)=1/2`。世界 A：`Y_i(1)=1,Y_i(0)=0`；世界 B：`U_i=T_i`，`Y_i(1)=U_i,Y_i(0)=U_i`。两世界拥有相同的观测 treatment-outcome 联合律，但 `E[Y_i(1)]` 分别为 `1` 与 `1/2`。所以不接受 exchangeability 时，**不能因已知 Bernoulli 统计结构就返回 POINT**。

另一个单独的诊断：若在某正质量 `C_i=c` 下目标 arm 支持为零，则该局部调整公式不适用。这个 route refusal **不是对所有可设想的模型的 NON-ID 证明**。

## 代码定位与兼容性

- `pfn_pipeline/identification_observational_nodewise_adjustment.py`：来源声明、scoped A5、条件支持、目标身份、独立重放。
- `ObservationalNodewiseAdjustedEffectsInquiryV28`：opt-in 统一业务路由 `R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS`。
- `inspect_verified_business_handoff_v27` 已识别新 route 并返回 `NO_ADAPTER`，不生成 `EstimationRequest`。旧 API 名称和原 8/9-route 假设目录保持兼容，新 `implemented_assumption_catalog_v28` 为**可选扩展**。
- 不对 A0 做变更；不实现 R4、R5、Chain-graph Auto-G、任意异质局部协变量维度、跨 W 总体、未知/动态网络或数值 Estimation。

## 文献关系

[Forastiere, Airoldi & Mealli (2021)](https://arxiv.org/abs/1609.06245) 支持本人处理与邻居 exposure 的调整研究动机；本模块**不是其广义 propensity 方法的实现**。[Aronow & Samii (2017)](https://arxiv.org/abs/1305.6156) 区分 Exposure 定义、实验设计与 causal estimand。[Sävje (2024)](https://doi.org/10.1093/biomet/asad019) 强调 exposure 定义本身不是 causal sufficiency。[Tchetgen Tchetgen, Fulcher & Shpitser (2021)](https://pmc.ncbi.nlm.nih.gov/articles/PMC8345318/) 的 Auto-G/chain-graph 并未由本路线实现。[Bhadra & Schweinberger (2026-08-09, v2)](https://arxiv.org/abs/2508.06808v2) 为整体网络识别分类提供背景。
