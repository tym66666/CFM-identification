# 次数型结果进入政策均值与差值

`network_policy_reading.Study.outcome_kind` 现在明确接收 `COUNT`（非负整数次数），例如每周缺货次数。模型需要自己选择该类型；程序不会把 `OTHER` 猜成计数，也不会补写原回答。

职责分工：

| 位置 | 职责 |
| --- | --- |
| `cfm_id_llm/network_policy_reading.py` | 定义结果类型；共用 `COUNT_RULE`，不授予科学假设 |
| `cfm_id/network_policy_dispatch.py` | 审核后，将计数均值送入现有实值均值 POINT 接口，保留类型转换记录 |
| `cfm_id/network_contrast_dispatch.py` | 保留两端、差值方向及共同评价范围；复用两端证明和重放 |
| `cfm_id/network_bounded_dispatch.py` | 明确阻断尚未接入的计数型有限模型求界 |
| `tests_gateway/test_policy_count_outcomes.py` | 检查 POINT、缺条件、拒绝、兼容和边界 |

数学依据：计数结果也是实值随机变量。已有 R1b 的随机化、一致性、正支持和有限一阶矩条件成立时，

\[
E\{Y_i(z)\}=E(Y_i\mid Z=z).
\]

对各对象的均值加权，或对两项政策均值相减，仍使用原有识别恒等式。R2 仍须另外审核所需的均值签名充分性和正支持。计数均值本身可以不是整数。

历史数学接口用 `continuous` 表示该实值结果入口；这里没有因此假设结果具有连续密度或服从 Poisson 分布。业务事实保留 `COUNT`，输出中的 `outcome_domain_embedding` 明示转换范围，证书仍由原有 Core 生成并独立重放。

边界：

- COUNT 不自动提供有限矩、上界、均值充分性或总体信息。有限记录继续不能替代精确总体信息。
- 实值模型中的 POINT 恒等式可以用于计数子模型；sharp 界限与非识别反例还需要在计数子模型中检查端点及反例可实现性。本次不作该扩展，返回 `COUNT_BOUNDED_MODEL_NOT_CONNECTED`，包括均值顺序求界。
- 观察性政策入口的 COUNT 转换未在本次接通，明确返回 `COUNT_OBSERVATIONAL_POLICY_NOT_CONNECTED`。不能由 Schema 能读 COUNT 推断所有识别路线都已支持它。
- 旧 BINARY、CONTINUOUS 输入保持兼容。旧安装若不认识 COUNT，需要连同读取层与业务适配层更新；不能只把新枚举发送给旧解析器。

本次没有修改数学 Core、科学批准要求或正式 A0 推荐配置。明确背景类型的薄 A0 仍是本地实验候选。
