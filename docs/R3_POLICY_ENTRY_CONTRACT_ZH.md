# 观察性网络固定政策均值：共同入口合同

共同入口连接已有 **R3_FULL_ASSIGNMENT**，并通过显式的 `observational_fact_profile="mean-signature"` 配置连接 **R3_MEAN_SIGNATURE**。原生定义与证明见 [R3 固定政策合同](R3_OBSERVATIONAL_FINITE_POLICY_AND_SIGNATURE_DIAGNOSTICS_ZH.md)，当前实现以 `pfn_pipeline.identification_observational_r3` 为准；本次不改数学 Core。[本轮接入验收与限制](R3_SIGNATURE_ENTRY_ACCEPTANCE_ZH.md)单独记录，不与历史LLM成绩混算。

## 核对已有 R3 的目标和接口

| 原生路线 | 目标与关键额外条件 | 本轮选择 |
|---|---|---|
| R3_FULL_ASSIGNMENT | 固定处理前背景 W 下的完整政策均值；完整向量条件交换性、一致性、固定网络、有限矩；完整政策有观测总体支持 | 接入；与现有固定政策目标一致，无需新增暴露定义或充分性 |
| R3_MEAN_SIGNATURE | 同一政策目标；支持不足时另需全安排均值签名充分性及目标签名支持 | 新读取配置接入；暴露定义、充分性与范围显式读取并独立审核，不因Full零支持自动授予条件 |
| R3_P_STANDARDIZED_EFFECTS | 按观测完整分配律在各 arm 内加权的均值差；目标本身随观测律改变 | 不等同固定政策或保持其他对象不变的直接效应 |
| R3_EXPOSURE_ADJUSTED_EFFECTS | 对共同离散处理前层标准化的暴露潜在结果；需个体潜在结果层暴露充分性和逐层均值交换性 | 不能借用 R2 的均值充分性代替其科学许可 |
| R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS | 节点个人／邻居处理前协变量条件下的暴露结果调整 | 需独立协变量范围、A4 和科学合同，不合并到本轮固定 W 入口 |

完整目标为固定的二元安排 z、明确评价名单 S 与固定处理前 W=w：

\[
V(z\mid w)=|S|^{-1}\sum_{i\in S}\mathbb E[Y_i(z)\mid W=w].
\]

在完整潜在结果表与完整处理向量的条件交换性、consistency、固定处理前图和有限条件一阶矩下，若 \(P_{obs}(T=z\mid W=w)>0\)，原生 R3 给出

\[
V(z\mid w)=|S|^{-1}\sum_{i\in S}\mathbb E[Y_i^{obs}\mid T=z,W=w].
\]

这是现有定理应用，不是新的数学机制。交换性是独立科学许可，不能从 p(T|W)、使用记录或模型读取推导。完整安排正性由数学后端检查；零支持不自动等于非识别证明。

当完整政策无支持时，若另行采用对每个评价对象、所有完整二元安排均成立的

\[
\mathbb E[Y_i(z)\mid W=w]=h_i(z_i,g_i(z),w),
\]

且每个评价对象的目标状态满足
\(P_{obs}(T_i=z_i,g_i(T)=g_i(z)\mid W=w)>0\)，同一原生后端给出

\[
V(z\mid w)=|S|^{-1}\sum_{i\in S}
\mathbb E[Y_i^{obs}\mid T_i=z_i,g_i(T)=g_i(z),W=w].
\]

该式仍需要前述完整向量条件交换性、一致性及有限矩。均值充分性不是暴露定义的逻辑推论，也不是要求个体潜在结果完全相同。本入口保留原生 E1–E5 映射及各自限制；核心同伴需要完整处理前名单，比例映射不允许评价孤立对象。完整政策有支持时优先使用Full，不额外要求均值充分性；已读取的其他声明仍保留，不删改原模型。

## 本轮输入与准入

- A0 已有 `OBSERVATIONAL` 分配标签；仅在研究结构、目标与原文经过审核后，用它选择观察性事实合同。它不授予 R3 科学许可，不改变用户问题。其他已知目标不能因为属于观察性就被送到随机化方法。
- A0 Prompt 和旧实验读取协议保持不变。本轮只新增一个必要的观察性政策事实合同；目标、图、固定处理前条件、完整观测总体律、均值覆盖、科学声明、额外限制与疑问分别表达。
- A4 沿用原生有限枚举合同：最多 12 个对象、4096 个正质量完整安排，精确有理概率合计为 1；同一个明确声明的总体算子覆盖观测分配律及所有正质量安排下指定对象的结果条件均值。不能把有限记录、频数或边际采用概率提升为这个算子。
- 完整支持表、所有正质量安排的均值覆盖、与本研究及 W 的一致性都须有独立来源声明与审核。缺少条目不自动补零；不将两个不完整来源拼成完整总体。
- 本轮仅接受明确的完整固定政策、等权评价名单和固定处理前 W；不做多层标准化、连续 W 积分、政策差值或动态网络。额外限制和未明确背景保留并停止，不删掉后求解。
- 若选用明确绑定总体信息状态的 A0 合同，已审核 MISSING 与事实阶段总体算子声明冲突时，复用既有两阶段一致性检查，停止并要求复查；UNKNOWN 不等于缺少，STATED 不授予 A4。旧合同不重新解释缺项语义。
- 复用独立意图、计划、读取、A4/A5、备注与完整重读变更审核。保持 `SYNTHETIC_TEST` 研究边界，不新增生产准入、Estimation 或 Policy 交接。

## 接口与验证义务

审核后编译 `ObservationalPolicyInquiryV23`，调用现有 `identify_network_business_query`。Full不提供signature/sufficiency；签名路线使用既有构造器绑定映射、充分性、评价范围与独立审核来源。POINT必须与当前计划的方法一致，返回study、target、source、assumptions及signature/sufficiency与已审输入逐项一致；原生独立replay必须通过，且执行和replay都未修改输入。保留完整证书与目标指纹，不另造数学证书。

新配置只是读取能力，不是用户选择定理或批准假设：

```python
from cfm_id import business_intake
session = business_intake.start_configured(case, {"observational_fact_profile": "mean-signature"})
```

默认配置及旧观察性 profile 保持原合同。新配置的请求、Schema、解析、来源审核、字段诊断、固定背景交接及显式重读在 `cfm_id_llm.fact_reading_contracts` 中一起登记。A0没有调整。

签名 profile 的请求现包含 `source_review_contract`，直接复用 `fact_source_contract` 中审核实际使用的字段职责与引用规则。概率行须引用行值及解释坐标的表头，不能隐式继承父记录来源；本 wire 没有启用 `definition_refs`。复查从首次请求提取同一规则。签名 System 使用共同读取说明，备注职责改由公共合同提供，避免沿用旧 profile 对尚无专用字段的均值充分性的说明。解析器不自动补引用、删备注或批准条件；这是请求与审核的合同对齐，不是正确率保证。

新签名请求内容改变后须重新调用并审核，旧请求的审核与复查历史不能移植到新请求。旧观察性 profile 的 System 与请求结构保持兼容，当前默认推荐配置不切换为签名 profile。

### 可选的显式定义引用

`observational_fact_profile="mean-signature-definitions"` 在同一读取家族中补充证据表达，不增加数学能力。维护模块为 `cfm_id_llm.network_observational_definitions`：

- 每张总体表保存自己的 `coordinates`：原表头对象顺序、0/1编码及其原文来源。概率行通过 `definition_refs=["table_coordinates"]` 明确使用**本表**的定义，行本身仍须引用概率值；不得借用另一张表或隐式继承父记录。
- 目标、均值充分性评价名单、总体信息对象可以显式引用 `study` 的对象身份与处理编码。政策选择、评价范围、科学采用状态及信息覆盖仍须各自有直接原文，名册不能替代这些声明。
- 解析保留原始回答和定义依赖回执，再将同一事实投影给原签名适配器；不替模型补来源、不改事实、不批准科学条件。共同登记中的 `model` 验证传输合同，`facts_model` 验证供适配器使用的语义事实，两者明确区分。
- 引用编号有效与结构完整只是本地检查；“引用是否真的解释了这个表头或主张”仍须独立来源审核。缺依赖、跨表依赖、无直接主张、错误坐标、来源拒绝及旧审核均不能进入数学执行。

首次 Schema、解析、来源工作表、封闭错误诊断与显式重读共同登记。旧默认及 `mean-signature` 请求保持原样；不迁移旧审核。此选项的真实复测和剩余误读见[验收记录](R3_SIGNATURE_ENTRY_ACCEPTANCE_ZH.md)。真实未决定的条件可以保留在 `unresolved`；不得把 `additional_restrictions` 的“不得重复已有条件”规则扩张成对所有备注的禁止。

```powershell
python -m examples.network_observational_signature_reference --allow-synthetic-reviews --output outputs/r3_signature_examples
```

示例包括签名POINT、无充分性仍可使用Full的POINT、充分性未定/拒绝、交换性缺失、样本信息和签名零支持。手工读取与合成审核均显式标注，不代替真实LLM验收。签名路线仍限当前固定W、最多12对象、明确总体表、等权固定政策与合成研究审核；不包括观测性两政策差值或跨背景平均。

正例包括相关观测分配、全体／指定子集、任意明确完整政策；负例包括未定／否定交换性、审核未通过、样本信息、表不完整、缺均值覆盖、零支持、未知政策对象、错误背景、额外条件、旧审核、错误目标证书及证书篡改。旧实验入口、保存恢复、重读与 CLI 同时验收。

案例参考和合成审核位于 `examples`，不进入运行依赖；实验记录位于源码之外。本轮离线验收不作为 LLM 准确率，也不声称 R3 其他目标已接通。结果见 接入验收（历史记录不随发布）。
