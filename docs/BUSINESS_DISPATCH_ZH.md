# 从业务读取到方法适用性检查

用户先描述业务，系统随后检查方法；用户不必先选后门、调整或前门。本次接通一个有限但完整的闭环：通用 A0 → 选定子问题的独立意图审核 → 共用 DAG 事实读取 → 原生问题与审核表 → 多方法检查 → 独立验证。

这里的“自动”指材料到原生问题的投影、候选方法组织及判据检查。科学假设仍须独立审核；引用存在也不证明业务解释正确。

## 在流程中的位置

| 步骤 | 当前模块 | 做什么 |
|---|---|---|
| 业务问题及多目标草稿 | `business_intake` | 不选数学方法；保留原文、多个目标和澄清 |
| 意图审核与读取合同选择 | `business_dispatch.prepare_reader` | 绑定当前子问题，审核业务目标、研究结构和来源；按已审核结构选择事实读取合同 |
| 共用 DAG 事实读取 | `dag_query_reading` 短编号格式，兼容原 `dag_frontdoor_reading` | 提取变量、图、目标、总体信息、模型声明、明确角色要求及当前子问题的干预取值；不作识别判断 |
| 原生问题准备 | `business_dispatch.inspect_methods` / `dag_method_dispatch` | 复用原生投影与有效域检查；生成待审核的后门、调整、前门问题；此时不运行图形识别算法 |
| 独立审核 | 分派计划审核 + 各原生读取/科学审核 | 确认原生目标仍回答选定业务问题、模型及限制完整保留；原生条件逐项 PENDING/ACCEPTED/REJECTED |
| 方法检查与发布 | `business_dispatch.execute` | 先检查全部审核，再运行候选方法的原生后端，并复核实际公式与证书 |

`--query q1` 是选择用户自己提出的一个子问题，不是选择数学方法。输出明确为 `SELECTED_QUERY_ONLY`，并保留 `remaining_query_ids`；一个子问题成功不代表整份咨询全部完成。

整份咨询使用 `business_case.prepare_case / execute_case`，或下文整题 CLI。它遍历当前读取稿的全部子问题，逐题独立绑定输入、审核与实际执行结果。整题额外要求独立检查“原问题是否全部被读取稿涵盖”，不能只靠模型自己输出的 query 数量证明没有漏问。

## 短来源编号与目标取值

新会话默认 `fact_format='short_refs'`。模型填写 `s0001` 等短编号及一个短上下文标识；完整来源哈希、原文位置与完整上下文摘要由程序保管。展开时重新从原文建立目录，不接受模型提供的哈希表，不猜测拼错编号。短上下文用于防止误混请求，不是身份认证；材料、当前子问题及审核仍由本地完整摘要绑定。

原始短编号回答、完整来源投影及对应表都保留在分派计划。任何材料、子问题、回答或取值变化都要求重新检查审核绑定。旧 `source_hash` 格式保留在单题兼容路径；不是将旧回答中的错误长哈希修复为新答案。可以用 `business_intake.configure_fact_format(intake, 'short_refs')` 为旧 A0 建立新的事实读取会话：原始 A0 不变，后续审核失效，需要新请求和新回复。

`query_scope` 区分完整干预分布、指定的 0/1 取值、未知及其他目标。未知不会默认扩成全部取值。计划审核新增 `requested_intervention_values_and_kernel_view`，要求审核原文与所请求取值是否一致。

数学后端仍证明完整的二元干预分布函数：对每个 x∈{0,1}，p_x(y)=F_x(P_obs)(y)。若用户仅问 x=0，结果保留该完整公式和证书，另给出 `query_view` 标注自由干预参数取 0。这里没有新增识别定理、求差值或估计数值，也不替换表达式中所有同名变量。例如前门公式中的内部处理边际求和仍遍历 0/1，不能一起固定为 0。

## 整题验收与未完成项

`execute_case` 接受当前 intake、按 query_id 保存的候选和独立审核记录，以及整题覆盖审核 `case_review`；只接受输入，不接受已经保存的成功结果充当证明。每次执行重新准备计划并调用现有后端、独立重放。

- 全部当前子问题都得到已验证 POINT 或 PARTIAL，且整题覆盖审核通过，才返回 `ALL_QUERIES_IDENTIFIED`；另用 `all_queries_point_identified` 表示全部均为点识别。
- 缺一份回答、审核待定/拒绝、来源不合法、NEEDS_INPUT 或 UNSUPPORTED 都保留为未完成项，整题为 `CASE_INCOMPLETE`。
- 已验证子问题的答案单独保留，不复制给其他子问题；不静默合并模型拆出的两问。
- 整题顶层不生成混合公式或证书。原题覆盖仍依赖独立语义审核，数学验证不证明自然语言理解无误。

准备全部子问题及覆盖审核表，不预选 q1 或数学方法：

```powershell
python -m cfm_id.business_case_cli plan --intake intake.json --output whole_case_plan.json
```

填写独立整题审核及逐题请求/读取/科学审核后执行：

```powershell
python -m cfm_id.business_case_cli execute --intake intake.json --submissions query_submissions.json --case-review case_review.json --select-research-protocol --output whole_case_result.json
```

`query_submissions.json` 是以当前 query_id 为键的对象，每条提供 `query_review, candidate, request_sha256, plan_review, native_reviews`；根据该问题的实际流程，还可提供 `note_review, reading_revision, change_review, information_evidence_review`。它们均为单题准备阶段取得的当前输入／独立审核，直接作为对象放进该子问的提交项，不是文件路径或保存的执行结果。整题与逐问复用同一校验，不自动补全审核。

`information_evidence_review`只用于已支持的单表与辅助引用合同，不合并多份总体信息、不批准科学条件；不能将同一记录跨子问或跨读取器复用。详情见整题来源审核验收（历史记录不随发布）。缺少某题保留缺口；额外或过期的query_id被拒绝。整题覆盖审核与各题审核必须使用同一授权类别。单题CLI继续用于准备逐题材料，整题CLI不联网、不读取密钥、不自动批准。

可运行的双问题离线例子（明确的合成审核，不是模型准确率）：

```powershell
python -m examples.business_case_reference --allow-synthetic-reviews --output outputs/business_case/reference_001
```

A0 发现读取遗漏或需要复查时，分派层保留 `READING_RECHECK_REQUIRED`；业务意图未明确时才转为 NEEDS_INPUT。专门读取缺项会汇总为去重的 `clarification_questions`，并明确“当前读取未说明，不证明原文没有”，应先核对材料。科学条件交研究者审核，不把它们直接作为业务人员的问答清单。

## 当前接通范围

变量因果 DAG 连接单个干预分布目标，沿用原生合同：最多 8 个二元节点（含显式潜变量）、固定递归 SCM、完整因果图和共同原因声明、独立结构噪声、完美干预、完整观测联合总体分布及严格正性。各项声明与科学批准分开。

对象网络已接通 [固定政策均值的共同读取与 R1b/R2 检查](NETWORK_POLICY_DISPATCH_ZH.md)：D1–D6 原设计、完整固定安排、明确评价名单和等权均值，R2 支持既有 E1–E5 及各自充分性和支持合同。它复用相同的意图审核、分派计划、逐项科学审核和整题汇总；没有把 DAG 分布目标套成网络均值。

没有新增定理。经典后门、DAG 调整及单观察变量前门继续使用各自原求解器和独立验证器。前两者不是两个不同业务类别；同一个问题可能同时满足它们。

- 网络干扰的其他效应目标、R3、有限 PARTIAL 等原生能力仍保留，尚未全部接到这条无路线分派桥。未连接的目标返回 `ADAPTER_NOT_CONNECTED`，不称为不可识别。
- 同时出现单位网络和变量因果图描述时保留二者，目前要求进一步处理表示关系；不会自动丢掉一类结构。非空网络描述也可能是“没有干扰”的陈述，通用字段没有布尔极性，当前保守留待澄清/扩展，不按关键词断言有干扰。
- DAG 中其他目标、一般 ID、集合/条件前门、IV、新科学限制不自动套入当前合同。
- 真实 LLM 的小样本接入检查与离线验收分开记录，原始回答保存在源码包外。调试期间更改过 Prompt 的样本不能合并为冻结准确率；离线参考候选只验收流程与数学准入。

## 同一问题怎样检查多个方法

若用户没有指定普通调整集或前门变量，就对同一目标和同一已声明模型准备三种现有方法。具体调整集与前门变量由各自原生算法检查或搜索，不让 LLM 猜定理。

用户的明确要求会约束检查范围：

| 原文中记录的要求 | 当前处理 |
|---|---|
| 未指定方法角色，`adjustment=null`、前门角色 UNSPECIFIED | 准备三种方法，审核后分别检查 |
| 明确要求某个普通调整集，包括空集 `[]` | 保留这个集合，检查经典后门与调整；不改成前门或换控制变量 |
| 明确指定某个前门变量 | 只检查该前门请求，不因其不适用而替换成普通调整 |
| 前门用途被禁止 | 保留禁止记录，不运行前门；其他允许的方法仍可检查 |
| 前门角色尚未决定 | NEEDS_INPUT，不把“未决定”当作允许搜索 |
| 同时要求普通调整和前门 | 当前桥未适配组合请求，保留两项要求并停止 |

投影到旧后门/调整格式时，只移去其 Schema 不支持的前门角色字段并改协议版本；完整原候选和角色限制仍绑定在分派计划中。改变这个字段，即使旧格式投影未变，也使计划审核失效。

所有计划方法的审核都在任何数学求解之前检查。一项审核待定、拒绝、过期或属于另一授权范围，不会通过尝试另一种方法绕过。审核齐全后，某个**数学充分判据不成立**，才允许继续检查同一已审核模型的其他候选方法。

多个成功公式均保留在 `answers` 中。顶层公式和证书按固定顺序展示首份已验证结果，`primary_method` 仅用于展示，不表示更强的统计表现。全部方法均不通过时返回 UNSUPPORTED，明确 `nonidentification_proved=false`。

## 可运行的离线例子

```powershell
python -m examples.business_dispatch_reference --allow-synthetic-reviews --output outputs/business_dispatch/reference_001
```

必须使用新目录。这是显式的合成审核协议，不能替真实研究批准假设，也不是在线模型实验。例子覆盖：

1. 观察混杂变量：后门和调整均给出通过重放的公式。
2. 经典后门不适用但调整可行：只由调整通过。
3. 未指定方法的前门结构：后门与调整不通过，前门通过。
4. 因果图声明缺失：NEEDS_INPUT。
5. 只有有限样本：NEEDS_INPUT。
6. 现有三种充分方法均不通过：UNSUPPORTED，未证明不可识别。

## 本地接口

中性读取会话已有 A0 候选后，先导出独立意图审核工作表：

```powershell
python -m cfm_id.business_dispatch_cli reader-plan --intake intake.json --query q1 --output intent_worksheet.json
```

审核人填写单独的 `DispatchReview`：当前 `binding_sha256`、审核人、理由、authority 以及工作表的全部 decisions。缺失与待定不会被自动改成接受。提交该记录后导出事实读取请求：

```powershell
python -m cfm_id.business_dispatch_cli reader-plan --intake intake.json --query q1 --query-review query_review.json --output reader_plan.json
```

`reader_plan.request` 的 system/user 可交给已授权 Provider；CLI 本身不联网、不读取密钥。一次事实读取服务于候选方法集合，不是每个方法分别调用模型。实际调用策略、重试和额度由调用层控制。

```powershell
python -m cfm_id.business_dispatch_cli method-plan --intake intake.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate actual_reading.json --output method_plan.json
```

该计划包含原生数学问题、逐方法读取/科学工作表以及一份完整投影审核表。审核人确认后，独立提供计划审核和各原生审核记录；运行时只做类型验证，不代填 ACCEPTED：

网络候选带有未解决备注时，会先返回 `note_review_worksheet`；`REVIEW_REQUIRED` 不一定已包含方法计划。先按 [备注审核](READING_NOTE_REVIEW_ZH.md) 独立提交 `--note-review`，通过后才出现 `plan_worksheet`。后续执行使用同一份备注审核；它不替代上述科学审核。

单个固定政策的数值信息条目同时引用一份原始数值表及其他定义材料时，可导出 [信息来源角色工作表](NETWORK_POLICY_DISPATCH_ZH.md#一份信息表及其辅助说明)：

```powershell
python -m cfm_id.business_dispatch_cli information-evidence-plan --intake intake.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate actual_reading.json --output information_evidence_worksheet.json
```

这是离线待审核工作表，不会自动生成接受记录。独立填写当前绑定、authority、审核者、依据、disposition、`table_source_ids` 和 `supporting_source_ids` 后，将该记录通过 `--information-evidence-review information_evidence_review.json` 同时传给 `method-plan` 与 `execute`。需要重新生成后续计划和原生审核，不能复用未包含该来源记录的旧批准。它不替代读取变动、备注或科学审核；当前不用于政策差值或 DAG 的来源拼接。

```powershell
python -m cfm_id.business_dispatch_cli execute --intake intake.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate actual_reading.json --plan-review plan_review.json --native-reviews native_reviews.json --select-research-protocol --output result.json
```

运行总会重新计算计划。保存的结果、计划或成功标记不能直接变成识别认证；改变原文、A0 候选、子问题、事实读取、角色要求或审核内容，都须重新检查对应绑定。哈希是内容绑定，不是身份认证。

若独立核对发现原文已齐而事实候选漏读或误分类，使用 [事实重读](FACT_READING_REVISION_ZH.md) 的 `recheck-plan`。它保留旧回答并创建新来源上下文；后续调用带上 `reading_revision`，不能手工修补候选或沿用旧计划批准。模型造成的未接入提示应先核对，不能直接当作识别库的真实能力边界。

## 下一种结构如何接入

网络局部直接与同伴效应已连接 D1–D6/E1–E5，详见[局部效应合同](NETWORK_EFFECT_DISPATCH_ZH.md)。两类目标复用同一事实读取协议，原设计条件平均和固定评价名单单独审核；不修改原生 R1a 求解和重放，也不把局部总效应误送入完整政策差值适配器。

通用层只负责原文、目标选择、审核绑定和停止状态；结构专属模块负责事实 Schema、向原生对象的完整投影、候选方法及证据复核。网络固定政策连接已按此边界实现；继续扩展时不要把 DAG 的分布合同硬套为网络均值，也不要再暴露一个平铺的九类用户菜单。

同一完整政策目标的 R1b/R2 条件检查，以及明确数值均值、界限和完整模型声明下的有限 D2/E1 合成 PARTIAL 已接通，见共同网络入口说明。没有界限声明时不得因 POINT 失败而自动补界限。扩展 IV 等不同模型时先确定目标、A4、A5 与数学合同，再接此生命周期。

整题汇总区分 `point_identified_query_ids` 和 `partially_identified_query_ids`；经独立重放的 PARTIAL 可以完成该问题的识别集合回答。`ALL_QUERIES_IDENTIFIED` 不承诺每问均为点识别，另有 `all_queries_point_identified` 明确这一条件。
