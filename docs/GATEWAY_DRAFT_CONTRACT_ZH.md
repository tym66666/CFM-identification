# CFM-ID Gateway 草稿规格合同（2026-10-17）

## 1. 原则

- **科学问题** `P=(M_A, O, Q; D)` 的对象包括目标、潜在世界模型类、总体信息与有效域。LLM v0.1 只**提议**这些对象的业务语义，不宣称已经给出数学模型类或已识别函数。
- v2.1 Identification Library 的分类位置：A0 来源与权限；A1 target/query；A2 units & variables；A3 unit network / variable DAG / exposure；A4 observable information **及 assignment design**；A5 assumptions；A6 validity/support。
- LLM 草稿与正式 `TaskSpec`、`IdentificationSpec` 是**不同**的接口，不应直接 `model_validate()` 到核心类后跳过人工确认。

## 2. 输入：BusinessCase

```text
case_id: unique id
business_question: original narrative
sources: [{source_id, kind, text, label?}]  # kind: BUSINESS_NARRATIVE/STUDY_PROTOCOL/DATA_DICTIONARY/DOMAIN_KNOWLEDGE/OTHER
response_language: zh | en
```

`source.kind` 由调用方声明，是定位原文出处的标签，不是 Gateway 验证的外部真实性。保留 `business_question` 作为 `source_id="business_question"` 的内置证据对象。

## 3. 输出：DraftProblemSpec

- A1 `target`: `kind`, `description`, `alternatives`；除网络 arm、政策价值/优化及典型效果外，允许 `OTHER/UNRESOLVED`，不强制套用现有 R1a/R1b/R2。
- A2 `units_variables`: analysis_unit/treatment/outcome/covariates/temporal_structure。
- A3 `structure`: unit_network/variable_causal_graph/exposure_mapping/network_pretreatment_status。出现 `unit_network` 不默认存在变量 DAG，也不证明 exposure sufficiency。
- A4 `information_design`: assignment_family/assignment_law，population_information_level/population_observable_operator，sample_data_description。**有原始数据字段 ≠ 具有所需的总体条件均值算子**。
- A5 `assumptions`: 仅 `PROPOSED/UNRESOLVED`，其 basis 可为 `REPORTED_BY_SOURCE/LLM_SUGGESTION/MISSING`。从用户协议中提取不自动升级为 `ADMITTED/CERTIFIED`。
- A6 `validity`: support_or_positivity/query_domain/other_conditions。该字段依然只是文本草稿，没有由 SupportEngine 实算。
- `ambiguities`、`clarifying_questions`：保留替代阅读和人工问题；不能把分配歧义偷偷改写。

每个 `SemanticClaim` 的 `basis`：

| basis | 内容 | 是否可授权进入识别定理 |
|---|---|---|
| EXPLICIT_TEXT | LLM 认为业务原文明确表达该语义，给定逐字证据 | **否**，仍需科学复核 |
| INTERPRETATION | 由原文支持的解释性候选，不等同事实 | **否** |
| UNRESOLVED | value=null/evidence=[] | **否** |

任意非空 claim 必须给出 `EvidenceQuote(source_id, quote)`，并被程序检查为对应来源的精确连续子串。这只能证明**字面引用存在**，不能证明自然语言推理有效或协议真实。

## 4. `FormulationReport` 的安全状态

`review_status`: `NEEDS_CLARIFICATION` 或 `DRAFT_READY_FOR_HUMAN_REVIEW`（只指草稿审查就绪）。

**恒定不变量**：`mathematical_verification = NOT_PERFORMED`; `estimation_handoff_allowed = false`。不存在 `identified_functional`、`verification_certificate`、`POINT/PARTIAL` 字段。应用程序必须禁止由这些草稿触发 Estimation。

A4 source authenticity、A5 external validity、A6 positive support 将来由研究者和相应严格 theorem core 核查。不能凭 draft 的 `population_information_level=FULL_JOINT_LAW` 就断言真有总体观测律。

## 5. 为什么不直接绑定现有 Schema

- v2.1 `VariableSemanticSpec` 同时包含旧场景的特定 query enums 与默认 ATE/RESOLVED；这些不应成为开放业务解析的默认结果。
- v0.1 因此建立的是**与旧库无依赖的轻量交换草稿**，不是新通用数学 IR。正式路由的底层类与实例仍归最新 v3/vX 核心库所有。
- 下一阶段 v0.2 再通过显式的、可测试的 `CoreIdentificationPort` 适配 verified core（v0.1 没有实现该 Port）。
