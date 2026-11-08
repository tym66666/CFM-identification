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
- `LIT-DAG-01`：后门 POINT；缺图 `NEEDS_INPUT`；控制中介 `UNSUPPORTED`。

以上均为 `api_calls=0`，显式合成审核，不是 LLM 准确率。

### 历史保存运行 + 参考改动版

- `LIT-NET-05`：校园邀请 POINT；缺设计 `NEEDS_INPUT`；反向 POINT。
- `LIT-NET-06`：示范农户 POINT；缺概率 `NEEDS_INPUT`；换政策 POINT。
- `LIT-NET-07`：观察性网络 POINT；缺交换性 `NEEDS_INPUT`；反向 POINT。
- `LIT-DAG-02`：前门 POINT；缺中介 `NEEDS_INPUT`；加直接边 `UNSUPPORTED`。

原题实际来自 2026-11-04 demo 保存运行；改动版目前为参考答案/预期，标为 `NOT_RUN`。

### 当前软件未支持

- `LIT-NET-08`：Auto-G，三个版本 `UNSUPPORTED`。
- `LIT-IV-01`：LATE，三个版本 `UNSUPPORTED`。
- `LIT-IV-02`：Balke–Pearl ATE bounds，三个版本 `UNSUPPORTED`。

均保存能力检查，没有伪造 IV/Auto-G 结果。

## 3. Holdout

- `LIT-NET-07`
- `LIT-NET-08`
- `LIT-IV-02`
- `LIT-DAG-02`

共 4/12，满足至少 1/3 的要求。参考答案已冻结。

## 4. 运行与校验

```powershell
.venv\Scripts\python evaluation/literature_cases/tools/validate_cases.py
.venv\Scripts\python -m unittest tests_gateway.test_literature_cases -v
```

预期：

- `errors: []`；
- 12 个案例；
- 4 个 holdout；
- public 无参考答案；
- manifest 文件齐全。

## 5. 主要边界

- `LIT-NET-05/06/07`、`LIT-DAG-02` 的改动版尚未实际运行；
- 当前没有真实 LLM 首答准确率；
- `UNSUPPORTED` 不等于不可识别；
- 论文参考与软件结果分开；
- sharp 只相对于声明的有限模型；
- 老师复核全部为 `PENDING_TEACHER`。

## 6. 后续

1. 老师复核 12 个案例；
2. 补跑 4 个 `NOT_RUN` 的改动版；
3. 真实 LLM 读取实验由任务 6 单独负责；
4. 最终 PR 前再跑完整测试和安装检查。
