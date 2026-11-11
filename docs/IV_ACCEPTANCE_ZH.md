# IV 研究接口：运行与验收

**当前开放结构化研究接口，尚未开放 IV 自由文本自动入口或网页。** 未执行真实模型全链路验收，合成测试不计作 LLM 成绩。

## 可运行的检查

在仓库根目录、安装项目依赖后运行：

```bash
python -B -m examples.iv_demo
python -B -m pytest -q tests/test_iv_task4.py tests_gateway/test_iv_research_route.py tests_gateway/test_research_route_entry.py tests_gateway/test_capability_registry.py
```

`examples.iv_demo` 直接展示数学后端；`examples.iv_research_fixture` 提供明确标记的合成问题和合成审核，不能将这些审核用于真实研究。

实际研究使用 `cfm_id.iv_research.prepare(problem)` 取得待审项目，分别完成读取审核与科学条件审核后调用 `submit(problem, review=..., research_protocol_selected=True)`。同一研究合同也可经 `research_route_catalog` 的登记接口执行。未审核、过期或被拒绝的记录不授权计算。

涉及来源目录时使用 `cfm_id_llm.iv_reading.inspect_candidate` 和 `submit_reviewed`。输入是 `problem` 与 `source_catalog`；目录须覆盖已声明来源，并提供 URI、摘要和定位。此接口只检查结构与绑定，不自动核查文章真实性或理解原文。

## 必须明确的内容

- Z 是工具/资格，D 是实际处理，Y 是二元结果；三者各自的 0/1 编码。
- 目标为顺从者 LATE 或全体 ATE，均按 Y(1)-Y(0) 定义；总体范围和结果时期明确。
- 八个总体条件概率及来源，不能用一份有限台账擅自代替总体分布。
- 工具独立性、排除限制、一致性与二元结果、无干扰、工具正支持，以及单调性模型选择；科学决定由研究者审核。

记录未定/拒绝的条件后保留停止结果，不为通过而补假设。新目标、新数据、新科学条件均需重审。

## 以后怎样验收自然语言入口

`examples/iv_business_materials.py` 保存四份合成业务原文，供后续候选入口研究：LATE 正例、ATE 界限、缺少排除限制、条件矛盾。它们不是当前已跑通的网页示例。

待目标交接、研究结构分派和网页审核补齐后，再使用当前推荐 Prompt/Skill 和真实模型请求。`examples/iv_model_call.py` 只是通用的单次请求记录工具，不意味着自动 IV 链路已连接。

每题保留原材料、实际请求与模型原答、读取/科学审核、停止原因或最终证书。首答、复查与人工修订分开；禁止人工补齐后冒充模型首答成功。无需追求所有模型 100% 或大量新增测试。
