# 计数结果进入局部均值 POINT 的数学边界

此说明只覆盖已接通的原设计条件平均局部效应，不增加数学定理或求解器。业务结果保留 `COUNT`：非负整数次数。均值及均值差可以是非整数；不假设 Poisson 分布，也不假设计数变量存在连续密度。

## 目标与条件

固定处理前网络和研究背景 (W=w)。完整二元处理向量记为 (Z\in\{0,1\}^N)，其已知分配律为 (q(z\mid w))，同伴分组为 (E_i(z))。对局部状态 ((a,e)) 定义

\[
\mathcal Z_i(a,e)=\{z:z_i=a,E_i(z)=e\},\qquad
\pi_i(a,e\mid w)=\sum_{z\in\mathcal Z_i(a,e)}q(z\mid w)>0.
\]

本入口的目标是按**原设计在该局部事件下的条件分布**平均完整潜在结果：

\[
\mu_i^q(a,e\mid w)=
\sum_{z\in\mathcal Z_i(a,e)}
\frac{q(z\mid w)}{\pi_i(a,e\mid w)}
\mathbb E[Y_i(z)\mid W=w].
\]

需要独立审核完整分配与潜在结果独立（给定 (W)）、一致性，以及相关潜在结果绝对一阶矩有限。网络、评价名单和权重在分配前固定。A4 必须声明可用的总体观测信息并覆盖所需局部格子；有限样本本身不授予这个信息算子。当前共同入口仍限 D1/E1，不能把原生库更广的设计范围算作本入口已经接通。

## 原有均值定理为什么适用

由全概率公式、一致性和完整分配随机化，

\[
\begin{aligned}
\mathbb E[Y_i\mid Z_i=a,E_i(Z)=e,W=w]
&=\sum_{z\in\mathcal Z_i(a,e)}
\frac{q(z\mid w)}{\pi_i(a,e\mid w)}
\mathbb E[Y_i\mid Z=z,W=w]\\
&=\sum_{z\in\mathcal Z_i(a,e)}
\frac{q(z\mid w)}{\pi_i(a,e\mid w)}
\mathbb E[Y_i(z)\mid W=w]\\
&=\mu_i^q(a,e\mid w).
\end{aligned}
\]

这一步只用可积性，没有使用连续性。若每个 (Y_i(z)\in\mathbb N_0\subset\mathbb R)，相同恒等式仍然成立。随后按已审核的比较方向与权重作线性组合，例如直接减少量为

\[
\sum_{i\in P}w_i\{\mu_i^q(0,e\mid w)-\mu_i^q(1,e\mid w)\}.
\]

两端分别按各自事件下的原设计条件分布平均；这不是某个固定完整政策的效应，也没有从分组定义推断“同组所有完整处理安排具有相同均值”。不需要、也未自动授予暴露均值充分性。

## 程序怎样表达

- 业务候选和审核计划保留 `outcome_kind=COUNT`。原生均值合同的历史数值标签只有 `continuous/binary`；适配层将 COUNT 放入前者代表的可积实值模型，并明确附带 `outcome_domain_embedding`，不把业务计数改称连续观测。
- 原生适用域检查使用 `INTEGRABLE_NUMERIC_OUTCOME_REQUIRED` 及有限条件一阶矩许可；没有密度或无原子分布条件。见 `pfn_pipeline/_internal/identification/randomized_network_arm.py` 的 `_eligibility_error`、`_expected_result_fields` 和独立重放。
- 只有正支持且业务、A4、科学条件审核通过，才应用既有 R1a 组合并重放证书。有限矩待审、拒绝科学条件、引用不足均不能进入求解。
- 这是将较大模型中的 POINT 恒等式用于其计数子模型。**不能把较大模型的非识别反例、可达端点或 sharp 界限直接转移到计数子模型。** 本次没有开放计数 PARTIAL；也没有删去真实上界、额外关系或具体总体数值来获得 POINT。

`tests_gateway/test_owned_effect_reading.py` 用真正的非负整数潜在结果逐个枚举完整分配，以精确有理数核对条件均值、支持及证书系数；同时检查均值可以非整数。这是实现验算，不能替代上述证明，也不是业务数据估计。

维护边界：读取类型与显式来源依赖在 `cfm_id_llm/owned_effect_reading.py`，原生调用在 `cfm_id/network_effect_dispatch.py`。本轮不改数学 Core、Estimation/Policy，也不把计数类型本身当作新的科学批准。
