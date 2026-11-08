# 离线审计 冻结分母、文件失败与证据分层

本工具读取已保存的模型输出，不请求模型、不读取认证文件、不修改旧实验。
旧 `score_predictions.py` 和阶段内 `audit_case.py` 保留用于历史追溯；
新验收使用下面的版本化入口。旧文件不会因此自动获得新容错行为。

## 已保存业务实验

当前明确支持 `language-generalization-v0.32` 和
`language-contract-fix-v0.33` 两种冻结配置，
分别重放 `business_materials_whole_clause_evidence` 和 `business_materials`。
其他实验不能直接套用其打分规则，返回 `UNSUPPORTED_AUDIT_PROFILE`。

在项目根目录执行（PowerShell，一行）：

```powershell
python -B -m evaluation.offline_audit --stage "<阶段目录>" --ledger "longcat=<账本目录>\REQUEST_LEDGER.json" --output "<新的报告目录>\audit.json"
```

输出文件必须是新文件，位于冻结阶段和账本目录之外。
多个凭据账本可以重复使用 `--ledger alias=path`；它们仅提供请求元数据。
审计器不会执行阶段目录中的 Python，也不会读取过去的 `gNN_audit.json`
来信任旧 PASS。

### 分母

- `planned_slots`：冻结计划中的全部槽位，包括尚未运行的题。
- `attempted_slots`：账本确认已调用的槽位；文件损坏或丢失不能减少该数。
- `authenticated_attempts`：账本中的实际尝试记录数，重复尝试也计入。
- 统计覆盖显式提供的账本；同一阶段计划外的请求或错误凭据请求单独列出，
  计入调用数，并令 `publishable_summary=false`，不能悄悄丢弃。
- `acceptance_per_planned_slot`：通过数／计划槽位数，表示计划完成并通过的比例。
- `acceptance_per_attempted_slot`：通过数／确认调用槽位数。
- 账本损坏或指针与账本冲突时，调用分母为 null，并报告未知数量，不臆测为 0。
- 计划损坏时，计划分母为 null，不能产生“0/0 全通过”。

两种比例必须带名称和分母一起展示，不能把“计划完成比例”当作模型准确率。
`publishable_summary` 仅指当前统计证据是否完整，不表示具备论文发表所需的
独立样本、盲测、泛化能力或科学假设批准。
计划中同一道输入有多个槽位时，每次尝试保留，不能取最好一次。
`unique_case_ids` 单独记录输入编号数；结构分组只按明确编号的
网络、分组和设计结构精确比较，不是图同构检查，也不是独立样本量估计。

### 失败分类

| 分类 | 含义 |
|---|---|
| `NOT_RUN` | 可读账本无该槽位请求，且无相冲突的结果指针 |
| `ATTEMPT_STATUS_UNKNOWN` / `LEDGER_ARTIFACT_CONFLICT` | 调用状态证据不足或矛盾 |
| `INCOMPLETE_ATTEMPT` | 账本仍为进行中；不算成功，也不算未运行 |
| `TRANSPORT_FAILURE` | 传输／服务请求没有成功完成 |
| `MODEL_FORMAT_FAILURE` | 请求结果未满足模型输出格式要求 |
| `ARTIFACT_PARSE_FAILURE` / `ARTIFACT_MISSING` | 已保存文件损坏／缺失 |
| `CONTRACT_FAILURE` | 草稿无法通过业务结构契约 |
| `SEMANTIC_FAILURE` | 可解析，但业务目标、条件或证据引用不符合冻结参考 |
| `IDENTIFICATION_EXPECTATION_FAILURE` | 未得到冻结目标所预期的识别状态 |
| `CERTIFICATE_FAILURE` / `RESULT_REPLAY_FAILURE` | 证书或保存结果无法重放 |
| `AUDIT_INPUT_FAILURE` | 冻结代码、公开输入或研究参考发生变化，暂停验收 |

所有计划槽位都会有行记录。一个槽位的保存文件损坏不会阻止其他槽位的审计。
输出不回显损坏文件内容或任意异常文本。

## 旧结构化预测的替代入口

这条路径仅比较结构字段，没有 Core 数学认证含义。它需要预先声明评测哪些题，
不能从模型实际返回了哪些 case_id 反推分母。

先冻结计划和参考摘要：

```powershell
python -B -m evaluation.structured_prediction_audit --output "<新计划路径>" freeze --case-id NBIB-001 --case-id NBIB-007
```

再评测 JSON：

```powershell
python -B -m evaluation.structured_prediction_audit --output "<新报告路径>" score --manifest "<计划路径>" --predictions "<预测文件>" --input-format json
```

JSON 支持数组和 `{"predictions":[...]}`。
JSONL 使用 `--input-format jsonl`，每个非空行是一条带 `case_id` 的预测。
损坏行记录行号，后续合法行继续处理；不会猜测损坏行属于哪一题。
未返回的计划题、重复 case_id、未知 case_id 及无效结构均明确记录。
整份 JSON 损坏时，仍为全部计划题保留失败行。
解析/身份不完整时 `publishable_summary=false`，不能发布一个看似完整的头条分数。

所有报告都是研究侧资料，含参考对比信息，禁止作为被测模型的测试内反馈。
开发调试中使用过的题不能称为盲测。

## 展示边界

业务语义、预期识别状态和证书重放分别记录。
`PASS` 表示符合该开发用例的预期；预期可能是 POINT、NEEDS_INPUT 或 UNSUPPORTED。
`llm_complete_proof_accuracy` 固定为 `NOT_MEASURED`，不能将 Core 的证明记到模型名下。
证书是精确支持检查及规则重放，不是 Lean/Coq 形式证明；
Core 与 verifier 共享的合同/结果构造仍需要外部手算与枚举测试补充。
符号识别不是数值效果估计，合成研究许可不是现实企业的科学批准。

## 测试

```powershell
python -B -m unittest tests_gateway.test_offline_audit tests_gateway.test_nbib_acceptance tests_gateway.test_acceptance_evidence tests_gateway.test_business_materials -v
```

测试只使用离线 fixture。Windows 若默认 TEMP 的子进程权限受限，
可将当前测试进程的 TEMP/TMP 设为工作区中专用的可写临时目录。
