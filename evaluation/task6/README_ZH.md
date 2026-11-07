# 任务6：LLM业务理解对照评测

当前状态（2026-11-08）：已有12情境、24材料、开发集64次及留出集32次真实A0记录；完成离线收尾汇总。现有审阅记录包含AI辅助预审，尚无可核对的研究者独立审核记录。全链路验收状态以实际审核及执行记录为准。

## 先看交付结果

- [收尾报告](results/20261105/任务6收尾报告.md)：实验、分层指标、错误归因、调用成本及配置建议。
- [机器汇总](results/20261105/summary.json)、[失败清单](results/20261105/failures.csv)。
- [冻结配置](results/20261105/experiment_config.json)、[Skill快照](results/20261105/Skill_snapshot.md)、[受限证据哈希](results/20261105/evidence_hashes.json)。
- [代码审查与待办](docs/任务6代码审查与待办.md)、[GitHub上传指南](docs/GitHub上传指南.md)、[提交说明草稿](docs/PR说明.md)。

开发集格式通过：基线28/32、候选29/32；留出集：基线13/16、候选15/16。格式通过不代表语义或识别正确。开发集run 7的候选文件缺失，但已从对应快照单独恢复解析后的候选；该条仍保留在全部尝试的分母中，详情见代码审查。

N01已有一次单独事实读取，后续停在FACT_SOURCE_REVIEW_REJECTED，未调用数学后端。保持默认配置，尚无足够证据支持修改默认。

## 离线复现

从仓库根目录运行，输出目录须不存在：

```powershell
python -m unittest discover -s evaluation/task6/tests -v
python -m evaluation.task6.scripts.closeout --output outputs/task6_closeout_recheck
```

closeout只用标准库，读取本机outputs/task6_dev_final_002、task6_holdout_final_001、task6_n01_chain/full，不调用模型。公开包不含私有原始请求/回答，独立复算需获得受限原始输出。原始实验与审核文件均未覆盖。

## 文件与验收

materials为24份自拟业务输入；references为待独立审读的参考草稿；scripts为调用、评分、事实台账和离线收尾工具；tests为离线契约检查；results为本次公开汇总。单例链路工具为scripts/n01_fullchain.py，默认不执行调用；其fact-call子命令会联网，不属于本次离线收尾步骤。

下一步由研究者审核参考和语义结果，并依据实际执行更新台账；人工修订回答应与首答分开统计。已查看的留出题不得再次称为全新未见题。

历史工具用法见docs/初始工作包说明_历史版本.md，其中“未执行API”等描述是最初打包时状态，当前状态以本文件和收尾报告为准。两方案同时更改Prompt和Schema/解析合同，不声称测出Skill单因素净效应。不修改数学Core或科学审批规则。

2026-11-06修复缺项评分及全链路未审核分母，并提供可重复的快照恢复脚本；详细口径见代码审查。
