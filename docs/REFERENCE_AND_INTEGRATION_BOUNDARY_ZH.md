# 数学 参考边界与独立 Gateway 对接注意事项

本次仅以用户上传的 **Causal-IDFM v2.9.1 Integration Correctness Hardening** 作为**只读参考**。比较发现：其 `cfm_id_llm` 的源码与原独立 v0.9 相同；科学许可和 typed target 审核工作主要位于 `cfm_id_bridge` 与 `pfn_pipeline`。本次交付的 v0.10 **不包含**这些数学目录，不声称已兼容所有正式 typed inquiry。

## 输入语义与授权的独立性

`BusinessInquiryV010.semantics` 存储来自企业材料的候选文本语义与来源。即使它声称“全部 300 人接受 AI”，也绝不自动构造 \\(\\mathbf z=(1,\\ldots,1)\\) 并附上科学许可证：节点顺序、处理编码、政策权重、总体 A4 信息等需要正式数学层独立核对。

新 `MultiQueryQualityReportV010` 是 **A0 草稿质量报告**，不是 `ScientificAdmissionV29`、`ApprovedScienceBindingV291`、IdentificationSpec 或数学结果。正式桥接时需要：

1. 保留每个 query 的 `case_id`、输入内容摘要、草稿 SHA 和具体语义；由独立审核确定精确节点、干预/对照、暴露、时间和聚合。
2. 数学侧不能仅凭 `business_status=FORMALIZATION_READY`、引用合法或 `semantic_status=COMPLETE` 自动批准科学条件。
3. `as_v09()` 只用于**旧版兼容**，会丢失新增 semantics；未来正式 typed crosswalk 应直接读取 v0.10 语义并执行一致性审查。
4. A4 总体算子与 A5 许可必须由受控科学对象及独立 reviewer 审核；既不由表格字段推断，也不由 LLM `INTERPRETATION` 决定。
5. 数学库 Unsupported 不等于数学不可识别；LLM Candidate 始终不得作为正式证书。

## 持续版本策略

保持 **Gateway v0.10.x**、**Math Core v2.9.1+** 和 **NBIB** 三条独立版本线。先由 Gateway 增强 Business → Candidate Query，再通过受控 adapter 独立升级，不在 Gateway 内复制数学 theorem 或 verifier。
