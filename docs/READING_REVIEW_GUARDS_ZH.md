# A0 原文复查与重读变化审核

业务材料齐全、模型却读错时，用户不应被要求改写成规范化 JSON。系统保留原文和实际回答，由独立审核指出疑点，再明确发起一次读取。新回答也可能退步，因此重新调用成功与接受新回答是两个步骤。

本功能属于读取和审核层，不改变数学 Core、Estimation 或 Policy，不自动判断自然语言为真，不授予科学假设许可。

| 环节 | 入口 | 作用 |
|---|---|---|
| A0 业务复查 | `intake_reading_revision.prepare_recheck` | 无需选择网络、DAG 或定理，对默认 compact A0 的实际候选定位复查 |
| 专门事实复查 | `fact_reading_revision.prepare_recheck` | 复用网络固定政策和短来源 DAG 合同 |
| 新旧候选变化审核 | `reading_change_review` | 展示全部字段差异，逐项与原文及保留条件核对 |
| 后续识别 | 原有 dispatch / case / native 接口 | 原有业务、科学与数学审核仍必须完成 |

## A0 复查接口

`prepare_recheck(intake, authority=...)` 返回反馈工作表，不调用模型。工作表绑定当前材料、完整候选、此前轮次和请求，包含 JSON Pointer 字段位置与原文目录。根路径 `""` 可用于结构不完整的旧候选。

审核者填写 `intake-reading-feedback-1` 记录，包含 `binding_sha256`、`authority`、`reviewer`、`evidence` 和非空 `issues`。每个 issue 使用 `field_path`、`kind`、`source_ids`、`reason`；语义反馈类型为 `OMITTED_OR_MISREAD`、`POSSIBLE_DUPLICATION` 或 `UNSUPPORTED_ADDITION`。不接收替代字段值或期望识别结论。

格式反馈可使用 `WIRE_FORMAT_ERROR`，但路径必须出现在工作表的 `format_issues` 中。诊断复用当前引用解码、扩展投影和Compact解析器，只提供错误位置、类型码和模型类型定义中的合法枚举；没有原候选值、自由报错文本或审核者提供的替换值。只有显式选择格式反馈才将诊断加入模型请求。它是有限辅助诊断，不能替代全部Schema、引用和语义检查；扩展错误未能细定位时仍被原解析器拒绝，诊断为空不能视为通过。

再次调用并提供反馈，返回新 intake：原文不变，旧候选和反馈存入 `reading_revision`，当前候选清空，请求重新绑定。模型只收到原材料、旧候选和位置/类型/原文编号，不收到审核者理由、身份、科学批准或金标准。最多三轮，每轮必须提供本轮反馈；无自动调用或自动重试。

默认 compact A0 支持此流程。历史 canonical A0 的普通读取与检查点继续兼容；canonical 重读明确拒绝，避免混用引用协议。

```python
from cfm_id import business_intake as intake
from cfm_id.intake_reading_revision import prepare_recheck, review_changes

worksheet = prepare_recheck(current_intake)
# 以下两个审核记录由独立对照原文的审核环节填写，不由候选自批。
next_intake = prepare_recheck(current_intake, feedback=independent_feedback)
request = intake.prepare_request(next_intake)
# 外部调用器经明确授权调用一次，并保存原始回复 raw。
received = intake.receive_candidate(
    next_intake, raw, request_sha256=request["request_sha256"]
)
inspection = intake.inspect(received)
# 若出现 reading_change_worksheet，逐项审核后保存。
reviewed = review_changes(received, independent_change_review)
```

CLI：`business_intake_cli recheck` 无 `--feedback` 时输出工作表，有 `--feedback` 时输出新检查点。默认权限标签为 `EXTERNAL_RESEARCH_REVIEW`，合成测试须显式选择 `--authority SYNTHETIC_TEST`。然后使用原有 `request`、`candidate`、`inspect` 命令。`review-changes --intake ... --review ... --output ...` 保存审核记录。所有命令本身均不调用 API。

## 审核全部字段变化

不论反馈点名哪个字段，程序比较完整旧候选与新候选。新增、删除、数值或布尔值变化、引用变化都保留；仅忽略事实读取每轮更新的 `reference_context`。不做同义匹配，不把 false 与 0、缺失与 null 当作相等。列表重排也不能绕过审核。

工作表逐项给出 `before_present`、`after_present`、`before`、`after`。`reading-change-review-1` 要求对全部差异填写 `ACCEPTED`、`REJECTED` 或 `PENDING`、理由和原文编号，并包含本轮绑定、审核者、证据说明和权限标签。

A0 的待定审核可以后续修订；再次调用 `review_changes` 会保留上一份审核及检查点摘要，形成新的本地状态，原查询批准随之失效。修订审核不会修改模型候选或再次调用 API。

- 未提供完整变化审核：`REVIEW_REQUIRED`，不生成可执行的方法计划。
- 任一变化被原文审核拒绝：`READING_RECHECK_REQUIRED`，保留新旧候选，不替模型改字段。
- 审核过期、来源不存在、跨案例复用：阻断。
- 全部变化接受：仅允许继续原有业务、事实和科学审核，不等于识别通过。
- 没有变化：不要求空变化审核；原有语义和科学审核仍保留，不能把错误旧回答当作正确。

例如，单调性正文仍在，但“无额外耦合条件”从 false 变成 true，工作表会展示这一变化，即使反馈仅点名额外限制字段。程序不靠关键字判断单调性的含义；审核者须对照原文拒绝矛盾变化。这是审核门，不是自动语义验证器或数学证明器。

事实读取的 `inspect_methods`、`execute` 和整题提交新增可选 `change_review`。有字段变化的重读候选需要此记录，然后重新获得计划、读取和科学审核。CLI 使用 `--change-review`。它与准备新请求的 `--feedback`、裁决未决备注的 `--note-review` 职责不同。

## 兼容性与验收

没有重读的 intake 序列化不增加两个空扩展字段；普通首读 Prompt、请求、既有检查点及批准绑定保持原格式。更改原材料会清空当前候选、复查与变化审核，将此前历史保留在本地事件中，再从原文重新开始。

回归见 `tests_gateway/test_reading_review_guards.py`、`tests_gateway/test_fact_reading_revision.py`，固定框架清单 S18。真实输出与调用证据保存在代码包外，不能用离线手工候选成绩代替模型准确率。

## 先判断为什么停下：用户缺项还是读取错误

目标未定不总是模型漏读。例：用户已说“五仓全启用、只评价两个仓”，但还没决定平均率还是总量。模型忠实保留 UNKNOWN 后，应补充的只是结果口径，不必重新问已经确定的政策和评价对象。反之，用户已经明确单仓准时概率而模型漏填，应复查原文，不让用户重复说明。

`intake_stop_review` 对当前 compact A0 的缺项和复查信号提供独立来源审核；它只调整停止原因，没有放行选项。

| 审核结论 | 后续状态 | 意义 |
|---|---|---|
| MATERIAL_GAP | 单题 NEEDS_INPUT；入口 BUSINESS_CLARIFICATION_REQUIRED | 对照原文确认所列目标坐标缺失，显示相应补问 |
| READING_ERROR | READING_RECHECK_REQUIRED | 原文已有信息却漏读，或有错误/矛盾；先走已有显式复查流程 |
| PENDING | REVIEW_REQUIRED | 尚未完成来源审核；不生成后续事实请求 |

判断由独立审核者作出，程序不自动证明自然语言含义。字段为 UNKNOWN 本身不能证明原文缺项。工作表展示原目标、缺项、完整复查信号、原审核动作和来源编号；审核记录必须覆盖所有待审核子问题，逐项填写理由及原文来源。它不接受替换答案、ACCEPTED、科学批准或识别结论。

在查询分派时，若调用者已经提交逐字段/查询审核，该记录先验证：拒绝、待审、过期、跨题或伪造的记录不能被同时存在的目标缺项掩盖。已确认的读取拒绝返回CHECK_BLOCKED；待审返回REVIEW_REQUIRED。已经生成的compact目标补问保留为`deferred_clarification_questions`，原候选和停止审核记录不被修改。没有提交审核时沿用原停止结果；审核全部接受后仍执行原缺项和格式门禁，不能把真实缺项变为可执行问题。

只有现有目标坐标缺失且没有其他读取冲突时，才允许 MATERIAL_GAP。UNRESOLVED 类别可伴随真实缺项，但 OTHER、非法 NOT_APPLICABLE、意图矛盾、共同事实格式错误等不能被降级成纯用户缺项；旧审核中的 A0_FORMULATOR 错误即使被整体缺项状态遮住，也仍然阻断该选项。

```python
from cfm_id import business_intake
from cfm_id.intake_stop_review import prepare_review, review_stop

worksheet = prepare_review(current_intake)["stop_worksheet"]
# independent_stop_review 来自对照原文的独立审核，不来自被测模型自批。
reviewed_intake = review_stop(current_intake, independent_stop_review)
plan = business_intake.clarification_plan(reviewed_intake)
```

合成验收须在上述两个函数明确传入 `authority='SYNTHETIC_TEST'`。真实流程默认 EXTERNAL_RESEARCH_REVIEW；这些是审核权限标签及内容绑定，不提供外部身份认证系统。

CLI不联网：

```powershell
python -m cfm_id.business_intake_cli review-stop --intake intake.json --output stop_worksheet.json
python -m cfm_id.business_intake_cli review-stop --intake intake.json --review independent_stop_review.json --output reviewed_intake.json
python -m cfm_id.business_intake_cli plan --intake reviewed_intake.json --output clarification_plan.json
```

默认处理已有 compact 缺项/复查信号；也可显式指定下述部分已知目标字段。格式不合法、来源绑定失效、待审核的重读变化继续使用原有阻断流程。对表面完整但语义错误的 STATED 字段仍由原来的独立意图/来源审核拒绝，此处不是新的完整语义检测器。无需复查的目标不会默认新增此项审核。

### 部分已知目标与批量答复

有些字段并非全空，例如“下一轮名额有限”已说明任务，但还没有名额数量。审核者可向 `intake_stop_review.prepare_review` 提供 `target_fields={"q3":["policy_assignment","aggregation"]}`，逐问检查这些字段是否确有缺项；原候选不会被程序改成 UNKNOWN，原先读错的部分仍须拒绝。字段范围、原文、候选和审核记录共同绑定；不允许给旧记录换范围继续用。

在 `inline-unified-contract-7` 中，本店效应的追问区分其他对象保持某种安排还是按规则平均，同伴效应的追问区分同伴两端与本店共同状态，政策选择询问候选范围、预算和目标而不要求先提供最优名单。比较方向本身确未决定时也可进行来源审核；非法运算、无效引用或尚未审核的重读变化仍先阻断。上述问题由程序的目标字段模板提出，不能称为模型自主发现并验证了条件。

审核状态仍只有 PENDING、MATERIAL_GAP、READING_ERROR。将某项确认成材料缺项并不接受其他字段，也不提供 A4/A5 许可。完整意图与来源审核、科学审核和证书检查仍分别执行。

推荐使用新的 `business_intake.append_replies(intake, plan, replies)`，一次追加同一版本下的多条答复。`replies` 为当前 clarification_id 到纯文本的映射；每项必须来自当前计划中已由来源审核确认的缺项。可只答其中部分，未答问题不会自动填值。任一编号、内容或计划不合规时，整批不写入。答复各自成为独立来源；助手的问题与原目标概括只作非证据上下文。材料更新后旧候选、重读/停止审核和旧请求绑定失效，重新读取并审核。历史单条 `append_reply` 接口保留。

```powershell
python -m cfm_id.business_intake_cli review-stop --intake intake.json --target-fields target_fields.json --output stop_worksheet.json
python -m cfm_id.business_intake_cli review-stop --intake intake.json --review independent_stop_review.json --output reviewed_intake.json
python -m cfm_id.business_intake_cli plan --intake reviewed_intake.json --output questions.json
python -m cfm_id.business_intake_cli replies --intake reviewed_intake.json --plan questions.json --replies-json replies.json --output next_intake.json
```

`target_fields.json` 只定义待核对字段范围，`independent_stop_review.json` 由审核者根据工作表和原文形成；上述命令不生成审批结论。引用绑定缺失或不匹配现可定位到 `/reference_context`；系统仍要求模型在显式重读中返回当前绑定，不自动补写或挪用旧绑定。

审核保存在 intake 的可选 `reading_stop_review`，原始候选与请求不改。旧检查点不增加空字段，原有请求及审核绑定保持兼容。确认缺项后从已知缺项字段生成问题，不重复泛问已经确定的目标；判为读取错误或待审的该子问题暂不生成用户补问。未涉及的其他子问题保留原有处理流程。

收到新候选、补充/修订材料、显式重读、更换后续读取配置或修订变化审核时，该停止审核清空并留历史；用户答复才进入新的可引用材料。停止审核自身的修订保留此前记录（最多20份），并使旧补问计划和查询批准失效。它不会把审核理由或决定发送给模型，不自动触发API。真实缺项补齐后仍须重新读取并完成意图、事实、科学审核和数学重放。

定向回归在 `tests_gateway/test_intake_stop_review.py`，纳入固定清单 S25。覆盖多题隔离、来源/候选绑定、非法降级、待审与修订、补问后的新材料、保存恢复、旧批准失效及CLI。真实返回的离线流程复验另存于源码包外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`，不增加模型准确率的样本数。

## 可选的 A0 短来源选择编号

`business_intake.start(case, a0_reference_contract='compact-source-selectors-1')` 在 compact 读取中启用短编号。CLI 创建会话可加 `--a0-reference-contract compact-source-selectors-1`。默认仍使用原格式，历史请求、检查点及证书不迁移、不重写；canonical 格式不能使用此选项。

每项 claim 的 refs 选择 `s0001` 等目录编号，顶层须原样返回一次 `reference_context`。程序将编号精确还原到原来的来源片段；只改变引用编码，不改正文、字段含义、UNKNOWN、目标、假设或识别方法。模型原始回答另行保留。错号、缺少/错误上下文、额外字段与重复引用继续拒绝，无模糊匹配或编辑距离修复。

上下文使用完整 SHA-256，绑定业务材料、原请求语义合同以及会话/材料修订标识；显式重读另绑定完整复查历史。补充答复或修订材料后生成新上下文；每轮显式重读也更新。接收时仍须匹配请求摘要，因此不能将旧候选或其他会话的同名短编号直接复用。该绑定用于检测错配，不是签名、身份认证或自然语言正确性的证明。

停止审核、重读定位及变化审核使用该会话当前的短来源目录。用户真实答复仍进入独立来源；审核理由不进入可引用材料。引用存在不代表语义正确，完整意图/来源审核和后续科学审核不能省略。只有请求上下文改变而其他字段完全相同时，不算业务语义变化；任何真实字段/引用变化仍按原规则逐项审核。

回归见 `tests_gateway/test_compact_short_refs.py` 与固定清单 S26。此选项先作为独立实验协议，是否成为默认须依据冻结的真实模型对照及负例结果，不能用手工夹具通过率替代模型准确率。

## 可选的 A0 响应区域完整性

`business_intake.start(case, a0_response_contract='explicit-sections-1')` 要求 compact 回答显式包含顶层 `common`、`queries` 及每个查询的 `semantics`。CLI 可加 `--a0-response-contract explicit-sections-1`。这是开发端输出协议配置，不是让业务用户选择识别路线；与长/短来源编号相互独立。历史默认不变，canonical 不能使用此配置。

请求 Schema 声明必填区域，接收时在原解析器补默认值前检查。遗漏 `common` 或任一查询的 `semantics` 返回 `A0_RESPONSE_SECTION_MISSING`，诊断只给固定字段路径，不补对象、不自动调用模型。类型错误仍由既有 Schema 检查拒绝。原始回答始终保留。

区域内部的未知字段依然允许 `UNKNOWN` 或省略；空区域的结构合法不代表业务完整，已知事实被遗漏、目标口径缺失和科学条件不足仍走既有阻断与独立审核。该配置不验证自然语言含义，不把格式通过当成识别资格。将来若推广为默认，应显式迁移请求合同，不能重写旧检查点或复用旧审核。

回归见 `tests_gateway/test_compact_sections.py`、清单 S27。覆盖长短编号、第二个查询缺区、未知与空区、旧绑定失效、显式重读、来源否决和科学审核后既有 POINT 独立重放。

## 字段职责、值状态与引用的逐项审核

在显式选用 `inline-unified-contract-3` 时，首次读取 Schema、复查的 `field_role_constraints` 与逐字段工作表来自同一份源码定义。复查定位只携带字段路径、问题类别和原文编号；职责说明来自代码，不来自审核者填写的自由文本理由。审核理由、替换答案和预期识别结论仍不发给模型。此修改避免模型只看到“这一字段可能读错”，却不知道当前字段究竟应记录什么；不意味着会自动纠错或自动接受新答案。

开发端可选的 `explicit-field-roles-1` 响应协议继承上述区域检查，并把共享字段定义直接提供给模型。它没有新增自动语义判断：模型即使引用真实原文，也可能把缺失说明填成已知值、混淆字段职责或写反差值方向。已有逐项审核仍须独立完成，协议变化使旧请求和审核失效。新旧格式的实际对照以[框架验收](FRAMEWORK_ACCEPTANCE_ZH.md)为准。

已有三项query review可使用[逐字段审核接口](BUSINESS_FIELD_CONTRACT_ZH.md)生成：先对每个共有事实和选定目标字段分别核对field_role、value_state、source_coverage，再形成原审核决定。原始候选不改，任何内层否决/待审不能被外层通过覆盖；实际引用与审核者另外找到的来源分开展示。没有自动语义分类器或科学许可。缺项目标与重读等已有阻断保留，旧简表及其请求保持兼容。
