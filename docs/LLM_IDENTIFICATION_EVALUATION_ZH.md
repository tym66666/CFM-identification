# CFM-ID Gateway 用真实 LLM 检查「听懂业务」与「数学识别」

## 0. 结论先说

这一版增加的是**可重复的评测工具**，不是新 Identification theorem，也不是更大的 LLM Agent。

评测两个问题：

- **A 业务理解（30 题）**：能否准确提取因果目标、assignment 设计、A4 信息粒度？何时应该询问而不是猜测？
- **B 候选识别推理（16 题）**：在目标、A4、A5 被固定后，LLM 会给出什么 POINT / NOT_POINT / UNDETERMINED 候选推导？会不会偷加假设、把四臂均值当成完整政策值？

离线 fixture 测试验证程序自己运行正常，**不代表任何真实 LLM 模型的正确率**。真正的因果公式、观测等价反例必须由数学审阅者核验。LLM 候选始终是 `LLM_UNVERIFIED`，不能移交 Estimation。

## 1. 正式 API 与数学库没有变化

- 继续保留 v0.1 Formulator、v0.2 Reviewer/Core Port 和 v0.3 Candidate Reasoner。
- 不修改任何 CFM-ID Identification Library 的 v2.x/v3 源码。
- B 阶段使用**测试专用的固定数学问题 + 虚构审核记录 + 模拟 UNSUPPORTED**，只是为了独立测试 LLM 数学推理，并**不**表明真正的 R1a/R1b/R2 不支持这些问题。
- 线上真实 Core 接入及认证状态仍是未来计划。

## 2. 使用前先查看所有题目，不会向外发送数据

```bash
python -m pip install -e .
python -m evaluation.real_benchmark --dry-run
python -m evaluation.math_oracles
```

所有题目均为人为编写的**合成业务文本**，没有真实公司的客户资料。源文件是 `evaluation/network_benchmark.json`，包含独立维护的参考标签和数学解释。**调用大模型时绝不向模型发送 `reference` 参考答案字段**（测试中有防泄漏用例）。

## 3. 完全离线检查（不调用云端 LLM）

```bash
python -m evaluation.real_benchmark \
  --provider fixtures \
  --output /tmp/cfm_v04_offline.json \
  --adjudication-template /tmp/cfm_v04_blank_reviews.json
```

预期：30 个业务模拟回复的 schema 审查通过、16 个候选模拟回复通过 v0.3 的审计。

请特别注意：**业务问题审查状态的参考一致性为 27/30，而不是 30/30**。其中 F17、F18、F23 触发了 v0.1 的粗粒度 exposure 要求；这说明早期规范化门禁可能过度要求 exposure mapping。例如 F17 明确指定固定其余人的处理，数学上不必把这个目标重新定义成 design-standardized exposure contrast。这里没有为了让测试结果好看而修改参考答案。详情见第 7 节。

生成的模拟候选表达式来源于题库参考答案，仅用于通路测试；它们不代表“LLM 推理出正确公式”。

## 4. 真正运行一个模型（需要自己配置凭证，并明确同意外传合成案例）

环境中只有你自己配置了 `CFM_ID_LLM_API_KEY` / `OPENAI_API_KEY` 才会访问 API。没有密钥时程序安全退出，不会偷偷发起在线请求。

先少量试跑 **业务理解**：

```bash
export CFM_ID_LLM_API_KEY='YOUR_KEY'
python -m evaluation.real_benchmark \
  --stage formulation \
  --provider openai-chat --model YOUR_JSON_CAPABLE_MODEL \
  --max-cases 5 --allow-external \
  --output /tmp/cfm_v04_live_formulation.json
```

再少量试跑 **数学候选推理**：

```bash
python -m evaluation.real_benchmark \
  --stage candidate \
  --provider openai-chat --model YOUR_JSON_CAPABLE_MODEL \
  --max-cases 5 --allow-external \
  --output /tmp/cfm_v04_live_candidate.json \
  --adjudication-template /tmp/cfm_v04_candidate_math_reviews.json
```

可以使用 `--case-id C06` 或 `--case-id F01` 只测某个题目。全量测试必须显式指定 `--all-cases`，或者设置 `--max-cases`；这样不至于误操作批量产生 API 成本。可用 `--pause-seconds`、`--timeout`、`--base-url` 调整。提供商采用 v0.1 已实现的 Chat-Completions JSON 兼容接口，不承诺与所有模型端点天然兼容。**切勿上传真实敏感业务文本、密钥或用户数据到公开仓库**。

附：如果希望给导师看直观概览，可运行：

```bash
python -m evaluation.render_report \
  --report /tmp/cfm_v04_offline.json \
  --output /tmp/cfm_v04_overview.html
```

离线示例页面会突出说明它**不是在线模型准确率**。

## 5. 哪些指标可以自动算？

**A 阶段**：target 类型、assignment 类型、A4 类型是否匹配；是否应该澄清；是否在 assignment 未知时捏造随机化、在 A4 只有样本时捏造总体观测律。它们是语义字段匹配率，不是数学定理准确率。

**B 阶段**：输出是否通过固定 v0.3 schema/安全审查；候选 POINT/NOT_POINT/UNDETERMINED 的标签是否与参考吻合；额外假设有没有按要求单列；`LLM_UNVERIFIED` 是否始终保留。

**绝不自动宣称**：公式已被证明、反例的观察等价已被验证、Sharp bounds 已被计算、Policy 值已经估计、PFN 可靠。即使标签全对，也不代表数学推导全部正确。

## 6. 数学审查的实际流程

1. 运行 `--stage candidate`，保存 `/tmp/cfm_v04_live_candidate.json` 和 `--adjudication-template` 指向的空白文件。
2. 对每个候选，把数学推导交给**两位不同的实际审阅者**，分别填写六项：目标是否保持、A5 是否被偷加、A4 是否被强化、A6/支持是否核对、结论是否正确、公式或观测等价反例是否有效。
3. 每项填 `PASS`、`FAIL`、`UNCERTAIN`；不要把模型自己写的验证说明当作人类审查。
4. 对每个案例复制一份审查记录，让两名审阅者使用不同 `reviewer_id`。如果只有一人审查，该题不计入“双人审查完成数”。
5. 填写后运行：

```bash
python -m evaluation.score_reviews \
  --run /tmp/cfm_v04_live_candidate.json \
  --reviews /tmp/cfm_v04_candidate_math_reviews.json \
  --output /tmp/cfm_v04_review_summary.json
```

审查文件绑定这一次运行内容的 SHA；换了模型、Prompt、题库或某条输出，旧记录不能继续复用。**人工审查也不等于自动定理认证**。

## 7. 真实暴露出的 规范化局限

这套评测有意保留三项“旧门禁比参考需求更严格”的案例：

- F17：目标明确为保持所有其他人的处理不变的直接效应，仍要求 exposure mapping。
- F18：跨期总效应并不自动要求把动态干预压缩成某个邻居 exposure。
- F23：两阶段高低饱和度设计已说明业务暴露含义，但现有 fixture / schema 并没有把它映射到一个标准 g_i。

**此处是评测发现，不代表旧版的数学 theorem 错误。** 因为这三个都只是 LLM 草稿阶段，建议未来根据严格 target 语义细化门禁，而不是为了测试立即重构 schemas。

## 8. 参考数学检查

`python -m evaluation.math_oracles` 提供 8 组 N=4 精确算术，覆盖固定配额支持、R2 签名支持、加权 arm、四臂均值不能反推完整政策值、观察性混杂反例、零 propensity、设计标准化与固定他人对比的区别、iid 完整政策支持。这些是局部构造/反例，**不是全部 16 题的自动定理验证**。

## 9. 与当前项目的关系

v0.4 的“真实模型评测准备”可以独立于数学 Identification Library 迭代。后续若 v3 完成，将 Gateway 的 Core Port 适配到最新的严格库即可；此次评测数据、人工打分与模型输出仍可作为独立评测层保留。优先根据真实错误案例决定新的 Prompt 或数学适配需求，不应凭 Mock 结果盲目增加新 family。
