# Identification 研究会话

这是一层供内部专门适配器使用的共同工作流，复用现有读取、审核、求解和验证接口。它不新增识别定理，不推断路线，不创建科学许可，不调用 Estimation 或 Policy。普通业务用户应从 [无路线业务读取会话](BUSINESS_INTAKE_ZH.md) 开始；这里的 `lane` 是开发调用层配置，不是用户必须提前了解的分类。[共同业务分派](BUSINESS_DISPATCH_ZH.md) 已连接 DAG 三种方法检查、有限范围的网络政策均值／差值及 D1/E1 局部效应，无需用户先创建某个 lane；精确范围见[能力登记](CAPABILITY_REGISTRY_ZH.md)。

接口合同与扩展落点见 [框架合同](FRAMEWORK_CONTRACT_ZH.md)，可重复执行的逐入口正负例见 [固定验收清单](FRAMEWORK_ACCEPTANCE_ZH.md)。本页保留具体操作方法。

均值顺序的内部运行实现已归入 `cfm_id.workflows.mean_order`，固定政策读取归入 `cfm_id_llm.readers`；旧导入兼容。新开发位置与目录职责见[开发入口](DEVELOPMENT_ENTRY_ZH.md)。

## 当前范围

| 显式 lane | 复用的业务链路 | 审核范围 |
|---|---|---|
| `NETWORK_D1_EFFECTS` | D1 效应读取 → intent_submission → 原 Core | 保留原独立合成审核限制 |
| `MEAN_ORDER_D2_E1` | 均值顺序读取与完整候选审核 → 有限后端 | 保留原合成审核、D2/E1 等合同 |
| `DAG_CLASSICAL_BACKDOOR` | DAG 业务审核 → 经典后门 | 原外部声明式研究或合成审核 |
| `DAG_ADJUSTMENT` | DAG 业务审核 → 调整路线 | 同上，使用专属审核类型 |
| `DAG_CLASSICAL_FRONTDOOR` | 前门角色读取 → 前门研究路线 | 同上，使用专属审核类型 |
| `NETWORK_FIXED_POLICY` | 固定名单读取 → 原固定政策 POINT 链 | 原固定名额审核；R1b 完整安排或 R2 均值签名，由原 Core 检验 |
| `NETWORK_FIXED_COMPARISON` | 甲减乙 → 两端原 R1b 证书与有符号组合 | 两端科学审核及独立方向／共同评价人群审核 |
| `BOUNDED_POLICY_MEAN_D2_E1` | 单个固定政策 → 原有限均值界限链 | D2/E1、精确总体均值与声明界限、最多 12 个节点，保留合成研究限制 |
| `BOUNDED_POLICY_CONTRAST_D2_E1` | 有序政策差值 → 同一均值模型上的联合求界 | 同上，另需两端来源与共同模型的独立联合审核 |

网络其他设计、观察性固定政策和库外候选继续使用原入口，本次没有全部纳入会话层。新接入的固定名单读取使用已有 `fixed-assignment-id` 合同；原试点需明确的均匀固定名额，不是所有随机设计的通用入口。显式选择 lane 是范围约束，不是对当前问题已经适用的保证。某条路线失败时不会静默换路线、添加条件或调用第二模型。

## 共同操作

`cfm_id.research_session` 提供：

1. `start(lane, bundle)`：建立公开业务材料的会话。
2. `prepare_request(session)`：导出原路线的请求，内容与原入口相同；无审核包、参考标签或认证信息。
3. `receive_candidate(session, actual_reply)`：保留实际 JSON 对象，不补字段、不修复答案；本地检查另由 `inspect` 完成。
4. `clarification_plan` / `append_reply`：依据当前读取的缺项提问，原样追加普通语言补充；清除当前候选和审核，要求重新读取。
5. `begin_item_review` / `item_review_worksheet` / `decide_item` / `finalize_item_review`：按当前路线展开具体声明，逐项记录审核人、理由及决定。原 `review_worksheet` / `record_review` 保留兼容；开启逐项审核后不能用旧的三个总开关绕过它。
6. `execute`：另行提供原生审核对象并显式选择研究协议，调用原审核链；只发布与证据一致且复核通过的数学结论。
7. `save` / `restore`：保存和恢复会话；文件不覆盖旧记录，不包含可执行 Core 对象或可直接恢复成认证状态的结果。

首版网络层对多个子问题保留原生诊断；只有整体已准备好审核时提交。混合状态不会自动挑出可回答部分或跨路线执行。

## 审核与失效

工作表是未批准视图。逐项审核全部接受并明确完成后，生成外层的三个完整决定和当前绑定；它们不会被转换成原生科学许可。
提供原生提交对象时，工作表同时列出 `native_review_materials`，包含被绑定的原生目标、总体信息、科学资料与审核记录，供审核者具体核对。该材料只属于审核流程，不进入模型请求或可执行上下文的恢复。
全部 ACCEPTED 还必须绑定实际原生提交对象的摘要，包括原生 A4/A5、审核和目标上下文；仅填写“同意”不能取得数学许可。

材料修订、补充或候选替换都会增加修订号并清除候选／审核的相应有效性。即使两次候选内容相同，新收到一次回答也需重新绑定外层审核。
原请求合同发生变化时，旧会话停止并要求新建／重新读取，不使用旧回复冒充新 Prompt 的结果。
原生科学条件或审核对象改变时，也必须重新审核外层提交绑定。原生链路继续独立拒绝过期审核、错目标、错来源和不支持条件。

这些哈希是内容绑定，不是数字签名、审核人身份认证或现实科学真实性证明。
原始文件应另行留存；会话历史记录前一修订的指纹与操作，当前文件不重复嵌入所有旧材料。

会话文件含审核人、理由和原生审核材料，**不属于可直接发送给 LLM 的公开输入**。新版保存标记为 `RESEARCH_SESSION_CHECKPOINT`，仍兼容旧标记。发给模型的只能是 `prepare_request` 返回的原路线请求；新增审核内容不会进入该请求。

补问依据是“当前读取缺项”，不能证明用户原文缺项。答复可以是“尚未决定”；它不会自动变成已满足条件。候选尚未读取、被拒绝或格式失败时不执行数学后端。

D1 目标补问保留原题 `question_slots` 与全部旧文档，并建立包含原目标和逐题补充的新 `active_goal_document`；材料检查验证追加链。这样补充可被当前来源编号引用，答复中的问号不会被当成新增题目。`MIXED` 等原生诊断状态仍会保留，不会自动执行其中已经就绪的子问题。

## 逐项审核：接受、修改和撤回

条目从当前候选与原生声明生成，不按业务题号配置，也不由模型输出直接批准。每次读取保存文件都会重新生成条目，核对是否删项、改义或改变绑定。

| 路线 | 展开的关键条目 |
|---|---|
| 网络 D1 效应 | 目标与评价人群、网络与分配概率、逐项 A4 总体信息算子、原生实际列出的五类许可。R1a 不额外加入均值充分性。 |
| D2/E1 均值顺序 | 比较方向与权重、网络和名额、每个总体均值单元、随机化／一致性／有限矩／均值充分性、每个节点的界限、每个节点自身和同伴两个轴的均值顺序。 |
| DAG 后门／调整／前门 | 目标与变量、完整总体分布、严格正性声明、图完整性／显式共同原因／独立噪声／理想干预等结构条件。图上的调整或前门判据仍由程序检验，不作为人工批准的替代品。 |
| 固定政策 POINT／政策差值 POINT | 完整安排、共同评价人群与权重；逐端原试点、原生实际 A4 和 A5；R2 的均值充分性仅在该原生声明存在时列出。 |
| 有限政策均值／联合差值 | 以上条目，以及全部已列总体均值单元、各节点界限及作用层次、共同模型和无额外耦合限制的审核；不自动加入均值顺序条件。 |

额外的“原生审核范围”条目保留合成研究限制和原生审核记录。部分识别条目显示 `bounds_kind`、研究背景、结果单位和适用范围；条件均值界限不被改写成逐个个体的几乎必然界限。顺序模式 `NONE` 的条目明确表示没有该限制，接受这项记录也不会加入单调性。

```python
from cfm_id import research_session as work

# native_submission 由独立审核流程准备，不能从 LLM 回复创建审批。
s = work.begin_item_review(s, native_submission=native_submission)
sheet = work.item_review_worksheet(s)
# 每条初始均为 PENDING，即使原生记录已经有 ACCEPTED。
work.write_json("items_pending.json", sheet)

# 阅读某一具体条目的 declaration 和 supporting_material 后填写。
row = sheet["items"][0]
s = work.decide_item(s, {
    "expected_review_sha256": sheet["review_sha256"],
    "item_id": row["item_id"],
    "decision": "ACCEPTED",  # 或 PENDING / REJECTED / WITHDRAWN
    "reviewer": "独立审核者姓名",
    "evidence": "在此填写针对该声明的具体依据、来源与审查理由。",
})
# 其他条目需要各自审核。每次提交前重新取工作表，不能复用旧摘要。
```

每次修改追加一条事件，保留上一决定、审核人和理由，并清除当前外层完成批准。即使仍填 ACCEPTED 而只是改理由，也需要重新完成审核。全部条目接受后：

```python
sheet = work.item_review_worksheet(s)
s = work.finalize_item_review(
    s, expected_review_sha256=sheet["review_sha256"],
    reviewer="独立审核者姓名", evidence="已复核当前全部声明、证据来源和原生提交绑定。",
)
work.save(s, "session_items_reviewed.json")
# 随后按下文 execute，原生 PENDING / REJECTED 和科学范围限制仍然生效。
```

| 决定／操作 | 当前会话的作用 |
|---|---|
| PENDING | 等待判断，不执行数学后端。 |
| REJECTED | CHECK_BLOCKED，不执行数学后端。 |
| WITHDRAWN | 撤回当前接受，回到 REVIEW_REQUIRED；原条件数值不被改写。 |
| 全部 ACCEPTED 但未 finalize | 仍不能执行。 |
| 全部接受并 finalize | 仅完成外层审核，继续经过原生审核和独立证明复核。 |

**撤回批准不等于数学上放宽假设。** 若要比较“去掉均值单调性之后区间怎样变化”，应按下文建立条件版本，显式修改材料／科学模型，在原路线重新准备候选和原生审核，再新建逐项清单。系统不自动复用旧决定，也不把未接受的条件偷偷删除后求解。

材料、候选或原生提交发生变化后，须重新建立当前审核。旧审核的摘要保留在历史中；旧结果文件仍是旧条件下的历史结论。撤回只作用于当前保存的会话分支，不是对所有离线副本的全局撤销服务。

## 保存后继续执行

三个模型族采用同一 Python API：

```python
from cfm_id import research_session as work

s = work.restore("session_reviewed.json")
# native_submission 来自独立审核者／可信调用代码，必须与外层审核绑定一致。
result = work.execute(
    s,
    native_submission=native_submission,
    research_protocol_selected=True,
)
work.write_json("new_result.json", result)
```

若不提供原生审核上下文，恢复后只可查看待审核状态，不能发布 POINT 或 PARTIAL。网络和均值顺序的 Core 上下文仍由 Python 调用方持有；首版不为它们增加通用 JSON 反序列化器，也不从磁盘 pickle 或任意模块路径载入对象。

DAG 原生审核已有封闭的 JSON 类型，因此命令行额外提供 `submit-dag`。并非九条 lane 均已实现纯 JSON 命令行执行：网络、固定政策和均值顺序的最终提交当前使用上述相同 Python API。

## 固定政策：一个均值与两个政策的差值

“让指定名单使用工具，评价哪些对象的平均结果”与“方案甲减方案乙”是两个不同目标。后一目标同时绑定两份完整安排、相同评价人群和权重，不能默认为全体，也不能把比较方向交换。

原生提交对象由既有独立审核流程准备，字段严格如下；本层不创建其中的批准：

| lane | `native_submission` 字段 |
|---|---|
| `NETWORK_FIXED_POLICY` | packet、context、submission_review、assignment_review |
| `NETWORK_FIXED_COMPARISON` | 同上；packet、context、assignment_review 均按 first／second 提供 |
| `BOUNDED_POLICY_MEAN_D2_E1` | query_id、packet、context、information、bounded_review、submission_review、assignment_review |
| `BOUNDED_POLICY_CONTRAST_D2_E1` | query_id、packet、context、information、assignment_review、joint_review；除 query_id／joint_review 外均为 first／second 两端对象 |

两个有限入口目前只接受一个完整问题。两个公式入口可以保留多个子问题，但会话要求整体准备好且审核覆盖完整问题集合；不自动缩小到某个已批准子集。

使用方式与前文一致：`start → prepare_request → receive_candidate → begin_item_review → decide_item → finalize_item_review → execute`。审核快照增加原生研究结构、目标、A4 来源和 A5 的纯数据视图；保存恢复不会把它反序列化成可执行 Core 对象。旧五条路线的快照格式和请求保持不变。

结果有两种不同表示：

- 公式 POINT：`PER_QUERY_OBSERVED_FUNCTIONALS`，与 D1 使用相同的 `queries[].functionals[]`，每项含 target_fingerprint 和 expression；新政策入口另列 target_coordinates。每次发布重新核对原生证书。公式识别不等于已经估计出业务数值。
- 有限模型：`EXACT_IDENTIFIED_INTERVAL`，显示精确有理数区间、sharp、informative 和逻辑范围；端点相等时是 POINT，否则是 PARTIAL。两种状态都重新调用原有限验证器。

联合差值在**同一个模型**内求界，保留两个政策共享的未知均值。例如两个单独政策均值尚不能确定，但比较同一政策与自身时，共同未知量抵消，差值精确为零。简单将两端各自区间相减通常无法体现这种约束，本入口不这样生成 sharp 结论。

POINT 入口支持不足时保留 UNSUPPORTED，不自动进入有限模式；有限模式需要额外的明确总体均值、结果界限与独立审核。原有限后端若返回 INCOMPATIBLE 而未给出不可行性证书，本层保留该诊断，但顶层 `mathematical_claim=None`、`certificate=None`、`independent_replay=False`，不宣传为已认证的不可行性证明。

## 同一业务问题的条件版本对照

`cfm_id.research_versions` 保留原会话，建立另一份明确声明条件的会话，并比较两版真实执行的结果。它不从 LLM 回答、版本标题或两个区间的宽窄推断模型包含关系，也不接受保存的结果 JSON 作为证明输入。

九条现有 lane 均可用 `fork_version` 保存分支。首批模型包含检查仅接入三条已有有限路线：`BOUNDED_POLICY_MEAN_D2_E1`、`BOUNDED_POLICY_CONTRAST_D2_E1`、`MEAN_ORDER_D2_E1`。其余路线可分别执行，尚未提供跨条件的自动包含结论。

### 具体能比较什么

先固定业务问题、数学目标、A4 总体信息与其余模型声明，再检查两类变化：

- **同一含义的界限变宽或变窄**：逐节点精确比较有理数下界、上界；条件均值界限与几乎必然结果界限不能互换。
- **增加或删除均值顺序限制**：仅针对既有均值顺序合同，按节点和自身／同伴两个轴比较限制集合。方向、作用层次和所有二元安排的适用范围保持不变。

依据是可行模型集合的包含关系。令固定 A4 为 $b$，固定目标为 $T$，两版模型分别为 $\mathcal M_0(b)$、$\mathcal M_1(b)$。若

$$
\mathcal M_0(b)\subseteq\mathcal M_1(b),
\qquad
\Theta_j=\{T(P):P\in\mathcal M_j(b)\},
$$

则每个旧模型仍是新模型，所以 $\Theta_0\subseteq\Theta_1$。在当前已接入的有限合同中，放宽同类界限、删除已声明的均值顺序不等式，都会保留原可行模型；其余谓词必须一致。每版的精确区间及 sharp 性仍由原数学实现与原独立验证器确定。本层随后核对区间是否遵守上述包含关系。

这是对明确声明集合的充分检查，不是一般数学模型的自动蕴含证明。非嵌套的声明可能因为约束冗余而产生嵌套甚至相同的区间；本层不会据此反推模型包含。删除冗余限制或放宽不起作用的界限，也不保证区间严格扩大，更不保证 POINT 一定变为 PARTIAL。

原模型、sharp 性与文献依据继续以[单政策数学合同](BOUNDED_POLICY_MATH_ZH.md)、[联合差值数学合同](BOUNDED_CONTRAST_MATH_ZH.txt)及[均值顺序研究合同](MEAN_ORDER_RESEARCH_ZH.txt)为准；对应文献映射在 `literature_support/routes/`。本层不新增识别定理。

| 情况 | 对照行为 |
|---|---|
| 同目标、同 A4、同基础模型，只有同类界限扩大／顺序删除 | 标记 WEAKENING；两版独立复核后检查旧区间包含于新区间。 |
| 只有反向的限制增加 | 标记 STRENGTHENING，检查反向包含。 |
| 数学声明相同，仅来源说明重新记录 | 可记 SAME_DECLARED_CONSTRAINTS；仍要求两版分别审核。 |
| 界限一端放宽、一端收紧，或自身顺序换成同伴顺序 | COMPARED_UNORDERED；可列出两个已复核区间，不发布模型包含结论。 |
| 目标、评价人群、权重、比较方向、A4 数值、网络或结果期间变化 | NOT_COMPARABLE；不调用后端进行“放宽假设”比较。各版仍可通过原入口单独研究。 |
| 界限层次改变、跨路线，或未接入的路线 | NOT_COMPARABLE，不猜测等价性或蕴含关系。 |
| 任一版审核未完成或已撤回 | 不发布对照结论。 |
| 任一版为 INCOMPATIBLE，或没有复核通过的非空 sharp 区间 | COMPARISON_BLOCKED；保留每版原诊断／证书，不把空模型伪装成区间。 |

首版还保守要求 `question_slots` 的原文完全相同，不自动认定业务问题的同义改写等价。模型内容按当前类型化声明比较，不按案例名称或版本父子关系判断。改变原生审核证据会使旧对照计划失效，即使数值条件未变。

### 使用接口

```python
from cfm_id import research_session as work, research_versions as versions

before = work.restore("before_reviewed.json")
after = versions.fork_version(
    before, label="仅撤去同伴均值顺序", reason="单独研究该科学限制对识别区间的作用。",
    bundle=changed_public_bundle,
)
work.save(after, "after_pending.json")
```

原会话不变，新会话有独立 ID；审核和逐项决定全部清空。公开请求材料完全相同时，可以保留原读取稿，但这不继承科学批准。公开材料变化时清除读取稿，须重新读取。随后由原路线准备该版真实的 `after_submission`，分别完成业务语义和原生科学审核、`begin_item_review → decide_item → finalize_item_review`。修改原生条件时不能复用旧版原生审核摘要。

```python
# before_submission / after_submission 是各版的实际原生上下文与审核对象，
# 由独立审核流程提供；不是模型输出，也不是从对照报告反序列化的对象。
plan = versions.plan_comparison(
    before, after,
    before_submission=before_submission, after_submission=after_submission,
)
work.write_json("comparison_plan.json", plan)  # 仅预览差异，不批准、不求解。
report = versions.compare_versions(
    before, after, plan=plan,
    before_submission=before_submission, after_submission=after_submission,
    research_protocol_selected=True,
)
work.write_json("comparison_result.json", report)
```

计划绑定两份完整会话、审核和原生提交。修改计划后重新计算哈希也不能绕过检查；执行期间输入发生变化同样停止。每次对照重新执行并验证两版，而不是读取之前保存的 POINT／PARTIAL 标签。对照必须有两版逐项审核；旧的三个总项批准仍可用于原单会话兼容入口，但不足以进入新对照。

读报告时分开看两层：`results.before/after` 是每版在原合同下的结论与独立证书；顶层 `conclusion` 是这一次允许发布的区间对照。`both_results_independently_replayed=True` 不独自意味着区间可比较，例如已认证的不相容证明。模型包含来自本层精确声明检查，**不声称又有一个独立包含关系证明器**。

命令行可以先分出新文件；最终对照仍通过上述 Python API 提供原生上下文：

```powershell
python -m cfm_id.research_session_cli fork-version --session before_reviewed.json --label "只放宽界限" --reason "单独研究界限假设对结果的影响。" --output after_pending.json
# 有新公开材料时另加 --bundle changed_public.json；输出不得覆盖旧文件。
```

父版本指纹仅用于追溯，不是数字签名、现实审批认证或跨离线副本的全局撤销。

### 三组可复现的离线对照

以下都是明确声明的合成研究条件，读取稿和审核由独立夹具提供，**不是新的 LLM 读取准确率结果，也不是从试点数据自动推断出的假设**。例子复用当前已支持的网络干扰模型：

| 相同业务目标 | 逐版只改变的条件 | 实际识别区间 |
|---|---|---|
| 四个合作小组：全员用辅助系统，减全员不用的平均完成率 | 全部潜在结果条件均值界限依次为 $[1/2,1/2]$、$[1/4,3/4]$、$[0,1]$；原试点固定两组使用，A4 支持单元均值始终为 $1/2$ | $[0,0]\rightarrow[-1/2,1/2]\rightarrow[-1,1]$ |
| 七个星形合作小组：全员用系统时的平均完成率 | 仅中心组均值界限按上面三档扩大；其他节点界限及 A4 不变 | $[1/2,1/2]\rightarrow[13/28,15/28]\rightarrow[3/7,4/7]$ |
| 四个合作小组：全员用减全员不用 | 从自身和同伴均值均不下降，到仅自身均值不下降，再到两项均不采用；A4 与界限不变 | $[1/5,1]\rightarrow[-1/5,1]\rightarrow[-1,1]$ |

第一组最后的 $[-1,1]$ 是二元结果差值的完整逻辑范围，说明此目标未获得比逻辑范围更窄的信息。软件仍返回 PARTIAL，而不是 UNSUPPORTED；也不把这一个目标的例子扩大为一般非识别定理。三组共九个独立审核版本、六次相邻对照，每次均走原求解器和独立复核。

### 接入真实 LLM 读取的受控验收

`examples.research_condition_reading_reference` 提供四份普通语言条件说明：同时拟采用自身与同伴条件、只采用自身条件、明确不采用两项条件、尚未决定同伴条件。业务目标保持相同。`cases()` 在调用前生成公开材料与独立合成参考；发给模型的只能是 `work.prepare_request(work.start(lane, bundle))`，不能发送 `fixture`、`reference`、预期状态或审核记录。

取得实际模型 JSON 后，`assess(case, actual_reply)` 分开检查完整条件语义、目标、原抽签事实和引用，再走原逐项审核与数学链。`prepare_session(case, actual_reply, parent=old_session)` 可将通过核对的实际读取接入上述版本对照；它保留原回答，不补值、不替换错误字段。这里的批准只来自明确的合成参考协议，不能将该函数用作真实业务的自动科学审核者。

“尚未决定”须保留为缺项并追问，不能按“明确不采用”求一个更宽区间。模型把它误读成已提出条件时，即使结构合法，也应记录语义失败并停止独立审核。统计要分别报告请求是否成功、JSON／Schema、语义与来源、预期分支、独立重放和版本对照；失败保留在预定分母中。一个业务的几份条件版本通过，不等于一般用户问题的准确率，也不证明 A4 或科学假设真实成立。

追问也按当前读取的声明性质区分：采用意向不明时，问“拟采用、明确不采用，还是尚未决定”；只有被读取为观察关系时才提示观察不能替代科学假设。问题标明对象及本人／同伴轴，两个轴都缺项时分别列出。追问先请用户核对原材料，不能把候选缺项当成原文必然缺项，也不能把答复“拟采用”当成科学批准。

对于仅报告观察的材料，涉及假设层级或试点外范围的后续问题以“若另拟提出科学条件”为前提。保留等待补充状态，不要求用户把观察数据转换成假设。已经明确拟采用、只是适用范围未知的条件，则直接追问其适用范围。

跨业务参考见 `examples.research_condition_transfer_reference`：链式冷链站点、评价指定子集；星形仓配门店、评价单店；另含仅报告观察和条件适用范围未定的负例。它复用同一读取、审核和对照接口。合成审核依据完整语义与当前审核状态，不依据 `expected_state`；预期 POINT／PARTIAL／NEEDS_INPUT 标签只用于事后评分，不能用预期答案来决定是否调用后端。

## 命令行

在源码根目录运行，所有输出使用新文件名：

```powershell
python -m cfm_id.research_session_cli new --lane DAG_CLASSICAL_FRONTDOOR --bundle public.json --output session0.json
python -m cfm_id.research_session_cli request --session session0.json --output request.json
# 由外部受控模型调用产生实际 reply.json；本 CLI 不调用 API。
python -m cfm_id.research_session_cli candidate --session session0.json --candidate reply.json --output session1.json
python -m cfm_id.research_session_cli inspect --session session1.json --output inspection.json
python -m cfm_id.research_session_cli plan --session session1.json --output clarification.json
```

独立审核者使用 inspection 中的原生待审核表准备 reading_review.json 和 science_review.json。
推荐用逐项审核；工作表不生成这些原生批准：

```powershell
python -m cfm_id.research_session_cli review-open-dag --session session1.json --reading-review reading_review.json --science-review science_review.json --output items0.json
python -m cfm_id.research_session_cli review-items --session items0.json --output checklist0.json
# change0.json 是上述 decide_item 参数对象；一次提交一条决定。
python -m cfm_id.research_session_cli review-decide --session items0.json --review change0.json --output items1.json
# 每次重新导出工作表并审核下一条，直到全部接受。
# finalize.json 只含 expected_review_sha256、reviewer、evidence。
python -m cfm_id.research_session_cli review-finalize --session items_complete.json --review finalize.json --output session2.json
python -m cfm_id.research_session_cli submit-dag --session session2.json --reading-review reading_review.json --science-review science_review.json --select-research-protocol --output result.json
```

网络／均值顺序用 Python `begin_item_review` 提供原生对象并保存后，同样可以用 `review-items` / `review-decide` / `review-finalize` 查看、修改和撤回。最终执行仍由 Python 调用方提供原生上下文。本次提供的是 API 与离线文件／CLI 工作流，尚未制作审核网页。

下面的总项审核仅为旧会话兼容；未开启逐项审核的旧会话可继续使用：

```powershell
python -m cfm_id.research_session_cli worksheet --session session1.json --reading-review reading_review.json --science-review science_review.json --output worksheet.json
# 审核者独立填写 session_review.json，仅包含 SessionReview 字段；不把整个工作表当成批准。
python -m cfm_id.research_session_cli review --session session1.json --review session_review.json --output session2.json
python -m cfm_id.research_session_cli submit-dag --session session2.json --reading-review reading_review.json --science-review science_review.json --select-research-protocol --output result.json
```

外层 SessionReview 字段为 binding_sha256、native_submission_sha256、reviewer、evidence、decisions，及可选的 item_review_sha256；存在逐项清单时必须绑定其当前摘要。
decisions 必须恰好包含 business_target_and_sources、population_information、scientific_assumptions。
未知或不接受条件时填 PENDING 或 REJECTED。外层接受不能覆盖原生审核的 PENDING / REJECTED。

## 结果约定

只读取顶层 `state`、`mathematical_claim`、`certificate`、`independent_replay` 判断本次发布结论。
`native_inspection` / `native_result` 保留诊断，不能从其中绕过顶层阻断提取认证结果。
网络原生 CORE_POINT 在外层记为 POINT，逐问题目标指纹及泛函不改变；原生状态保留在诊断中。
原有 READING_REVIEW_REQUIRED 表示读取合同未通过，在会话层记为 CHECK_BLOCKED，不视为等待批准。
缺项、不支持、拒绝审核和证明失败不发布数学结论。UNSUPPORTED 仍不代表一般数学非识别。

当前所有结果 `production_admission=False`、`estimation_handoff_allowed=False`。
网络发表前与原生已审核问题重新求解／重放并核对完整证明摘要；另外两类重新检查原生证据与公开结论。
无论成功失败，本层都不生成真实业务的科学审批。

## 离线验收与扩展

```powershell
python -m pytest tests_gateway/test_research_session.py -q
python -m pytest tests_gateway/test_research_item_review.py -q
python -m pytest tests_gateway/test_research_policy_session.py -q
python -m pytest tests_gateway/test_research_versions.py -q
python -m pytest tests_gateway/test_research_condition_reading.py -q
python -m pytest tests_gateway/test_research_condition_transfer.py -q
python -m examples.research_session_reference --allow-synthetic-reviews --output outputs/session_acceptance
python -m examples.research_item_review_reference --allow-synthetic-reviews --output outputs/item_review_acceptance
python -m examples.research_policy_session_reference --allow-synthetic-reviews --output outputs/policy_session_acceptance
python -m examples.research_condition_versions_reference --allow-synthetic-reviews --output outputs/condition_versions_acceptance
```

参考程序明确使用独立合成夹具，走真实数学后端与证书验证；不属于新 LLM 准确率实验。
该程序在 `examples`，通用会话与适配代码不导入它，不按题号选择答案。

新增 lane 应补：公开材料边界、原生请求与候选检查、独立审核摘要、原生提交、公开结论与证据核对、正负例及会话失效测试。
接入逐项审核还要在 `cfm_id.review_items.checklist` 明确列出该路线自己的声明、来源和适用范围，覆盖“未采用”条件、撤回、过期和原生拒绝的测试；不能只新增一个统一“同意科学假设”的开关。
固定政策的四条薄适配集中在 `cfm_id.session_policy_routes`，供扩展时参考：请求与预览、精确原生字段、纯数据审核快照、逐项条目、原生提交、公开结论的独立复核。原数学实现位于既有模块；适配器不重新推导识别公式或界限。
接入新的条件对照时，另需列清固定目标、A4 和基础模型字段，给出明确的模型包含依据，并测试非嵌套条件、冗余条件、模型不相容、旧审核失效和证书／展示不一致。不要用区间宽度、自动删除未批准条件或 LLM 的判断替代这一检查。
使用自己的数学合同与验证器，不强行共享不同模型的假设或证明类型。后续可以逐条纳入其他已有业务入口，再研究新的数学路线。
