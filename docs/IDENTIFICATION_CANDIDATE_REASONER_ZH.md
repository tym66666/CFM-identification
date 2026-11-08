# CFM-ID 独立 LLM Gateway Identification Candidate Reasoner 说明

> **适用范围**：本仓库已包含 Gateway 与数学模块。本页说明候选研究的兼容接口；其中的编号用于追溯协议，不表示需要另装旧版本。当前公共入口和实际覆盖以根目录 README 与能力登记为准，候选研究尚未自动接入所有业务分支。

## 1. 功能定位

CFM-ID 中的两个 LLM 职责不同：

- **A0 / Formulator（v0.10）**：业务描述和文件 → 多查询规范化草稿；区分业务澄清、重新抽取和科学审核。
- **Identification Candidate Reasoner（本 v0.11）**：经独立业务确认与科学审核后，**可信数学 Core 确认当前定理覆盖不足** → 对原查询提出未认证的识别表达式、附加 A4/A5/A6 条件、或观测等价反例思路。

无论 LLM 如何自称，输出都固定 `LLM_UNVERIFIED`、`estimation_handoff_allowed=false`、`mathematical_certificate=null`。若数学 Core 输出 `POINT`，应该使用 Core 的已验证结果，不能让 LLM 覆盖。如果返回 `NEEDS_INPUT` / `NO_ADAPTER` / `INCOMPATIBLE` / 错误 / 独立验证失败，本模块不会将其误用为“定理覆盖不足”。

**软件 `UNSUPPORTED` != 数学 `NOT_POINT`。** 即使候选包含两世界反例也仅属于人工审查草稿，不是完成数学证明。

## 2. 本轮具体实现

| 文件 | 功能 |
|---|---|
| `cfm_id_llm/candidate_queries.py` | v0.10 多查询 → 逐查询审核 → 可信 coverage port → 模型候选 → 独立字段审计；包含新输入/输出 Schema |
| `cfm_id_llm/candidate_query_prompts.py` | 单一查询的专门识别推理 Prompt + 动态 JSON Schema |
| `cfm_id_llm/candidate_preview_cli.py` | **只支持离线 Mock 覆盖结果**；可选择 Mock 或真实模型生成候选，但这仍不是可信数学 Core |
| `evaluation/candidate_reasoning_eval.py` | 19 组离线软件分流与安全探针、8 个小网络独立数学 sanity oracle、数学候选专家评分模板 |
| `tests/test_candidate_queries.py` | 55 项定向安全回归；v0.1–v0.10 接口原样保留 |

新方案复用旧 `CandidateDraftV03` 作为数学提案的受限语言，外加 `CandidateProposalV011`：

- `query_id`、`target_sha256`：候选对应哪一条用户业务查询；
- `semantics_sha256`：同时锁定该查询的处理、对照、暴露、政策范围等八项候选语义；
- `science_scope_sha256`：锁定独立科学上下文 A4 来源与 A5 许可；
- `proposed_validation_checks`：强制列出下一步核对公式和反例的步骤；
- `known_core_coverage_gap`：说明要探索的**软件定理覆盖缺口**，不得当成数学非识别结论。

旧 `CandidateReasonerV03` 仍可导入，便于历史研究复现，但新多查询集成应优先使用 v0.11 合同。

## 3. 真实生产环境应怎样与 集成

v0.11 的 `TrustedCoveragePortV011` 是一个**由宿主工程实现的 Python Protocol**，不是可以让浏览器提交任意“Core 已 UNSUPPORTED”JSON 的接口。

宿主应在其受信任的进程中真正执行 `run_verified_multiquery_v29()`，逐查询核对科学审批并取得数学 Core 路由结果，随后实现 `lookup(...) -> CoreCoverageV011`。必须保持两套审核独立；不能因为 A0 的 `FORMALIZATION_READY` 就认为 A4/A5 有效。

严格转换必须核对：

1. 业务资料内容与 v0.10 `input_sha256` 一致；v0.10 多查询草稿和 `draft_sha256` 一致。
2. 当前业务审阅确实覆盖该 `query_id`；该查询的 `target_sha256` 和 `semantics_sha256` 不变。
3. 受信科学审核记录、正式数学目标坐标与 `ApprovedScienceBindingV291` 对应。**不是只检查自然语言目标类型。**
4. `CoreCoverageV011.formal_target_sha256` 由 `formal_target_fingerprint_v29(inquiry)` 计算；`business_math_crosswalk_sha256` 对应已独立核对的 `ApprovedScienceBindingV291.scope_digest`。
5. `science_scope.scientific_review_sha256` 必须是实际 `ScientificAdmissionV29` 的摘要；A4 typed source 与 A5 scoped license 由真正审批后的数学对象映射，不能从 LLM 文本推断。
6. **仅当** Core 的确返回 `status='UNSUPPORTED'`、`fallback='ELIGIBLE_NOT_EXECUTED'` 且 reason_code 在当前 v2.9.1 有条件放行的集合（`THEOREM_BACKEND_UNAVAILABLE` / `NO_REGISTERED_THEOREM` / `OFF_SUPPORT_ALTERNATE_THEOREM`）时，才允许候选推理。
7. 由于 v2.9.1 业务接口基于旧 v0.9 多查询审阅，而 v0.11 使用 v0.10 的独立 SHA，宿主还需要**明确的版本 Crosswalk**。目前独立 Gateway 没有提供无需人工审批的自动转换，也没有生产 Core port 的现成实现。

**重要**：v0.11 自己无法证明 Python 调用方是真正受信任的、谁执行了审批或业务措辞与精确数学目标是否吻合。它只校验 port 返回的结构化证据和已绑定资料。生产部署必须在宿主可信代码层控制 port 实现、科学审批人身份与参数来源，不能用浏览器上传的 JSON 当作可信数学执行。

## 4. 执行模拟多查询流程

在仓库根目录：

```bash
python -m pip install -e .

python -m cfm_id_llm.candidate_preview_cli \
  --case assets/candidate_mock_fixtures/business_case.json \
  --a0-report assets/candidate_mock_fixtures/a0_quality_report.json \
  --business-review assets/candidate_mock_fixtures/human_business_review_MOCK.json \
  --mock-outcomes assets/candidate_mock_fixtures/mock_core_coverage.json \
  --mock-candidate assets/candidate_mock_fixtures/mock_candidate_q2.json \
  --allow-mock-preview \
  --output /tmp/candidate_v011_preview.json
```

结果预期：`q1` 模拟为已经有现成定理，不执行候选推理；`q2` 模拟为 `NO_REGISTERED_THEOREM`，获得 `UNVERIFIED_CANDIDATE / MOCK_PREVIEW`。上例不是实际 R1a/R1b/R2 的覆盖测试，且没有调用在线 LLM。

确需在此**模拟数学覆盖**前提下用在线模型试验 Prompt 时，可选择 `--provider openai-chat --model <model> --allow-external --allow-mock-preview`，在你本地设置 `CFM_ID_LLM_API_KEY`。**不要在聊天中提供密钥**；模型只看到已审核的目标、来源摘录与科学上下文，不默认发送完整原始附件。使用任何有机密的材料前，仍须单独取得分享许可。

## 5. 候选质量测量与局限

```bash
python -m evaluation.candidate_reasoning_eval \
  --output /tmp/candidate_v011_offline.json \
  --worksheet /tmp/candidate_v011_expert_UNSCORED.json
```

- 19/19 软件探针通过只说明 Mock 分流规则、JSON Schema、审核绑定和拒绝条件有效。
- 8/8 小网络 oracle 使用固定精确有理数计算，对基准中的特定数学事实作 sanity check；它们**不是**对模型自然语言候选公式的证明。
- 专家评审表默认全部 `null`，包括正式 estimand 保真、A4/A5 合法性、公式有效性、观测等价及目标分歧。必须由具备数学背景的研究者独立核对，才可能报告候选质量。
- 本轮未调用真实模型；没有真实模型准确率，也没有证明生成的候选能发现新的识别定理。

## 6. 离 还差什么？

1. **生产适配实测**：结合数学库最新修复版，实现受信任的 in-process Core port，跑一次真正的单查询/多查询 `UNSUPPORTED` → 未认证候选路径，并测试 all blocked statuses。
2. **数学候选专家标注**：先建立独立的 Formal-backed 输入集；让多名研究者核对公式、前提、反例，报告错误率与有价值候选的比例。
3. **真实 API 对照**：使用强模型、当前 Prompt 和必要的改进版进行盲测；不要把 Mock 自检当成模型准确率。
4. **A0 用户澄清收尾**：v0.10 已有业务/科学分流，但完整产品级多轮闭环仍可完善；不需要做复杂 Agent。

**如果现成模型已足够好，就继续使用 Prompt；不必为了借鉴 UniCo 而训练专用模型。**
