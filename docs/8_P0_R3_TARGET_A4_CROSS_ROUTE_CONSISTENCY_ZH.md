# P0 增量：跨 R3 Target 身份与 A4 来源一致性（只读）

**基线**：正式 v2.8 `Causal-IDFM-Identification-v2.8-R3-Nodewise-Neighbor-Adjustment.zip`。  
**性质**：非破坏式 P0 兼容增量，不是 v2.9、不增加数学 Family、不修改任何已发布 R1/R2/R3 定理证书。  
**排除**：A0 由其他开发线负责；R4/R5、PARTIAL、IV、DAG、Network Auto-G 不在本轮实现。

## 1. 为什么需要

已有 R3 p-standardized 效应在 v2.6 完整处理向量观测律与 v2.7 因子化律下，均具有相同的数学识别原理，但两种历史证书使用不同 target fingerprint 命名空间。禁止仅根据这两个 fingerprint 字符串不等，判断因果目标不同；也不能仅凭 `DIRECT` 名字相同，就将 R3 p-standardized 与 R3 exposure-adjusted / nodewise-adjusted 视为同一个 estimand。

这次的核心功能是**在已通过独立 theorem replay 的业务结果之上**，添加一个单独的 *comparison receipt*；原证书、不变式、目标公式均保持原样。

## 2. 数学合同

在固定 `W=w`、给定处理前网络与同一 treatment/outcome/study protocol 的约束下：

- R3 p-standardized arm 的数学目标以观测分配律 $p(\mathbf t\mid w)$ 为标准化权重。对同一节点签名 $(T_i,S_i^g)$ 和同一有理系数线性组合，若 $p$ 完全一致，则数学 target 一致。
- 完整 A4 律 $p(\mathbf t\mid w)$ 与因子化 A4 律 $p(\mathbf t\mid w)=\prod_j r_j^{t_j}(1-r_j)^{1-t_j}$ 在 $n\le12$ 时都精确展开为具有正质量的完整二元处理向量与其有理数概率。没有浮点阈值、没有样本近似。
- 对 $n>12$ 的纯独立 Bernoulli 观测处理律，两套相同节点次序的 $r_j$ 均逐项一致，当且仅当完整处理向量分布一致。比较不需要枚举 $2^n$。
- 对 $n>12$ 的分层/节点协变量 **混合**因子化律，当前不假设两种不同混合分解产生不同边缘律，也不在无法枚举的情况下冒充可比较：只对完全相同的已声明模型给出受限一致性记录，否则 `MARGINAL_LAW_EQUIVALENCE_UNRESOLVED`。
- 对同一固定研究协议及条件层 $w$，一个真实的观测联合处理分配律只能有一个。若两个被独立接受的 A4 来源宣称的 $p(\mathbf T\mid W=w)$ 被精确证明不同，**两者不能同时作为该研究情境的一致总体律来向下游合并**。这不表示某一个来源单独被软件证伪，也不是因果不可识别证明。

定义额外比较指纹（**不能替代旧 theorem target fingerprint**）：

```text
SHA256({
  version: CROSS_R3_P_STANDARDIZED_LINEAR_TARGET_V1,
  scope: study.shared_scope_digest,
  signature: signature.signature_fingerprint,
  law: exact_normalized_observational_law_digest,
  terms: canonical_effect_linear_terms
})
```

其中 `source_id`、`provenance` 不属于数学 estimand 的身份：两家 A4 提供方可以描述相同的目标，但是它们的来源、证书不因此等价。完整 A4 操作数也不是任何 outcome conditional mean 的实际数值；本轮不对两个来源的真实数据或条件均值作实证一致性判断。

## 3. API 与门禁

```python
from pfn_pipeline import (
    inspect_r3_target_a4_v28p0,
    compare_r3_target_a4_v28p0,
    inspect_r3_joint_handoff_v28p0,
)

receipt = inspect_r3_target_a4_v28p0(point_outcome)
pair = compare_r3_target_a4_v28p0(point_outcome_1, point_outcome_2)
review = inspect_r3_joint_handoff_v28p0(
    (point_outcome_1, point_outcome_2), require_single_target=True
)
```

三项 API **必先调用原 `replay_verified_business_outcome`**。非 R3、非 POINT、无法重放、包装类型篡改一律拒绝。`inspect_r3_joint_handoff_v28p0` 是**只读审计**，不创建任何 EstimationRequest，不调用 PFN、不输出 outcome 或 policy 数值。默认仅在目标与 A4 被严格对拍时，允许一个 *symbolic* 共同目标的分组；即使对拍成功，`conditional_mean_values_reconciled=False` 与 `NO_ADAPTER` 仍保持。

### 结果分类

| 结果 | 安全解释 |
|---|---|
| `SAME_TARGET` + `EXACT_MARGINAL_TREATMENT_LAW_AGREEMENT` | 同一研究、同一 p-standardized 数学目标、同一精确总体处理律；可合并**目标身份**，不能自动合并估计或数值 |
| `DISTINCT_DECLARED_TARGET` | 同一观测律，不同已声明 effect linear terms，不能合并成一个目标 |
| `CROSS_TARGET_SEMANTICS_NOT_CERTIFIED_EQUIVALENT` | p-standardized 与 exposure/局部协变量调整，或其他跨 target class，不允许根据同名 Direct 合并 |
| `CONFLICTING_MARGINAL_TREATMENT_LAWS` | 同一 study/protocol 声明不同观测总体处理律，合并应拒绝，须对源头进行人工核查 |
| `A4_SAME_SOURCE_ID_DIFFERENT_PROVENANCE` | 同一来源 ID 的 provenance 不一致，拒绝复合交付 |
| `A4_SAME_SOURCE_ID_DIFFERENT_MODEL` | 同一来源 ID、同一 operator，但条件分配模型不同，拒绝复合交付 |
| `MARGINAL_LAW_EQUIVALENCE_UNRESOLVED` | 大规模复杂混合律未得到整体等价证据，不得以缺少反例代替证明 |
| `DIFFERENT_STUDY_OR_PROTOCOL` | 不同目标条件层/研究协议，不能视为同一因果目标 |

## 4. 对抗测试与科学边界

- E1–E5 原 theorem/Exposure/支持算法保持原状；原 R3 p-standardized、共享 B G-formula、节点特异调整分别由原 verifier 重放。
- 新测试包含两种表示等价、不同来源等目标、同研究不同 $p$、完整表与因子化律冲突、同 ID provenance/model 冲突、不同 contrast、调整 Target 与 p-standardized Target 不可合并、300 节点因子化等价、相关 treatment 的混合律边缘化、Policy Target 类型区别、篡改证书与非 POINT 拒绝。
- `source_id` 和 SHA-256 只提供软件一致性检查，**不是**来源真实存在、数据独立采样、因果科学假设为真的证明。跨 Route 共用 A4 条件均值算子的数值关系不在本轮检查范围。
- 不覆盖大型相关观测分配的通用因子化/链图概率证明；不能声称解决 R3 的任意高维调整、Forastiere 全 GPS、Network Auto-G 或 Estimation adapter。

## 5. 下一步（不含 A0/R4/R5）

1. 研究可审计的多来源 A4 信息蕴含和条件 outcome 算子值一致性；实际数据接入需 Estimation 配套，不在 Identification 中假造数值。
2. 设计**有限且确有理论保证**的相关观测处理律支持计算，逐渐去除 R3 节点独立因子化限制。
3. 进一步区分跨 $W$ 标准化的目标总体与固定 $W=w$ 条件 Target，明确分层总体算子及许可。
4. 和 Estimation/Policy 团队共同签署 typed estimator capability registry，只有适配器确实实现、测试并绑定 Target 时才允许下游请求。
5. 完成远端 Python 3.11 GitHub Actions、浏览器展示 QA、旧 checkpoint smoke 连续运行稳定性。
