# IV 从业务原文到审核结果的运行说明

目前未执行真实外部模型调用，也没有真实人工科学审核。合成测试、程序生成的待审核工作表和真实审核记录必须区分。

## 材料与预算

A：资格随机发放、实际参加及三个月二元结果，问因获得资格才参加者的效应。
B：同一来源与总体信息，问全体参加减全体不参加；单调性与不施加单调性各建明确版本、重新审核。
C：原文明确未确定排除限制，或只有有限记录，应追问并停止。
D：总体信息与已声明单调模型冲突，即使第一阶段正且Wald比值在合法范围仍须阻断并重放矛盾证据。

`examples/iv_business_materials.py` 提供上述四题的**合成原文**，不包含预先计算的答案。它不是脱敏真实业务。真实材料由研究者提供：原问、资格规则、参加及结果编码、观察时期、信息来源、总体范围和逐项假设声明；不能用完整台账自动声称总体分布已知。参考答案永远不进入请求。

建议四题各一次A0和事实首读，每阶段至多一次显式复查，最多16次；早停阶段不调用。传输失败独立计数，不自动换模型、参数或追加提示版本。

## 创建推荐请求

以下命令在合入本补丁的主项目根目录、同一Python环境执行，所有输出使用新文件。业务输入使用现有BusinessCase：`case_id, business_question, sources:[{source_id,text}], response_language`。运行前记录Git SHA、依赖版本和源码摘要。

```powershell
python -B -m cfm_id.project config
python -B -m cfm_id.project start --input case.json --output outputs/iv_run/A/start
```

该入口保持包内推荐JSON不变，实际加载`target-first-skill-1`及其Skill资源。本补丁增加LATE目标与字段说明，因此新请求摘要发生变化；旧回答和旧批准不能伪装成新请求。保留真实`request.json`及Skill清单，不手工拼提示词。

## 一次真实模型调用

`provider.json`只允许模型名、HTTPS服务地址、密钥**环境变量名**及非秘密预算参数。例如下面值需由本人实际配置，不能原样假装可用：

```json
{"model":"YOUR_ACTUAL_MODEL","base_url":"https://YOUR_AUTHORIZED_HOST/v1","api_key_env":"CFM_ID_LLM_API_KEY","max_tokens":4096,"timeout":60}
```

服务若要求`max_completion_tokens`，显式替换`max_tokens`，二者不能同时出现。此入口使用现有Chat兼容Provider，不假定任意模型都兼容；接口失败如实保存。凭据在本地进程环境配置，不发到聊天、不写入文件。

```powershell
python -B -m examples.iv_model_call --request outputs/iv_run/A/start/request.json --config provider.json --stage a0-first --output outputs/iv_run/A/a0_first --allow-model-call
python -B -m cfm_id.business_intake_cli candidate --intake outputs/iv_run/A/start/intake.json --request outputs/iv_run/A/start/request.json --candidate outputs/iv_run/A/a0_first/model_candidate.json --output outputs/iv_run/A/received.json
python -B -m cfm_id.business_intake_cli inspect --intake outputs/iv_run/A/received.json --output outputs/iv_run/A/reading_report.json
python -B -m cfm_id.business_field_review worksheet --intake outputs/iv_run/A/received.json --query q1 --output outputs/iv_run/A/a0_worksheet.json
```

`q1`必须对应实际目标。首答由最终文本observer在JSON解析前保存；非法JSON不修补。命令、上海时间起止、耗时、退出码、模型诊断分别保存。CLI不执行数学、不生成审核。

## 独立审核与事实读取

研究者填写逐字段工作表，使用`EXTERNAL_RESEARCH_REVIEW`，提供身份文字、证据和逐项理由；待定保持PENDING。再用`business_field_review submit --intake ... --query q1 --record ... --output ...`提交。将返回的`query_review`对象原样另存为`query_review.json`，不要把完整包装对象误作审核记录。

```powershell
python -B -m cfm_id.business_dispatch_cli reader-plan --intake outputs/iv_run/A/received.json --query q1 --query-review query_review.json --output reader_plan.json
python -B -m examples.iv_model_call --request reader_plan.json --config provider.json --stage fact-first --output outputs/iv_run/A/fact_first --allow-model-call
python -B -m cfm_id.business_dispatch_cli source-review-plan --intake outputs/iv_run/A/received.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate outputs/iv_run/A/fact_first/model_candidate.json --output source_worksheet.json
```

事实读取保留各项声明、未知或否定及本字段来源，另保留总体信息身份、Z/D/Y编码和单调模型选择。来源审核检查原文是否支持该读取，不批准科学真实性。整份材料完整性须单独核对，不能只审已填字段。

将真实来源审核存为`source_review.json`。`method-plan`与`execute`都必须传入同一来源审核：

```powershell
python -B -m cfm_id.business_dispatch_cli method-plan --intake outputs/iv_run/A/received.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate outputs/iv_run/A/fact_first/model_candidate.json --source-review source_review.json --output method_plan.json
```

计划中的`plan_worksheet`和`methods[0].native_worksheet`均只含PENDING。真实审核者分别填写计划审核与IV原生读取/科学审核。原生记录格式为`{"BINARY_IV_LATE_ATE": {"version":"binary-iv-research-1","problem_sha256":"工作表值","reading_review":...,"science_review":...}}`。两个子审核各含authority、reviewer、evidence、problem_sha256和完整decisions；记录内容必须来自实际审核，不能自动全部接受。

```powershell
python -B -m cfm_id.business_dispatch_cli execute --intake outputs/iv_run/A/received.json --query q1 --query-review query_review.json --reader-plan reader_plan.json --candidate outputs/iv_run/A/fact_first/model_candidate.json --source-review source_review.json --plan-review plan_review.json --native-reviews native_reviews.json --select-research-protocol --output final_result.json
```

未满足条件时按真实停止结果结束。执行器重新构建计划并核对绑定，不能提交旧结果作为许可证。LATE与ATE各自求解并独立重放，输出只在声明的二元无干扰模型内有效。

## 复查、修正与保存

A0复查使用`cfm_id.intake_reading_revision.prepare_recheck`；事实复查使用`business_dispatch_cli recheck-plan`或`cfm_id.fact_reading_revision.prepare_recheck`。先生成反馈工作表，审核人提供原文和字段位置后才产生新请求。事实重读的`reading_revision`必须沿reader-plan、method-plan、execute传递；变化需`change_review`，原来源/计划/科学批准失效。不要把参考答案或替换值传给模型。

人工直接修正另存`human_corrections.json`，记录旧值、新值、原文依据、理由、人员、时间；保留模型首答，修正后重新建立绑定并审核。不得将人工改过的JSON统计成模型首答或模型复查。

每题保留：原文和附件摘要、实际Prompt及Schema、配置及Skill哈希、首答原文和候选、格式/语义/来源报告、真实人工审核、发生过的模型复查、所有变化审核、最终结果/证书/重放、人工修正、命令和运行时间。未发生的步骤写NOT_PERFORMED，不生成假记录。合成回归与真实验收分目录、分统计。

## 本地验证

```powershell
python -B -m pytest -q tests/test_iv_task4.py tests_gateway/test_iv_research_route.py tests_gateway/test_iv_business.py
python -B scripts/check_framework.py --suite quick --output outputs/iv_checks/quick
python -B scripts/check_framework.py --suite chain --output outputs/iv_checks/chain
python -B scripts/check_framework.py --suite full --output outputs/iv_checks/full
python -B scripts/check_offline.py
```

这些是离线程序测试；通过不等于真实模型首读、现实假设或人工审核已通过。
