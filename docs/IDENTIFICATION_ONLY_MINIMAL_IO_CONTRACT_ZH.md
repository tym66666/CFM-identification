# Causal-IDFM · Identification-only 最小输入输出合同

**基线：v2.9.2 Maintenance P2 + ID-only 兼容增量。数学 Core、A0、Estimation、Policy 原代码均未修改。**

## 1. 单一数学入口

`pfn_pipeline.identification_business.identify_network_business_query(inquiry)` 是正式定理入口。只接受已审核的 typed inquiry；独立核验采用 `replay_verified_business_outcome(outcome)`。任何展示逻辑都不能从业务纯文本自行构造 q、A4、A5、Exposure 或 theorem certificate。

本轮 `identification_only.report.from_verified_core` 不是第二套识别引擎。它重新调用 Core replay，然后产生轻量 JSON 报告；原定理和证书仍属于 `pfn_pipeline`。

## 2. 输入：数学必需 vs 用户体验

```text
业务自然语言 / PDF / DOCX / XLSX
    -> A0 候选（其他团队负责）
    -> 独立确认的 A1 Target 与 A2/A3 Network/Design/Exposure
    -> A4 typed population observable & admission
    -> A5 scoped scientific assumptions & human review
    -> typed inquiry -> Identification Core
```

当前离线 HTML 可以读取 TXT、MD、CSV、JSON 的文本预览；PDF/DOCX/XLSX 只登记文件名，不解析、OCR 或推断数学设置。点击“导出待审核输入”产生 `UNREVIEWED_INPUT_NO_IDENTIFICATION` 的 JSON，**不得**解释为已执行 Core。A0 后续若提供 reviewed typed packets，应调用既有 `python -m cfm_id_bridge identify` CLI 及真实 Core；本轮没有改造 A0。

## 3. 输出：简单且可审计

`schema_version=cfm-id-identification-only-report-v1`：

- `business_question` / `setting` / `inputs`：使用者要做什么，Design/Exposure，以及已声明的 A4/A5（这里只是展示性说明，不能替代 scoped licence）。
- `identification.status`：只来自原 Core，`POINT`、`NEEDS_INPUT`、`UNSUPPORTED`。
- `identification.theorem_route` / `formula` / `target` / `support`：仅对 Core + replay 的 POINT 输出；未验证不产生公式。
- `proof.level=CORE_REPLAY_VERIFIED`、`certificate_sha256`：原始正式 verifier 与 replay 的证据标识。
- `next_step`：缺少什么或下一步科学输入，而不是编造数值。
- `numeric_effect_estimate=null`、`nonidentification_proven=false`：不冒充 Estimation，也不从 UNSUPPORTED 推出 NON-ID。

隔离研究的 Star7 区间使用 `category=PARTIAL_RESEARCH_ONLY` 且 `proof.level=RESEARCH_WITNESSES_ONLY`，绝不伪装成生产 R4。LLM 外部候选使用 `category=UNVERIFIED_LLM_CANDIDATE`、`identification.status=NOT_EVALUATED`，既不授权 POINT，也不授权数学 NON-ID。

## 4. 唯一快速路径与归属

```
bash scripts/run_identification_only.sh fast
bash scripts/run_identification_only.sh demo
bash scripts/run_identification_only.sh id-all
```

`fast` 包含三节点 Golden、R3 三表示消融和新展示合同测试；`id-all` 对 53 个只涉及识别/业务审核/符号效果的测试模块执行独立进程回归。它**明确排除**四个依赖历史 PFN 训练/模拟/估计环境的测试文件：`test_pipeline_smoke.py`、`test_identification_integration.py`、`test_identification_estimation_contract.py`、`test_batch_identification.py`。还排除只诊断旧 PFN 运行、不检验识别结论的 `test_minimal_pfn_diagnostic_ablation.py`。这属于本模块的验收边界，并非删除这些历史测试或宣称整个仓库全部通过。

用于主项目的完整回归仍保留既有入口，当前 Identification 工作不承担 PFN-smoke 的可靠性研究。

## 5. 本轮展示事实与不能声称的能力

- 6 种现有合成业务中的 18 个 Formal-backed 样例，以及 9 个 Golden 单因素消融，共 27 个正式 Core 查询；所有 POINT 都重新 replay。
- 研究性 Star7 Partial 区间另列，没有正式 R4 certificate。
- HTML 支持输入业务要求文本、上传材料、导出未审核输入 JSON 和查看预置 Core 输出；**静态 HTML 内不会运行 Python 核心**。
- 看板成功数量不是现实市场覆盖率。样例使用研究者事先指定的合成 A4/A5，尚未取得真实企业科学审核。

## 6. 必须持续维护的不变量

1. 未审核业务描述不能直接变成数学 POINT；
2. 缺 A4/A5、安全拒绝和零支持不能自动写成 `NON_IDENTIFIED`；
3. 同名 Direct 但不同 q/p/调整目标不能视为同一 Target；
4. `POINT` 必须原定理与独立 replay 均通过；
5. 未认证的 LLM 候选、研究性 PARTIAL、历史 JSON 导入不能改变正式 Core 结果；
6. 严格维持数学 Core 不动，调试先缩成三节点 Golden，再逐项消融。

**业务语义绑定风险：** `from_verified_core` 只准从 `SYNTHETIC_APPROVED_FIXTURE` 产生展示报告，且 `business_semantics_independently_certified=false`。真实业务必须使用已有 v2.9 业务意图 crosswalk + 科学审核桥接，不得把向展示层填写了一段文字当作业务 Target 被形式证明。
