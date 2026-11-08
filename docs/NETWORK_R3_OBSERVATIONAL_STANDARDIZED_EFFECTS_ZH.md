# Causal-IDFM Identification R3 观测网络标准化效应与分类复用

**基线**：v2.5；**新增正式能力**：小型固定网络、固定条件层 `W=w` 下的 Observational-Law-Standardized `DIRECT / SPILLOVER / TOTAL` 和事先声明权重的群体聚合。**不是新增 theorem family**；不是两阶段随机化；不改变 R1a/R1b/R2、Estimation、Policy 的已发布数学含义。

## 1. 有限、分层、尽量正交的分类

**核心抽象划分**（拒绝把每种 Effect、D×E、图拓扑建立成 Family）：

| 分层 | 角色 | 可复用边界 |
|---|---|---|
| A1 Target | `q` 标准化 arm、`p_obs` 标准化 arm/contrast、固定完整政策、有限随机政策 | `DIRECT/SPILLOVER/TOTAL` 是组合公式，不是因果许可；R1a/R3 共用 `EffectQueryV18` 与 `compile_effect_query_terms` |
| A2/A3 Study & Network | 固定处理前无向图、节点顺序、binary T、pre-treatment W | 一张图可参与不同实验或观测协议；Graph family ≠ Theorem family |
| A4 Information | 实验设计已知 `q`，或观测总体 `p_obs(T|W)`，加 outcome 总体算子 | q 不可用观测 propensity 代替；完整 assignment law 比样本频数强 |
| A5 Identification License | full-vector randomization、conditional exchangeability、mean-signature sufficiency | Signature 的存在不是 sufficiency；交换性不能从观测律自动确认 |
| A6 Validity | full-assignment support、每个 arm 支持、每个目标 signature 支持 | 数学目标的正支持门槛因 route 而不同；没有支持不代表所有因果方案数学上均不能识别 |

正式 Route 群组应按**核心识别许可**划分，而不是按用户问的是 Direct 还是 Policy。这些路线的适用域允许交叉：例如已知 q 的 R1b 和接受 signature sufficiency 的 R2 都可识别同一个政策目标，因此“不重叠”不应误解为强制选择唯一可用定理。统一入口可以有明确的择优准则，并保留审计记录。

当前注册的数学路线：R1a 实验设计标准化 arm + 代数组合、R1b 完整 assignment policy、R2 额外结构假设下的 signature policy，以及 R3 观测交换性下的 full policy、signature policy、**p 标准化 arm/contrast（v2.6 新增）**。当前不将每个实例的 D1–D5/E1–E5 组合注册为 theorem family。

## 2. 新 A1 Target 与 R3 定理

对固定条件 `W=w`，观测总体的完整分配律 `p(t|w)=P_obs(T=t|W=w)` 和已定义的 one-hop exposure `S_i=g_i(T,G)`，若 `ρ_i(a,s|w)>0`，定义

\[
\rho_i(a,s\mid w)=\sum_{\mathbf t:t_i=a,g_i(\mathbf t,G)=s}p(\mathbf t\mid w),
\]

\[
\mu_i^p(a,s\mid w)=
\sum_{\mathbf t:t_i=a,g_i(\mathbf t,G)=s}
\frac{p(\mathbf t\mid w)}{\rho_i(a,s\mid w)}
\mathbb E[Y_i(\mathbf t)\mid W=w].
\]

**A5：**已明确接受 `(i)` full-vector conditional exchangeability：整个潜在结果表 `Y_i(t)` 与完整观测处理向量 `T` 在 `W=w` 下独立；`(ii)` consistency；`(iii)` 处理前固定图；`(iv)` 有限条件一阶矩。**A4：**已准入的符号性总体分配律与同一来源覆盖的 assignment-conditioned node outcome 均值算子；sample-level 经验统计不能冒充总体信息。

则通过按完整观测分配条件均值展开并使用交换性：

\[
\mu_i^p(a,s\mid w)
=\mathbb E[Y_i^{obs}\mid T_i=a,S_i=s,W=w].
\]

对上述 arm means 应用事先选择的精确线性系数，得到 `DIRECT/SPILLOVER/TOTAL` 及预处理分组平均。**不需要 mean-signature sufficiency**：暴露在这里是区分标准化目标的索引，并不是对潜在结果的结构等价类约束。

**重要语义边界：**`Direct^p_i(s)=μ^p_i(1,s)−μ^p_i(0,s)` 比较的是**可能具有不同完整分配权重**的两个随机化标准化目标；不是保持其他节点 treatment 固定不变的 controlled direct effect，也不是固定政策福利 `V(z)`。观测分配律 `p` 是数学目标的一部分，因此进入 target fingerprint；A4 来源 ID、承认证据仅进入证书指纹。不同 p，即使网络和 target 文字相同，其 p 标准化因果目标也可能不同。

## 3. 最小复用设计

- **R3 基础门禁复用**：从 v2.3 `identification_observational_r3.py` 抽出 `_validated_observational_basis()`；R3 Policy 与新 R3 Effects 共用同一 A4/A5 校验，没有伪造一个 dummy policy target。
- **A1 代数复用**：`identification_composition.py` 增加 `compile_effect_query_terms()`，内部复用 R1a 原 `_terms_from_recipe`；对效果名称、精确权重、分组来源的规则只维护一套。R3 不能复用 R1a 的随机化许可或其 Batch 证书。
- **E1–E5 Exposure 复用**：正式主计算使用 `ExposureSpec`；独立 A6 重放使用算术判别 `_manual_exposure_classify_v26()`。该独立算法同时服务原 R3 policy 和新 effects，避免两份独立 verifier 随 E4/E5 演进产生语义漂移。
- **一个查询类型**：新增 `ObservationalEffectsInquiryV26`，能够接收多项 `EffectQueryV18`，正式业务入口返回 `VerifiedBusinessOutcomeV21`，继承既有 `POINT / NEEDS_INPUT / UNSUPPORTED` 诊断。
- **一个识别结果类型**：`VerifiedObservationalEffectsV26`，每个效应有已审核的精确 arm 支持、系数、符号 identification functional、目标 fingerprint 和独立 replay。**没有数值效果和 PFN adapter**。

## 4. 当前有效域与不足

支持 E1–E5 且根据节点度数验证状态；E2 有孤立节点时相关 arm 不定义，E3 要有全体有效的处理前核心合作者。沿用 v2.3 观测总体信息最多 **12 个节点 / 4096 个显式正质量 assignment cells**，固定一个 W 条件层、binary T、固定无向图。观察 `p(T|W)` 可能在节点间强相关，**不能把它当作独立 Bernoulli q**。

不能自动从现实样本推出总体 A4；不做连续 W 积分、不确认真实交换性、不做动态/有向/加权网络、不返回实际销售效果、不自动获得 PFN 估计器；两阶段 cluster saturation 不是本轮实现。本轮只完成 R3 的新 Target 类，而不是创建新识别家族。

## 5. 正反验收与运行

```bash
python -B -m unittest discover -s tests -p 'test_observational_standardized_effects.py' -v
python -B -m unittest discover -s tests -q
python -B -m examples.run_observational_effects --output-dir showcase_v26
```

该演示对预设的 **C38–C48 共 11 张增量业务卡**执行正式 API：7 个 POINT、3 个 `NEEDS_INPUT`、1 个 `UNSUPPORTED`（均在合成示例环境下），含 R3-Full 作为不同目标的对照。HTML/JSON 来源于真实 `VerifiedBusinessOutcomeV21` 与 replay，不含效果数值。原 32+5 张业务卡沿用既有成果，本版本没有宣称全部重新审计。

与既有测试共同验证：完整观测律的非独立分配、E1–E5 与四种典型图、zero arm support、未确认 A5、伪造总体 A4、来源/研究坐标错误、证书篡改和重新算 digest 后的伪造；最重要的是一个不满足 exposure sufficiency 的显式潜在结果 world 中，p 标准化识别公式仍精确成立。
