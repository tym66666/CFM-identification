# 任务 2 PR 描述

## 问题与最终行为

新增任务 2 文献案例库与可评测题库底座。

- 12 个文献/数学情境，覆盖网络、IV、DAG；
- 每个情境包含原题、缺条件版、目标/条件变化版，共 36 份公开材料；
- 4 个 development holdout；
- 参考答案、实际运行记录和老师复核表放在 `research_only/`；
- 新增 JSONL 评测清单、schema 和 scoring 工具。

## 数学与接口

- 不修改数学 Core；
- 新增的只是案例材料、参考答案、运行工具和测试；
- 每个案例区分：
  - `paper_reference`：论文给出什么；
  - `software_expected`：当前软件应该输出什么；
  - `actual_run`：实际输出了什么；
- `UNSUPPORTED` 不等于不可识别；
- 公开材料不包含目标指纹、证书或参考答案。

## 实际验证

- 案例库校验：

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
```

结果：`errors: []`，12 个案例，4 个 holdout。

- 任务 2 单元测试：

```powershell
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
```

结果：13 项通过。

- 全仓库 quick：

```powershell
.venv\Scripts\python scripts/check_framework.py --suite quick --output outputs/final_quick_20261111
```

结果：`110 passed`。

- 全仓库 chain：

```powershell
.venv\Scripts\python scripts/check_framework.py --suite chain --output outputs/final_chain_20261111
```

结果：`1086 passed`。

- 真实 LLM 首答/复查：未运行。任务书把 LLM 读取对照实验归任务 6；本 PR 只提供题库和评分底座。

## 未完成与边界

- 12 个案例仍是 `PENDING_TEACHER`，需要老师复核；
- 4 个 holdout 是 development holdout，不是对仓库历史的盲测；
- `LIT-NET-07` 的改动版作为 holdout 刻意未运行；
- `LIT-DAG-02` 的 `changed_target` 是 holdout 组的一部分；
- 全仓库 `full` 套件未运行；
- 安装/发布验收未在本 PR 中重复执行；
- 真实 API 调用、Prompt/Skill 对照实验不在此 PR 范围内。
