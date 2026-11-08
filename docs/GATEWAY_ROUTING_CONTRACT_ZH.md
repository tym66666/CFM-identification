# Gateway 分流合同：最小数学语义与接口

## 为什么要有独立的 

用户正在独立更新 CFM-ID 的数学 Library，未来可能是 v3、v4。本模块现在只负责**业务表达和可靠分流**，不重新实现 Identification 定理，也不依赖 v2.1 的内部 Python 类。

用户能提出各种业务问题，并不意味着系统必须给出一个确定的识别结论。目标是：**已有严格定理时用严格结果；未覆盖时明确说出差距；输入还不够时要求澄清；禁止把猜测冒充证明。**

## 1. 规范化合同（保留）

`BusinessCase → ProblemFormulator → DraftProblemSpec → FormulationReport`

A1 Target；A2 Units/Variables；A3 Network/Exposure/DAG；A4 Population Information + Study Design；A5 假设及来源；A6 support/domain。A0 体现为每个语义主张的 source_id/原文引用。

保留 v0.1 原 schema，避免刚开发分流就破坏此前固定的草稿数据格式。

## 2. 人工审核合同

`HumanReviewV02` 必须显式给出 reviewer、审核说明、对应的 `input_sha256` 和 `draft_sha256`，以及从草稿中被单独接受的 A5 假设名。`confirm_formulation()` 会**重新运行原文引用校验和完整性检查**，而不是只相信 `report.review_status`。

- 草稿只被确认了表达准确，不代表实际随机化协议、完整总体信息算子、均值签名充分性已被科学核实。
- 没有审核记录，任何核心识别调用都不发生。
- 修改任何一个草稿内容或原始业务输入，旧审核失效。
- `admitted_assumptions=[]` 是合法的：表示本记录没有新增接受 A5，实际 Core 会依据自己所需条件继续检查或要求输入。
- 文件式人工审核记录是调用方明确提供的**声明**；Gateway 无法验证 `reviewed_by` 真的是人。正式 UI 应使用可核实的用户确认动作和审计记录，不能让 LLM 自行生成此文件后伪装成审批。

## 3. Core Port 和独立验证

`CoreCapabilitiesV02` 用于表示 adapter id、library version 和路由列表。

`CoreDecisionV02` 中 `status` 与数学识别分开看：

- 数学主张：`POINT`、`PARTIAL`、`NOT_POINT`（证明不是 point，不意味着没有 partial）、`NO_USEFUL_ID`（特定目标下无有用识别，须严格证明）。
- 工作流结果：`NEEDS_INPUT`、`UNSUPPORTED`、`NO_ADAPTER`、`INCOMPATIBLE`、`ERROR`。

有数学主张时必须携带识别路线、相关数学证据和（对于 POINT/PARTIAL）符号识别表达式。生产级 CORE_VERIFIED 还必须通过 `replay_verify()` 的独立证书检查。

Gateway 对返回的 source binding、decision hash、verifier receipt 和路由身份做一致性检查；这只是流程和协议层核验，正式证明仍由生产 Adapter 负责。

## 4. LLM fallback 的门槛（尚未执行）

只有：

1. 业务被充分规范化；
2. 研究者确认了相同的数学问题与证据来源；
3. 真实 Core 明确返回 `UNSUPPORTED`（只是当前 theorem 库无覆盖）；

才标记 `ELIGIBLE_NOT_IMPLEMENTED`，为 v0.3 的候选推理准备。

以下情况一律不能自动进入 LLM 推导代替：A4/A5 缺失、未确认的 target、NO_ADAPTER、INCOMPATIBLE、执行 ERROR、证书验证失败。

即便未来 LLM 给出一个表面合理的公式，也只能是 `LLM_UNVERIFIED`，不能冒用 `CORE_VERIFIED` 或估计结果。

## 5. 为什么 没有真实的 Verified POINT Demo

当前仓库仅含 `MockCorePort`。它返回的是预设情形，并没有运行 R1a/R1b/R2。Mock 返回 POINT 时，系统始终显示 `MOCK_CORE_RESULT / MOCK_ONLY`。它能证明**分流软件逻辑**工作，不能证明新的识别问题可识别。

未来将由 v3+ 的真实 core adapter 实现认证和重放。在此之前，我们不会声称具有已经连接的数学认证能力。
