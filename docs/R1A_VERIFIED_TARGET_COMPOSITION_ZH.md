# Causal-IDFM R1a — Verified Target Composition （2026-10-16）

**状态：正式增量代码，旧 `identify()`、旧 Batch、PFN、Policy 均未改变。** 这是已经 POINT 识别的设计标准化 arm means 的**线性闭包及其独立证书检查**，不是新的因果识别定理，也不是 R1b/R2 固定政策识别。

## 1. 明确的数学目标

已知处理前固定网络、二元全向量分配律 `q(T|W)` 与已定义的 exposure `S_i=g_i(T,W)`，现有正式 family 已证明，对 `π_i(a,s|W)>0`：

\[
\mu_i^q(a,s\mid W)
=\mathbb E_q[Y_i(\mathbf T)\mid T_i=a,S_i=s,W]
=\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,W].
\]

不要求 `Y_i(T)=Y_i(T_i,S_i)`。对于预先确定、有限、非零、**精确有理数**系数 `c_{ias}`：

\[
Q_c=\sum_{i,a,s}c_{ias}\mu_i^q(a,s\mid W)
=\sum_{i,a,s}c_{ias}\mathbb E[Y_i^{obs}\mid W,T_i=a,S_i=s].
\]

右侧是可用总体观测律上的 functional。在同一 `q/g/W`、同一 outcome semantics、每个非零系数 arm 都有正 support、相关 A4 observable 可导出且原随机化假设获认可时，`Q_c` 为 POINT。该证明是线性算子作用在已验证 POINT 上的封闭性，不是拿样本均值计算业务收益。

### 三种具名 design-standardized effects

给定显式 `s0`, `s1`：**DIRECT 固定 exposure，因此调用接口时它的 `comparison_exposure` 必须等于 `reference_exposure`；SPILLOVER/TOTAL 则要求两者不同。**

- `DIRECT_i(s0) = μ_i(1,s0)-μ_i(0,s0)`；
- `SPILLOVER_i(a;s0,s1) = μ_i(a,s1)-μ_i(a,s0)`（默认 `a=1`）；
- `TOTAL_i(s0,s1) = μ_i(1,s1)-μ_i(0,s0)`。

在 D2/D3 fixed-quota designs 下，这些是 **design-standardized contrasts**，不是固定他人完整分配的 controlled direct effect。E2 有三种状态，调用者必须显式选 `s0/s1`；例如 0→2。用户不能只写一个「溢出效应」标签，就认为系统知道所问的 `Q`。

### 节点/部门平均

预先定义节点组 `H` 和与 outcomes 无关的处理前非负权重 `w_i`：

\[
\overline{\mathrm{Total}}_H=\sum_{i\in H}w_i\{\mu_i(1,s_1)-\mu_i(0,s_0)\},\quad \sum_{i\in H}w_i=1.
\]

接口在精确有理数域中归一化并记录 `cohort_authority/cohort_evidence`。它只能记录**声明**的组来源，不可能凭 SHA-256 验证真实业务组是否确实在 treatment 前已定义。`TRUSTED_FIXTURE` 只接受 synthetic study，真实业务应采用经审阅的 `STUDY_PROTOCOL` 或 `HUMAN_CONFIRMED_PRETREATMENT`。

## 2. 生产接口与现有组件的关系

新增模块：`pfn_pipeline/identification_composition.py`。

- `identify_verified_node_effect(batch, a4_source, node_id, kind, reference_exposure, comparison_exposure)`：单节点具名目标；
- `identify_verified_group_effect(batch, a4_source, node_weights, kind, ..., cohort_authority, cohort_evidence)`：按事先约定节点权重平均；
- `identify_verified_linear_target(batch, a4_source, tuple[ArmLinearTerm,...])`：严格指定的一般线性泛函，**不擅自冠以 Direct/Policy 名称**；
- `identify_verified_effect_bundle(batch, a4_source, tuple[EffectQueryV18,...])`：多个业务问题共享一次源 Batch 证书检查；
- `replay_verified_composition(saved)`、`replay_verified_effect_bundle(saved)`：重复对原 anchor、来源身份、所使用的 arm 支持及组合公式进行核验。

输出对象分别为 `VerifiedCompositionV18` / `VerifiedCompositionBundleV18`（保留 `status=POINT`、`verification_status=VERIFIED`、公式、所用非零项、support、来源、证书、fingerprint）。**它们是新的 typed envelope，而不是冒充 v1.0 `IdentificationResult` 及旧 PFN `EstimationRequest`**。`estimation_request` 恒为 `None`。面向 Demo 的 `summary()` 还会逐项输出 `constituent_arms`：node/arm 坐标、精确系数、**总体支持概率**与 arm 指纹；其中支持概率是已知实验设计的数值，不能误称为实际因果效应数值。

### 兼容与 A4

显式要求 `A4SourceV1` 且它须声明经接受的 **symbolic population operator 或 exact population value**；`NODE_ARM_MEANS` 需要覆盖每一个非零项；`NODE_FULL_LAW` / `FULL_JOINT_LAW` 可按照已有 A4 白名单规则导出 arm means。`PAIRWISE_MARGINALS`、`ASSIGNMENT_NODE_MEANS`（还没有完整条件均值匹配证明）、未确认来源与有限样本估计都不能借用此入口推出 POINT。

已知 `q` 与 A4 信息可用本身不足以推出 POINT；仍然依赖源 Batch 的正式 full-vector randomization、consistency、处理前网络、有限一阶矩等验证。该模块并不会自动确认未审阅的因果假设。

### Replay 的效率与安全取舍

v1.0 `replay_network_arm_batch()` 会重新逐项计算整个 `[N,2,S]` 网格。对于一个请求只使用几个 arm 的情况，这相当于每换一个业务目标重复验证许多无关节点，ER300 上很昂贵。

v1.8 做的是**选择性独立重放**：

1. 检查 Batch 版本、shape/coverage、所有网格字段的 SHA-256 与 source specification identity；
2. replay 源 `anchor` 的正式 theorem，并独立重新执行 seed arm 的正式 `identify()`；
3. 对目标中**每个非零项**的 arm 重新用两套精确支持算法（原 SupportEngine 与独立组合计数/生成多项式）校验概率、状态与 child fingerprint；
4. 检查明示 A4 来源的算子、覆盖节点、坐标次序、设计律、exposure、条件化上下文；
5. 重新生成合法的组合 terms、精确系数、identified functional 与复合证书，检测篡改。

不再反复计算 **未被本次 Q 使用的** 1,200 个支持事件，**但也不能称为重新运行了原 `replay_network_arm_batch()` 的整网格回放**。原始 Batch 在首次生成时仍需完成 v1.0 的整网格独立核验。v1.8 对此次使用的 arm 进行了新的独立复算，并验证其出处与完整网格摘要。

`target_fingerprint` 绑定实际 child targets、精确系数、outcome 和 W 语义，不随 seed arm、构造路径、人工审核状态变化；certificate digest 则包括 source Batch、explicit A4、真实 recipe 和 provenance，故可追溯不同来源。

## 3. 用法示例

```python
from pfn_pipeline import (
    identify_randomized_network_batch, identify_verified_effect_bundle,
    replay_verified_effect_bundle, EffectQueryV18,
)
from pfn_pipeline.identification_a4_shadow import declare_a4_source

# task 为 经确认的 randomized-network arm TaskSpec
batch = identify_randomized_network_batch(task)
selected = ('node-0', 'node-1', 'node-2')
a4 = declare_a4_source(
    batch.template, source_id='reviewed-operator',
    operator='NODE_ARM_MEANS',
    provenance='explicit approved study population operator',
    admission='ADMITTED', availability='SYMBOLIC_POPULATION_OPERATOR',
    outcome_nodes=selected, node_order=batch.node_ids,
    arm_cells=tuple((i,a,s) for i in selected for a in (0,1) for s in (0,1)),
)
queries = (
    EffectQueryV18('DIRECT', (('node-0', 1),), 0, 0),
    EffectQueryV18('SPILLOVER', (('node-0', 1),), 0, 1),
    EffectQueryV18('TOTAL', (('node-0', 1),), 0, 1),
    EffectQueryV18('TOTAL', tuple((i,1) for i in selected), 0, 1,
                   cohort_authority='STUDY_PROTOCOL',
                   cohort_evidence='Group fixed before treatment'),
)
bundle = identify_verified_effect_bundle(batch, a4, queries)
replay_verified_effect_bundle(bundle)
for result in bundle.results:
    print(result.status, result.identified_functional)
```

如果 target 的某一非零项为零支持，返回 `CompositionUnavailable(reason_code='ZERO_ARM_SUPPORT')`，不删除这个节点后冒充完整组平均；如果相关 A4 算子不完整，返回 `A4_ARM_COVERAGE_INCOMPLETE`；本模块不会将这些状态误标为 `PARTIAL`。

## 4. 可运行命令与验收

```bash
python -B -m examples.run_verified_r1a_composition
python -B -m examples.run_verified_r1a_composition --er300
python -B -m unittest discover -s tests -p 'test_verified_target_composition.py' -v
python -B -m unittest discover -s tests -p 'test_*.py' -q
```

ER300 直接使用 shared `simulate_task()` 的图与明确 Bernoulli(.5) 协议；**不复写一份独立 ER20 demo 图，也不调用 PFN 或旧 heavyweight legacy bridge**。示例的 synthetic A4 来源是明确演示声明，不是实际已观察的总体数值。完整效果示例保留给未来 Estimation adapter。

## 5. 未覆盖范围 / 下一步

R1a only：不识别真正固定完整分配政策福利、不跨 q/W 混合不同 Batch、不在 zero-support 上做外推、也没有 observational adjustment 或 network partial-ID solver。下一阶段可根据现有数学合同开始 R1b Verified Fixed Policy，仍须 A4 full-assignment resolution 和完整分配支持证明；R2 structural sufficiency 则需要额外因果假设。
