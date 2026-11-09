# 任务 2：文献案例库说明

## 1. 范围

本目录实现任务 2 的文献案例库：

- 12 个情境；
- 每个情境包含原题、缺条件版、目标/条件变化版；
- 公开业务材料与隔离参考答案分离；
- 论文参考、软件预期、实际运行分开记录；
- 4 个 holdout。

## 2. 目录

```text
literature_support/cases/          来源卡、原文摘录、案例说明
evaluation/literature_cases/public/          公开业务材料
evaluation/literature_cases/research_only/   参考答案、实际输出、运行记录、复核表
evaluation/literature_cases/tools/           导出、运行、校验工具
evaluation/literature_cases/registry.json    案例登记
```

## 3. 12 个情境

| 编号 | 类型 | 论文/来源 | 原题状态 | 改动版 |
|---|---|---|---|---|
| LIT-NET-01 | 网络 | Aronow–Samii (2017) | POINT ×3 | 缺网络 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-02 | 网络 | Hudgens–Halloran (2008) | POINT | 缺第一阶段排除 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-03 | 网络 | Manski (2013) + 项目有限模型 | PARTIAL `[3/7,4/7]` | 缺模型 `NEEDS_INPUT`；额外限制 `ADAPTER_NOT_CONNECTED` |
| LIT-NET-04 | 网络 | Manski (2013) + 项目均值顺序模型 | PARTIAL `[1/5,1]` | 缺同伴顺序 `NEEDS_INPUT`；单对象 POINT `1/5` |
| LIT-NET-05 | 网络 | Paluck et al. (2016) / Aronow–Samii | POINT | 缺设计 `NEEDS_INPUT`；反向 POINT |
| LIT-NET-06 | 网络 | Beaman et al. (2021) | POINT | 缺概率 `NEEDS_INPUT`；换政策 POINT |
| LIT-NET-07 | 网络 | Forastiere et al. (2021) | POINT（holdout 历史保存） | 缺交换性 `NEEDS_INPUT`（holdout 未运行）；反向 POINT（holdout 未运行） |
| LIT-NET-08 | 网络 | Tchetgen et al. (2021) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-IV-01 | IV | Imbens–Angrist (1994) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-IV-02 | IV | Balke–Pearl (1997) | UNSUPPORTED | UNSUPPORTED；UNSUPPORTED |
| LIT-DAG-01 | DAG | Pearl (1995) 后门 | POINT | 缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED` |
| LIT-DAG-02 | DAG | Pearl (1995) 前门 | POINT | 缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`（holdout） |

## 4. Holdout

4 个 holdout：

- `LIT-NET-07` 观察性网络；
- `LIT-NET-08` Auto-G；
- `LIT-IV-02` Balke–Pearl ATE 界限；
- `LIT-DAG-02` 前门。

它们的参考答案已冻结，开发时不能用来调材料。

## 5. 运行性质

- `LIT-NET-01/02/03/04/05/06`、`LIT-DAG-01/02`：2026-11-08/09 结构化运行，`api_calls=0`，显式合成审核；
- `LIT-NET-07`：holdout，原题保留历史保存运行，改动版刻意未运行；
- `LIT-NET-08`、`LIT-IV-01/02`：当前软件无对应后端，全部 `UNSUPPORTED`，并保存能力检查；
- 本库不声称真实 LLM 首答准确率。

## 6. 复现

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
```

各结构化案例的运行脚本：

```text
evaluation/literature_cases/tools/run_lit_net_01.py
evaluation/literature_cases/tools/run_lit_net_02.py
evaluation/literature_cases/tools/run_lit_net_03.py
evaluation/literature_cases/tools/run_lit_net_04.py
evaluation/literature_cases/tools/run_lit_dag_01.py
```

## 7. 边界

- `UNSUPPORTED` 不是“已证明不可识别”；
- 样本不等于总体；
- 论文参考不等于软件结果；
- sharp 只相对于声明的有限模型；
- 合成案例不是论文数据复现；
- 老师复核通过前不能标成正式验收；
- `LIT-NET-07` 是 holdout，改动版未运行；最终评测时再跑。
