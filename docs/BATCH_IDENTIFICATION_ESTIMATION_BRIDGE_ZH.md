# — Batch Identification 与现有 ER300 Estimation 桥接

## 范围与约束

本次仅扩展本仓库 Identification-owned 代码。**没有修改**现有数学 backend、`TaskSpec`、Estimation、Policy 或 PFN 权重。原来的 `identify(task)`、`estimate_effects(task, identified, model)` 完全保留。

### 1. 已确认新 family 单 arm → 全节点 arm 证明网格

```python
from pfn_pipeline import (
    identify_randomized_network_batch, make_heterogeneous_bernoulli_arm_task,
    replay_network_arm_batch,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

# net: 已经从正式研究协议确认的 NetworkExposureSpec
seed_task = make_heterogeneous_bernoulli_arm_task(
    net, propensities={node: "1/2" for node in net.node_ids},
    node_id=net.node_ids[0], own_treatment_value=0, exposure_value=0,
    source="actual declared protocol", evidence="documented evidence",
    admitted=True, query_authority="HUMAN_CONFIRMED",
)
batch = identify_randomized_network_batch(seed_task)
replay_network_arm_batch(batch)
print(batch.shape)                  # [N, 2, 2] 或 [N, 2, 3]
print(batch.coverage_status)       # ALL_POINT_IDENTIFIED / SOME_ARMS_UNSUPPORTED
print(batch.cell(net.node_ids[0], 0, 0))
assert batch.estimation_request is None
```

- 支持已实现 D1/D2/D3 × E1/E2/E3；原论文/定理前提由已验证的正式 seed 承接，**不通过观测样本补认假设**。入口要求选作锚点的那个单 arm 已有正 support 且 `POINT/VERIFIED`；若锚点本身为零 support，需要在**同一研究规格下**换一个有正 support 的锚点，不能推断“其他所有 arm 都不支持”。
- 返回每 arm `status`（POINT 或 UNSUPPORTED）、`reason_code`、精确 `joint_support`（有理数字符串；E2 孤立节点为 `None`）、`target_fingerprint`、整体 `batch_sha256`。
- 状态 `SOME_ARMS_UNSUPPORTED` 只表示某些查询无定义或零 support，**不是数学上的 PARTIAL identification**。
- 全网络 `[N,2,S]` 是查询坐标形状，不是 `μ` 的预测数值，也不意味着 PFN 支持动态 S。
- v1.0 不提供任意表格/任意 DAG/任意 q,g；网络必须符合已实现的固定网络 family 与资源上限。

### 2. 同一个 ER300 legacy TaskSpec 的安全 bridge

```python
from pfn_pipeline import (
    identify, simulate_task, bind_legacy_response_batch,
    replay_legacy_response_batch_bridge, estimate_bound_legacy_response,
)

legacy_task = simulate_task(seed=2026)  # 仅合成 demo，真实研究需正式确认协议
legacy_id = identify(legacy_task)       # 已有 NETWORK_MAJORITY_RESPONSE_POLICY_SCORE
link = bind_legacy_response_batch(legacy_id)
replay_legacy_response_batch_bridge(link)
assert link.batch.coverage_status == "ALL_POINT_IDENTIFIED"
assert link.batch.shape == (300, 2, 2)
# 模型必须由 Estimation 项目提供正确的已训练 checkpoint：
# estimates = estimate_bound_legacy_response(link, model=trained_model)
```

Bridge 严格从 **同一个 replay-verified legacy TaskSpec** 中导出新的形式化 seed，逐 arm 与旧响应证书的联合设计 support 对拍，并绑定旧规格的 fingerprint。它**不生产新 EstimationRequest**，只在确认数学一致后复用**原始已验证四臂 response request**。所生成的 `link.batch` 本身仍是 population-only，无估计请求。

运行时调用 `estimate_bound_legacy_response(link, model=...)` 会重新 replay bridge 和旧 handoff，再委托原 `estimate_effects()`；新 D1/D2/D3 或 E2/E3 任务不能通过这条桥自行跳转到旧 PFN。模型未训练、checkpoint 不匹配或事实数据缺失等由原 Estimation 报错。

**演示测试例外：** `build_model()` 返回未训练模型；仅在 smoke test 中显式提供 `allow_untrained=True`，所产数字绝不能当研究估计、已训练 PFN 结果或有效因果效应。

### 3. 为何没有直接把新 batch 变成 PFN 请求？

- 旧 PFN `predict` 接受 iid Bernoulli(1/2)、E1、连续 outcome、已知事实 `X,T,Y,A` 和四臂 `[N,2,2]`。
- 新 batch 用同一个 `q,g,W` 组织数学证明，但若由另一研究规格独立构造，不能只比较网络、`p` 和数组形状就宣称其条件背景 `W` 已经相同。
- D2/D3 配额、异质 p_i、E2/E3 可能改变目标权重或 arm 坐标，还没有匹配的训练标签/模型；应报告 `NO_ADAPTER`。
- Policy 使用四臂代理评分不等于固定完整分配下真实 rollout welfare；本次不改变 Policy 语义。

### 4. 验证方法

```bash
python -B -m unittest discover -s tests -p "test_batch_identification.py" -v
python -B -m unittest discover -s tests -p "test_*.py" -q
python -B -m examples.run_batch_identification_and_legacy_bridge
```

要在 ER300 进行精确的 1200-arm 批量与独立 replay，可运行示例加 `--er300`。稠密图精确 Fraction 运算需要一定时间，且此步骤无需 checkpoint。
