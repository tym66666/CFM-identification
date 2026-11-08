# Identification Problem Taxonomy & Family Contract v1

> 历史设计文档：以下“当前能力/未来能力”保留当时语境，不作为最新覆盖声明。分类依据与维护判断请读[分类与文献依据](../literature_support/CLASSIFICATION_ZH.md)，当前运行范围见[CURRENT_SCOPE](CURRENT_SCOPE_ZH.md)。本次只补导航，不修改原数学内容。

**状态：跨 family 的科学问题分类合同（文档规范）；当前没有新建一套 `CausalTaskSpec`。**

## 1. 四个层次，不能混淆

1. **Problem**：明确因果世界集合、总体可用信息、目标与适用域，数学上可写为 `P=(M_A,O,Q;D)`。
2. **Family / Theorem Route**：对某一类正式问题，给出适用前提、POINT 泛函或 identified set 的推导与验证方法。`POINT` 是定理结论，不能仅由用户输入的标签决定。
3. **Setting / Instance**：setting 选择 family 内的设计与暴露规则（如 D2×E2），instance 提供具体图、配额、节点及 arm；ER300 只是一张固定网络实例，并非 family。
4. **Result & Handoff**：返回 `IdentificationResult` 的数学保证，之后**另行**判断现有 Estimation 是否支持该目标。

当观测信息为 `o` 时，识别集合为 `Γ_P(o)={Q(M): M∈M_A, O(M)=o}`（需检查兼容模型集合非空）。POINT 表示 singleton；没有求解器、输入不完整或缺少估计 adapter 都不自动意味着 PARTIAL。

## 2. 用户输入如何正规化：七个分类位置

| 阶段和分类 | 该处必须说清楚的数学语义 | 当前代码位置 / 当前能力 | 未来可能扩展（不是已实现） |
|---|---|---|---|
| A0 **输入来源与权限** | 业务叙述、实验协议、专家确认、合成真值是否区分？ | 用户/代码提供 `TaskSpec`，内部 assumption provenance、query authority；没有自动 NL→formal | LLM parser、UniCo-style offline 生成与评测、澄清请求 |
| A1 **Target / Query** | 目标是单 arm、响应面、对比、总体均值还是政策价值？标准化权重和条件 `W` 是什么？ | `TaskSpec.estimand/target_semantics`、内部 `QuerySpec`；新 family 单 arm，v1.0 批量组合；旧 ER300 四臂 response/score | CATE、ATE、干预分布、动态政策、真实固定全分配收益 |
| A2 **Units & Variables** | 研究单位、处理取值空间、outcome、条件变量和时间索引 | `TaskSpec.node_ids,outcome_kind`、`variable_domains`；固定节点、二元 treatment、当前 PFN 连续 outcome | 多值/连续 treatment、纵向和多 outcome |
| A3 **Structure** | `G_unit`（单位网络）、`G_var`（变量 DAG/ADMG）、暴露规则 `g` 三者不同 | `TaskSpec.adjacency`、内部 `StructureSpec/NetworkExposureSpec`、`randomized_network_arm_theorem_contract.grouping`；已知固定简单无向网络 E1/E2/E3，无需 DAG | 有向/加权/二部/动态网络；DAG/ADMG；曝光错设和未知图 |
| A4 **Information & Design** | 已知实验联合分配律 `q(T\|W)` 与可用总体观测概率律分别是什么？ | `assignment_design` + 内部 D1/D2/D3、`InformationSignature`；使用实验总体 node-arm 条件均值 | 观测研究、多数据源、cluster randomization、IV/proxy、缺失数据 |
| A5 **Assumption regime** | 哪些世界被允许？假设是否由研究协议/专家认可？ | `Assumption` 状态和来源；当前 full-vector randomization + consistency 等 | ignorability、exclusion、monotonicity、completeness、敏感性约束 |
| A6 **Validity / Support** | 哪些查询有定义、定理支持概率是否为正、计算是否超出资源域？ | 内部 `SupportEngine` 支持 D1/D2/D3×E1/E2/E3；E2 孤立节点无定义 | 连续处理 positivity、IV 算子 rank、约束可行性、部分识别域 |

注：A0 是**解析/澄清过程**，A1–A5 定义科学规格，A6 是适用域检验。现在不要机械对应为七个公共 Python 类；当前公共合同仍是 `TaskSpec` 携带严格的 `IdentificationSpec`。

## 3. 数学分类如何决定 theorem family

共享的 family route 合同应回答：

- **Supports**：要求的目标类型、结构、总体信息、假设是什么；遇到未知前提应 `NEEDS_INPUT`，不是用 LLM 推断“成立”。
- **Solve**：使用哪个定理、支持计算或约束求解，提供哪种泛函/集合及有效域。
- **Verify**：独立检查形式化目标、证明证书、support/界与输入绑定。
- **Emit**：用统一 `IdentificationResult` 返回数学结论，不声称任意 estimator 已经可运行。

目前 stable family：`NETWORK_RANDOMIZED_ARM_MEAN`（正式内部 backend `randomized_network_arm_mean_v1`），目标为

\[
\pi_i^q(a,s\mid W)=P_q(T_i=a,S_i=s\mid W),\qquad
\mu_i^q(a,s\mid W)=E_q[Y_i(\mathbf T)\mid T_i=a,S_i=s,W].
\]

已知 `q`、处理前 `g`、full-vector randomization、consistency、有限条件一阶矩、正 support 时：

\[
\mu_i^q(a,s\mid W)=E[Y_i^{obs}\mid W,T_i=a,S_i=s].
\]

不需要 exposure sufficiency；固定配额 D2/D3 必须按原联合分配律在 **`T_i=a` 与 `S_i=s` 同时条件化**。`q` 或 `g` 改变时，目标也可能改变，不能直接当成“同一个 query 假设放松”。

其他候选 family：变量图 POINT identification（包括 backdoor/frontdoor 等规则）、带 IV 的识别、network structure/assumption weakening 下的 partial-ID、离散 bound optimizer。这些都是**可能的数学/算法路线**，不意味着当前代码已实现完整兼容。

## 4. Family 内部可变，跨 family 接口稳定

- **当前 family 内部**：`AssignmentSpec(D1/D2/D3)` + `ExposureSpec(E1/E2/E3)` + `SupportEngine`。新 design/g 只要符合 theorem，尽量替换内部组件，不克隆定理。
- **跨 family 应稳定**：形式化目标/总体信息/assumption 来源 → route selection → 可核验 `IdentificationResult` → estimator capability matching。Backdoor/IV 不需要被迫实现“邻居 treated count”。
- **v1.0 的 Batch**：仅把同一个已确认 `q,g,W` 下的**逐节点逐 arm** POINT 结论组织为可验证 `[N,2,S]` 网格。其 `population_joint_support` **不是**已估计的均值表，也不是推断区间。
- **Estimation**：独立判定训练目标、arm 顺序、数据协议、checkpoint 和运行条件；`NO_ADAPTER` 与 `PARTIAL` 是不同概念。

## 5. 当前最小开发顺序

1. 完整保留 ER300 Bernoulli(1/2) + E1 四臂路线，并用批量证明对拍已有响应目标。
2. 新的 batch 只生成 POINT 状态、joint support、mask、指纹、证书；不会根据形状自动调用 PFN。
3. 只有与**同一原始 TaskSpec** 绑定、已独立 replay 的 legacy 响应结果，才能经批量审计继续执行原 EstimationRequest。
4. 等 Estimation 负责人定义 D1/D2/D3、E2/E3 的训练目标和适配器后，再显式扩展 Capability/Request。再选择第二条数学 family。

**研究提醒：** 现有统一 randomized POINT proposition 是现有随机化识别原理的特例/直接推论；将来新颖的 PARTIAL 研究需要固定真正依赖待放松假设的同一 causal query，并核对现有文献。
