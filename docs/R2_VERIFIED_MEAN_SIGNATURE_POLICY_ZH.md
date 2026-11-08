# Causal-IDFM R2 经验证的 Mean-Signature-Sufficient Policy POINT

> 本文保留原数学定义与当时开发说明；历史版本／完成状态不代表当前业务入口。当前覆盖见 [能力边界](CURRENT_SCOPE_ZH.md)，数学材料归属见 [证据导航](MATH_AND_EVIDENCE_ZH.md)。

**范围：** 在 R1b v1.9 基础上增加一条真正不同的、依赖额外结构假设的政策识别定理。当前支持固定处理前简单无向网络、单时点二元 treatment、D1/D2/D3 设计、E1/E2/E3 预处理 signature 和固定全向量政策值。保留全部原始 `identify()`、R1a、R1b、Batch、PFN 与 Policy。

## 1. 要识别的因果目标

给定固定处理前条件 `W=w` 和完整二元干预 `z`，预先指定 `ω_i≥0`、`Σ_i ω_i=1`，

\[
  V(z\mid w)=\sum_{i=1}^N\omega_i\,m_i(z,w),\qquad
  m_i(z,w)=\mathbb E[Y_i(z)\mid W=w].
\]

**本 R2 定理额外要求一个经过实质审阅、显式采用的 A5 假设：** 对政策中权重非零的每个节点 `i`，存在函数 `h_i(a,s,w)`，使得**所有完整 assignment `u∈{0,1}^N`** 均有

\[
  m_i(u,w)=h_i(u_i,g_i(u,w),w).
\]

这是 **mean signature sufficiency**，比 R1a 识别 design-standardized arms 所需条件更强；signature 只是可计算的分组，**定义了 `g` 并不会自动证明这个假设成立**。它也不同于 `Y_i(u)=Y_i(u_i,g_i(u))` 在个体潜在结果层面的更强限制。

再设完整实验设计已知 `q(u|W)`，真实分配满足 full-vector randomization、consistency、固定处理前网络和有限条件一阶矩。政策节点所需 `(a_i,s_i)=(z_i,g_i(z,w))` 具有 **正的原设计支持**

\[
  \pi_i(a_i,s_i\mid w)=P_q(T_i=a_i,g_i(T,w)=s_i\mid W=w)>0.
\]

若 A4 确实提供/蕴含 `E[Y_i^{obs}|W,T_i=a_i,g_i(T)=s_i]`，则

\[
 \boxed{V(z\mid w)=\sum_{i:\omega_i>0}\omega_i
   \mathbb E[Y_i^{obs}\mid W=w,T_i=z_i,g_i(T,w)=g_i(z,w)]}.
\]

**完整 `q(z)` 可以是 0。** R1b 要求完整分配支持，R2 利用额外的潜在结果均值等价类连接原实验未观察到的完整干预。这不意味着在所有情况下都可外推：任何政策节点的目标 signature 类别支持为零都必须拒绝 R2。

## 2. 复用与新增的输入合同

直接使用现有 `NetworkStudyContextV17`、`TargetSemanticsV15` 和 `Assumption`。新增：

- `SignatureSpecV20`：已知的 E1 majority、E2 三档 treated-neighbor fraction 或 E3 处理前核心合作者多数；绑定研究网络、treatment、signature 指纹，不包含因果许可。
- `MeanSignatureSufficiencyV20`：显式的**额外结构性假设**，绑定签名和被覆盖节点。必须是经过人工或领域知识实质采用的 `ADMITTED/CERTIFIED` 记录、含审阅证据；不能从设计律或 LLM 推测中 DERIVED。
- `SignaturePopulationSourceV20`：确切的 A4 来源。直接 signature arm means 必须列出每一个用于政策公式的 `(node,a,s)`；也可用确切的 `NODE_FULL_LAW`、`FULL_JOINT_LAW` 推导。有限样本估计、未审核、签名不符、节点覆盖不足均被拒绝。
- `VerifiedSignaturePolicyV20`：POINT/VERIFIED、每个使用节点的精确联合支持概率、研究设计下该完整政策的精确 `q(z)`、所用定理、逐节点观测条件均值 formula、目标指纹、证书与按需 replay；**没有数值因果效果**，`estimation_request=None`。

`TargetSemanticsV15` 中固定完整政策的科学身份不依赖采用 R1b 还是 R2。因此新 R2 复用 R1b 的同一跨 route policy-target fingerprint 规则，签名、结构假设、设计及 A4 来源单独进入证书身份。

## 3. 验证的边界与算法

- D1：利用原 Poisson-binomial SupportEngine，与独立生成多项式检查；若全体 Bernoulli 概率相同，再加入二项式闭式校验，按 `(a,s,degree)` 缓存已经三重对拍的结果。**不**将此加速套用到异质 `p_i`。
- D2：超几何支持计算与独立的全局组合数计数；D3：双配额卷积与另一套全局组合计数。
- E1：允许 isolate 的 `S_i=0`；E2：所涉及节点度数为 0 则拒绝；E3：每个节点需要非空且真实存在的处理前核心邻居集合。
- 零权重节点不要求其政策 signature 类别支持；但所有 `ω_i>0` 的节点均检查。
- Replay 会重算研究对象、signature、结构假设记录、A4 来源、设计概率、所有使用节点的 signature support、公式和证书。SHA-256 用于检测记录变化，**不能证明外部证据真实或证明假设在现实成立**。

## 4. 直接可运行的正反演示

```bash
python -B -m examples.run_verified_r2_signature_policy
python -B -m examples.run_verified_r2_signature_policy --er300
python -B -m examples.run_verified_r2_signature_policy --er300-baseline
python -B -m unittest discover -s tests -p 'test_verified_signature_policy_r2.py' -v
python -B -m unittest discover -s tests -p 'test_design_support_property_audit.py' -v
```

1. Star-5、D2 每次 4/5 treated、目标全员 treated：`q(z)=0`，中心 `(1,majority=1)` 支持 `4/5`，各叶节点支持 `3/5`，R2 `POINT/VERIFIED`，R1b 拒绝。
2. 共享 ER300 **原始 Bernoulli(.5) 协议**：两条 route 可同时识别相同 `Q`，科学目标身份相同。对于这个 q，`q(all-treated)=2^{-300}`，所以其有限样本识别与估计困难特别需要区分。
3. **共享 ER300 图，假设性 D2 固定 150/300 treated 协议**：`q(all-treated)=0`，R2 在额外 mean-majority sufficiency 和全部 300 个类别正支持的前提下仍为 POINT；这**不是**原 Estimation 的 Bernoulli 实验，也未训练新的 PFN。
4. 若将额外 mean sufficiency 改为 LLM `PROPOSED`，返回 `NEEDS_INPUT`；缺少 A4 相关节点类别时返回 `A4_SIGNATURE_INFORMATION_INSUFFICIENT`；目标节点类别 zero-support 返回 `ZERO_POLICY_SIGNATURE_SUPPORT`。

所有示例的 A4 来源均明确标注为**人为审核/合成 fixture 的符号总体算子声明**，不是经过实验测出的总体均值。合成 Oracle 仅存在 tests 中，不进入 Production Identification。

## 5. 尚不支持与论文边界

- 无法由 Local interference 自动推出粗粒度 E1/E2/E3 sufficiency；也没有为一般“局部完整配置”新增签名后端。
- 未实现 general stochastic policy kernels、Policy 端真实 welfare 数值、observational network ignorability route、network partial sharp bounds、未知/动态图等。
- `identify_verified_signature_policy()` 是新的**正式独立 API**，不是旧 v1.7 Shadow Router 强制注册后的自动选择结果。旧 Router 仍需进行单独的正式路由迁移。
- 本定理是标准随机化与结构充分性识别推导的系统实现，**不声称数学新颖性**。

## 6. 正确性审查注意事项

原有 legacy `identify()` 的 A4 判断基于变量名称集合，已有回归测试明确记录存在过宽/过窄案例。R1a、R1b 及新 R2 使用更加严格的独立信息来源声明，不表示所有遗留路径已统一迁移。应在未来受控升级中以 typed information operator 正式替换 legacy gate，而不是默默将 Shadow 结果当作定理许可证。
