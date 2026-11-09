# 文献案例 LLM 评测底座

这里不调用任何 API，只提供可复跑的导出与评分接口。

## 文件

```text
cases.jsonl                          36 条公开输入（模型可见，不含答案）
schema.json                          单次尝试的 JSONL 字段
../research_only/benchmark/references.jsonl   36 条参考答案索引（禁止给模型）
../tools/export_benchmark.py         重新导出 cases/references
../tools/score_benchmark.py          对记录的 attempts 评分
```

## 使用

```powershell
python evaluation/literature_cases/tools/export_benchmark.py
python evaluation/literature_cases/tools/score_benchmark.py --attempts attempts.jsonl --output score.json
```

`attempts.jsonl` 每行至少包含：

```json
{"case_id":"LIT-NET-01","variant":"original","run_id":"r1","model":"deepseek","prompt_version":"v1","transport_complete":true,"contract_passed":true,"query_count":3,"semantic_passed":true,"expected_decision_passed":true,"point_present":true,"point_replay_passed":true}
```

评分分开报告：

- 传输失败；
- JSON/合同失败；
- 语义读取失败；
- 预期识别状态失败；
- 证书重放失败；
- PASS。

并分开统计 development 与 holdout。  
API Key 只走环境变量或受控本地配置，不写入仓库。
