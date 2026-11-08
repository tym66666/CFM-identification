# Two-stage / Randomized Saturation — 数学合同草案及可执行验收（pre-，非生产定理）

**状态：DRAFT / RESEARCH ORACLE ONLY。**本文件不宣布 v2.7 已实现，不新增正式 D6，不更改 R1a/R1b/R2/R3 Identification 或 Policy/Estimation 接口。当前只研究一个有限、明确、可验证的 **固定处理前分组 + 第一阶段随机 quota profile + 第二阶段组内独立均匀固定配额** 子域。

## A0/A1：研究问题及 Target

固定预处理网络 `G`、节点集 `V`、条件层 `W=w`、处理前分组划分 `C_1,...,C_H`。完整二元处理 `T∈{0,1}^N`。在第一阶段 quota profile `U=(m_1,...,m_H)` 对结果**没有独立于完整处理向量 T 的额外直接影响**的明示假设下，潜在结果写为 `Y_i(t)`。

**必须特别确认此排除式语义：**若向员工公开“所属团队将执行80% 的 AI 开放比例”这一政策声明，即使最终分配 `t` 相同，也可能产生独立的行为影响，此时应该是 `Y_i(t,u)`。不能将 `U` 从潜在结果中隐去再套用现有 R1a/R1b/R2。该排除/版本稳定性假设不能由软件检验，也不能因 `U` 只是设计代码而默认成立。

如能明确接受上述约束，R1a 的 arm 目标应以**边际完整分配律 `q(t|w)`**标准化，R1b 的真实固定政策目标仍为 `V(z|w)=∑_iω_iE[Y_i(z)|W=w]`。R2 必须额外明确接受相应 signature 下的均值充分性；第一阶段分组和 quota profile 本身不构成 sufficiency。

## A2/A3：设计与网络

- `C_h` 由处理前信息确定，是 **assignment groups**，不要求是图连通分量；跨组边允许且必须计入 exposure。不能把其与 D4“整簇共享一个处理”的 cluster Bernoulli 混淆。
- 第一阶段从有限、已知、精确有理数分布 `π(u|w)>0` 抽取 quota profile；各 `m_h(u)` 为整数且满足 `0≤m_h(u)≤|C_h|`。整个 profile 联合分布必须已知，可以产生跨组 quota 相关性；独立 profile 选择只是它的一个特例。
- 第二阶段给定 `u` 后，各组独立，从 `C_h` 中 **均匀无放回**地选择恰好 `m_h(u)` 名 treated。无动态自适应过程，不用估计出来的 propensity 代替已知设计律。

## 核心精确分配律

定义 `n_h=|C_h|`、`S_h(t)=∑_{j∈C_h}t_j`，则

\[
q(\mathbf t\mid w)=\sum_{\mathbf u}\pi(\mathbf u\mid w)
\prod_{h=1}^{H}
\frac{\mathbb 1\{S_h(\mathbf t)=m_h(\mathbf u)\}}
{\binom{n_h}{m_h(\mathbf u)}}.
\]

由于组间在**给定第一阶段 profile**后独立，混合后的边际分配不必跨组独立。若 `π` 只有一个支持 profile，这个定律退化成组内固定配额的 D3/D5 特例；若某组 `m_h(u)` 为 0 或 `n_h`，该组全 0 或全 1 是设计必然结果，不表示具有另一个处理状态的条件支持。

## A6：精确邻居处理人数支持

令 `R_i⊆N_G(i)` 为 Exposure 使用的处理前 reference neighbors，`d_{ih}=|R_i∩C_h|`，节点 `i` 属于 `C_{h_*}`。在第一阶段给定 `U=u` 且条件 `T_i=a` 可行时，

\[
p_i(a\mid u)=P(T_i=a\mid U=u,W=w)
=\begin{cases}m_{h_*}(u)/n_{h_*},&a=1,\\
1-m_{h_*}(u)/n_{h_*},&a=0.
\end{cases}
\]

给定 `U=u,T_i=a`，各组 reference treated-neighbor counts 独立且服从超几何分布：

\[
K_{ih}\mid U=u,T_i=a\sim\operatorname{Hypergeom}
\big(N_{ih},M_{ih},d_{ih}\big),
\quad N_{ih}=n_h-\mathbb1\{h=h_*\},\quad
M_{ih}=m_h(u)-a\mathbb1\{h=h_*\}.
\]

这里 Hypergeom 表示在 `N` 人中固定 `M` 名 treated，观察其中预设的 `d` 名 reference neighbors 里有多少 treated。若 `p_i(a|u)=0`，不能对这项条件律进行除零计算；它对联合支持质量的贡献为零。

因此有**联合（而不是无条件第一阶段平均的条件）分布**：

\[
P_q(T_i=a,K_i=k\mid W=w)
=\sum_u \pi(u\mid w)p_i(a\mid u)
\left[\underset{h=1}^{H}{\ast}
\operatorname{Hypergeom}(N_{ih},M_{ih},d_{ih})\right](k).
\]

当且仅当 `P_q(T_i=a|W)>0`，

\[
P_q(K_i=k\mid T_i=a,W)=
\frac{P_q(T_i=a,K_i=k\mid W)}{\sum_jP_q(T_i=a,K_i=j\mid W)}.
\]

**严禁用 `∑_uπ(u)P(K_i=k|T_i=a,U=u)` 作为上述条件律。**因为 `T_i=a` 会改变第一阶段 profile 的后验权重，正确系数必须是 `π(u) p_i(a|u)` 并最终正规化。旧 D1–D5 可调用的 R1a/R2 联合 arm/signature 支持可再对 `k` 按合法 exposure 状态求和；R1b 使用上述 `q(z)`。E2 的孤立节点仍要拒绝未定义 exposure；E3 的 `R_i` 应由完整预处理核心合作者声明给出。

## A4 / A5 / A6 正式接入前的硬门槛

**A4**：必须分别提供已知两阶段设计律（第一阶段 profile 概率、处理前 groups、组内均匀抽样证据）和与目标相匹配的总体 outcome 信息算子；仅有处理名单、样本比例或 treatment logs 不是已知随机化设计。`q` 不能继承观测研究的 `p_obs` 身份。

**A5**：须确认随机化机制相对整个潜在结果表的独立性、consistency、图固定且处理前、条件一阶矩有限；另外特别记录第一阶段 profile 不独立影响潜在结果的结构/版本假设。没有这条许可，`Y_i(t,u)` 目标应独立立项，禁止直接重用现有 theorem。

**A6**：精准处理 `(i)` 全部分配概率归一性、`(ii)` 自身处理零概率、`(iii)` reference count 的联合支持、`(iv)` R1a 每个 requested arm、`(v)` R1b `q(z)>0`、`(vi)` R2 每个带非零权重政策签名支持；零支持不意味着所有因果目标不可识别。需要独立 full-vector enumeration 作小图 oracle，不能完全依赖同一公式的两次调用。

## 已实现的研究型 oracle / 验收（当前工作副本）

`predevelopment/two_stage_exact_oracle.py` 提供一个 **独立于生产 pfn_pipeline 的有限有理数计算器**：有限 profile 严格校验、`q(z)`、全向量枚举 support、按第一阶段混合的超几何卷积、两种算法对拍、零处理臂返回 undefined 的条件律。它**不是** `AssignmentSpec` 注册类型，不能从业务入口获得 POINT。

`tests/test_predevelopment_two_stage_math.py` 覆盖：2–3 组与 3–6 节点混合协议、跨组邻边、第一阶段相关 quotas、完整概率和为 1、每个节点两种自身 treatment 的 count 支持、单 profile 退化为正式 D5 的 q 和 count、第一阶段选择偏差、零自身处理支持与坏协议拒绝。

案例：四节点两组 `{a,b},{c,d}`；`π((0,1))=π((2,1))=1/2`。对于节点 a，`P(T_a=1)=1/2`，条件 `T_a=1` 下第一个 profile 后验权重变为 0；对 reference 邻居 `{b,c}`，

\[
P(K_a=0,1,2\mid T_a=1)=(0,\tfrac12,\tfrac12),
\quad P(T_a=1,K_a=0,1,2)=(0,\tfrac14,\tfrac14).
\]

该精确值由组超几何卷积与枚举全部 `2^4` 完整处理向量分别核对。它是**分配概率计算的正反测试**，没有 Y 结果模型或任何因果估计值。

## 后续真正开发前尚需明确的问题

1. 第一阶段空间：是否只允许组级独立饱和度抽取，还是允许整个 quota profile 的联合抽样（当前研究 oracle 允许后者）？需要取舍可靠性、性能和常见业务价值。
2. 第一阶段的结果是否已被受试者知晓并可能直接影响 outcome？若是，应将问题升级为包含 `U` 的政策目标，不能直接复用本草案的排除假设。
3. 选择 `H`、组大小、profile 数目、精确有理分母的资源限额，并明示性能超过限制时 `UNSUPPORTED` 而不是错误 POINT。
4. 原 D3/D5 的精确概率内核如何共享，同时保留独立 verifier（禁止同一算法包装两次后声称独立证明）。
5. A4 的两阶段设计记录与 route/target fingerprint 中必须绑定 `π`、配额、组身份、节点顺序、W 条件层；第一阶段 profile 重新加权通常会改变 q-std arm 目标身份。
6. 如未来需要 conditional-on-first-stage 的目标 `μ_i(a,s|U=u,W)`，它**不同于**当前的边际 `q` 标准化目标，应单独定义。

**准备状态**：设计律数学合同草案和研究 oracle 正反例已建立；尚未注册正式设计/识别 API，尚未提供生产 verifier、全仓库的 Two-stage Identification 结果或真实估计器；现阶段不允许标为 v2.7 DONE。
