# Binary IV（LATE / ATE）开发说明

## 本次改动范围

本目录是对现有 CFM 仓库的增量提交，不是独立 Python 包。以主项目快照为基线应用增量补丁；公共模块采用差异合并，禁止整包覆盖；不得新增或覆盖 `cfm_id/__init__.py`、`pyproject.toml` 或其他公共配置。

- `cfm_id/iv_*`：二元工具变量输入合同、潜在响应类型模型、LATE/ATE 求解与独立验证。
- `cfm_id/capability_registry.py`、`cfm_id/research_route_catalog.py`：在现有研究路由注册表中登记 IV 路由。
- `cfm_id_llm/iv_fact_reading.py` 与 `cfm_id/iv_business_dispatch.py`：接入推荐A0、共同读取登记、来源审核、计划审核及独立证书流程；`iv_reading.py`仅保留显式结构化研究适配；读取结果不等于科学假设获批。
- `literature_support/routes/binary_iv_late_ate.json`：路线与文献依据映射。
- `examples/`、`tests/`、`tests_gateway/`：最小示例与回归测试。

## 本地测试

在仓库根目录执行：

```bash
python -m pytest -q tests/test_iv_task4.py tests_gateway/test_iv_research_route.py tests_gateway/test_research_route_entry.py tests_gateway/test_capability_registry.py
```

## 结论边界

- 二元结果变量的效应差范围为 `[-1, 1]`；负 LATE 不构成模型矛盾。
- 观测分布可行性、LATE 点识别、ATE 部分识别及科学假设审核是不同判断，不得互相替代。
- 求解器数值失败、输入缺失、审核未完成和已验证的约束矛盾必须使用不同停止状态。
- 路由注册仅表示代码可调用，不表示工具变量独立性、排除限制或单调性已被证明。

## 业务验收记录（提交前填写真实运行结果）

负责人要求从脱敏业务原文开始，使用仓库当前推荐的 Prompt / Skill 和实际审核流程，至少记录 LATE 正例、ATE 界限例，以及缺少关键条件或条件矛盾的负例。每个案例分别记录：

1. 脱敏输入材料及来源定位；
2. Prompt / Skill 名称与版本、运行命令；
3. 模型首答（原样保留）；
4. 人工复查意见及审核状态；
5. 最终结果；
6. 人工修正内容（单独记录，不覆盖模型首答）。

不得用合成 fixture 或单元测试结果冒充真实业务运行记录。当前代码包提供测试 fixture，但真实业务记录须按项目审核流程实际运行后补入。

详细运行步骤见 [IV_ACCEPTANCE_ZH.md](IV_ACCEPTANCE_ZH.md)。真实模型与人工审核尚未执行，不把合成测试称为最终业务验收。公共`__init__.py`、推荐reading.json和pyproject.toml保持主快照原样；仅两个既有测试元数据文件追加IV义务。
