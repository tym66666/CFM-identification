# Gateway 测试、真实性和安全边界

## 核验范围

- `python -m unittest discover -s tests -p 'test_*.py' -v`：结构校验、状态禁止越权、逐字原文证据、A4 误标提示、分配歧义、Mock 隔离、HTTP 错误脱敏、JSON 模式响应、CLI 文本/JSON 输出。
- `python -m evaluation.run_mock_benchmark`：7 个**手工编写答案**的测试工件，包括中文/英文、模糊 half assignment、明确 Bernoulli、complete randomization policy、缺变量、观测性 spillover、完整理论信息算子声明。
- 这个 benchmark **不测真实 LLM 准确度**，只测 Mock 回放、contract 和用例一致性。若要报告 LLM 的业务覆盖率，需未来调用真实模型并人工核对参考答案。

## 主要风险及缓解

1. **LLM 编造字段或证据**：禁止额外字段；非空值必须引用 `source_id` 和原文连续片段；不匹配直接抛出 `DraftValidationError`。但正确引用不能保证逻辑蕴涵。
2. **假设被擅自认证**：schema 只允许 PROPOSED/UNRESOLVED；其他值 hard fail。
3. **把有限样本当成总体信息**：A4 拆开 sample description 与 population operator，误从 T/Y 字段宣称完整律时添加阻断警告；规则只是启发式，不能保证捕捉全部语义造假。
4. **半数随机分配设计歧义**：没有明确独立/固定配额依据时标注阻断问题；正则启发式存在漏报/误报，需要真实数据评估。
5. **错误识别结论下传**：v0.1 没有 POINT 字段、verifier、EstimationRequest；恒定输出 `NOT_PERFORMED`、`handoff_allowed=false`。
6. **提示注入**：业务原文单独用 JSON 标记为数据；程序只接受 schema 候选，不执行文档指令。无法保证外部模型不会受提示注入影响；本地校验仍是必要边界。
7. **数据外传**：选择 `--provider openai-chat` 才能联网；调用前需用户自行脱敏并遵循数据政策。API Key 从环境变量读取，HTTP 异常不回显响应体。
8. **模型不兼容或内容拒答**：当前 Chat JSON mode Provider 非通用：新模型可能只支持 Responses API 或不支持 `json_object`；发生错误会拒绝而非静默输出假数据。
9. **来源真实性**：user-provided study protocol 可以伪造。源码只能验证引用存在，不验证实验真实执行或数据来源可信。

## 下一阶段需要额外采集的指标

真实模型人工核查的 target extraction、design disambiguation、A4 hallucination、A5 unsafe promotion、校验失败率、多语言、成本与延迟、模型与 prompt 版本变化敏感性。与 v0.2 正式路由成功率分别报告。
