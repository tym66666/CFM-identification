# Causal-IDFM 数学合同：D5 多组固定配额与 A6 零支持解释

日期：2026-10-17 · 生产增量 · 基线 v2.4

## 一、正式新增的 D5 及明确边界

D5 (`MultiGroupFixedQuotaDesignV25`) 要求已知、固定且在处理前确定的节点分区 $G_1,\dots,G_H$（**3–64 个非空组**），每组精确固定 $m_h\in\{0,\dots,|G_h|\}$ 名额，并在该组内均匀无放回抽取处理节点；各组的处理分配相互独立。允许任意跨组网络边。因此**分组是随机化 strata，不是 partial interference clusters**。

$$
q(\mathbf t\mid W)=\mathbf1\{\forall h,\sum_{i\in G_h}t_i=m_h\}
\prod_{h=1}^H {\binom{|G_h|}{m_h}}^{-1}.
$$

这不是 D4 的簇级 Bernoulli，不是“固定数量簇 treated”，也不是两阶段随机饱和度试验；不能把 H 个分组当成 H 个独立节点处理。D5 是 D3 两组配额机制的严格推广；为兼容历史证明指纹，D3 原合同未改，D5 使用独立的版本化设计 kind。

### 单节点 Arm 支持

目标节点 $i\in G_{h_*}$、自身处理 $a$、参考邻居集合 $R_i$，设 $c_h=|R_i\cap G_h|$、$\delta_h=\mathbf1\{h=h_*\}$。

$$
P_q(T_i=a\mid W)=
\begin{cases}m_{h_*}/|G_{h_*}|,&a=1,\\1-m_{h_*}/|G_{h_*}|,&a=0.\end{cases}
$$

对每组的邻居计数 $K_{ih}$，条件于 $T_i=a$ 有

$$
P(K_{ih}=k\mid T_i=a,W)=
\frac{\binom{c_h}{k}\binom{|G_h|-\delta_h-c_h}{m_h-a\delta_h-k}}
{\binom{|G_h|-\delta_h}{m_h-a\delta_h}}.
$$

在自身处理有正概率时，各组条件计数独立，$K_i=\sum_h K_{ih}$ 的概率由卷积得到。E1–E5 的条件暴露分组，均通过对 $K_i$ 的概率质量合并得到精确 $\pi_i^q(a,s)$。当 $P(T_i=a)=0$ 时，joint support 定义为零，不使用未定义的条件概率。

**独立 verifier** 不调用该条件计算，而是直接在原始分配律下计算每组可行完整分配的整数个数

$$
C(c_h,k)C(|G_h|-\delta_h-c_h,m_h-a\delta_h-k),
$$

将这些整数生成多项式相乘，再除以 $\prod_h\binom{|G_h|}{m_h}$ 并选出目标签名对应的计数项。第三项小图 Oracle 则完全枚举二元分配并求和。三种实现思路独立，避免将同一 DP 的自我复算当作数学证据。

### 继续复用的 Family

- **R1a**：在完整向量随机化、consistency、已知 q、固定预处理网络、可积性、充分的 typed A4 条件算子和目标 arm 的 $\pi_i^q(a,s)>0$ 时，$\mu_i^q(a,s\mid W)=E[Y_i^{obs}\mid W,T_i=a,S_i=s]$。**不需要 exposure sufficiency**。
- **R1b**：在 $q(\mathbf z)>0$ 与 assignment-resolution A4 条件下，固定策略值为加权 $E[Y_i^{obs}\mid W,\mathbf T=\mathbf z]$；D5 的 $q(\mathbf z)$ 通过各组配额精确核对。
- **R2**：只有对所选 signature 另行明确接受并记录 $E[Y_i(\mathbf t)\mid W]=h_i(t_i,g_i(\mathbf t,G),W)$，且每个有权重节点签名在原始 D5 中支持为正、A4 充分，才可识别某些完整策略零支持的政策值。**E1/E5 的切换会改变 A5 结构充分性含义。**

Target/完整分配律指纹均保持与数据/网络/曝光签名绑定。改变分组、名额或基准网络意味着另一个已声明的实验，不是对既有结果做事后可行性修补。

## 二、A6 Signature Support Diagnostics 

`diagnose_policy_signature_support_v25(study, target, signature)` 是**非定理性**的支持诊断，覆盖 D1–D5 × E1–E5：

1. 要求 typed 的实验 Study、固定政策 Target、相同网络/研究范围的 Signature。
2. 对政策中每个**非零权重**节点，计算目标签名、原始分配律下自身处理概率、条件于自身处理的**精确可达邻居处理人数集合**、可达 exposure 状态、联合签名支持，以及节点级原因码。
3. 对 D2/D3/D5 节点展示（有时跨组）名额约束；对于 D4 的簇内 treatment 完全相关，精确可达集合可能有空缺，比如 $\{0,2\}$，不能只看区间上下界。
4. 使用正式 SupportEngine 与独立的原设计计数 verifier 进行一致性对拍；每条记录保存可重新核验的摘要，提供 `replay_policy_signature_support_v25`。
5. D2、$N\le24$ 时，仅列出在**反事实的新实验**中可让所有有权重节点签名支持为正的其他固定配额 $m'$。这一建议**不是**将旧实验的数据改成新 $q$，也不是为当前结果增加识别许可。

零支持原因主要有 `OWN_TREATMENT_ZERO_SUPPORT`、`TARGET_EXPOSURE_UNREACHABLE`、`EXPOSURE_UNDEFINED_FOR_ISOLATE`。`UNSUPPORTED` 表示此签名在原设计下不满足当前 R2 路线条件，不等于数学上已证明在全部可能假设中非点识别。

签名支持为正也**不能确认**：随机化真实性、A4 总体信息是否存在、结构充分性假设是否正确、有限样本估计稳定性、估计器/PFN 支持情况，或真实政策收益数值。

## 三、真实执行与验收说明

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -q
python -B -m unittest tests.test_multi_group_quota_and_support -v
python -B -m examples.run_multi_group_and_diagnostics --output-dir showcase_v25
```

- 新增 12 项专项测试：随机小图独立穷举、五种 exposure、D5 canonical identity、R1a/BATCH、R1b、R2、未确认 A5 拒绝、D2/Star 和 D5 节点支持、D4 簇级可达集合有空缺、45 个组合及 Ring300。
- 九张固定网络 × D5 × 五种 Exposure = **45 个组合**；每行正例仅验证其中一个 arm，并经过正式定理与 replay。不能直接作为行业实际业务覆盖率。
- 300 节点 Ring、60 组、每组固定处理 2 人，在一个指定节点上完成 E1/E5/E4 三个已验证 arm，joint support 分别为 **2/5、1/5、1/5**。这是非 ER 网络，未计算数值效应或 PFN。
- Star7/D2/m=3：中心 E1、E4 支持为零，E5 为 **3/7**；D2 新实验若仍要全员政策签名可达，E1 最少需 5 名 treated，E4 需 7 名；前者绝不代替已经发生的固定 3 人实验。

## 四、仍未实现与下一阶段

**尚未实现**：两阶段 saturation randomization、固定数量簇随机化、D5 有依赖的分层匹配/全局 rerandomization、超过 64 组的版本化 D5、连续 treatment、多期/有向/加权图、一般自然语言 Business→Spec、R3 Observational Direct/Spillover 通用识别、Network Partial-ID、为新增 D5 指定的 PFN Estimation adapter。远端 GitHub Actions Python 3.11 未在本工作区实际触发，不能声称已通过。

**下一步建议**：基于已有 R1a/R1b/R2 的可验证能力和覆盖矩阵，先研究并实现独立的两阶段随机分配合同（明确组抽样与组内设计、条件支持），或建设条件交换性下合法的 R3 直接/溢出 Target。两者都不能仅作为 D5 的又一个 label 添加。
