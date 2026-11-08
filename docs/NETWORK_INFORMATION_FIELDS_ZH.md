# 样本与总体信息的字段合同

共同业务入口仍由原问题开始；用户不选择识别路线。开发端可显式配置 `network-source-selections-information-1`，在既有字段职责合同上试用更明确的样本表示及三项跨字段规则。默认配置、旧字段、协议版本和旧请求保持不变。

## 样本资料怎样保留

`information` 中记录 `operator=FINITE_SAMPLE`、`availability=FINITE_SAMPLE`、原文明示的 `outcome_nodes` 及完整来源引用；`assignment_cells`、`signature_cells` 均为空列表。这两个格子字段专门表示总体信息。原始样本数值、样本条件、数量及其他细节仍保留在材料中，通过 `source_ids` 可回查，并没有删除原材料或把样本当作无资料。

这一表示供 Identification 读取层区分信息性质，不承担样本估计。有限样本不能因为较精确、满足字段规则或看起来合理而改称总体均值。总体／样本性质未明确时继续保留未知；模型不替用户确认。

## 三项规则的共同来源

`cfm_id_llm/information_field_rules.py` 保存三个既有规则，并生成新配置的 JSON Schema 条件与复查诊断：

| 非空内容 | 必须对应的字段 |
|---|---|
| `assignment_cells` | `operator=ASSIGNMENT_NODE_MEANS` |
| `signature_cells` | `operator=NODE_SIGNATURE_MEANS` |
| `signature_cells` 中非 null 的 `value` | `availability=EXACT_POPULATION_VALUE` |

旧解析器改为调用相同规则，接受／拒绝语义及错误代码保持不变。新 Schema 将三项组合关系明确发给模型；未宣称 Schema 已覆盖所有来源、坐标或数学检查。符号总体均值仍可保留 null 数值，完整联合总体分布不会被降格为均值表。

新配置同时把“同源均值表保留所有格子”的说明限定为**总体签名均值表**，补充样本通过原文引用保留的规则。没有新增科学假设、默认数值或估计器。

## 出错后的显式复查

新配置的 `feedback_worksheet.format_issues` 可列出真实冲突的字段路径、固定错误码与 `field_rule`。这些字段来自代码中的三项规则，不包含候选数值或审核人的标准答案。

审核人选择确实存在的路径及 `WIRE_FORMAT_ERROR` 后，原有重读机制才将相应诊断发给模型；仅提交普通语义反馈时不发送这些诊断。旧配置仍只使用原类型诊断，因此历史复查请求不改变。

模型重新输出完整候选，原回答保留。全部变化须独立按原文审核，随后才可能进入科学审核。若模型为了格式正确而将样本改成精确总体，或删除真实额外条件，应否决变化；格式通过不授予识别许可。模型 API 的调用与预算由外部运行程序管理，本模块不自动调用或重试。

## 使用与验收

```python
from cfm_id import business_intake
from cfm_id_llm.network_information_contract import CONTRACT

session = business_intake.start(original_case, network_fact_contract=CONTRACT)
```

已有会话也可用 `configure_network_fact_contract` 显式切换；切换保留原材料及 A0 候选，使旧审核及请求绑定失效，需要重新审核。不要手动改旧返回的来源上下文来套新请求。

定向测试位于 `tests_gateway/test_network_information_contract.py`，固定框架清单 S22 检查样本拒绝、原文保留、诊断作用域、变化审核以及 R1b/R2/有限 PARTIAL 的原数学重放。测试夹具与真实模型返回分别统计；本配置不因少量复测通过就成为默认。

2026-10-27 实际验证：完整框架 624 个测试、125 个子测试通过；252 种组合的新旧解析行为一致，15 份历史请求保持不变。DeepSeek 4.1 与 LongCat 各复测三组既有材料：样本题正确进入 NEEDS_INPUT，精确总体题经独立审核及重放得到 POINT 1/2，真实跨对象约束被保留并使当前适配器停止。共六次新事实请求，复用原实际 A0；不是六道新业务或一般准确率。完整报告保存在源码包外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。

随后冻结相同代码与 Prompt，用三份新合成材料从真实 A0 开始测试：总体符号与样本混合、信息性质未知、单对象符号均值。两模型共六条目标链，经本地独立 SYNTHETIC_TEST 审核后五条达到预期结果，三条 POINT 完成独立重放，两条真实缺项停止；DeepSeek 的单对象 aggregation 漏填在一次复查后仍未恢复。LongCat 另有一条负例边表引用覆盖不完整，因此结果及全部事实引用同时正确为四条，不能报告六题全通过。实际执行的五次事实读取均正确区分信息职责，但不代表一般准确率。此批次未修改代码或再次运行完整框架，保留该配置为显式试用。请求和原始结果留在源码包外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。
