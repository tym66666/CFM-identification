# 读取备注的独立审核

LLM 读取事实时可能同时写下“还需判断能否识别”“某个总体均值未提供”等备注。备注是待核对的模型判断；它可能指向真实缺项，也可能只是把后续数学工作重复了一遍。不能将所有备注直接当成用户缺少事实，也不能为提高通过率静默删除。

`reading_note_review` 位于**事实读取之后、方法计划和科学审核之前**。目前连接共同网络固定政策读取，包括 R1b/R2 和有限数值有界模型。它不是新识别路线，也不要求业务用户预先选择方法；未连接的 DAG 读取不会忽略传入的审核记录，而是明确停止。

## 一条备注如何处理

| 独立审核结论 | 后续处理 |
|---|---|
| `PENDING` | 继续待审，不能执行 |
| `MATERIAL_GAP` | 原材料确实缺少内容，保留缺项并提出补充问题 |
| `READING_ERROR` | 模型误读或漏读，要求重新读取；不替模型填写字段 |
| `NONBLOCKING_COMMENT` | 经原文复核属于解释性备注，允许继续其他检查 |
| `DEFER_TO_MATHEMATICS` | 属于支持性、公式或界限等数学判断，交给原验证链 |

例如“目标能否唯一确定需进一步识别分析”不要求用户先提供识别答案；“是否还有其他总体信息尚未决定”是真实待确认条件。对零概率目标签名，不能为了消除备注而伪造条件均值；是否允许有界模型及其 sharp 结论仍由独立数学合同决定。

未审核备注返回 `REVIEW_REQUIRED`，提供 `note_review_worksheet`；此时没有 `plan_worksheet`，调用方必须区分两者。已确认的读取错误返回 `READING_RECHECK_REQUIRED`，真实缺项返回 `NEEDS_INPUT`。混合备注中有任何未解决项，就不能仅凭另一条备注放行。

结构化缺项与附加限制始终独立检查。即使备注被放行，缺少目标、A4 数值、界限或完整模型声明仍会停止；额外单调性等未接入限制也不会被删除。停止时保留原始候选、原备注、已提交的审核回执以及结构化诊断。

## 审核记录与绑定

独立提交 `ReadingNoteReview`，包含当前工作表的 `binding_sha256`、审核权限、审核人、理由和每条备注的决策。非待定决策必须引用当前完整来源编号。编号由工作表提供，不使用模型自行编造的编号。

绑定涵盖原材料、当前子问题、读取请求、意图审核、完整候选和全部备注；修改或重排备注、修改任何候选字段、更换来源或子问题，都使旧备注审核失效。备注决策又进入后续计划及原生审核的绑定；修改决策后不能沿用旧批准。

回执明确记录 `candidate_modified=false`、`scientific_approval=false`。原始候选不修改，备注不截断；方法计划、读取语义和 A4/A5 科学条件仍需独立审核，再求解并重放原生证书。备注记录不能直接产生 POINT、PARTIAL 或估计许可。

内容哈希保证记录与材料一致，**不证明审核理由正确，也不认证审核人身份**。原文是否支持某结论依然需要独立实质审查。合成例子的 `SYNTHETIC_TEST` 不能冒充真实研究审批。

## 调用方式

先按共同业务分派流程运行 `method-plan`。若输出有 `note_review_worksheet` 且没有 `plan_worksheet`，填写单独的备注审核文件，再调用：

```powershell
python -m cfm_id.business_dispatch_cli method-plan --intake intake.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate actual_reading.json --note-review note_review.json --output reviewed_method_plan.json
```

若得到方法计划，分别完成计划审核和各方法的读取／科学审核。`execute` 使用相同的 `--note-review note_review.json`，加上现有计划与原生审核参数。整题 `business_case` 提交则在对应子问题中放入 `note_review`；不混入其他问题。

工作表是待填模板，不是批准。生产模块没有按关键词自动放行、默认接受全部备注或调用模型为自己批准的逻辑。测试中的批准助手仅用于显式合成夹具。

## 原文引用容量

A0 一项“可用总体信息”有时需要引用均值表、界限和模型范围中的多个句子。精简读取 `refs` 与内部 `SemanticClaim.evidence` 共用 `MAX_CLAIM_EVIDENCE=64`，不再因超过八条而丢掉整份有效引用。64 是有限的资源容量设置，不是数学假设，也不承诺任意长度材料均可处理。

转换逐条保留来源，不截断引用、不拼造事实。原文目录总容量、字段文字长度、重复／未知／过期来源检查以及语义与科学审核均继续保留。超过上限仍明确拒绝；不能靠删除证据通过检查。

容量进入实际请求 Schema，因此请求摘要随之变化。旧失败记录保留；新请求必须新读，不能给旧回答重新贴上“当前模型调用”的标签。对历史回复的离线研究性分析应单列，与新模型准确率区分。

定向回归：`tests_gateway/test_reading_note_review.py`、`tests_gateway/test_business_intake_compact.py`；共同验收清单 S16 绑定备注审核要求。
