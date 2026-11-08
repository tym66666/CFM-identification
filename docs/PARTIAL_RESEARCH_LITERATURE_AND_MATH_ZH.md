# 非主线研究：最小 Network PARTIAL 示范和文献路线（Research only）

> 本文不是正式 R4/Network PARTIAL 后端。`research_partial/` 与 `pfn_pipeline/` 隔离，既不返回生产 POINT，也不发正式 PARTIAL 证书。当前 version 1 主线仍优先广覆盖 POINT。

## 文献定位与优先级

| 优先级 | 文献与精确链接 | 已有内容 | 最值得与当前代码结合的 Setting | 难度 |
|---|---|---|---|---|
| 1 | Wang, Ziyan; Liu, Yiran; Zhang, Zhiheng (2026), **Partial Identification of Policy Values under Network Interference**, ICML, PMLR 306:128571–128597. https://proceedings.mlr.press/v306/wang26ez.html | 非重叠网络政策价值、暴露映射、平滑性约束及 LP bounds | R1b 完整政策 zero support / R2 签名部分覆盖，扩展至有额外平滑性约束的政策上下界 | 中；需新 A5 + LP sharpness |
| 2 | Manski (2013), **Identification of Treatment Response with Social Interactions**, Econometrics Journal 16:S1–S23. https://doi.org/10.1111/j.1368-423X.2012.00368.x | 社会交互响应的结构约束、单调性与部分识别 | 现有 R2 mean-signature sufficiency 基础上引入有界结果，继而研究单调响应约束 | 很低到中 |
| 3 | Schröder, Oprescu, Feuerriegel & Kallus (2026), **Causal Inference on Networks under Misspecified Exposure Mappings: A Partial Identification Framework**, arXiv:2602.03459. https://arxiv.org/abs/2602.03459 | Exposure mapping 可能失真时的 direct/spillover sharp bounds | E1/E2/E5 粗暴露不能严格充分时，替代“假设正确”的 POINT 结论 | 中高；不可直接将其公式套在 R2 |
| 4 | Duarte, Finkelstein, Knox 等 (2023/2024), **An Automated Approach to Causal Inference in Discrete Settings**, JASA, https://doi.org/10.1080/01621459.2023.2216909 | 离散因果模型自动界限/优化 | 未来做一般有限网络的约束世界求解 R4 | 高，组合数量爆炸 |
| 背景 | Aronow & Samii (2017), Ann. Appl. Stat., https://doi.org/10.1214/16-AOAS1005；Hudgens & Halloran (2008), JASA, https://doi.org/10.1198/016214508000000292 | 定义网络 Exposure、随机化设计及因果 estimand | 保留 v1 POINT Target 的标准化语义，定义 Partial 目标时避免混淆 | 背景必读 |

第一条 Wang–Liu–Zhang 与本项目政策路线非常贴近，但本文展示的极简 [0,1] 界**并未复现该论文的平滑性 LP 方法**。Schröder 则是更有创新和科学意义、但开发难度高的后续研究选项。

## 这次真正做了的微型 Partial 研究示例

固定 Star7 处理前简单无向网络：一个中心 hub 与 6 个叶节点相连。原实验是 D2 均匀 complete randomization，每次恰好 3 人 treated，共 `C(7,3)=35` 种完整分配；E1 指邻居 treated 人数超过严格一半。

目标为全员处理政策的平均结果：

\[
V(\mathbf1)=\frac17\sum_{i=1}^7 E[Y_i(\mathbf1)\mid W].
\]

本例**另外单独明确接受**：

- 随机化、Consistency、固定网络、相关总体 arm 均值可得；
- R2 的 mean-signature sufficiency：`E[Y_i(t)|W]=h_i(t_i,g_i(t,G),W)`；
- 任意目标政策的结果支持有真实科学依据的 `0≤Y_i(t)≤1`（例如二元转化率）；
- 除上述外**没有跨节点、跨签名的平滑性、单调性或其他耦合限制**。

在全员处理政策下，每个叶节点的签名为 `(T_i=1,E1=1)`，由于自身及 hub 同时 treated 是可能的，其联合支持精确为 `1/7`。中心 hub 要求自己 treated 且至少 4 位叶节点 treated，共需≥5 人，而原实验只有 3 个 treated，因此其目标签名支持为零。

设 6 个叶节点上述签名的已识别总体条件均值为 `μ_i`。中心 hub 未观测该签名下的均值 `h_hub(1,1)`，仅能限定在 `[0,1]`。于是得到:

\[
\boxed{\frac17\sum_{i\in\mathrm{leaves}}\mu_i\ \le\ V(\mathbf1)\ \le\ \frac17\Big(\sum_{i\in\mathrm{leaves}}\mu_i+1\Big).}
\]

区间宽度 `1/7`。若**只用于示例**设所有叶节点 `μ_i=1/2`，区间 `[3/7, 4/7]`；这些 μ 不是估计数据或实际销售转化率。我们构造两个与全部 35 种原随机实验的观测分布一致的世界：所有可达的 potential outcomes 都取 `1/2`，但 hub 在不可达的 `(1,1)` 签名下分别取 `0` 与 `1`。两者同时满足 mean-signature sufficiency 和结果边界，并分别实现政策值 `3/7` 和 `4/7`。在**本例给定限制模型类**下两端可达，区间 sharp。

代码 `research_partial/star7_bounded_r2_policy_demo.py` 通过现有 `SupportEngine` 精确支持与**独立对 35 个 assignment 的穷举**双重核验，通过端点 compatible-world witnesses。它不是现有 `R2` 生产 verifier 的新能力。用户未明确接受额外 A5（有界 outcome 与 sufficiency）时，此界无效。

## 如果之后确实要正式做 R4，建议先实现怎样的最小 backend？

仅考虑 **D2/D5、E1/E5、已知固定无向图、均值签名充分性和上下界有界**，目标为固定政策加权均值，输出：

1. A1 指定目标政策和节点权重；
2. A4 独立 typed population arm means；
3. A5 独立接受 outcome boundedness + mean-signature sufficiency，不可从观察数据自动推出；
4. A6 按节点划分签名已支持/未支持；
5. 数学 identified set 的区间端点、sharpness 证明/反例、独立 verifier + replay；
6. 不把原 POINT 结果的 `UNSUPPORTED` 自动转译成 PARTIAL。

在这一步之前，应优先完成 6 类高频业务和独立真实科学审核基准。若导师希望展示 PARTIAL，本次研究原型已经足以作为**明确标注为数学研究候选能力**的一页演示，不能宣传为正式系统路线。
