# CFM-ID LLM Gateway 候选识别推理合同

## 一句话

**旧版：** 先用 LLM 理解业务，再检查数学库能否处理。

**新增：** 当已确认的业务问题超出真正的严格数学库时，让 LLM 提出*待核查的公式、条件或反例*。这可以帮助用户获得研究思路，但**不能因此声称因果目标已经被严格识别**。

## 运行资格

严格生产流程必须依次满足：

1. `FormulationReport` 从真实业务原文提取，并通过引用与语义完整性审计。
2. 研究者显式提供 `HumanReviewV02`，且其来源和草稿指纹与当前问题相同。
3. 当前可信生产 Core 返回 `UNSUPPORTED`，分流是 `CORE_UNSUPPORTED / ELIGIBLE_NOT_IMPLEMENTED`。注意 UNSUPPORTED 不等于 NON-IDENTIFIED。
4. 不能带有数学证书、冲突信息、`NEEDS_INPUT`、`NO_ADAPTER`、`INCOMPATIBLE`、程序错误或验证失败。

本仓库**没有真正的 Production Core Adapter**，所以本地演示提供 `--allow-mock-preview` 明确允许 `MockCorePort(status=UNSUPPORTED)` 的测试流。演示的 `execution_mode=MOCK_PREVIEW`，并不证明真实数学库确实不支持这个问题。

`CandidateReasonerV03.run()` 会再次校验源数据、审阅绑定和分流信息。不能直接传一句未确认的自然语言就生成看似可靠的识别结果。

## 候选答案应包括什么？

`CandidateDraftV03`：

- **原始因果目标**：`target_kind + target_description` 必须精确对应经审阅的 A1，不得更换。
- **候选识别类型**：POINT、PARTIAL、NOT_POINT 或 UNDETERMINED。所有类型都只是 *LLM 声称*。
- **使用的 A4**：精确复制已审阅的总体信息算子，或把新增算子标为 `ADDITIONAL_OPERATOR`。
- **使用的 A5**：`admitted_assumptions_used` 仅能引用 `HumanReviewV02.admitted_assumptions` 中的名称。
- **额外条件**：A4/A5/A6 等尚未确认的要求必须独立列出。只有在条件确实得到补充后才可能适用，故标 `IF_ADDITIONAL_REQUIREMENTS`。
- **识别候选**：POINT/PARTIAL 给出公式或集合；NOT_POINT 提出两个观测等价但目标不同的 causal worlds；UNDETERMINED 不能硬凑公式。
- **理由与待核查项**：陈述关键步骤与下一轮可核查的证明或反例问题。

`CandidateReportV03` 固定 `verification_level=LLM_UNVERIFIED`、`estimation_handoff_allowed=false` 和 `mathematical_certificate=null`。模型如试图输出证书、验证结论或 Estimation 权限，其额外字段会被拒绝。

## 能检查什么，不能检查什么？

本地程序可以拒绝：

- 将设计标准化 arm mean 偷换成 policy value；
- 将未确认的 consistency 或 mean-signature sufficiency 伪装为已接受；
- 将 A4 从已审阅信息改成更强的总体算子；
- 自称 NOT_POINT，却不提出两个观测等价世界的具体思路；
- 自称公式已认证、试图制造伪造证书；
- 输入变化后复用旧审阅、证书失败后进入 LLM 回退。

但此类审计**无法自动证明符号公式是否正确**；LLM 还可能在自然语言推导中隐含未经声明的假设、给出假的观测等价反例或引用虚构文献。因此“格式校验通过”只是一个可审查候选，不能升级为 VERIFIED。以后可引入独立的 theorem backend、有限小图枚举或专家审查，将高价值候选正式沉淀回数学库。

## 对实际业务的直观例子

业务定义 `S_i=1{Σ_j w_ij T_j / Σ_j w_ij>0.6}`，其中权重在随机分配之前固定。已知独立 Bernoulli 随机化和一个明确声明的总体联合律，想求 `μ_i^q(1,1)`。

这不是当前 E1/E2/E3 的现成 exposure calculator，但 LLM 可能想到：在 full-vector randomization、consistency、目标 arm 有正支持时，尝试使用 `E[Yobs_i | T_i=1, S_i=1, W]`。这属于**可讨论的条件性候选**，不是 R1a 正式认证，也不是任何实际销售增益估计。

配套 Demo **故意**让 Mock Core 回复 UNSUPPORTED，以展示候选分流，不代表最新实际数学库不能处理加权 exposure。

## 后续接入 v3+

数学库不断进化不影响本模块的主要源码。未来适配器必须确保：

- 真实 `identify()` 按指定 `ProblemSpec` 返回状态，A4/A5/A6 条件由独立数学检查确认；
- `UNSUPPORTED` 确实表示库缺少适配定理，而非缺少输入或运行失败；
- `replay_verify()` 由真实独立验证器执行，不能只回复 True；
- `CandidateReportV03` 绝不通过 Estimation Handoff。

外部源文档和审阅草稿应按不可信数据处理。调用云端 LLM 时会上传经审阅草稿及其中的证据摘录（不会默认上传全部原始附件）；包含敏感信息时应先得到适当授权并脱敏。当前提供兼容 Chat Completions 的 HTTP Provider，但没有在本轮进行真实线上 API 调用。
