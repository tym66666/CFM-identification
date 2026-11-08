# — D1 异质独立 Bernoulli 的 Randomized-Network POINT

**范围：**固定已知处理前网络、单节点单 arm、已知每个节点的 Bernoulli 随机化概率 `p_i`，E1 严格多数或 E2 邻居 treated 比例三档。D1 与已有 D2/D3 共享 `RandomizedNetworkArmBackend`、`AssignmentSpec`、`ExposureSpec` 和 `SupportEngine`。

## 1. 数学定义

已知的完整实验分配律是

\[
q(\mathbf t\mid W)=\prod_{j=1}^N p_j^{t_j}(1-p_j)^{1-t_j},\quad 0\le p_j\le 1.
\]

对于固定节点 `i` 和 arm `(a,s)`，定义 `K_i` 为所有邻居的 treated 总数，`S_i=g(K_i,d_i)`。D1 由于本人的处理与其他人的分配独立，有

\[
\pi_i(a,s\mid W)
=\underbrace{p_i^a(1-p_i)^{1-a}}_{P(T_i=a\mid W)}
\sum_{k:g(k,d_i)=s}
\underbrace{P(K_i=k\mid W)}_{\text{Poisson-binomial}}.
\]

内层邻居计数分布使用逐个 Bernoulli 的精确有理数 DP 计算，不枚举 `2^N` 种完整分配。即使 `p_i=0/1` 也合法，但发生概率为零的查询 arm **不能**返回 POINT。

当**已知联合分配律、full-vector randomization、consistency、固定处理前网络、条件可积性**已被接受，并且 `\pi_i(a,s\mid W)>0` 时：

\[
\boxed{\mu_i^q(a,s\mid W)=\mathbb E[Y_i^{obs}\mid W,T_i=a,S_i=s]},
\]

为 population POINT 识别。暴露仅用于目标分组，**没有要求** `Y_i(\mathbf T)=Y_i(T_i,S_i)`。换 `p_j` 可能改变 conditional target weights，即使某个查询的 support 恰好不变。因此 target fingerprint 绑定全部节点的已知 `p_j`，不只是邻居概率。

## 2. 公共入口

```python
from pfn_pipeline import (
    identify, make_heterogeneous_bernoulli_arm_task,
    replay_population_identification,
)
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

net = NetworkExposureSpec(
    network_id='known-protocol',
    node_ids=['0','1','2','3'],
    undirected_edges=[('0','1'),('0','2'),('0','3')],
)
p = {'0': '1/2', '1': '1/4', '2': '1/2', '3': '3/4'}
task = make_heterogeneous_bernoulli_arm_task(
    net, propensities=p, node_id='0', own_treatment_value=1,
    exposure_value=1, exposure_definition='strict_majority',
    source='documented synthetic randomized protocol',
    evidence='known p_i and fixed pretreatment graph',
    synthetic=True, admitted=True, query_authority='TRUSTED_FIXTURE',
)
result = identify(task)
assert (result.status, result.verification_status) == ('POINT','VERIFIED')
assert result.result['certificate']['joint_arm_support_probability'] == '1/4'
assert result.estimation_request is None
assert replay_population_identification(result).verification_status == 'VERIFIED'
```

完整六臂演示：`python -m examples.run_heterogeneous_bernoulli_arm`。

`TRUSTED_FIXTURE` 只适用于真实有来源的合成 fixture。实际研究需有实验协议确认 `p_i`、randomization、网络等事实，不能由 LLM 或模型结果自动标记 `admitted=True`。

## 3. 精确支持概率与独立审查

在上述四节点星形网络中：

| `a` | E1 低 | E1 高 | E2 低 | E2 中 | E2 高 |
|---|---:|---:|---:|---:|---:|
| 0 | 1/4 | 1/4 | 3/64 | 13/64 | 1/4 |
| 1 | 1/4 | 1/4 | 3/64 | 13/64 | 1/4 |

- **Proposer**：`AssignmentSpec` 用 Poisson-binomial 顺序 DP，`SupportEngine` 进行 E1/E2 精确分箱。
- **Independent verifier**：不调用 DP 或 SupportEngine，而以独立的平衡多项式乘法重算 `q` 的邻居计数分布并核对证明证书。
- **Small-N oracle**：测试对 `N≤8` 的所有完整分配向量直接计算 `q(t)`、暴露和六个联合 arm 概率，与以上两条实现逐项比较。
- **强制拒绝**：缺少节点 `p_i`、概率越界、proposed/unresolved assumptions、zero support、孤立节点的 E2、被篡改的结果或目标指纹，不得冒充 POINT 证书。

此版本**不会**把 D1 的人口 POINT 结论冒充为现有 PFN 可执行的四臂 estimator；`estimation_request=None`，`workflow_status=IDENTIFIED_NO_ESTIMATION_ADAPTER`。原 ER300 的 IID Bernoulli → Estimation → Policy 演示保留原有路径。

## 4. 复现

```bash
python -B -m unittest discover -s tests -p 'test_heterogeneous_bernoulli_arm_integration.py' -v
python -B -m unittest discover -s tests -p 'test_*.py' -q
python -m examples.run_heterogeneous_bernoulli_arm
```

**尚未支持：**E3 core collaborators；一般 exposure sufficiency、PARTIAL、确定性政策收益以及 D1/D2/D3 的 PFN estimation adapters。与这条 family 无关的历史 Identification 后端未更改。
