# 共同业务入口：原随机设计下的局部直接与同伴效应

本入口连接已有 R1a 组合能力，不增加数学定理，不修改求解器或验证器。用户提交业务原问题；A0 与独立业务审核确认目标后，共同分派选择局部效应事实读取协议。用户不需要选择 R1a 或内部研究会话。

本轮实际正负例、失败和重读结果见接入验收记录（历史记录不随发布）。框架通过与模型首答准确率分别报告。

2026-10-30：可选读取格式保留 COUNT，并在原有可积数值均值 POINT 合同下调用 R1a；不增加密度、Poisson 或计数 PARTIAL 假设。[数学依据与适用边界](COUNT_LOCAL_MEAN_CONTRACT_ZH.md)、实际读取与重放验收（历史记录不随发布）另列。

## 业务问题及精确含义

示例原文保存在 `examples/network_effect_dispatch_reference.py`，包括完整门店和配送站材料、两个问题、实验分配说明、原始总体信息及研究条件。例如：

> 四家门店会相互调配员工。评价名单在抽签前固定为全部四家，对门店取等权平均。合作对象过半启用时，自己启用排班助手与自己未启用相比，本周顾客平均等待分钟数相差多少？前者减后者。
>
> 自己不启用时，合作对象过半启用与至多一半启用相比，平均等待分钟数相差多少？前者减后者。
>
> 两种比较都不固定其他对象的完整名单；在满足各端自身与同伴条件的安排中，按原试点抽签概率平均，不另外改变抽签规则。

最后一句是**目标定义**的一部分，不能仅凭“试点采用随机抽签”自动补上。局部状态相同的完整名单仍可能产生不同结果。本入口不默认暴露充分性，也不把这个目标改成全员启用与全员不启用的政策差值。

## 沿用的数学合同

给定处理前背景 \(W\)、固定网络和完整分配概率 \(q(z\mid W)\)，令

\[
\pi_i(a,e\mid W)=\sum_{z:z_i=a,\,g_i(z)=e}q(z\mid W).
\]

当该概率严格为正时，目标为

\[
\mu_i^q(a,e\mid W)=
\sum_{z:z_i=a,\,g_i(z)=e}
\frac{q(z\mid W)}{\pi_i(a,e\mid W)}E[Y_i(z)\mid W].
\]

在完整处理向量随机化、一致性等经独立审核的原生条件下，已有 R1a 给出

\[
\mu_i^q(a,e\mid W)=E[Y_i^{\mathrm{obs}}\mid T_i=a,g_i(T)=e,W].
\]

对抽签前固定的非空评价名单 \(S\)，当前桥接的是

\[
\theta_{\mathrm{direct}}=
\frac1{|S|}\sum_{i\in S}[\mu_i^q(a,e\mid W)-\mu_i^q(b,e\mid W)],\quad \{a,b\}=\{0,1\},
\]

\[
\theta_{\mathrm{spillover}}=
\frac1{|S|}\sum_{i\in S}[\mu_i^q(a,e_1\mid W)-\mu_i^q(a,e_0\mid W)].
\]

评价全体、指定子集或单个对象，都使用同一目标合同。名单不能由本轮实际中签情况决定。改变 \(q\) 会改变目标里的平均规则；不能把不同规则下的均值视为同一个量。

直接效应的两个方向均已接入。原生具名 `DIRECT` 合同仍严格表示 1 减 0；0 减 1 在业务适配器中编译为系数分别为 \(+1/|S|\)、\(-1/|S|\) 的 `ArmLinearTerm`，调用已有 `identify_verified_linear_target` 和 `replay_verified_composition`。不改数学 Core，不交换业务两端，也不把旧公式加负号冒充新证书。来源、全部非零项支持、目标系数和独立审核仍逐项检查。

反向直接效应返回 `network-local-effect-linear-evidence-1` 展示容器，`results[0]` 是实际原生单个线性组合证书摘要；它不是原生具名效应 bundle。`native_evidence` 保留实际 `VerifiedCompositionV18` 内容。正向直接效应和同伴效应的旧输出保持兼容。验收见反向目标与框架核查（历史记录不随发布）。

具体定义与既有证明链见 [R1a 组合合同](R1A_VERIFIED_TARGET_COMPOSITION_ZH.md)、`pfn_pipeline/identification_composition.py` 和 `pfn_pipeline/_internal/identification/randomized_network_arm.py`。这属于已有独立证书重放，不是新增形式证明助手级认证。

## 接入范围与独立审核

| 层次 | 当前范围／要求 |
|---|---|
| 网络 | 完整、处理前固定、简单无向网络；二元处理 |
| 分配 | D1–D6：独立抽签、总名额、两组名额、簇抽签、多组名额、两阶段名额混合；保留完整联合规律，边际比例不能代替 |
| 暴露 | E1–E5：严格多数、三档比例、固定核心同伴、多值人数、是否有人使用；定义本身不授予充分性假设 |
| 目标 | 原设计条件平均下的直接或同伴效应；固定评价名单，单对象或等权均值 |
| A4 | 一份已声明来源覆盖所需的全部对象与两端格子；支持 `NODE_ARM_MEANS`、`NODE_FULL_LAW`、`FULL_JOINT_LAW` |
| A5／基础条件 | 已知分配律、完整处理向量随机化、一致性、处理前固定网络、有限条件一阶矩，逐项独立审核；D6 额外审核第一阶段方案没有超出最终名单的直接结果影响 |
| 数学检查 | 实际正支持、原生目标及来源绑定、R1a 组合证书、独立重放 |
| 审核权限 | 当前仍仅 `SYNTHETIC_TEST` 研究合同；不发放生产或 Estimation 准入 |

LLM 可以读取原文“拟采用”科学条件，但不能自行批准。业务目标、读取事实、科学条件和方法计划分别审核；任一待定或拒绝都不能执行。显式重读保留旧回答，完整变更重新审核，旧批准失效。

A4 来源审核还必须确认信息对应同一原试点分配律、结果定义和背景；仅有相同对象名和状态标签不够。内容摘要和原生证明不能代替这项科学来源核对。

不会从批处理求出的格子倒推材料“已经提供”这些总体均值。若需要把多个互补来源联合起来，当前报告适配缺口；没有覆盖的格子保持缺失。零支持保持原生不适用结果，不自动补界限或触发 LLM 候选研究。

当前未连接：D1–D6/E1–E5 之外的设置、非等权总体、两端自身与暴露同时改变的局部总效应、多来源联合及额外科学约束。部分能力已有原生接口；本入口的限制不代表数学上不可识别。已接设计/暴露的参数、边界与测试见[统一接入说明](NETWORK_DESIGN_EXPOSURE_ENTRY_ZH.md)。

## 文件与协议边界

- `cfm_id_llm/network_effect_reading.py`：事实 Schema、原文编号和 Prompt；复用既有网络、设计、科学声明记录。
- `cfm_id_llm/source_coverage_contract.py`：公开字段与来源责任对应，生成请求前检查 Schema 漂移；只给引用说明，不证明语义正确或补引用。实际重复测试见[来源覆盖验收](NETWORK_EFFECT_SOURCE_COVERAGE_ZH.md)。
- `cfm_id/network_effect_dispatch.py`：目标坐标、适用范围、独立审核、原生编译和证据检查。
- `cfm_id/capability_registry.py`：直接效应和同伴效应共同登记到 `NETWORK_RANDOMIZED_EFFECT_FACTS`，方法为既有 `R1A_COMPOSITION`。
- `tests_gateway/test_network_effect_dispatch.py`：完整业务正负例、穷举分配对照、审核阻断、错证书及重读。

`effect_fact_contract=network-randomized-effect-reading-1` 是独立读取协议。历史 `network_fact_contract` 控制固定政策读取，不控制这份局部效应 Schema。旧政策均值、两政策差值和 DAG 请求保持各自合同。登记描述升级为 `identification-capability-registry-2`，用 `target_kinds` 列表表达同一读取协议可以接受多个目标；历史数学证书和研究目录协议不变。

## 本地复现

在子项目根目录、已经安装项目依赖的 Python 环境运行：

```powershell
python -m pytest tests_gateway/test_network_effect_dispatch.py tests_gateway/test_capability_registry.py tests_gateway/test_effect_source_coverage.py tests_gateway/test_effect_citation_order.py tests_gateway/test_effect_a4_scope.py -q
python -m examples.network_effect_dispatch_reference --allow-synthetic-reviews --output ./local_results/network_effect_reference
python -m evaluation.framework_acceptance --output ./local_results/framework_effect
```

两个输出目录必须是新目录。示例是人工标准答案和显式合成审核，API 调用为零，不能作为 LLM 准确率。实际模型测试必须保留首答、模型误读、独立审核和每次重读；真实科学假设的成立不能由上述测试证明。
