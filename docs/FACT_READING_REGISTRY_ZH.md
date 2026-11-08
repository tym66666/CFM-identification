# 共同事实读取登记与扩展

所有当前 **short_refs** 事实读取家族已接入 `cfm_id_llm.fact_reading_contracts.registrations()`。登记配对既有组件，不解释业务、不审批条件、不增加数学能力。学生从 `cfm_id.project` 开始，配置见[唯一推荐配置](BUSINESS_READING_CONFIG_ZH.md)。

| 读取家族 | 事实实现与特殊边界 | 业务适配器 |
|---|---|---|
| 固定政策均值 | `network_fact_protocols` 拥有既有配置表；单个完整政策、评价范围与信息角色 | `network_policy_dispatch` / 有限有界适配 |
| 两政策差值 | `network_contrast_reading` 复用政策组件；保留差值专属方向、共同评价范围、联合模型检查 | `network_contrast_dispatch` / `network_mean_order_dispatch`；推荐 profile 增加可选、带来源的均值顺序字段，旧 profile 保持兼容 |
| 随机化局部效应 | `readers/local_effect_lifecycle` 配对 legacy / role / owned / scoped 既有实现；解析须消费已审核局部请求 | `network_effect_dispatch` |
| R3 观察性政策 | `network_observational_policy_reading`及显式`network_observational_signature_reading`配置；复用构造/解析，固定背景须跨阶段独立交接，均值充分性单独审核 | `network_observational_policy_dispatch` |
| 变量 DAG | `dag_query_reading`；保留干预值、查询范围及原生投影 | `dag_method_dispatch` |
| 单个设计平均状态均值 | `network_extended_reading`；明确本人/同伴状态、评价范围与原设计条件平均 | `network_extended_dispatch` |
| 有限混合政策均值 | `network_extended_reading`；有限完整政策及正权重，逐政策审核和重放 | `network_extended_dispatch` |
| 观察性网络效应 | `network_extended_reading`；分别保留观测律标准化、共享层调整和局部协变量调整的合同 | `network_extended_dispatch` |

这是读取合同的分类，不是业务用户必须选择的八种数学方法。数学覆盖仍只有 `cfm_id.capability_registry` 一处运行登记；一份读取合同可能交给多个已有数学方法检查。

两政策读取登记现复用 `TargetContextHandoff` 交接明确固定背景：首次请求不增加字段或提示，重读定位复用 `/study/context`；业务适配器独立要求目标匹配和条件模型审核，见[合同](FIXED_BACKGROUND_CONTRAST_ZH.md)。这不增加一个新定理或业务路由。

## 一份登记贯穿哪些环节

```text
已审目标 → business_dispatch.prepare_reader → 登记的请求工厂
                           ↓
原始回答 → model 格式诊断 / 来源工作表 → 原生解析与业务适配
                           ↓
显式复查取同一来源目录和字段约束 → 全部变化重新审核
                           ↓
目标交接、A4/A5、适用域检查 → 原数学入口 → 独立 replay
```

| 登记组件 | 责任 |
|---|---|
| `make_request` / `request` | 请求工厂及配置；既有方向和局部角色说明继续由原有装饰步骤加入 |
| `model`、`parse` / `parse_candidate` | 输出格式与实际解析；局部效应通过 `contextual_parse` 接收已审查询，不从模型答案批准目标类别 |
| `reference_catalog`、`documents` | 来源目录与材料定义；来源工作表和重读使用同一拥有者 |
| `field_constraints` / `contextual_constraints` | 公开诊断与重读帮助；不能读取参考答案 |
| `target_context` | 显式跨阶段目标条件交接；R3 保留独立审核项，不因字符串相同自动批准 |
| `clarify_comparison` | 两政策差值方向说明；首次与重读共同使用 |
| `profile_field`、`profile`、`wire_version` | 区分请求配置与输出版本；未知值拒绝，不静默退回默认 |

配置模块仍拥有各自的协议表：政策归 `network_fact_protocols`，局部效应配对归 `readers/local_effect_lifecycle`。公共登记消费它们，不复制第二份版本表。局部 A0 说明归 `compact_response_contract.LOCAL_PROFILE_MODULES`；增加协议必须连同 Schema、审核、诊断、重读一起验收。

## 兼容与数学边界

R3观察性固定政策在同一家族内提供 `observational_fact_profile="mean-signature"`，增加暴露定义和同一固定W下的条件均值充分性。它有独立Schema/引用上下文，复用旧请求构造、解析与System Prompt；默认与历史记录不变。登记同时拥有新字段的公开诊断及重读说明。配置不是R3科学批准，完整政策有支持时仍可用原Full路线。详见[R3入口合同](R3_POLICY_ENTRY_CONTRACT_ZH.md)。

同一家族的 `mean-signature-definitions` 增加逐表定义依赖，复用公共 `source_reference_wire.definition_evidence` 解析与来源审核。登记的 `model` 是带定义引用的传输模型，`facts_model` 是投影后的原签名事实模型；只有确有传输／语义差异时才需后者。数学编译仍使用原事实，不将定义回执当成A4或A5许可；新协议与旧协议各自绑定，禁止自动转换旧审核。

- 旧 hash 来源 DAG 接口继续走明确的兼容分支；不伪装成 short_refs 登记。旧显式数学/研究接口保留。
- 原生编译、求解、科学审核和独立验证函数未改变。局部目标、DAG 限制也没有因为统一登记而被抹平。
- 两政策差值仍是**第一政策减第二政策**；共同评价名单、权重和信息模型必须独立审核。联合 sharp 界不能通过两个边际区间相减替代。
- 明示错误协议阻断；历史最小调用允许省略原本可选元数据，仍按原接口验收。改变材料、配置或目标后旧批准失效。
- 共同登记不意味着所有原生目标都已接入自然语言，也不把当前未覆盖当成非识别证明。

## 实验配置与验收

`network-policy-definition-refs-1` 是显式实验选项：直接主张引用与编码/名册定义依赖分别保存，定义不能变成新的总体信息，也不能自动补目标或覆盖名单。本轮不提升它或其他实验配置为学生默认。

### 可选的政策定义引用样板

`network-policy-record-definitions-1` 复用上述显式依赖解析，并将其补齐到均值充分性记录的 `covered_nodes`。每条记录保留自己的主张来源；模型另用 `definition_refs` 明确引用名册/编码定义。定义只解释名称和编码，不证明政策选择、总体信息存在或科学条件已接受。缺直接主张、缺定义依赖、来源被拒绝或科学条件未定，仍须阻断。

维护入口是 `policy_record_definitions`，公共解析仍在 `policy_evidence_dependencies`；政策均值和两政策差值共享此规则。来源工作表、绑定、诊断、重读及原生审核复用既有生命周期，不自动添加模型未选的来源。旧协议保持原请求。该配置仍为显式实验选项，四次事实读取的对照结果见[真实验收记录](NETWORK_DESIGN_LIVE_ACCEPTANCE_ZH.md#显式定义依赖接口的四次事实读取对照)。

既有 R3、政策均值、差值合同测试分别在 `test_fact_reading_contracts`、`test_policy_reading_contracts`、`test_contrast_reading_contracts`。局部效应与 DAG 的原生正负例继续由原专项测试负责；`test_student_handoff` 检查八类共同登记、公共配置和三个教学链路；历史测试名称中的 `five` 保留兼容，不表示当前只有五类。固定框架的 S87 只是验收索引，不是新数学分类。

### 主政策、记录范围和状态引用的接口对照

显式实验组合 `single-action-target-1` + `network-policy-scopes-1` 修正三处字段职责，未替换推荐配置：

- 政策均值和两政策比较的 A0 主安排只在 `semantics.intervention` 填一次；比较基准和方向独立保留。旧消费者的 `policy_assignment` 是有记录的同值兼容视图，不是第二次提取。重复填写、缺主端或引用不成立均阻断；不借目标句补写。
- 每条总体／样本信息分开记录 `scope_status` 和 `scope_source_ids`。`UNSPECIFIED` 的对象与坐标集合须为空；`DECLARED` 须有明确对象及覆盖原句。名册定义、信息存在、信息覆盖分别审核。范围未说明的有限记录可与已知总体分布并存，但不能替代总体信息。
- 科学状态与引用配对同时进入首次 Schema 和解析检查；公开复查给出封闭错误码及字段规则，不回传任意异常内容。`NOT_STATED` 不得携带引用；明确未决定／拒绝等状态须引用相应原文。

维护模块分别为 `policy_action_contract` 和 `policy_scope_reading`，登记、来源工作表、重读、科学审核及证书重放沿用公共生命周期。测试集中在 `test_policy_interface_contracts`，归入现有 S86 验收义务。历史配置不自动改写为新协议。

显式候选 `network-policy-scopes-2` 的定义依赖组合规则归 `policy_assumption_dependencies` 一处维护，Schema、解析、审核说明和诊断共同消费；政策均值和两政策差值均已配对。旧协议与推荐起点不变，详见[合同及实际验收](ASSUMPTION_DEPENDENCY_CONTRACT_ZH.md)。

新增能力要提交哪些证明、接口和测试见[维护规则](EXTENSION_MAINTENANCE_ZH.md)。最新实际成绩统一见[本次交接验收](DELIVERY_READINESS_ZH.md)；本页不累积每轮测试计数。
