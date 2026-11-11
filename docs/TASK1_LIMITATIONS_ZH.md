# Task 1（网络拓展 / POINT 拓展）缺项与限制表

对照 Task2-1031 第 2 页「怎么算完成」与第 9 页「统一要求」。本表只覆盖任务 1；日期 2026-11-09。

> **辅助计算 vs 正式识别**：正式识别是证书路径（`identify` + `randomized_network_arm` 后端 / `identification_policy_r1b` 与 `identification_policy_r2` 政策后端），消费可观测总体信息并签发绑定定理合同的 VERIFIED 证书。给定各安排结果再算期望只是**核对工具**（`tests/task1_target_helpers.py`），用于手算对照与组合查找表，**不能据此认定正式识别已完成**，也不保留为包内第二套识别系统。

## 0. 状态口径

- **已完成**：能力已实现并通过独立验证；在支持成立时签发 POINT/VERIFIED，支持不成立时如实返回 UNSUPPORTED（属数学结果，不是未接线）。
- **部分完成**：主路径已实现，但在本文写明的范围内有已声明的边界。
- **未完成**：未实现，或明确不属本任务范围；不能当作已接入能力使用。

## 1. 完成状态（逐项）

| 项 | 状态 | 落点 / 边界 | 验证 |
|---|---|---|---|
| ① 不等概率固定名额 | 已完成 | `randomized_arm_family/assignment_extensions.py` `UnequalProbabilityFixedQuotaDesign`(+wire `…V1`) | `tests/test_task1_assignment_extensions.py`、`test_task1_backend_integration.py` |
| ② 按平衡规则重随机化 | 已完成 | 同上 `RerandomizedBalancedDesign`(+wire)；协变量名单须与研究名单完全一致，多/缺对象明确拒绝 | 同上 |
| ③ 固定权重暴露 W | 已完成 | `exposure_extensions.py` `WeightedExposureSpec`（字段 `weights`/`mode`）：单臂/批量/组合证书 + 效应业务派单 + 扩展 R1A 路由（D1–D8）。政策值路线不使用暴露；R2 签名路线不纳入 W（见 U3） | `test_task1_weighted_grouped_certificate.py`、`test_task1_weighted_grouped_batch.py`、`test_task1_weighted_grouped_business_case.py`、`test_task1_extended_routes.py` |
| ④ 分组暴露 G | 已完成 | 同上 `GroupedExposureSpec`（字段 `groups`）：坐标须为每群一计数的向量；正式流程范围同 W | 同上 |
| 目标 `local_direct_mean` | 已完成 | 组合 DIRECT：同一暴露下 own 1 vs 0。若某设计/名单在该暴露下无 own=0/1 的共同正支持，则如实不识别（数学结果，非未接线） | `test_task1_backend_integration.py`、160 例参考 |
| 目标 `peer_spillover_mean` | 已完成 | 组合 SPILLOVER：同 own 下两种暴露（D1–D8，含 W/G） | `test_task1_weighted_grouped_batch.py`、160 例参考 |
| 目标 `policy_mean` | 已完成 | R1B 固定政策值 + R2 均值签名充分性（含 D7/D8）；另接 R1B 有限政策混合 | `test_task1_policy_r2.py`、`test_task1_extended_routes.py`、160 例参考 |
| 目标 `policy_contrast` | 已完成 | R1B / R2 两政策端点差值（含 D7/D8） | `test_task1_policy_r2_business.py`、160 例参考 |
| 组合查找表 | 已完成 | `docs/task1_combination_lookup.md`（`examples/generate_task1_combination_lookup.py` 生成） | `test_task1_combination_lookup.py` |
| 证明与文档（三篇文献） | 已完成 | `docs/TASK1_POINT_EXTENSION_MATH_ZH.md` | — |
| 示例（手算/新设计/新暴露/完整业务） | 已完成 | `examples/task1_walkthrough.py`、`task1_business_case_reference.py`、`task1_weighted_grouped_business_case.py` | `tests_gateway/test_task1_business_case.py`、`test_task1_weighted_grouped_business_case.py` |
| 完整业务案例（四类目标） | 已完成 | 设计×暴露 160 例：D1–D8×E1–E5×{effect,spillover,policy,contrast}；W/G 业务案例另列 | `examples/network_design_exposure_reference.py`、160 例参考 |
| 缺项与限制表 | 已完成 | 本文 | — |
| 更新代码入口 / 扩展规则 | 已完成 | `docs/DEVELOPMENT_ENTRY_ZH.md`、`docs/EXTENSION_MAINTENANCE_ZH.md` | — |
| literature_support 依据条目 | 已完成 | `literature_support/catalog.json`（三卡）与 `routes/task1_network_point_extension.json` | `tests_gateway/test_evidence_ownership.py` |
| 新设计进 arm-mean 证书后端 | 已完成 | 单臂 `randomized_network_arm.py`、批量 `identification_batch.py`、组合 `identification_composition.py` | `test_task1_backend_integration.py` |
| W/G 批量 / 组合 / 效应派单 | 已完成 | 批量 `_compute_wg`（状态轴=按节点可达状态并集，非矩形，不可达格 pad UNSUPPORTED）；组合（W/G 坐标解析 + 独立 oracle）；派单 `network_effect_dispatch` | `test_task1_weighted_grouped_batch.py`、`test_task1_weighted_grouped_business_case.py` |
| 扩展业务路由（R1A 单臂 / R1B 有限政策混合） | 已完成 | `network_extended_dispatch`：W/G 字符串坐标不再按整数比较；新设计政策载荷补 `nodes` | `test_task1_extended_routes.py` |
| 业务读取与转换（含 W/G 字段） | 已完成 | `cfm_id/network_design_adapter.py`、`cfm_id_llm/network_design_reading.py`、`network_policy_reading.py`、`network_effect_reading.py`、`network_extended_reading.py` | 派单回归 |
| 公共入口证据（正例/拒绝/证书） | 已完成 | `examples/task1_public_entry_evidence.py`：15 个完整正例（POINT+VERIFIED+独立回放）+ 8 个缺项/拒绝例（期望原因码一致）；读取为手造 fixture，`real_llm_runs=0` | `tests_gateway/test_task1_public_entry_evidence.py` |
| 独立验证器（新设计/新暴露） | 部分完成 | D7/D8 分配质量、W/G 暴露统计量、D1–D3 分配质量均为独立复算；**D4–D6 的分配质量仍沿用验证器既有“设计全律镜像”**（暴露统计量仍独立） | `test_task1_verifier_independence.py` |

## 2. 未完成项（明确状态）

| # | 项 | 状态 | 当前边界 | 后续处理 |
|---|---|---|---|---|
| U1 | 新设计 N>8 的解析支持 | 未完成（研究级） | 无解析计数律；`N>8` 报不可处理，不猜测支持（单臂/批量/组合/R1B/R2 同此边界） | 推导条件计数律或引入须独立验证的近似 |
| U2 | 数值 PFN Estimation | 未完成（范围外） | 任务只要求识别（POINT functional），有限样本数值估计不纳入 | 属 Estimation，需独立契约 |
| U3 | R2 均值签名充分性支持 W/G 暴露 | 未完成（不属本任务） | R2 的签名族仅 E1–E5；W/G 无“签名充分性”定义，故 W/G 走 R1B/效应路线 | 若需要，另定 W/G 的签名与充分性语义 |
| U4 | D4–D6 上 W/G 分配质量的独立复算 | 部分完成 | 仅继承设计全律镜像；W/G 统计量独立 | 为 D4–D6 编写独立分配质量算法 |
| U5 | 政策值默认优先 R2 | 未完成（既有选择策略） | 两路线都可用时派单按“首个成功”返回 R1B 为主；R2 可计划并独立执行 | 如需默认优先 R2，改选择策略 |
| U6 | 任意 stochastic policy kernel / 动态或未知图 / 多值或连续处理 / 时序干预 / R3 对新设计新暴露 | 未完成（研究级） | 见 §4 | 研究级，不展开 |

## 3. 可复现方法

- 组合查找表：`python -m examples.generate_task1_combination_lookup` → 重写 `docs/task1_combination_lookup.md`（逐格运行真实 `SupportEngine` 与四类目标核对工具）。
- 业务案例：`python -m examples.task1_business_case_reference --output <dir> --allow-synthetic-reviews`。
- 加权/分组暴露业务案例：`python -m examples.task1_weighted_grouped_business_case --output <dir> --allow-synthetic-reviews`（W 加权 + G 分组 × DIRECT/SPILLOVER，四例全 POINT 且独立回放通过）。
- 已有示例回放：`python -m examples.student_handoff --output <dir> --allow-synthetic-reviews`、`python -m examples.network_design_exposure_reference --output <dir> --allow-synthetic-reviews`（D1–D8 × E1–E5 × 四族，160 例全 PASS）。
- 公共入口证据：`python -m examples.task1_public_entry_evidence [--output <dir>]` → 打印/写出 JSON 报告，含 15 个正例（状态/验证/独立回放/证书摘要）与 8 个缺项/拒绝例（期望与实际原因码）。报告显式记录 `hand_written_fixture=true`、`real_llm_runs=0`、`model_api_calls=0`。
- 测试：`tests/test_task1_*.py` 覆盖穷举对拍、零支持、四类目标手算核对、验证器独立性、W/G 证书、R2 政策值（D7/D8）与证书篡改拒绝；`tests_gateway/test_task1_*` 覆盖 W/G、R2 与扩展路由业务派单。

## 4. 未解决项（研究级，超出本机必做）

- `N>8` 的新设计解析计数律（或精确支持的一般化）。
- 任意 stochastic policy kernel（政策值只支持固定分配与有限认证混合）。
- 动态/未知图、多值或连续处理、时序干预。
- 观测网络（R3）对新设计/新暴露的条件分解。

## 5. 边界状态总结

- **新设计 D7/D8**：已完成接入——arm-mean 证书后端（单臂/批量/组合）、扩展业务路由（R1A 单臂 / R1B 有限政策混合）、政策值 R1B 与 R2；精确枚举 N≤8。
- **加权/分组暴露 W/G**：已完成接入正式流程——单臂证书、批量 `_compute_wg`、组合（坐标解析 + 独立 oracle）、效应业务派单、扩展 R1A 业务路由（D1–D8）。R2 签名路线不纳入 W/G（U3）。
- **政策均值/两政策差值**：已完成 R1B 与 R2 双路线接入新设计（D7/D8）；R2 亦提供两政策端点。
- **明确未完成**：N>8 解析支持（U1）、PFN 估计（U2）、R2 的 W/G 签名（U3）、D4–D6 的 W/G 独立分配质量（U4）、默认优先 R2（U5）、研究级扩展（U6）。
- **四类目标的内部核对工具** `tests/task1_target_helpers.py` 只是手算对照/组合表，不是正式识别系统。

本表与 `docs/TASK1_POINT_EXTENSION_MATH_ZH.md`（数学合同）配套，是受限识别结果的边界声明，不构成对真实业务假设成立或实证效应大小的声明。
