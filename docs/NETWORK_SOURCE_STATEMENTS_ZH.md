# 从原文科学声明到未批准的事实字段

当前网络事实读取原本要求模型直接填写 `true/false/null`。在线负例出现过：模型正确读出随机名单，却把它同时当作“完整处理向量与所有潜在结果独立”的科学声明。再次提醒不要推断并未稳定消除该错误。

本实验把两件事拆开：原文描述了什么分配规则，以及原文对某个科学条件表达了什么态度。只改变读取合同，不改变 POINT／PARTIAL 的数学合同、证明或独立重放。

## 原文声明的结构

历史分配规则、完整网络、目标、总体信息等仍使用原字段。原 assumptions 拆成：

- `design_facts`：完整历史分配规则是否已给出、网络是否明确在处理前固定。
- `scientific_statements`：处理安排与全部潜在结果独立性、一致性、有限条件一阶矩。每项使用原文态度和逐字引用，不让模型直接填写科学真值。
- `mean_sufficiency`：同样记录原文态度和引用，同时保留范围及覆盖对象。暴露函数本身不产生均值充分性。

| 原文态度 | 新状态 | 投影到旧读取值 | 意义与限制 |
|---|---|---|---|
| 明确采用 | ADOPTED | true | 仅表示原文这样陈述，尚未批准 |
| 明确拟采用 | PROPOSED | true | 保留候选条件，仍需独立批准 |
| 明确不采用或否定 | NOT_ADOPTED | false | 当前路线不能依赖此条件；不证明反命题 |
| 明确尚未决定 | UNDECIDED | null | 不替研究者决定 |
| 未提及 | NOT_STATED | null | 不从抽签方式、结果类型等补出 |
| 存在未解决冲突 | CONFLICTING | null，阻断重查 | 保留双方引用，不挑一方继续 |

当前试用格式 `network-source-selections-1` 中，每项使用 `status` 和 `source_ids`。除 NOT_STATED 外必须选择当前材料的来源编号；程序取回完整来源段落并写入 receipt，模型无需重复抄写。来源不存在、重复编号、无来源的明确态度、未知状态和错用旧引用上下文均拒绝。NOT_STATED 不携带假造的“未提及证明”；均值充分性未提及时也不能补覆盖范围。

例如原文是“研究负责人拟采用以下条件：处理安排与全部潜在结果独立；一致性……”，模型只需为对应字段返回 `{"status":"PROPOSED","source_ids":["s0006"]}`。程序取回整段原文，保留共享的“拟采用”前缀，不能把这个状态视为已批准。

首轮格式 `network-source-statements-1` 要求模型填写逐字 `quotations=[{source_id, quote}]`，仍保留用于重现历史请求。在线比较发现模型会将共用前缀与后面的列表条目拼成并不存在的连续原句；该格式仍严格拒绝这些回答。来源编号格式使用独立协议和新请求，不回写或修补旧回答。冲突可以集中在同一段，因此编号格式允许一段包含双方；冲突态仍一律要求重新核查。

**引用存在不证明语义正确。** 模型仍可能把真实的抽签原句错误解释成科学独立性声明。返回的 `statement_reading_receipt` 因此分别记录 `quotation_occurrence_verified=true`、`semantic_entailment_verified=false`、`scientific_approval=false`。原模型 JSON、声明态度、逐字原句和转换结果均保留，来源审核与科学批准仍由既有独立审核负责。

程序转换只依照明确状态，不用正则识别业务句子，不替模型修值。ADOPTED 和 PROPOSED 投影相同，但原态度保存在 receipt 和原候选中；false 只用于现有适用性阻断，不推导数学反例或非识别结论。

## 接入与兼容

默认继续使用旧合同。试用时由调用器显式设置：

```python
from cfm_id import business_intake as intake

current = intake.start(case, network_fact_contract="network-source-selections-1")
# 已有 A0 的研究会话，也可显式切换后续读取格式：
updated = intake.configure_network_fact_contract(current, "network-source-selections-1")
```

这不是要求业务用户选择识别路线，而是开发端的候选读取格式。设置项保存于 intake；更改后需重新审核当前查询，旧事实请求、旧审批和旧复查绑定不可沿用。A0 请求及原候选保持原样。DAG 事实读取不改成此网络格式。

历史 intake 没有该字段时，序列化不增加空值，原请求及方法计划保持一致。新合同有独立 wire 版本，旧 JSON 不会被自动当作新回答。网络显式重读、全部字段变化审核和整题汇总保留原机制；冲突态即使存在其他不依赖该条件的候选路线，也先要求核对冲突原文。

## 本轮范围

实现入口是 `cfm_id_llm/network_statement_reading.py`，测试为 `tests_gateway/test_network_statement_reading.py`。合成正例经完整独立测试审核后，仍调用原生 R1b/R2 和有限 PARTIAL 求解器，并重放证书。没有增加定理、默认科学许可或模型推理证明。

本轮在线实验只比较专门事实读取层：两种业务/分配结构、六份科学声明版本，共 24 个首轮预注册请求，旧/逐字引用合同及 DeepSeek 4/LongCat 交叉对照；后续同材料测试来源编号合同，并单列 DeepSeek 4.1 的访问及读取结果。不是六个独立业务领域，也不是新的端到端准确率。证据位于仓库外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED` 和 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`，原始失败保留，未运行请求不当作完成。默认切换需更多实际稳定性证据，本轮保持实验选项。

科学条件态度读对，不代表其他字段都对。本轮还发现逐对象 `(Y_i,T)` 总体分布被误读成更强的全部结果 `(Y_1,...,Y_n,T)` 联合分布。二者保留为不同 A4 字段；程序不自动升格或降格。该问题须另做范围语义与负例对照，不能用科学声明字段的通过率替代整份读取准确率。

结果类型的计数语义、A0 重复字段和明确时期字段尚未在本实验一起改动，以免无法判断改动来源。新材料使用二元结果和同一试点周，单独检验科学声明的读取。

## 字段职责说明接入（2026-10-27）

开发端可显式选择 `network-source-selections-roles-1`。它使用相同的来源编号 wire 和解析器，入口为 `cfm_id_llm/network_reading_contract.py`；只替换三处重叠的系统说明，并同步相应 Schema 字段描述。原材料、字段类型和枚举不改动，默认配置不切换。

```python
current = intake.start(case, network_fact_contract="network-source-selections-roles-1")
```

这次澄清三件事：

- `information` 已表示的总体／样本性质、联合变量和覆盖范围，不重复抄入 `additional_restrictions`；无法表达的信息和真实限制必须保留。
- `listed_means_are_complete_information` 只问是否还有其他总体信息。`no_additional_coupling_constraints` 则以基础条件、已声明的均值充分性、所列均值及逐对象界限为参照；存在另外采用的跨对象／跨安排关系时应为 false，即使原文在列完这项关系后说“没有其他限制”。未声明是否排除时仍为 null。
- 完整有界模型允许部分均值未定，这不等于原材料缺项。真正缺少范围、评价对象或完整性声明时仍保留未知。

这是 Prompt 和字段解释修订，不是候选清洗器。程序不删除重复限制、不纠正错误布尔值、不推导科学许可。相同候选继续经过原来源、完整模型与科学审核；真实额外限制仍阻断尚未连接的适配器。独立重读保留旧候选，所有变化重新审核。

共同入口已完成离线兼容和完整框架验收：新增 11 项合同检查，固定框架共 590 tests／125 subtests 通过。它验证接口边界，不证明 LLM 准确；真实完整链结果单独保存在仓库外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。
