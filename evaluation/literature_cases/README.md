# 文献案例库（任务 2）

本目录保存“论文问题 → 业务材料 → 参考答案 → 运行记录”的案例库。

## 目录约定

```text
evaluation/literature_cases/
  public/
    LIT-<FAMILY>-<NN>/
      original/
      missing_condition/
      changed_target/
  research_only/
    LIT-<FAMILY>-<NN>/
      reference.json
      actual_outputs.json / structured_runs/
      run_record.md
      review_teacher.md
  benchmark/            公开 JSONL 与评分 schema
  tools/                导出、运行、校验、评分
  registry.json
  README.md
```

## 三条硬规则

1. `public/` 只放业务问题、协议、数据字典和附件，**不能放参考答案、公式、目标指纹或预期状态**。
2. `research_only/` 放参考答案、原文摘录、实际输出和复核记录，**不能作为模型输入**。
3. 论文参考、软件预期、实际运行必须分开记录。

## 当前案例（12 个）

| 案例 | 类型 | 状态 |
|---|---|---|
| `LIT-NET-01` | 网络 | 三个 POINT；缺条件 `NEEDS_INPUT`；反向 POINT |
| `LIT-NET-02` | 网络 | 疫苗 POINT；缺第一阶段排除 `NEEDS_INPUT`；反向 POINT |
| `LIT-NET-03` | 网络 | PARTIAL `[3/7,4/7]`；缺模型 `NEEDS_INPUT`；额外限制 `ADAPTER_NOT_CONNECTED` |
| `LIT-NET-04` | 网络 | PARTIAL `[1/5,1]`；缺同伴顺序 `NEEDS_INPUT`；单对象 POINT `1/5` |
| `LIT-NET-05` | 网络 | 校园邀请 POINT；缺设计 `NEEDS_INPUT`；反向 POINT |
| `LIT-NET-06` | 网络 | 示范农户 POINT；缺概率 `NEEDS_INPUT`；换政策 POINT |
| `LIT-NET-07` | 网络 | 观察性 POINT（历史保存）；缺交换性 `NEEDS_INPUT`（holdout，未运行）；反向 POINT（holdout，未运行） |
| `LIT-NET-08` | 网络 | Auto-G：三个版本均 `UNSUPPORTED`（holdout） |
| `LIT-IV-01` | IV | LATE：三个版本均 `UNSUPPORTED` |
| `LIT-IV-02` | IV | Balke–Pearl ATE 界限：三个版本均 `UNSUPPORTED`（holdout） |
| `LIT-DAG-01` | DAG | 后门 POINT；缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED` |
| `LIT-DAG-02` | DAG | 前门 POINT；缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`（holdout） |

## 说明

- `LIT-NET-01/02/03/04/05/06`、`LIT-DAG-01/02` 有完整结构化运行记录；
- `LIT-NET-07` 是 holdout，改动版刻意未运行；
- `LIT-NET-08`、`LIT-IV-02` 是 holdout，当前软件未支持，记录为 `UNSUPPORTED`；
- 所有老师复核状态均为 `PENDING_TEACHER`。

## 新增案例

1. 在 `literature_support/cases/` 写来源卡和案例说明。
2. 在 `public/` 写三个版本的业务材料与 manifest。
3. 在 `research_only/` 写参考答案、原文摘录、运行记录和复核表。
4. 在 `registry.json` 登记。
5. 运行 `python evaluation/literature_cases/tools/validate_cases.py`。
6. 实际运行或如实记录 `UNSUPPORTED`。
7. 交老师复核后再标 `ACCEPTED`。
