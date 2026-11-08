# 业务语言输入与分层解释合同

## 1. 目的

让业务员和投资人可以像平常一样提出问题；数学家仍然能够看到 A1–A6、定理与证据。**展示层不增加任何数学能力**。以下所有状态来自 v0.1–v0.3 的现有结构化输出。

- 业务输入：`BusinessCase`（也可以在 CLI 中直接用 `--question` 生成）
- 业务规范化：保留 `DraftProblemSpec` 原有 A1–A6 Schema；新 Prompt `cfm-id-business-formulator-v0.5.0` 只调整理解和问题提问方式。
- 核心识别：仍然只能通过 `CoreIdentificationPort`；当前仓库 **没有真实 R1a/R1b/R2 适配器**。
- LLM fallback：仅在 v0.3 安全条件许可时运行；其候选无数学证书。
- 对外解释：`explain_business(case, GatewayRunV03, audience)` 构造 `BusinessExplanationV05`，只转换原有状态，不生成估计数字、利润或 ROI。

## 2. 三种展示视角

| 视角 | 页面首先回答 | 隐藏/附加内容 |
| --- | --- | --- |
| business | 用户究竟在问什么、现在能否回答、还需要确认什么 | 默认不暴露长公式和 A4 等技术术语 |
| investor | 以上内容，以及**识别并不是收益估计，ROI 还不能计算** | 不从四臂目标推断推广收益 |
| scholar | 明确目标种类、assignment、A4 粒度、A5 候选、路线状态和公式来源 | 允许展开数学细节，但不把它当作证书 |

默认只问不超过两个重要澄清问题。如果用户已有足够清楚的问题，等待研究人员确认，而不是强制继续问问题。**业务问题直观不等于数学前提放松。**

## 3. 安全展示状态

- `NEED_INFORMATION`：描述不清，先问人；不能把缺少的数据或假设自动猜成成立。
- `WAIT_REVIEW`：草稿已整理，但还没通过研究者审核。
- `NO_CORE`：本仓库没接数学识别库。并不等于不可识别。
- `MOCK_PREVIEW`：来自 MockCore，**不能标成正式 VERIFIED**，即使模拟返回 POINT。
- `VERIFIED_BY_CORE`：仅当上游已成功由正式 Core Adapter 的独立 replay 验证；v0.5 只显示收到的已核验结果，不提供新证明。
- `CORE_NEEDS_INFORMATION`：识别库需要附加信息/假设；不允许偷加。
- `LIBRARY_GAP`：代码库不覆盖的问题；不能当成数学上不可识别。
- `UNVERIFIED_SUGGESTION`：LLM 提议，可阅读但不能交给 Estimation/Policy。
- `TECHNICAL_BLOCK`、`CANDIDATE_REJECTED`：发现校验错误、输出不可信或 provider 故障，直接拦截。

此外 `candidate_verification_level` 始终明确标记所有真实或 Mock 的 LLM 候选为 `LLM_UNVERIFIED`。在同一次 Mock 演示中，Core 的 `MOCK_ONLY` 与 LLM 的 `LLM_UNVERIFIED` 是**两种不同属性**，不能互相覆盖。

## 4. 保护措施

1. 对外输出模型 `BusinessExplanationV05` 明确禁止设置 `estimation_handoff_allowed=true` 与 `has_numerical_estimate=true`。
2. 在展示前重新核对业务输入、Formulation、Routing 和 Candidate 的内容指纹；不允许把其他业务的候选拼过来。
3. HTML 使用静态模板、无 JavaScript，所有从业务/模型来的文本通过 `html.escape` 转义；不执行模型生成的 HTML/Python。
4. 真实云端模型必须显式 `--allow-external` 并配置环境变量密钥，默认 Mock 离线运行。
5. 24 个演示题全为合成业务语言；开发参考标签与发给 LLM 的材料分开储存。
6. 已被研究人员确认不代表现实世界因果假设被证明，统计估计/商业 ROI 仍属下游。

## 5. 保留的限制

- v0.5 **没有** LLM 真实在线模型准确率，也没有新的 network Identification theorem。
- 业务解释是**模板驱动、确定性的状态转换**，不是让另一个 LLM 自动润色数学结论。
- 24 个问题覆盖语言理解场景，**不代表** 24 个网络业务都已正式可识别。
- 旧 v0.4 的 30 个正式化 fixture 中，此次修正了 F17 一项的过度阻塞，现有匹配为 28/30；F18、F23 仍需显式澄清，不能为追求分数而放松定义。
- 如果用户没有提供足够的网络、分配和 A4/A5 资料，系统可以让业务人员补充事实，但不能据此自行宣称定理适用。
- 对未被当前题库覆盖的行业，本次只提供通用自然语言 Schema 和提示，不承诺任何实际覆盖率。
