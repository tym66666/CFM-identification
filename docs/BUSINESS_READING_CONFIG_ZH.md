# 唯一推荐读取配置

学生和新应用统一从 `cfm_id.project.start(case)` 开始。它加载包内唯一配置 [`cfm_id/configuration/reading.json`](../cfm_id/configuration/reading.json)：

```json
{
  "version": "business-reading-config-1",
  "reading_format": "compact",
  "fact_format": "short_refs",
  "assignment_semantics": "joint-assignment-law-1",
  "target_summary_contract": "target-summary-3",
  "a0_reference_contract": "compact-source-paragraphs-1",
  "a0_response_contract": "target-first-skill-1",
  "network_fact_contract": "network-shared-definitions-1"
}
```

2026-11-02 按项目负责人的选择，将目标优先的新候选作为主维护方案。A0 使用已固定的简短 Skill 与 Schema；本轮没有继续调整它们。政策均值、两政策差值、局部效应和观察性政策的事实读取接收一份带原文位置的已审核意图，必须经过来源与跨阶段一致性审核才能进入原有数学入口。详见[意图交接](REVIEWED_INTENT_HANDOFF_ZH.md)。这是开发和使用入口的收拢，不是准确率已稳定的声明。

2026-11-03，固定政策均值和两政策差值改用 `network-shared-definitions-1`：共同定义集中审核，网络证据独立列出，每条概率、政策、信息与科学条件仍须提供自己的证据。均值顺序能力保留。局部效应、R3 和 DAG 继续使用各自专门协议；DAG暂不使用本次网络意图交接。不会把未支持目标改成固定政策，也不会失败后静默换回旧A0。当前真实验收配置和边界见[共同定义验收](SHARED_DEFINITION_ACCEPTANCE_ZH.md)。

## 三种配置的地位

R3新增能力的本地验收使用`observational_fact_profile="mean-signature"`，详见[R3合同](R3_POLICY_ENTRY_CONTRACT_ZH.md)。它允许同一家族读取显式暴露定义和条件均值充分性；本轮不改变上面的统一推荐配置，也不改写历史记录。只有先通过独立审核及原生验证才能使用签名路线；尚未据此声称真实LLM首读稳定。

需要逐表显式引用对象顺序和编码时，可选 `mean-signature-definitions`；它与旧签名配置使用同一数学入口，新增内容只涉及定义依赖的读取与审核。仍是显式验收选项，不根据名称或日期自动替换推荐配置；小批真实复测未证明首读稳定。

| 地位 | 位置 | 使用规则 |
|---|---|---|
| 唯一推荐起点 | `cfm_id/configuration/reading.json` | 新会话由 `project.start` 加载；学生不自行拼装 |
| 历史兼容默认 | `ReadingConfig()`、[compatibility_default.json](../examples/legacy/configs/compatibility_default.json) | 旧 API、旧 CLI 默认不改，继续重建旧请求；不是学生推荐起点 |
| 实验或历史配置 | 旧协议说明（历史记录不随发布）、`examples/legacy/configs/previous_research.json` | 只用于明确的比较或复现；必须连同当时请求、回答和审核使用。旧A0停止新增优化，必要兼容和正确性修复仍维护 |

`network-policy-definition-refs-1`、`network-policy-record-definitions-1`、`organized-reading-1` 等保留为实验配置，本次不提升默认。第二项补齐科学条件覆盖名单的显式定义依赖，见[共同读取登记](FACT_READING_REGISTRY_ZH.md#可选的政策定义引用样板)；少量事实读取对照通过不代表完整 A0 链路稳定。旧协议的内部标识参与绑定，不能因清理文件名而改写，也不能给旧会话自动套新配置。

## 实际调用

本地接口对照另有 `single-action-target-1`（A0 主政策单一归属）与 `network-policy-scopes-1`（信息范围和状态引用配对）。两者仍为显式实验配置，见[读取登记](FACT_READING_REGISTRY_ZH.md#主政策记录范围和状态引用的接口对照)。不得把历史回答删除重复字段后当成新协议模型成绩；需用新请求重新读取。这些历史读取实验未替换推荐配置；本次均值顺序 Schema 扩展见上文。

候选 `single-action-target-2` 仅增加精确重复别名兼容，并向事实阶段交接单份已审核意图。其与材料清单的冻结验收尚未通过完整真实链路，因此不替换推荐起点。阶段职责、兼容界限及实际失败见[政策交接](POLICY_STAGE_OWNERSHIP_ZH.md)与[冻结验收](CONTRACT_CLOSURE_ACCEPTANCE_ZH.md)。

`guided-policy-reading-1` 复用该单一主政策合同，集中读取步骤，并将已审核政策交接扩展到 R3。2026-11-01 的四份新材料对照没有显示首读增益，**不作为推荐配置**。调用结束后仅补齐候选 Schema 与背景解析规则的一处差异，未重新计分。见[冻结对照、接口修复与停止决定](GUIDED_POLICY_READING_ACCEPTANCE_ZH.md)。

`model-policy-output-1` 进一步把固定政策主字段与旧兼容别名分开：模型只填主字段，适配器生成旧接口视图；旧协议原样保留。本轮少量真实验收仍有读取错误，因此也不自动替换推荐配置。具体职责、兼容规则和验收见[政策字段分离](POLICY_STAGE_OWNERSHIP_ZH.md#模型输出和兼容视图分开)。普通用户仍从 `project.start` 开始，无需按版本号挑配置。

后续显式候选 `network-policy-scopes-2` 将“未声明假设的定义依赖”统一到 Schema、解析、来源审核和诊断。固定政策均值及两政策差值共同使用；旧协议和推荐配置不变。[共同规则与验收](ASSUMPTION_DEPENDENCY_CONTRACT_ZH.md)记录了改善及限制，本次事实阶段复测不替代完整 A0 验收。

```python
from cfm_id import project
from cfm_id.business_intake import prepare_request
session = project.start(case)
request = prepare_request(session)
```

```powershell
python -m cfm_id.project config
python -m cfm_id.project start --input case.json --output outputs/new_case
```

`start` 仅生成会话和 A0 请求，不联网、不代填回答、不自动审核。其余步骤继续复用 [会话](BUSINESS_INTAKE_ZH.md) 和 [分派](BUSINESS_DISPATCH_ZH.md) 接口。三个离线示例也调用同一个 `project.start`。

`ReadingConfig` 验证配置组合，拒绝未知字段、非法值和不兼容格式。配置不包含 API Key、数学路线、预期结论或科学批准。修改配置只能创建新会话；不能搬用旧批准。

## 如何维护

可单独选择 `material_handoff="information-inventory-1"`，为固定政策均值／两政策差值接入来源绑定的材料清单。它是交接与审核选项，不是新的 Prompt 版本或数学路线。需要 compact A0、short_refs 事实格式及独立 A0 字段审核；随后必须完成新的材料审核工作表。其他读取族当前不支持此选项。默认不启用，推荐配置未改动，历史会话序列化不增加该空字段。已有会话可用 `configure_material_handoff` 显式启用，会保留原答并使旧审核失效；不能借此恢复因历史 Prompt 已变化而失效的检查点。详见 [来源审核](FACT_SOURCE_REVIEW_ZH.md)。

只有一处推荐 JSON，读取函数负责加载与验证，文档不维护第二个配置对象。需要变更起点时，同步验收首次请求、事实读取配对、来源审核、重读、整题执行和源码外安装；原协议继续保留旧请求兼容。真实读取效果另做冻结评测。

五类事实配套均由 [共同登记](FACT_READING_REGISTRY_ZH.md) 管理；能力与适用域由 `cfm_id.capability_registry` 管理。二者职责不同，普通用户无需选择读取家族或数学方法。
