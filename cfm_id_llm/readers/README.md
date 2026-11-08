# 专门读取实现

本目录维护已有读取合同的运行实现。输入为公开材料，输出为候选；不生成科学批准、参考答案或识别证明。

| 模块 | 职责 |
|---|---|
| `fixed_policy` | 当前保留的显式固定政策目标读取；其他人使用状态与评价名单分别记录 |
| `fixed_policy_partial` | 保留历史完整名册／未知坐标表达的兼容层 |
| `fixed_policy_base` | 固定政策读取的类型、来源目标投影和只读检查 |
| `mean_order` | 既有均值顺序读取、明确的有损投影及投影记录 |
| `mean_order_count_guidance` | 既有固定人数／另行上限的公开字段说明 |

本轮只是迁移，未改变 Prompt、Schema、缺项规则或协议字符串。旧 `evaluation.business_fixed_intent*`、`evaluation.mean_order_factored_reading`、`evaluation.mean_order_count_guidance` 保留兼容导入；新运行代码使用本目录。

`reference_wire`、`wire_metrics` 留在评测层，不随 reader 导出。现有包根目录的其他读取模块尚未迁入；不要复制一份在这里造成两个实现。普通应用从 `cfm_id.business_intake` 开始，不要求用户选择这里的读取模块。
