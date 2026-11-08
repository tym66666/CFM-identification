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
      paper_extract.md
      actual_outputs.json
      run_record.md
      review_teacher.md
  tools/
    validate_cases.py
  registry.json
  README.md
```

## 三条硬规则

1. `public/` 只放业务问题、协议、数据字典和附件，**不能放参考答案、公式、目标指纹或预期状态**。
2. `research_only/` 放参考答案、原文摘录、实际输出和复核记录，**不能作为模型输入**。
3. 论文参考、软件预期、实际运行必须分开记录：

```text
paper_reference    论文在什么条件下给出什么公式/界
software_expected  当前仓库应该输出什么
actual_run         系统实际输出了什么
```

## 当前案例

- `LIT-NET-01`：Aronow & Samii (2017) N60 网络案例，三个目标：直接、溢出、局部总效应。
  - 状态：结构化运行完成；原题三个 POINT，缺条件版 `NEEDS_INPUT`，目标变化版反向溢出 POINT。
  - 运行性质：`api_calls=0`，显式合成审核，不调用 LLM。
  - 复核：`PENDING_TEACHER`。

- `LIT-IV-01`：Imbens & Angrist (1994) 培训资格 LATE 案例。
  - 状态：论文参考完成；当前仓库没有 IV 读取器/数学后端，三个版本均如实记为 `UNSUPPORTED`。
  - 运行性质：`api_calls=0`，只做能力目录检查，没有伪造 IV 求解。
  - 复核：`PENDING_TEACHER`。

- `LIT-DAG-01`：Pearl (1995) 后门准则案例。
  - 状态：原题 POINT，调整集合 `["资深员工"]`，证书重放通过；缺图条件版 `NEEDS_INPUT`；控制治疗后中介版 `UNSUPPORTED`。
  - 运行性质：`api_calls=0`，显式合成审核，不调用 LLM。
  - 复核：`PENDING_TEACHER`。

## 新增案例的最小步骤

1. 在 `literature_support/cases/` 写来源卡和案例说明。
2. 在 `public/` 写三个版本的业务材料与 manifest。
3. 在 `research_only/` 写参考答案、原文摘录、运行记录和复核表。
4. 在 `registry.json` 登记。
5. 运行 `python evaluation/literature_cases/tools/validate_cases.py`。
6. 实际运行三个版本，补运行记录。
7. 交老师复核后再标 `ACCEPTED`。
