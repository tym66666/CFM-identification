# Causal-IDFM Post-release P1.1：R3 Nodewise 条件相关观测处理 A4 数学合同

**性质：正式 A4 子域增量；不是新识别定理、不是新 Route，也不是新的 A5 科学假设。** A0、Estimation、R4/R5、DAG/PARTIAL 不在本轮范围内。

## 1. 精确研究子域与目标

- 已知、处理前固定的**简单无向网络** \(G\)，\(N\leq 300\) 等受现有资源门禁限制；单时点二元处理 \(T_j\in\{0,1\}\)；一个预先指定的条件背景 \(W=w\)。
- 每个节点有一个**处理前二元协变量** \(X_j\in\{0,1\}\)，且目前只使用 \(C_i=(X_i,\sum_{j\in N_G(i)} X_j)\) 为节点特异调整层。Exposure \(S_i=g_i(\mathbf T,G)\) 沿用 E1–E5，E3 仍以预先指定核心合作者定义 treatment exposure，但 \(C_i\) 的邻居计数始终采用全部无向图邻居。
- 目标为 \(\theta_i(a,s\mid w)=\mathbb E[Y_i(a,s)\mid W=w]\) 及其预先指定的有限线性 Direct/Spillover/Total/加权平均。**不等于** R3 p-standardized arm，也不等于任意固定政策价值。

## 2. 新增 A4（观测相关 treatment）

明确给定有限完整处理前协变量向量分布
\[
P(\mathbf X=\mathbf x\mid W=w)=m_{\mathbf x}, \quad
m_{\mathbf x}>0,\quad \sum_{\mathbf x}m_{\mathbf x}=1.
\]
对于各正质量 \(\mathbf x\)，声明并接受观测处理律
\[
\boxed{p_{\rm obs}(\mathbf t\mid\mathbf X=\mathbf x,W=w)
=\sum_{h=1}^{H_{\mathbf x}}\alpha_{h\mid\mathbf x}
\prod_{j=1}^{N}r_{hj\mid\mathbf x}^{t_j}(1-r_{hj\mid\mathbf x})^{1-t_j}}
\]
其中 \(1\le H_{\mathbf x}\le16\)，\(\alpha_{h\mid\mathbf x}>0\)、总和为 1，\(r_{hj\mid\mathbf x}\in[0,1]\)。权重、propensity 和 \(m_{\mathbf x}\) 均采用精确有理数，不从有限样本猜测。最多 24 个显式协变量 profile。混合分量可以在给定 \(\mathbf X\) 后产生节点 treatment 的正或负相关。

**关键区别：** 分配律相关性是 A4 的事实/声明；它**不能**导出因果交换性。若共同的选择环境也直接影响潜在结果，后面 A5 可能不成立。

A4 还必须明确提供目标涉及的全部 \((i,a,s,c)\) 的总体条件均值算子
\[
\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,C_i=c,W=w]
\]
并与研究、网络、结果、Exposure、协变量、operator、来源、可用性及 A5 许可坐标一致。只提供样本统计量、变量名称或 propensity 模型，不构成上述总体算子。

## 3. A5：两项独立且不可自动接受的科学限制

1. **Potential-outcome exposure sufficiency**：\(Y_i(\mathbf t)=Y_i(t_i,g_i(\mathbf t,G))\)，以及 consistency、固定处理前图和有限条件一阶矩。
2. **Nodewise local exposure mean exchangeability**（本实现的许可形式）：对每个正质量的 \(c\) 和目标 arm，
\[
\mathbb E[Y_i(a,s)\mid T_i=a,S_i=s,C_i=c,W=w]
=\mathbb E[Y_i(a,s)\mid C_i=c,W=w].
\]
它必须根据业务设计/领域知识被明确接受，且 scoped 到研究、Exposure、节点及 \(C_i\) 的定义。观测处理律具有混合分解，不意味着这些等式成立。

## 4. A6：逐个节点局部调整层的正支持

\(\mathcal C_i=\{C_i(\mathbf x):m_{\mathbf x}>0\}\)，
\[
M_i(c)=\sum_{\mathbf x:C_i(\mathbf x)=c}m_{\mathbf x},
\]
\[
J_i(a,s,c)=\sum_{\mathbf x:C_i(\mathbf x)=c}m_{\mathbf x}
\sum_h\alpha_{h\mid\mathbf x} P_{h,\mathbf x}(T_i=a,S_i=s).
\]
其中 \(P_{h,\mathbf x}\) 是第 \(h\) 个**条件独立** Bernoulli 分量，含 \(i\) 本人的处理概率与其暴露参考邻居的 Poisson-binomial 处理人数分布。程序要求**每个 \(M_i(c)>0\) 的局部层都满足 \(J_i(a,s,c)>0\)**。

不是要求每个 profile / 每个 Bernoulli 分量分别有正支持。同一个 \(c\) 的其他正质量 profile 或混合分量可以合法贡献正支持。也不能以总体 arm 正支持替代逐 \(c\) 正支持。

## 5. 识别结论与证明

若 A4/A5/A6 全满足，
\[
\boxed{\theta_i(a,s\mid w)
=\sum_{c\in\mathcal C_i} M_i(c)
\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,C_i=c,W=w]}.
\]
证明：以 \(C_i\) 全概率分解潜在结果均值；在每个层内由局部条件均值交换性把潜在结果均值换为选择该 arm 的潜在结果条件均值；以 exposure sufficiency + consistency 换为观测 \(Y_i^{obs}\)；正支持确保条件均值有定义；A4 确保全部右侧总体算子可得。有限线性组合的每个非零项再分别应用此恒等式。

**这个识别公式不含 propensity 或混合分量权重**，后者只用于支持验证和识别结果的 A4 证书。因此保持相同 \(P(\mathbf X)\) 和目标定义、只改变观测 treatment propensity，不应改变 Target fingerprint；但会改变 source/证书 fingerprint。

## 6. 反例与独立正确性 oracle

- **有相关处理、仍无因果识别**：令未观测共同状态 \(U\sim Bernoulli(1/2)\)，给定 \(U=1\) 各 treatment Bernoulli(3/4)，给定 \(U=0\) 则 Bernoulli(1/4)，但潜在结果 \(Y_i(\mathbf t)=U\) 不随 treatment 变化。混合观测分配律完全合法，隐藏 \(U\) 却同时影响处理和结果，违反局部条件均值交换性。仅有此 A4 和观测总体律不能证明处理效应等于条件结果差。对于两节点完整相邻网络，exposure 可以包含邻居的全部二元处理状态，故粗略“暴露定义”也无法挽救未观测混杂。
- **零支持**：若某个有正权重的节点局部层中，全部混合分量都令 \(T_i=0\)，目标需要 \(T_i=1\)，则 \(J_i(1,s,c)=0\)，拒绝 POINT。
- **不能错误要求分量正支持**：一个混合分量的支持可以为零，只要相同 \(c\) 的整体混合支持为正，条件总体均值仍有合法支持。
- **独立 oracle**：E1–E5 的小图概率用每个 Bernoulli 分量的全处理向量穷举对拍；Verifier 用不同的逆向邻居生成递推并直接计算 exposure 条件，不调用主支持算法；证书 replay 再次从 typed 输入重建证明。

## 7. 代码落点、稳定性、没有完成的事

- 复用 `identification_observational_nodewise_adjustment.py` 里的 R3 原 theorem、proof、certificate 和 business entry，仅扩展一种明确定义的 A4 source profile。
- 新声明构造器：`identification_observational_nodewise_mixture_a4.py` 的 `declare_nodewise_correlated_arm_population_v28p2`。
- 旧 Nodewise factorized-A4 来源与公开 API 保留；原来 `NodewisePretreatmentProfileV28`、source FP 与 Target FP 不更改意义。
- 不支持任意高维 \(X\)、连续 treatment、未知/动态网络、任意相关联合观测律、不符合该 mixture 的 treatment assignment、跨 \(W\) 标准化、自动发现/证实科学假设、估计实际 causal 数值、Generalized Propensity Score Estimation、Network Auto-G。

参考文献：Forastiere, Airoldi & Mealli (2021), *Identification and estimation of treatment and interference effects in observational studies on networks*（JASA, DOI: 10.1080/01621459.2020.1768100）；Bhadra & Schweinberger, *Causal Inference Under Network Interference*（综述，arXiv:2508.06808）。本路线受相关理论启发，但**不是对其全部 estimator 或假设的实现**。
