# 任务 2 总报告

## 1. 交付范围

- 12 个文献/数学情境；
- 每个情境 3 个版本：原题、缺条件、目标/条件变化；
- 来源卡、公开业务材料、隔离参考答案、运行记录、老师复核表；
- 4 个 holdout；
- 案例校验工具和单元测试。

## 2. 状态汇总

### 完整结构化运行

- `LIT-NET-01`：POINT ×3；缺条件 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-02`：疫苗 POINT；缺第一阶段排除 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-03`：PARTIAL `[3/7,4/7]`；缺模型 `NEEDS_INPUT`；额外限制 `ADAPTER_NOT_CONNECTED`。
- `LIT-NET-04`：PARTIAL `[1/5,1]`；缺同伴顺序 `NEEDS_INPUT`；单对象 POINT `1/5`。
- `LIT-NET-05`：校园邀请 POINT；缺设计 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-06`：示范农户 POINT；缺概率 `NEEDS_INPUT`；换政策 POINT。
- `LIT-DAG-01`：后门 POINT；缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED`。
- `LIT-DAG-02`：前门 POINT；缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`（holdout）。

以上均为 `api_calls=0`，显式合成审核，不是 LLM 准确率。

### 历史保存运行（holdout）

- `LIT-NET-07`：观察性网络 POINT；缺交换性 `NEEDS_INPUT`；反向 POINT。

原题来自历史 demo 保存运行；改动版刻意未运行，以保持 holdout。

### 当前软件未支持

- `LIT-NET-08`：Auto-G，三个版本 `UNSUPPORTED`。
- `LIT-IV-01`：LATE，三个版本 `UNSUPPORTED`。
- `LIT-IV-02`：Balke–Pearl ATE bounds，三个版本 `UNSUPPORTED`。

均保存能力检查，没有伪造 IV/Auto-G 结果。

## 2.5 LLM 评测底座

- `benchmark/cases.jsonl`：36 条公开输入，不含答案；
- `research_only/benchmark/references.jsonl`：36 条参考答案索引；
- `tools/export_benchmark.py` / `score_benchmark.py`：导出与评分；
- API Key 不进仓库，评分分开 development / holdout。

## 3. Holdout

- `LIT-NET-07`
- `LIT-NET-08`
- `LIT-IV-02`
- `LIT-DAG-02`

共 4/12，满足至少 1/3 的要求。参考答案已冻结。

holdout 范围是“开发 holdout”：不用于调材料；部分来源材料在 demo 历史中存在，因此不是对仓库历史的盲测。

## 4. 运行与校验

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
```

实际结果：

- `validate_cases.py`：`errors: []`；
- 13 项任务 2 单元测试通过；
- 全仓库 quick：`110 passed`；
- 全仓库 chain：`1086 passed`；
- 12 个案例、4 个 holdout、public 无参考答案。

## 5. 主要边界

- `LIT-NET-07` 的改动版尚未实际运行，作为 holdout 保留；
- 当前没有真实 LLM 首答准确率；
- `UNSUPPORTED` 不等于不可识别；
- 论文参考与软件结果分开；
- sharp 只相对于声明的有限模型；
- 老师复核全部为 `PENDING_TEACHER`。

## 6. 后续

1. 老师复核 12 个案例；
2. 最终评测时再运行 `LIT-NET-07` 的 holdout；
3. 真实 LLM 读取实验由任务 6 单独负责；
4. 最终 PR 前再跑 full 套件和安装检查；quick/chain 已通过。
