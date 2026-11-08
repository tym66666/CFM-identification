# 业务材料 → 真实 Core → 未验证候选：

## 当前覆盖范围

当前入口为 evaluation.business_candidate_constraints.evaluate_with_candidates；它复用 v0.35 的接线与审核规则。
它调用原有 business_materials.evaluate_draft，并将其完整返回值保存在 identification 中。
原 v0246 默认入口不变；显式 enable_candidates=True 才启用新分支。

这是 SYNTHETIC_BENCHMARK_ONLY 的实验接线，目前只接固定政策目标的真实定理覆盖缺口。
它不是任意新业务类型的生产审批服务，尚未适配的目标、NO_ADAPTER、NEEDS_INPUT、Core 错误与验证失败均不能靠候选绕过。

## 必需输入与审核

除原有业务 bundle、模型 reading、独立 synthetic science packet 外，调用方必须提供 ReviewedMaterialsContextV035：
- 已审核的 Gateway 业务草稿和逐查询审核；
- RealCoreCoveragePortV012 及其独立数学目标、科学许可、证据和交叉映射；
- 明确确认上述上下文对应当前业务文件、模型草稿和科学包的 MaterialsCandidateApprovalV035。

审核对象绑定当前内容摘要，逐次重查。它不是数字签名，也不证明现实中的 A4/A5 成立。
运行时不会从 LLM 输出创建审批。examples/materials_candidate_fixture.py 中的审批只是明确标记的合成测试科学家断言，不能复制成生产自动审批。

当前接线重新编译已审核的固定政策，比较其完整 typed inquiry 与真实 Core port 的查询。
既有 port 再次执行真实 Core，候选模块随后执行 v0.11 身份、假设与输出边界检查。

## 请求合同修正

原 v0.11 Prompt 缺少当前材料的完整数学坐标。新增的候选上下文只包含合成网络、处理分配律、政策向量、单位权重和已声明的数学前提；不发送参考答案、评分标签、原始科学审批包、密钥或证明答案。

旧 port 的 A4 引用中 level 可能为空。v0.35 要求另外显式审核 reviewed_a4_levels，只允许 NODE_FULL_LAW / FULL_JOINT_LAW 的同名精确类型映射。
未审核的映射被拦截；节点总体律不能升级成完整联合总体律。没有从有限样本数据推导总体 A4。

## 结果与展示

- identification：原 Core 结果，候选不得覆盖。
- candidate_results：LLM_UNVERIFIED 候选，可为候选 POINT / PARTIAL / NOT_POINT 或无法确定。
- core_verified_query_count：只统计原 Core 的 POINT 且证书已重放的查询。
- unverified_candidate_count：只表示候选通过格式、目标及许可边界检查，不是数学正确率。
- mathematical_candidate_verification 固定为 NOT_PERFORMED。
- estimation_handoff_allowed、estimation_called、policy_called 固定为 false。

嵌套 identification.candidate_generator_called 属于原识别阶段，保持原值；整个新流程是否调用候选，以外层 candidate_generator_called / candidate_model_calls 为准。
调用失败也保留原 Core 输出，每个符合条件的查询只尝试一次，不重试、不切换模型。

## 本轮实验口径

assets/candidate_material_fixtures/materials_cases.json 保存了以前真实 LongCat 业务阅读的冻结输出及来源摘要。
4 个回归输入分别覆盖已认证、目标不明确、独立抽签条件缺失和真实政策覆盖缺口。

本轮在线候选试验仅有 1 道独立业务题 G32-08。初始计划比较 LongCat 与 DeepSeek 各 1 次；随后各自冻结 v0.35.1、v0.35.2、v0.35.3，额外各调用 LongCat 1 次，保留前次问题与失败。共 5 次 HTTP 请求。
它延续先前真实业务阅读结果，不是本轮重新执行了一次完整的业务规范化，也不是新盲测。
合成科学许可仍需单独声明；候选质量与接口、格式检查分别报告。

## 离线复现

在源码根目录运行：
    python -B -m unittest tests_gateway.test_business_candidate_base tests_gateway.test_business_candidate_prompt tests_gateway.test_business_candidate_identifiers tests_gateway.test_business_candidate_constraints tests_gateway.test_candidate_queries tests_gateway.test_candidate_eval tests_gateway.test_trusted_core tests_gateway.test_business_materials -v

在线实验脚本及冻结请求保存在 LOCAL_EVIDENCE_NOT_DISTRIBUTED。
已执行的 slot 禁止重跑。后续在线试验应建立新冻结计划，并沿用现有请求账本计数。

## 后续修正

v0.35.1 仅补充 System Prompt：精确目标与已审核条件无需重复确认，consistency 不能替代支持条件，NODE_FULL_LAW 不提供零概率条件量。

v0.35.2 另外将请求中 REVIEWED_OPERATOR 的 operator/level 限定为已审核的精确组合；解释应写在推导字段。验证器没有放宽，也不在模型输出后修剪字符串冒充成功。

v0.35.3 将 Python 验证器已执行的跨字段规则显式写入请求 Schema，包括 NOT_POINT/UNDETERMINED 的公式为空、反例与判断匹配、追加条件与适用范围匹配。格式通过仍不能证明反例正确。

业务题、数学目标、网络、随机化设计、A4/A5 均保持不变。这些版本基于已观察输出修正，不属于独立盲测或模型能力排名。

## 文本展示

    python -B -m evaluation.candidate_presentation --input <candidate_result.json> --output <新文件.txt>

文本始终分开显示原 Core 状态与未验证的候选判断。候选中的 NOT_POINT 或 POINT 不是 Core 判定；数学质量仍需另外审查。
