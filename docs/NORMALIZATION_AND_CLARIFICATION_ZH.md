# CFM-ID-LLM-Gateway 业务规范化与补充信息合同

## 1. 这个模块做什么

面向业务人员：直接输入自然语言。LLM 根据 A1–A6 输出 `DraftProblemSpec`，每个确定字段配原文 `source_id + quote`。代码（而非 LLM 自评）验证 JSON 结构与引用确实来自相应业务材料。随后系统仅向业务人员展示最多两个最关键、可用日常语言回答的问题，同时保留研究人员需要审查的详细条件。

**不做**：证明 POINT / PARTIAL、假设科学认证、由有限数据猜出完整 population A4、计算效果数值、替代 Identification Core。

业务输入可以只是一句话；结构化 JSON 是系统的**内部输出**，不是要求普通用户手填的格式。

## 2. 完整数据路径

`BusinessCase -> Provider(LLM/Mock) -> DraftProblemSpec -> audit_draft -> NormalizationReviewV06`

- `FormulationReport` 同时存草稿、来源指纹和规范化审查问题，保持与 v0.5 兼容。
- `NormalizationReviewV06` 使用 `input_sha256` 和 `draft_sha256` 绑定一次审查，并单独区分 `business_questions` 与 `research_review_notes`。
- A4 仍必须由研究者确认可用**总体观测信息的类型与粒度**。询问业务用户“有谁参与、谁被分组、关系与结果的记录”，是收集上下文，不是认证了总体律。
- 所有经过 LLM 提议或从材料报道的 A5 条件仍需独立科学确认。完整的 Prompt 和现有 theorem family 不在此处强制绑定。
- 对网络用户，单位关系结构、变量 DAG、暴露定义始终分开。

## 3. 人类澄清流程

系统展示有限数量可理解的问题。每题有 `question_id`，绑定当时的输入与草稿。

`ClarificationAnswerV06(question_id, input_sha256, draft_sha256, answer)` 必须与正在显示的题目匹配。

`append_clarification()` 只会向 **BusinessCase.sources** 新增一条 `BUSINESS_NARRATIVE` 类型的未验证记录，不会对旧 `DraftProblemSpec` 做字段 patch。更新 BusinessCase 后，原输入指纹改变：

1. 原来的 FormulationReport 立即过期；
2. 必须**重新运行** LLM 规范化、重新审核证据和阻塞条件；
3. 原来的任何人工批准也不能再对新内容生效；
4. 新回复即使说“我们确实随机”，也**不是** full-vector randomization 的自动数学许可。

另外，模型重新规范化后应该删除已经澄清的旧问题。Mock 示例展示了 `UNRESOLVED -> COMPLETE_RANDOMIZATION`（仅用户报道），但 A4 仍保持 `UNRESOLVED`。

## 4. 可重复运行的离线演示

在源码根目录（未配置 API Key）：

```bash
python -m cfm_id_llm.normalization_cli formulate \
  --case examples/sales_ambiguous.json \
  --provider mock \
  --mock-response examples/sales_ambiguous_mock_response.json

python -m evaluation.demo_clarification --output before_after.json
python -m evaluation.self_probe --output self_examples_report.json
```

`formulate --format json --output review.json --case-output case.json` 会保存可回传的精确审查状态与输入。用户通过 `apply-answer --case case.json --review review.json --answer reply.json --output updated_case.json` 附加回答，之后需要用新的模型回复重新 formulate。

## 5. 真实 LLM API（需用户本地自行测试）

```bash
export CFM_ID_LLM_API_KEY='[在自己的环境中设置，勿发送到聊天中]'
python -m cfm_id_llm.normalization_cli formulate \
  --case examples/sales_ambiguous.json \
  --provider openai-chat --model YOUR_JSON_CAPABLE_MODEL \
  --allow-external --format json --output online_draft_review.json
```

只有显式 `--allow-external` 才会发送业务数据。该命令需要模型供应商支持 Chat-Completions JSON mode。真实模型可能输出不合法 JSON 或错误引用，程序会安全拒绝；这些并非自动修复的数学结果。

**本轮未使用在线模型，也没有真实在线数学/语义准确率。**

## 6. 关于“让模型自己出题自己答”的正确解释

`evaluation/self_authored_normalizations.json` 保存了我（本次 ChatGPT）直接阅读 **8 条日常业务叙述**后手工整理的候选 JSON，`evaluation/self_probe.py` 使其经过同一 Schema 和原文逐字引用检查。

它能验证“这些示例可以通过我们自己程序的字段和引用规则”，不能证明 LLM 的泛化能力、因果正确性，或实时在线 API 成绩。评判者与输出撰写者重叠，而且我在编写这些答案之前已看到开发者参考提示，因此 **不属于盲测或独立准确率评测**；即使所有目标类别与提示一致，也不能据此报告真实模型正确率。

## 7. 面向未来 v3 的接口边界

保持 `FormulationReport/DraftProblemSpec` 为 Gateway 拥有的草稿合同。**不创建或冒充真实** `TaskSpec / IdentificationSpec / IdentificationResult`，也不定义任何“已获认证”的 A4/A5。

待你提供最新版数学 Library，再构造小而严格的 `CoreAdapterV3`，映射经人工审核的任务到真正的数学后端。`v0.6` 本身绝不绕过已经存在的 v0.2 人工审核、v0.3 VERIFIED/UNVERIFIED 分流规则。
