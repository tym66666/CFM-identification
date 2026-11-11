# 二元工具变量：当前交付范围

本次接纳 **LATE / ATE 数学能力、独立证书检查和显式研究接口**。IV 的自由文本自动分派和网页链路尚未开放；原有网络和 DAG 入口保持原行为。

## 代码在哪里

| 内容 | 位置 | 职责 |
|---|---|---|
| 模型、求解与验证 | `cfm_id/iv_types.py`、`iv_contract.py`、`iv_late_solver.py`、`iv_late_verify.py`、`iv_ate_solver.py`、`iv_ate_verify.py` | 二元 Z/D/Y，LATE 与 sharp ATE 界限；验证不调用优化器 |
| 研究合同与审核 | `cfm_id/iv_route_contract.py`、`iv_research.py`、`iv_research_adapter.py` | 读取审核和科学条件审核分开，绑定当前问题，再求解和重放 |
| 结构化来源检查 | `cfm_id_llm/iv_reading.py` | 接收明确的数学候选及来源目录；不理解自然语言，不生成审批 |
| 公共登记 | `cfm_id/capability_registry.py` | 只登记正式研究接口；不登记公共业务方法 |
| 数学与文献 | `docs/IV_MATH_ZH.md`、`IV_LITERATURE_MAPPING_ZH.md`、`literature_support/routes/binary_iv_late_ate.json` | 定理范围、自行推导、文献与阅读程度 |
| 示例与测试 | `examples/iv_demo.py`、`iv_research_fixture.py`、`tests/test_iv_task4.py`、`tests_gateway/test_iv_research_route.py` | 合成演示及审核、证书边界检查，不是实际 LLM 准确率 |

运行与验收见 [IV_ACCEPTANCE_ZH.md](IV_ACCEPTANCE_ZH.md)。研究登记不证明任何科学假设在现实中成立。审批记录的身份文字不等于身份认证。

## 当前支持及限制

- 给定完整精确总体条件分布 P(D,Y|Z)，二元工具、实际处理、结果；有限样本频数不能直接作为此总体输入。
- LATE 固定表示参加减不参加的顺从者平均效应，即 Y(1)-Y(0)。在已审核的单调模型内，先检查相容性，再计算比率；负效应合法。
- ATE 给出相对于所声明二元 IV 模型的 sharp 区间；是否施加处理单调性必须明确选择。
- 缺项、审核未定或拒绝、条件不相容、数值故障分别报告。证书在公开数值容差内重放，不属于形式证明系统。
- 不自动进入估计或策略，也不将 IV 与网络干扰模型组合。

## 后续自动入口工作

学生 PR 中的自动业务接入草稿保留在 Git 历史，当前 main 不启用该部分。启用前必须完成：

1. 保持用户比较方向、结果编码、评价范围与时期；不能将反向问题自动改成 Y(1)-Y(0)。
2. 用有原文依据的工具与实际处理区分研究结构，不能仅因用户问 ATE 就路由到 IV。
3. 接通网页的能力说明、逐项科学审核与结果展示，并确保原有网页仍能启动。
4. 用少量完整原文实际调用推荐 Prompt/Skill，分别保留首答、复查、审核及证书；缺条件和矛盾必须正确停止。

这几项未完成前，不声称 IV 自由文本端到端验收通过，不靠增加提示词或放宽审核替代接口工作。
