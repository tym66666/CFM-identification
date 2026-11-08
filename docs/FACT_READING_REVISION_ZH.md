# 原文定位的事实重读

补充：重读候选若有字段变化，当前流程先要求 [完整变化审核](READING_REVIEW_GUARDS_ZH.md)，通过后才生成原有计划审核。下面的执行示例在出现 `reading_change_worksheet` 时需再提供 `change_review`；CLI 对应 `--change-review`。这是接受新回答的审核，不是准备复查请求的 feedback。

原材料明确说明“每轮恰好两家、所有组合等概率”，候选却填成 OTHER，这属于读取错误。不能因此告诉用户数学库不支持这类设计，也不能在后台替候选填入正确分类。`fact_reading_revision` 将这类问题接为一轮明确、可追溯的新读取。

流程是：原回答 → 独立核对字段与原文 → 新的完整读取请求 → 新回答重新检查 → 必要的计划、语义和科学审核 → 原数学求解与重放。它是读取生命周期的一部分，不增加用户选择识别路线的菜单。

## 反馈是什么

审核人提交 `ReadingFeedback`，绑定当前子问题、读取请求、原材料、意图审核和完整候选。每个问题包含：

- `field_path`：原 JSON 中的字段或父对象位置，使用 JSON Pointer；空字符串表示整个对象，适合关键字段被完全遗漏的情况。
- `kind`：`OMITTED_OR_MISREAD`、`POSSIBLE_DUPLICATION`、`UNSUPPORTED_ADDITION`；事实读取的类型错误可明确选择 `WIRE_FORMAT_ERROR`。
- `source_ids`：当前工作表中可核对的原文位置。
- `reason`：独立核查理由，留在本地记录中。

“可能重复”不是删除命令。原文可能有真正的额外限制，模型必须重新核对全部字段并输出完整候选。程序不修改旧 JSON，不填写新值，不合并约束，也不替科学审核批准任何条件。

真实缺项仍走补充材料流程；读取错误先走重读。没有证据证明原文缺项时，不把模型的漏填直接转化为要求用户补充的事实。备注本身的实质分类仍可使用 [备注审核](READING_NOTE_REVIEW_ZH.md)，不能用备注放行代替新候选。

## 模型实际看到什么

新请求包含原问题、原材料和原 Schema，并附上上一份候选、出错字段、错误类别和对应的原文短编号。审核人身份、自由文本审核理由、科学批准和标准答案不进入模型请求。旧回答和复查定位明确标为非事实来源。

显式使用 `network-source-selections-information-4` 时，初读、审核工作表与复查共用 [公开字段定义](../cfm_id_llm/network_field_contract.py)。复查按字段路径挑选有关定义，放在 `public_field_constraints`；内容仅来自源码中的当前合同，与具体题目的标准答案无关。定义不是新增事实，不能作为引用，也不自动把未知状态改成已知。旧事实协议不新增这个键，旧请求保持逐字节兼容。

每轮更新 `reference_context` 和请求摘要。旧回答不能套上新请求摘要继续用；新回答必须在新来源上下文中重新生成。更换来源、子问题、原 Prompt、先前候选或反馈，都会使对应旧绑定失效。未使用重读的普通请求保持原格式不变。

最新显式选项 `network-source-selections-outcome-1` 沿用同一流程，另共享 [结果尺度与独立声明定义](../cfm_id_llm/network_outcome_contract.py)。它明确 0/1 无量纲结果、原文连续量尺度和相邻声明各自的未知状态；未知单位仍不能由审核人补入。真实配送站复查曾只撤回重复界限段落，随后须完成全部变化审核、来源审核、科学审核和证书重放，不能只看被点出的那一个字段。时长未知负例中的另一处重复仍未修复，反馈准备完成不等于已经调用或读取成功。

`reading_revision` 保存所有旧候选和独立反馈；`reading_revision_receipt` 给出轮次、内容摘要以及 `candidate_modified=false`、`scientific_approval=false`、`automatic_retry=false`。整题结果同样保留记录。

每条链最多三轮，每轮均须明确的新反馈和调用。模块自身不联网、不读取密钥、不自动重试。达到上限时返回 `EXPLICIT_RECHECK_ROUND_LIMIT`，需人工诊断，不能无休止重试到出现有利答案。

`network-source-selections-remainder-1` 进一步把剩余信息和真实缺项的定义接入同一流程，代码入口为 [network_remainder_contract.py](../cfm_id_llm/network_remainder_contract.py)。定位一个重复段落时，模型仍须核查其中是否夹有尚未表达的真实条件；程序不删除它。反馈只说明待核对的位置与类别，不意味着审核人已经证明重复。最新实际复查中，结果定义修正还伴随两处引用和一处标点变化，全部逐项审核后才继续；不能只检查最初指出的字段。

哈希证明内容绑定，不证明审核人的身份或判断正确。字段和原文编号合法也不证明二者语义一致，仍需独立实质复核。本机制不保证 LLM 下一次一定读对。

## Python 接口

```python
from cfm_id import business_dispatch as dispatch
from cfm_id.fact_reading_revision import prepare_recheck

pending = prepare_recheck(
    intake, "q1", query_review=query_review,
    candidate=actual_old_reply, request_sha256=current_request_sha256,
    reading_revision=current_revision,  # 第一轮为 None
)
# 根据 pending["feedback_worksheet"] 独立填写反馈记录；不自动批准。
next_reader = prepare_recheck(
    intake, "q1", query_review=query_review,
    candidate=actual_old_reply, request_sha256=current_request_sha256,
    reading_revision=current_revision, feedback=independent_feedback,
)
# 确认 READY_TO_READ 后，由外部已授权 Provider 调用 next_reader["request"]。
# 下一份实际回答保持原样：
plan = dispatch.inspect_methods(
    intake, "q1", query_review=query_review,
    candidate=actual_new_reply,
    request_sha256=next_reader["request_sha256"],
    reading_revision=next_reader["reading_revision"],
)
```

上述新请求不授予执行许可。形成可审核的方法计划后，仍需独立审核；`dispatch.execute` 和整题提交均携带相同 `reading_revision`。旧计划不能作为新一轮批准。若新候选还存在误读或真实缺项，继续保留停止状态及原因。

当前支持共同网络固定政策读取和短来源格式的 DAG 读取。两者共享反馈及记录机制，各自保留事实合同和数学方法。旧长来源格式不会被自动转换。

## 类型格式诊断

`feedback_worksheet.format_issues` 由当前读取器的固定 Pydantic 类型合同生成，列出出错位置、错误类型；枚举错误另列合同允许的文字值。它不检查原文是否支持候选，不提供识别结果，也不是完整的请求 JSON Schema 验证。未知读取器或类型校验异常时不生成这种提示，既有原文定位重读仍可使用。

只有审核人明确选用 `WIRE_FORMAT_ERROR`，且位置确实属于本轮诊断时，程序才在新请求附上对应 `wire_format_constraints`。调用者不能自填合法枚举、替换值或标准答案。格式提示是协议元数据；`source_ids` 仍须指定相关原材料供重新核对含义，不能把协议元数据引用为业务事实。缺少的必填字段可以按诊断位置定位，无需先在候选中造出该字段。

仅使用原有三类原文反馈时，新请求不附加类型提示；默认首次请求不变。A0 的类型格式重读尚未接入，不能把专用事实读取器的诊断套用到 A0。格式修正后，全部字段的变化仍先经独立审核，再进行新的科学审核和原数学重放。回归 `test_wire_format_recheck`（固定清单 S21）包含真实额外条件、完整性未知以及修好格式同时改坏其他字段的否决测试。

显式使用 `network-source-selections-information-1` 时，同一流程还可提供代码生成的三项[信息字段组合规则](NETWORK_INFORMATION_FIELDS_ZH.md)。规则来自与内部解析共用的固定定义，不是审核人输入的替换值；旧配置的诊断和请求保持不变。样本标签与总体格子冲突时，模型必须按原文重新选择表示，不能为过校验升级样本性质。

## CLI

```powershell
python -m cfm_id.business_dispatch_cli recheck-plan --intake intake.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate actual_old_reply.json --output recheck_worksheet.json
```

填写独立反馈后，再运行同一命令并增加 `--feedback feedback.json`，使用新的输出文件，例如 `next_reader.json`。取其中 `reading_revision` 字段保存为单独 JSON；后续 `reader-plan`、`method-plan` 和 `execute` 通过 `--reading-revision revision.json` 接收该记录。`--reader-plan` 要指向本轮完整的新请求记录，`--candidate` 要指向本轮实际回答。

所有 CLI 均离线运行、拒绝覆盖已有输出。格式拒绝、真实缺项、未接入限制、读取复查仍是不同原因；最终是否可识别由数学模块决定。

回归文件为 `tests_gateway/test_fact_reading_revision.py`，固定框架清单 S17 覆盖来源与审核绑定、旧候选保存、无标准答案泄漏、轮次限制、网络／DAG 复用、单问 CLI 和整题执行。
