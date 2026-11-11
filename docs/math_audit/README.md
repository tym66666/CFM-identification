# 数学审查导航

## 本轮范围

任务 7 对 R1a、R1b、R2、R3-Full 和三类政策界限各选取一个代表案例，独立计算支持概率、目标值或区间，并与项目输出对照。部分案例还检查了错误证书能否被拒绝。

- [详细审查报告](classification_review.md)汇总识别条件、路线重叠、反例和文献核对。
- [分类说明](../../literature_support/CLASSIFICATION_ZH.md)解释各路线解决什么问题、为什么分开、何时可以同时适用。
- [文献目录](../../literature_support/catalog.json)记录原文版本和阅读范围，[路线映射](../../literature_support/routes/)记录文献与项目条件的对应关系。
- 当前软件覆盖以[能力说明](../CURRENT_SCOPE_ZH.md)和[能力登记](../../cfm_id/capability_registry.py)为准。下表记录本轮复算所选的案例。

## 主要结论

- R1a 的目标是在给定实验设计下，对同一暴露类别中的安排取加权平均。R1b、R2 和本轮讨论的 R3 固定政策路线则针对一个指定的完整安排。不同路线在各自条件同时成立时，可以识别同一个固定政策值。
- R2 的 Star-5 案例表明，完整安排的概率为零时，如果各正权重节点的目标签名仍有正支持，并且接受均值签名充分性，仍可识别该政策值。
- R3-Full 已运行独立复算。R3-Signature 已审读数学合同和代码分支，尚未新增对应运行验证。
- 两个政策共享的未知均值可能在相减时抵消。代表案例的联合差值为 `1/5`，分别求界再相减得到的区间为 `[-3/10, 7/10]`。

## 复算方法

从仓库根目录使用项目 Python 环境按需运行。下表给出此前代表案例的结果，详细数学条件见各合同。

| 脚本 | 检查内容与此前结果 | 数学说明 |
|---|---|---|
| `check_r1a_arm_support.py` | 单 arm 支持概率 `1/2`，目标均值 `1/3`，错误概率证书被拒绝 | [R1a arm 合同](../ABSTRACTION_RANDOMIZED_ARM_ZH.md) |
| `check_r1b_fixed_policy.py` | 完整安排概率 `1/12`，固定政策值 `7/12`，交换节点系数并重算摘要后仍被拒绝 | [R1b 固定政策合同](../R1B_VERIFIED_FULL_ASSIGNMENT_POLICY_ZH.md) |
| `check_r2_star5_support.py` | 完整安排概率为零，各目标签名均有正支持，政策值 `7/20` | [R2 签名政策合同](../R2_VERIFIED_MEAN_SIGNATURE_POLICY_ZH.md) |
| `check_r3_full_policy.py` | 目标安排的观测概率 `2/3`，固定背景政策值 `5/12`，替换公式中的目标安排并重算摘要后仍被拒绝 | [R3 固定政策合同](../R3_OBSERVATIONAL_FINITE_POLICY_AND_SIGNATURE_DIAGNOSTICS_ZH.md) |
| `check_bounded_policy_star7.py` | 枚举七网点的目标签名支持，政策区间 `[3/7, 4/7]`，达不到下界的见证被拒绝 | [单政策界](../BOUNDED_POLICY_MATH_ZH.md) |
| `check_bounded_contrast_cancellation.py` | 复算共享未知均值抵消后的联合差值区间 `[1/5, 1/5]` | [联合差值界](../BOUNDED_CONTRAST_MATH_ZH.txt) |
| `check_mean_order_ladder.py` | 固定目标和总体信息，`BOTH`、`OWN`、`NONE` 的区间依次为 `[1/5, 1]`、`[-1/5, 1]`、`[-1, 1]` | [均值顺序差值界](../MEAN_ORDER_RESEARCH_ZH.txt) |

```sh
python -B -m evaluation.math_audit.check_r1a_arm_support
python -B -m evaluation.math_audit.check_r1b_fixed_policy
python -B -m evaluation.math_audit.check_r2_star5_support
python -B -m evaluation.math_audit.check_r3_full_policy
python -B -m evaluation.math_audit.check_bounded_policy_star7
python -B -m evaluation.math_audit.check_bounded_contrast_cancellation
python -B -m evaluation.math_audit.check_mean_order_ladder
```

此前在提交 `d2a8149` 上统一运行上述七个脚本，全部通过。当时单独运行的下界见证回归测试也通过（1 项）。

## 本次整理验收

清理旧导航、过程笔记和独立见证测试文件后，从仓库根目录按上文命令重跑了七个独立复算脚本，全部通过，结果与上表一致。R3 的运行复算覆盖 Full 代表案例。Signature 已审读数学合同和代码分支，尚未新增对应运行验证。

下界见证测试已并入 `tests_gateway/test_bounded_policy.py`。运行 `python -B -m unittest tests_gateway.test_bounded_policy -v`，共 32 项测试全部通过，其中包含拒绝可行但未达到证书所报下界的见证。

## 尚未完成

- R3-Signature 的独立运行复算仍待补充。
- 其他设计与暴露组合、未审读的实现分支，以及更广的 PARTIAL 和 DAG 分类留待后续。具体的文献疑问见[详细审查报告](classification_review.md)。