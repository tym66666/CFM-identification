# Randomized-Network POINT 的小规模内部抽象

> **适用范围：**已知、处理前固定的 unit network；D2 全网络固定名额 / D3 两组独立固定名额；E1 严格多数 / E2 邻居 treated 比例三档；单节点、单 arm 的 design-standardized mean。此阶段**不是**通用 causal ID，且不支持 D1、E3、PARTIAL 或新 PFN adapter。

## 1. 为什么抽象，哪些合同不变

四个已经验证的 D2/D3 × E1/E2 setting 共用同一条 POINT 定理：

\[
\pi_i(a,s\mid W)=P_q(T_i=a,S_i=s\mid W)>0
\quad\Longrightarrow\quad
\mu_i^q(a,s\mid W)=\mathbb E[Y_i^{\mathrm{obs}}\mid W,T_i=a,S_i=s],
\]

其中还需**明确承认**已知联合 assignment law、完整向量随机化、consistency、固定处理前网络及有限一阶矩等假设。暴露是目标分组；**不要求**真实潜在结果仅依赖 `(T_i,S_i)`。

**不变：**公共 `TaskSpec`、内部已序列化的 `IdentificationSpec / RandomizedNetworkArmMeanContractV1`、target fingerprint、证书字段/规则 ID、独立 verifier、`IdentificationResult`、ER300 旧路线及 Estimation/Policy 快照。`CausalTaskSpec` 仍只是概念名称，没有引入同名类。

## 2. 三个内部组件（不是三份新的公共 Schema）

源码在 `pfn_pipeline/_internal/identification/randomized_arm_family/`：

| 文件 | 组件 | 职责 | 不负责 |
|---|---|---|---|
| `assignment.py` | `AssignmentSpec` | 将现有 **D2/D3 typed design** 转为已知的完整向量概率 `q(t|W)`、本人处理概率 `P(T_i=a|W)` 和条件邻居 treated-count 分布 `P(K_i=k\mid T_i=a,W)` | 估计 outcome、验证实验是否真的随机化、推断未知分配机制 |
| `exposure.py` | `ExposureSpec` | 对 E1/E2 执行精确整数分箱 `k,d\mapsto s` 并声明合法 exposure states | 宣称 exposure sufficiency、定义新干扰机制 |
| `support.py` | `SupportEngine` | 组合上述两个组件，返回精确有理数的 `P(T_i=a,S_i=s\mid W)`，内部同时记录 own/conditional/joint 三层概率 | 证明随机化假设为真、调用 PFN、生成独立验证结论 |

`AssignmentSpec` 和 `ExposureSpec` 是**运行时不序列化的内部 adapter**：它们读现有 v1 合同，不会替换公共接口或引入第二套 TaskSpec。保留了原来的 `joint_support`、`joint_support_two_group` 等兼容入口。

### 计算分解

对于固定节点 `i` 和 treatment `a`：

1. `AssignmentSpec` 根据原始实验完整分配律得到 `p_a=P(T_i=a|W)`，并在 `p_a>0` 时求 `h_k=P(K_i=k|T_i=a,W)`。
2. `ExposureSpec` 从 `k` 和节点度数 `d_i` 得到分组 `g_i(k,d_i)`。
3. `SupportEngine` 返回：

\[
\underbrace{\pi_i(a,s\mid W)}_{\text{joint support}}
=\underbrace{p_a}_{\text{本人概率}}
\underbrace{\sum_{k:g_i(k,d_i)=s}h_k}_{\text{给定本人后的 exposure 概率}}.
\]

D2 的 `h_k` 是 hypergeometric；D3 按 `T_i=a` 扣掉本人所在组的一个配额后，把两组的 conditional hypergeometric 分布卷积。跨组网络边允许，实验分组不等于网络分组。E2 用 `3k<d` 和 `3k<2d` 做边界判断；`d=0` 无法定义三档比例。`p_a=0` 时联合概率为零，不能声称条件分布可估。

如需数学上的目标核，仍由**已知完整分配律**唯一规定：

\[
\kappa^q_{i,a,s}(\mathbf t\mid W)
=\frac{q(\mathbf t\mid W)\mathbf 1\{t_i=a,g_i(\mathbf t,W)=s\}}{\pi_i(a,s\mid W)},
\quad \pi_i(a,s\mid W)>0.
\]

本次不增设第二份可序列化的目标核模型；原有 theorem contract 的 design、grouping 和 query fingerprint 已约束该语义。

## 3. 正式路径与证明边界

```text
Public TaskSpec + IdentificationSpec (原样)
               ↓
       Assumptions / query gate (原样)
               ↓
       AssignmentSpec(design)
         + ExposureSpec(grouping)
               ↓
       SupportEngine.evaluate(...)
               ↓
       同一个 POINT theorem backend
               ↓
       原有 proof certificate / result
               ↓
       原有 independent verifier (原组合计数，未调用 SupportEngine)
               ↓
       POINT / VERIFIED，无匹配 Estimation adapter 时无 EstimationRequest
```

这里的 `POINT` 是总体可识别，不等于有限样本 cell 一定出现，也不等于现在已经支持 D2/D3 的 PFN estimation 或确定性 policy welfare。

## 4. 示例与测试

```bash
python -m examples.run_randomized_arm_components
python -m unittest discover -s tests -p "test_randomized_arm_abstraction.py" -v
python -m unittest discover -s tests -p "test_*.py" -q
```

新增测试涵盖：D2/D3 × E1/E2 的独立完整分配穷举、组配额极端情形、跨组边、支持概率归一化、E2 分箱边界/孤立点、显式 `q(t|W)` 归一化，以及**故意破坏 proposer 的 support 后由未共享概率计算的 verifier 拒绝**。

v0.5 的原有证书以及已发布结果格式仍需保持：对 20 个固定公开查询（含结构性零 support），升级前后的 source specification、serialized result、diagnostics 与 handoff 均应一致。旧 ER300 Notebook 要照常运行。

## 5. 暂时不扩展

- D1 异质 Bernoulli 的 Poisson-binomial law 与 protocol / schema 接入。
- E3 处理前 core collaborators：它需要明确**参考邻居集合**，不仅是改变 E1/E2 的 count binning；不能在当前全邻居分箱中暗中假设已经支持。
- 批量 arm、通用 identified-set / PARTIAL、真实政策收益识别、LLM/UniCo。

这版成功标准不是“类名变通用了”，而是**四个已有组合在同一个纯内部 SupportEngine 下运行、旧证书完全一致、计算结果可由独立枚举和 verifier 核查**。
