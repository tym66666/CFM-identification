# Causal-IDFM R1b Verified Full-Assignment Policy POINT

**性质：** 对 v1.8 的增量式正式识别能力；用于 network-first、固定处理前简单无向网络、二元单时点 treatment。**没有**重写第一条 R1a family、旧 Policy / Estimation、A4 Shadow 或 `identify()`。

## 1. 数学目标、识别定理

给定研究上下文 `W=w`，有序节点集合 `V`，完整二元 assignment `z∈{0,1}^N`，事先指定的权重 `ω_i≥0`、`Σ_iω_i=1`，定义真实固定政策均值

\[
 V(\mathbf z\mid w)=\sum_i\omega_i\,E[Y_i(\mathbf z)\mid W=w].
\]

**R1b POINT 的充要接口条件（此处为充分的可执行 route，不声称对所有模型数学必要）：**

1. 固定的 pretreatment `W,G` 与明确坐标、outcome/treatment 语义；
2. 已知且经过协议确认的联合随机分配律 `q(z|W)`，当前计算支持 D1 异质独立 Bernoulli、D2 complete randomization、D3 两组固定配额；
3. Full-vector randomization `T ⟂ {Y_i(u)}_{i,u} | W`；consistency `Y_i^obs=Y_i(T)`；所需条件一阶矩有限；这些 A5 条件须由可信研究来源明确承认；
4. 目标固定完整分配事件 **`q(z|w)>0`**；
5. A4 至少包含每个 `ω_i>0` 节点的完整 `T=z` 条件均值，或可导出它的 `NODE_FULL_LAW/FULL_JOINT_LAW`，需要被明示为已审阅的 population operator。只提供曝光分组 arm means **不够**。

由随机化与 consistency，`E[Y_i(z)|W]=E[Y_i^obs|T=z,W]`，因此

\[
\boxed{V(\mathbf z\mid w)=\sum_i\omega_iE[Y_i^{obs}\mid \mathbf T=\mathbf z,W=w].}
\]

该识别不需要假设 locality、正确的 exposure mapping 或 exposure sufficiency。其有效性也不以历史 Estimation PFN 对政策目标的可估计性为前提。

**注意：** `q(z)=0` 并不导致固定政策目标无定义，也不自动意味着数学上的 PARTIAL；只是此 R1b route 不能使用，应评估未来 R2 等额外结构假设。`q(z)>0` 在人口识别层面成立，不能推出一次 ER300 实验有可靠的政策值估计。`1/2^300` 虽为正，但非常小。

## 2. 新的正式 API

`pfn_pipeline.identification_policy_r1b` 提供：

- `identify_verified_fixed_policy(study, target, sources, assumptions=...)`：签发固定政策的 `VerifiedFixedPolicyV19`；失败抛 `R1bPolicyUnavailable.reason_code`。
- `replay_verified_fixed_policy(result)`：重建来源、A5、A4、分配支持与标识，严格比对已保存结果。
- `identify_verified_finite_policy_mixture((result_z1, result_z2, ...), policy_probabilities=('1/4','3/4',...))`：对至多 64 个 **分别 R1b-VERIFIED 且属于相同 study/protocol、相同节点权重**的固定政策做有限显式随机混合。
- `replay_verified_finite_policy_mixture(result)`：独立回放每个固定政策证明并核对组合证书。

这些 API 都不调用 PFN、不计算真实数值 outcome、不改变 legacy `NetworkPolicyValueBernoulliBackend`，也不尝试 general stochastic-kernel `r`、policy learning 或 off-support 外推。混合策略原理只是有限线性闭包：

\[
 V(r\mid w)=\sum_{k=1}^K\alpha_k V(\mathbf z^{(k)}\mid w),\quad
 r=\sum_k\alpha_k\delta_{\mathbf z^{(k)}},\ \alpha_k>0,\sum_k\alpha_k=1.
\]

## 3. A1 / A4 / A5 / A6 的分工

输入沿用 v1.7 非 arm 对象：`NetworkStudyContextV17`、`TargetSemanticsV15` 和 `NetworkA4SourceV17`，`Assumption` 仍单独输入。

- A1：目标 `V(z)` 的全向量 treatment、节点 outcome 权重和 `W`，不包含原实验 `q` 或 exposure；R1b v1.9 的额外科学指纹明确包含 treatment 变量身份。
- A4：只接受显式被审阅的 `ASSIGNMENT_NODE_MEANS`（目标格子），`NODE_FULL_LAW`、`FULL_JOINT_LAW`；不以 arm-level 信息填充 assignment-level 格子；来源与 study protocol 绑定。
- A5：要确认 known design、full-vector randomization、consistency、fixed pretreatment network、finite moments；`PROPOSED/UNRESOLVED` 不自动成许可。
- A6：精确 `q(z)>0`，独立重算 D1/D2/D3 的 full-vector probability，并核对旧支持计算器的值。

v1.7 RouteAssessment **继续是 Shadow**：它的 `THEOREM_BACKEND_UNAVAILABLE` 表示原候选 registry 未注册此新正式 solver；R1b 正式 API 单独运行，只有完成 theorem + verifier 后才报告 `POINT / VERIFIED`。不伪造原 Shadow 的输出以冒充 theorem。

`VerifiedFixedPolicyV19.summary()` 提供 `status`、`verification_status`、`target_fingerprint`、`assignment_probability`、`required_observables`、`identified_functional`、`a4_rule_id`、`certificate_sha256` 和 `estimation_request=None`。它不包含政策收益预测值。两层指纹：数学目标身份独立于原 q 和证据状态，签发证书则绑定研究方案、A4 来源、A5 证据和 q。

独立的设计支持验证由第二套算式计算 D1 乘积、D2 组合数、D3 各组组合数，并与既有 `AssignmentSpec.full_assignment_probability()` 对拍。replay 从保存的 typed 输入**重新计算完整输出**；它检测声明或输出被篡改，**不能证明外部声明真实**，也不是 Lean 形式化的数学证明。

## 4. 运行验证

```bash
python -B -m unittest discover -s tests -p 'test_verified_fixed_policy_r1b.py' -v
python -B -m unittest discover -s tests -p 'test_*.py' -q
python -B -m examples.run_verified_r1b_fixed_policy
python -B -m examples.run_verified_r1b_fixed_policy --er300 --output /tmp/r1b_ER300.json
```

三节点 toy 与实际共享 ER300：固定全员处理的 `q(z)>0` 和 POINT 可检验；同时展示只给 arm means 的 `INFORMATION_BLOCKED`、随机化未确认的 `NEEDS_INPUT`；有限两原子随机政策可 POINT。`--er300` **使用共享真实固定 ER300 图文件**，但 A4 来源是为演示显式声明的**符号总体信息算子**，并非实际测得的总体分布或有限样本估计值。

## 5. 未覆盖的业务与下一步

- **未覆盖：** 仅有四臂均值时任意固定全向量政策值、D2/D3 off-support 固定政策、一般 `r` 的策略分配律、非实验网络条件调整、未知/dynamic graph、真正的 policy value 数值估计。
- **R2 下一轮**：在额外 mean exposure sufficiency/局部响应类假设已确认、各节点对应政策 signature 正支持且拥有 A4 node-class means 的情况下，识别某些原 q 不支持的完整政策。不能拿 R1b 的完整支持证书替代类别支持。

此定理属于已知随机化识别原理的直接推论，不宣称新理论创新。第三方参考：Aronow & Samii (2017)，Hudgens & Halloran (2008)，Sävje (2024)；现有合同见 `CFM_ID_R1_R2_Formal_Theorem_Contracts_v1_0_ZH.md`。
