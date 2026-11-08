# Randomized-Network POINT family — （D2/D3 × E1/E2）

这是**已实现能力**的说明。v0.4 的 D2×E1、D3×E1 历史接口保留；v0.5 在同一个 `RandomizedNetworkArmBackend` 中加入三档 treated-neighbor fraction（E2）。现有共享 ER300 iid Bernoulli → PFN → Policy 演示不被修改。

## 1. 数学目标不变

固定处理前 network 和上下文 `W`，已知原联合分配律 `q(u|W)`，研究节点 `i` 和某个 arm `(a,s)`：

\[
\pi_i(a,s|W)=\sum_{u:u_i=a,g_i(u,W)=s}q(u|W),
\]

\[
\mu_i^q(a,s|W)=\sum_{u:u_i=a,g_i(u,W)=s}
\frac{q(u|W)}{\pi_i(a,s|W)}\mathbb E[Y_i(u)|W].
\]

在已知分配机制、full-vector randomization、consistency、条件可积性和 **当前查询 arm 的正 support** 下，

\[
\boxed{\mu_i^q(a,s|W)=\mathbb E[Y_i^{obs}|W,T_i=a,S_i=s].}
\]

这是**总体 POINT 识别**，不假设 `Y_i(u)=Y_i(u_i,S_i(u))`，不声称有限样本精度，更不声称某个确定性 rollout 的政策价值已被识别。

## 2. 两种 exposure grouping

记 `K_i(u)` 为所有邻居中 treated 人数，`d_i` 为节点度数。

| Exposure | 状态 | 规则 |
|---|---|---|
| E1 strict majority | `s∈{0,1}` | `s=1` 当且仅当 `K_i > floor(d_i/2)`，平票低档 |
| E2 three-level fraction | `s∈{0,1,2}` | 若 `3K_i<d_i` 则 0；若 `d_i≤3K_i<2d_i` 则 1；否则 2 |

E2 只对 `d_i>0` 的节点定义；查询孤立节点时返回 `UNSUPPORTED / EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE`。E1 的孤立节点规则保持不变。E2 分档使用整数不等式，避免 `1/3`、`2/3` 的浮点比较误差。

## 3. Support：改变 exposure，不改变 POINT theorem

- D2 全网络固定总名额 `m`：`q(u)=1/C(N,m)` 对合法分配成立，proposer 先使用 `K_i|T_i=a ~ Hypergeom(N−1,d_i,m−a)` 再按 E1/E2 分档，最后乘 `P(T_i=a)`。
- D3 两组分别固定名额 `m_1,m_2`：给定 `T_i=a`，本人组消耗 `a` 个名额；组内两个超几何计数条件独立，卷积之后按 E1/E2 分档，再乘本人的 treatment 概率。
- Verifier 独立地从原始合法分配计数来计算 joint support，并 replay 包含 `design + exposure + arm + network` 的指纹及证书；测试第三条路径直接穷举小图合法分配。

注意：不能仅按合法**总分配个数**判断 POINT，必须计算查询 arm 的**联合概率**。零 support 时这一定义的条件 arm mean 不成立，不自动变成 PARTIAL。

## 4. 一个 D2×E2 五人演示

固定 `N=5,m=2`，节点 0 的邻居是 `{1,2,3}`，节点 4 是非邻居。合法分配总共 `C(5,2)=10` 个。

| own treatment | low `s=0` | medium `s=1` | high `s=2` |
|---|---:|---:|---:|
| `a=0` | `0` | `3/10` | `3/10` |
| `a=1` | `1/10` | `3/10` | `0` |

其中正 support 的四个 arm 在必要假设得到承认时均为 `POINT / VERIFIED`；另外两个返回 `ZERO_ARM_SUPPORT`。

运行：

```bash
python -m examples.run_complete_randomization_three_level_arm
```

也可以使用公共 API：

```python
from pfn_pipeline import identify, make_complete_randomization_arm_task, replay_population_identification
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

net = NetworkExposureSpec(
    network_id="small-e2", node_ids=["0", "1", "2", "3", "4"],
    undirected_edges=[("0", "1"), ("0", "2"), ("0", "3")],
)
task = make_complete_randomization_arm_task(
    net, m=2, node_id="0", own_treatment_value=1, exposure_value=1,
    exposure_definition="three_level_treated_neighbor_fraction",
    source="documented synthetic protocol", evidence="known assignment and pretreatment graph",
    synthetic=True, admitted=True, query_authority="TRUSTED_FIXTURE",
)
result = identify(task)
assert (result.status, result.verification_status) == ("POINT", "VERIFIED")
assert result.result["certificate"]["joint_arm_support_probability"] == "3/10"
assert result.estimation_request is None
assert replay_population_identification(result).verification_status == "VERIFIED"
```

`TRUSTED_FIXTURE` 仅用于真实有证据的合成测试；真实研究须基于协议确认条件，通常使用 `query_authority="HUMAN_CONFIRMED"`。`admitted=True` 表示研究者采纳假设，**不表示程序已根据数据证明了该假设**。

## 5. 实际支持与不支持

| 已支持 | 尚不支持 |
|---|---|
| 单节点/单 arm 的 D2×E1/E2、D3×E1/E2 | D1 hetero Bernoulli、E3 core collaborator |
| 完整 design 和 exposure 的联合目标指纹 | 批量 arm vector 查询、政策真实 welfare |
| 精确有理数联合 support 与独立 proof replay | 新设计和三档 exposure 的 PFN estimation adapter |
| 无正 support、未解决假设、孤立节点的拒绝路径 | 自动 PARTIAL、UniCo 前置 LLM |

E2 被同一 family 支持，并不意味着已完成通用 plug-in `ExposureSpec` 类；当前只是确定了设计和分箱的可组合边界。旧四臂 ER300 demo 依旧走原来的独立 Bernoulli 路线。

## 6. 复现

```bash
python -m pytest -q
python -m examples.run_complete_randomization_arm
python -m examples.run_two_group_quota_arm
python -m examples.run_complete_randomization_three_level_arm
```
