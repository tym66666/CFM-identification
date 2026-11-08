# Identification 框架合同

本表对齐当前实现，不新增数学许可。统一的是业务材料、候选、独立审核、执行和证据发布的生命周期；各路线保留自己的数学对象与有效域。操作示例见 [研究会话指南](RESEARCH_SESSION_ZH.md)，固定检查见 [框架验收清单](FRAMEWORK_ACCEPTANCE_ZH.md)。

已有能力及其入口对应关系由 [能力登记](CAPABILITY_REGISTRY_ZH.md) 集中维护。数学路线、共同业务读取类别和内部研究会话仍是三个不同视图；共同分派使用登记中的实际函数，并阻断类别或方法错配。登记不替代科学审核及数学适用性检查。

## 业务起点与内部调用层次

真实用户从原问题开始，不预选方法。`cfm_id.project` 连接目标读取、独立审核与共同分派。当前八个事实家族涵盖随机化效应、固定政策、两政策、观察性固定背景政策、单臂、有限政策、观察性效应及 DAG；具体目标与方法以[能力登记](CAPABILITY_REGISTRY_ZH.md)为准。下方九个显式会话是保留的研究接口，范围与共同业务入口不同，不能用它们的数量代表网页能力。

| 层次 | 当前入口 | 接受什么 | 不负责什么 |
|---|---|---|---|
| 业务读取起点 | `cfm_id.project` 加载唯一推荐配置，复用 `business_intake`；无 lane | 业务问题、来源、A0 多目标候选与澄清 | 不选择数学方法，不创建科学许可，不生成数学结论 |
| 审核后分派 | `cfm_id.business_dispatch` | 当前子问题、独立意图审核、八类已登记事实家族及其专属模型审核 | 不接受 LLM 方法名作为证明，不把桥接未完成当成不可识别；数值 PARTIAL 需完整模型，保留合成研究限制 |
| 内部专门会话适配 | `cfm_id.research_session`；九个显式 lane | 原文、专门读取候选、逐项审核、原生提交对象 | 当前需研究调用层选择；不创建原生许可，不直接调用模型 |
| 显式数学研究路线 | `cfm_id.research_route_catalog` / `research_route_workflow` | 严格数学问题及相应科学审核 | 不检查原业务是否被正确理解；当前注册后门、调整、前门、均值顺序四个适配器 |
| 原生数学与业务接口 | `pfn_pipeline.identification_business`、有限政策与 DAG 各模块 | 各自类型化目标、A4、A5 和审核绑定 | 不因为 LLM 说 POINT 就认定识别，不把样本替换为总体信息 |

九个会话适配器不是九个定理，也不等于四个数学适配器。它们是既有内部配置，不是最终业务分类或用户菜单。网络 R1a/R1b/R2/R3 的完整已有能力不都从这九个适配器进入。旧 `pfn_pipeline.TaskSpec → identify` 是另一个保留的程序化接口，见 [原生识别接口](IDENTIFICATION_INTERFACE.md)。

## 内部专门会话的生命周期合同

| 环节 | 公开操作 | 必须保持的约束 |
|---|---|---|
| 材料 | `start(lane, bundle)` | 调用者显式选择入口；校验各路线的公开材料字段，不接收参考标签和审批包作为模型输入 |
| 请求 | `prepare_request` | 复用原路线请求；只导出，不联网；审核内容、会话历史和测试金标准不进入请求 |
| 候选 | `receive_candidate`、`inspect` | 保留实际 JSON 对象，检查格式、来源、目标和缺项；不修补模型回答，不调用数学后端 |
| 补问 | `clarification_plan`、`append_reply` | 问题绑定当前材料和候选；“当前读取未说明”不等于“原文未说明”；答复原样作为材料，清除候选与审核，重新读取 |
| 审核 | `begin_item_review`、`decide_item`、`finalize_item_review` | 每项初始 PENDING；接受、待定、拒绝、撤回均有记录。外层全部接受不生成原生科学许可 |
| 执行 | `execute(..., native_submission=..., research_protocol_selected=True)` | 必须精确绑定当前原生目标、信息和审核；仍由原生链再次检查；研究选择必须为布尔真 |
| 证据 | `session_routes.published_evidence` | 重新核对目标、实际公式／区间和证书，运行独立 replay；成功标记本身不是证据 |
| 保存 | `save`、`restore` | 新文件写入；校验材料、请求、审核与事件绑定；不反序列化可执行 Core 上下文，不从保存的结果恢复认证 |
| 条件版本 | `fork_version`、`plan_comparison`、`compare_versions` | 新版本不继承批准；只有已适配的有限路线允许模型包含对照，每版独立执行与重放 |

D1 的目标补问保留原问题索引和全部旧文件，另建包含原文与逐题补充的新活动目标文件。补充中的问号不会被误当成新增目标；新来源可以被候选引用。材料读取时验证这条追加链。其他路线继续使用原有题目绑定方式。

## 输入与独立审核

公开 bundle 不是统一的大型 JSON：

| 业务类别 | 公开字段 |
|---|---|
| D1 网络效应 | 必需 `case_id, documents, question_slots, structure`；具体 D1 读取还验证 `tables, file_inventory, active_goal_document` 等材料一致性。允许字段以 `session_routes.public_bundle` 为准 |
| 固定政策、差值、均值顺序 | 精确为 `case_id, node_order, documents, question_slots` |
| DAG | 精确为 `case_id, documents, question` |

候选必须符合该入口现有读取 schema，不能将这些字段拼成“通用答案”。共同审核类别是：A1–A3 目标与研究结构、A4 可用总体信息、A5 科学条件，以及 `REVIEW_SCOPE` 原生审核范围。具体声明由当前目标和原生资料展开，不存在各路线都默认成立的 A5 清单。A6 对应实际有效域检查及证明复核，不是再勾选一个同意项。

| lane / 原生提交对象 | 另外需要的审核 |
|---|---|
| `NETWORK_D1_EFFECTS`：`packet, context, submission_review` | 每题目标与来源；实际 A4 算子和实际列出的随机化、一致性等许可 |
| `MEAN_ORDER_D2_E1`：`science, packet, context, assignment_review, review, factored_review` | 两端目标、名额、共同均值模型、逐节点界限、OWN/PEERS 均值顺序的完整读取与科学审核 |
| 三个 DAG lane：`reading_review, science_review` | 读取含义与来源、图及共同原因、总体分布和正性、SCM 条件；前门还有专属角色审核 |
| `NETWORK_FIXED_POLICY` / `NETWORK_FIXED_COMPARISON`：`packet, context, submission_review, assignment_review` | 明确均匀固定名额；完整政策；比较还需两端审核、方向、共同评价人群 |
| `BOUNDED_POLICY_MEAN_D2_E1`：固定政策提交字段再加 `query_id, information, bounded_review` | 精确列出的总体均值、界限层次及作用范围、有限模型审核 |
| `BOUNDED_POLICY_CONTRAST_D2_E1`：`query_id, packet, context, information, assignment_review, joint_review` | 两端在同一模型中联合求界，不能把两个独立端点区间机械相减 |

上述字段为精确集合，多余的批准标记也会被拒绝。配对入口的 `context` 必须有且只有 `first, second`。公开会话文件包含审核资料，不应直接发给模型；只能发送 `prepare_request` 的返回内容。

## 九个兼容研究会话的适用域与结果

| 显式 lane | 目标及主要边界 | 成功证据 |
|---|---|---|
| `NETWORK_D1_EFFECTS` | 当前 D1 局部效应业务链；已知共同分配律、明确剩余安排与评价人群；不等同全部 D1–D6/E1–E5 | 按子问题输出可观测泛函、目标指纹和原 Core 证书 |
| `NETWORK_FIXED_POLICY` | 一个完整固定政策的均值；读取入口要求明确均匀固定名额；由原 Core 判 R1b 完整安排或 R2 均值签名条件 | 公式 POINT；R2 的均值充分性需另行授权 |
| `NETWORK_FIXED_COMPARISON` | 两个完整政策、第一减第二；当前为两端 R1b POINT 的有符号组合 | 两端证书及方向／目标绑定的组合证书 |
| `BOUNDED_POLICY_MEAN_D2_E1` | 单个政策均值；D2 均匀固定名额、E1 严格多数（平票低、孤立点零）、最多 12 节点 | 精确 sharp 区间；退化时 POINT |
| `BOUNDED_POLICY_CONTRAST_D2_E1` | 同一有限模型中的两个政策差值；共享未知均值可抵消；同上 D2/E1/12 节点 | 联合精确 sharp 区间或 POINT |
| `MEAN_ORDER_D2_E1` | 上述有限共同模型，另声明逐节点 OWN/PEERS 均值非递减；作用于所有二元安排；不是个体潜在结果单调性 | sharp 区间／POINT；不相容时可有 Farkas 证书 |
| `DAG_CLASSICAL_BACKDOOR` | 静态因果 DAG，经典后门充分判据；最多 8 个二元节点（含显式潜变量） | 干预分布的符号调整公式、图判据与独立证书 |
| `DAG_ADJUSTMENT` | 同一 DAG 合同下的调整判据；不是一般潜变量图 ID | 调整公式及专属证书 |
| `DAG_CLASSICAL_FRONTDOOR` | 同一 DAG 合同、单个观察前门变量；不是集合前门／条件前门 | 嵌套可观测分布公式及专属证书 |

有限模型还要求固定处理前简单无向网络、二元处理、列明的精确总体均值和界限；无顺序入口不能夹带额外耦合约束。`CONDITIONAL_MEAN` 与 `ALMOST_SURE_OUTCOME` 界限含义保留区分。sharp 只相对于完整声明的模型，不能据此认定现实假设为真。

DAG 使用已审核的完整观察变量联合总体分布与严格正性声明，完整图及显式共同原因、独立结构噪声、理想干预等原合同条件；没有从有限样本估计概率。未找到当前充分判据所需集合不等于已经证明一般不可识别。

除 DAG 保留外部声明式研究或合成审核外，这些网络会话链保留原有独立合成审核限制。所有会话结果均为 `production_admission=False, estimation_handoff_allowed=False`。这不是生产环境的自动审批入口。

## 状态与证据不能混用

共同结果字段包括 `state, reason_code, mathematical_claim, certificate, independent_replay, backend_called` 和会话绑定；诊断保留 `native_inspection` / 执行后的 `native_result`。

| 状态／情况 | 消费者应如何处理 |
|---|---|
| `READING_REQUIRED` | 尚无当前有效读取，不能审批或求解 |
| `NEEDS_INPUT` | 当前读取缺条件，可核对原文并补问 |
| `REVIEW_REQUIRED` | 可以审核；不是已经通过审核或已经识别 |
| `CHECK_BLOCKED` | 审核、来源、绑定或证明检查失败；数学结论为空 |
| 原生 `DRAFT_INVALID`、`MIXED` 等 | 保留原生诊断；例如一题缺项一题就绪时不自动执行后者；不能将未知状态视为成功 |
| `UNSUPPORTED` | 当前入口不覆盖；不代表一般不可识别，不静默换路线／调用模型 |
| `POINT` / `PARTIAL` | 还须有匹配目标的 claim、certificate 与实际 replay；公式 POINT 不意味着得到数值估计 |
| `INCOMPATIBLE` | 区分具体入口：均值顺序可提供已重放的矛盾证书；两条无顺序有限政策入口仅给诊断，不发布不可行证书 |

数学 claim 的表示有 `PER_QUERY_OBSERVED_FUNCTIONALS`、`OBSERVED_DISTRIBUTION_FUNCTIONAL`、`EXACT_IDENTIFIED_INTERVAL` 和均值顺序的 `CONSTRAINT_CONTRADICTION`。它们不是可互换的任意文本。库外 `LLM_UNVERIFIED` 位于独立候选研究入口，不是上述认证结果，也不由会话失败自动触发。

## 扩展一次需要改哪里

先区分读取协议、业务适配和数学机制。读取配置及网络请求／解析配对已收拢到明确接点，详见[开发端读取配置与扩展约定](BUSINESS_READING_CONFIG_ZH.md#扩展前先判断改的是哪一层)；数学路线仍使用下面的既有层次，没有另建一份路由目录。

目前采用显式封闭分派，还不是“增加一个文件即可自动注册”的插件系统。下面是代码落点，不是机械文件数量承诺。

| 新能力 | 新增内容 | 需要核对／修改的公共接点 |
|---|---|---|
| 既有路线的新业务材料 | 原文、目标标签、正负例 | 通常无需改公共运行代码；由原合同检查能否表达，不按题号特判 |
| 新 DAG 数学路线并接入业务会话 | 数学 schema、证明、独立 verifier、专属审核；必要时专属读取 | `research_route_catalog` 注册；`dag_business` 合同分派；`session_routes` lane；`review_items` 的 DAG 声明内容。CLI 使用既有 DAG 集合，但仍应验收 |
| 新网络／PARTIAL 语义族 | 精确目标、A4/A5、数学后端及验证器、业务桥 | `session_routes` 的材料／请求／检查／提交／快照／证据；`review_items` 的逐项声明。固定政策同族由 `session_policy_routes` 承担分派与条目 |
| 新的条件包含比较 | 数学上明确什么保持不变、什么放宽 | `research_versions` 描述与包含判断；未适配前只能各自报告，不能声称集合包含 |
| 新的文件式 CLI 提交 | 可安全重建的原生对象接口 | `research_session_cli`；当前网络上下文仍需 Python 调用方提供，不能通用反序列化任意执行对象 |
| 每一种新增 lane | 明确合成正例、缺项／错目标／撤回／篡改等负例 | 更新固定验收清单及逐 lane 测试；新增入口却无验收会直接失败 |

共同会话状态机、数学求解器、独立验证器和 Prompt 不应仅为注册相似业务反复修改。新科学内容确有不同审核语义时，明确增加相应声明；不能为了减少文件改动把它压成一个通用“假设已满足”开关。

当前仍未解决：一般 IV／潜变量图 ID、通用 PARTIAL、集合／条件前门、跨路线模型包含、多入口自动编排、现实审核人的认证及旧副本全局撤销。内容哈希用于一致性与过期检查，不是签名、现实真实性证明或形式证明助手级认证。


读取职责维护补充：局部协议由 `compact_response_contract.LOCAL_PROFILE_MODULES` 封闭登记；首次说明、显式重读与审核按选定协议共享字段定义。该登记只连接读取工具，不替代 `capability_registry` 的数学能力登记，也不赋予求解许可。历史评价范围实验另行保留；当前检查与限制见[发布验收](RELEASE_ACCEPTANCE_ZH.md)。
