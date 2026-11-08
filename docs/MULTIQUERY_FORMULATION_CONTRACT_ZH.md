# 多业务目标规范化合同

**一句话：公司提供一次业务描述和相关文件，Gateway 能把其中真正提出的几个问题分别整理清楚；它不因此完成数学识别。**

## 为什么做这个增量

例如一家销售公司同时想知道“使用 AI 的人是否提升业绩”“没使用 AI 的同事是否受影响”“以后全员推广会怎样”。这不是一个查询的三种叫法，而是三个不同的因果目标。旧 `DraftProblemSpec` 只有一个主要 `target`，`alternatives` 不足以表示同时成立的多个目标。

## 输入与输出

- 输入：已有的 `BusinessCase`，或者 v0.8 已有的 PDF / CSV / XLSX 等材料汇总；表格仍默认只传字段/结构摘要，原始数据不送外部模型。
- 输出：`MultiQueryDraftV09`，含**原封不动复用的** `shared_draft: DraftProblemSpec`、`primary_query_id`、1–8 个 `BusinessInquiryV09`。
- 每个 Inquiry 有 `query_id`、`business_goal`（业务到底想知道什么）、`target`（数学目标候选）、可选的 `requested_comparison_or_policy`（详细对比或推广方案）和针对该问题的必要澄清。
- `shared_draft.target` 必须与 primary query 的 target 完全一致，避免主要目标在两处冲突。
- 完整业务材料和每个目标都需要逐字引用原始 `source_id/quote`。字段来源匹配只证明“材料中有这句话”，不证明对其数学解释正确，也不证明因果假设成立。

## 与现有版本兼容

`DraftProblemSpec`、旧 v0.1–v0.8 Prompt、旧 CLI、R1/R2、Mock Core、Estimation 等全部不修改。v0.9 是新增的可选入口，不会复制最新版 Identification Library 的内部 Schema 或数学定理。

调用流程：

```
Business + Documents
  -> one consolidated v0.9 Prompt / one LLM call
  -> MultiQueryDraftV09
  -> exact quote/schema validation
  -> reuse old deterministic audit FOR EACH query
  -> per-query NEEDS_CLARIFICATION / DRAFT_READY_FOR_HUMAN_REVIEW
  -> optional explicit human review (bound to all source + query hashes)
  -> future Core Adapter preview ONLY, never a live TaskSpec
```

**整个流程从不产生数学认证。** 真正的 Identification Library 尚未接入；`CORE_VERIFIED`、POINT 数值、政策价值、Estimation Handoff 均不能由该层宣布。

## 审核约束

- 若 q2 被悄悄换成另一个政策目标，即使 q1 没变，整份多查询审核摘要也会改变。旧人工确认不得继续使用。
- 可只由研究者确认某一个 query；未确认的 query 不会进入预备 handoff 清单。
- `HumanMultiQueryReviewV09` 是用户或研究者提供的确认**记录**，不是密码学签名，不能证明审阅者身份，也不能自动接受 A5 的科学真实性。
- `CoreHandoffPreviewV09` 只是未来 adapter 用的说明清单：`core_adapter_state=NOT_CONNECTED`、`mathematical_verification=NOT_PERFORMED`、`estimation_handoff_allowed=false`。
- 当前共享 A4/A5 仍要按每条查询分别审查；不同目标可能需要不同粒度的可观测信息或额外条件。

## 离线演示

```bash
python -m cfm_id_llm.multiquery_cli \
  --manifest examples/multisource/case.json \
  --provider mock \
  --mock-response examples/multisource/mock_multiquery.json

python -m evaluation.render_multiquery_demo
```

## 关于 转换

未来对接 Library 时，仍需真实 `CoreAdapter` 把**每一个**经过必要研究者确认的 query 映射到最新的数学输入；一个完整查询的公式或证书不能直接当作另一个查询的证明。这一转换尚未实现。
