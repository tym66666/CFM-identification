# 已知处理前核心合作者 exposure（E3）的 POINT 识别

**覆盖范围：**已知、处理前固定的 network；D1 异质独立 Bernoulli、D2 全网固定 treated 配额、D3 两组分别固定配额；单节点单 arm 的 E3 核心伙伴严格多数 exposure。**这不是新定理或新估计器。**

## 1. E3 与 E1 有何不同？

对每个节点 `i`，研究设计在 treatment 发生**以前**明确给出一个非空核心伙伴集合

\[
\varnothing\neq C_i\subseteq\mathcal N(i),\qquad
S_i(\mathbf t)=\mathbf1\!\left\{\sum_{j\in C_i}t_j>\lfloor |C_i|/2\rfloor\right\}.
\]

E1 用的是**全部邻居** `N(i)`；E3 用的是**处理前给定的子集** `C_i`。两者都按“超过一半”分组，偶数人数出现平局时都属于 `S_i=0`。代码不学习、不猜测 `C_i`，也不把核心伙伴集合当作因果真实机制的充分表示。

所需信息：完整固定图，以及针对**每个**节点的 `C_i` 显式声明；`C_i` 必须非空、无重复、没有自身，且是原网络邻居子集。这样 `IdentificationSpec` 可以包含完整、可重放的参考集合，并防止遗漏节点时自动回退到全邻居。

## 2. 与 D1/D2/D3 组合时，哪些部分不变？

仍然使用**原始完整随机化分配律** `q(t|W)`，定义

\[
\pi_i^q(a,s\mid W)
=\sum_{\mathbf t}q(\mathbf t\mid W)
\mathbf1\{t_i=a,\,S_i(\mathbf t)=s\}.
\]

当假设已承认、条件绝对一阶矩有限，且 `pi_i(a,s|W)>0` 时，同一条随机化识别定理给出

\[
\boxed{\mu_i^q(a,s\mid W)
=\mathbb E[Y_i^{obs}\mid W,T_i=a,S_i=s].}
\]

不要求 `Y_i(t)` 仅由 `(t_i,S_i(t))` 决定。改变核心成员可能改变 conditional target weights，**即使某个 arm 的联合 support 恰好不变**；因此已知完整 `C_i` 映射必须绑定到 theorem contract 和 target fingerprint，而不是只存 support 数字。

计算只需把 treated-neighbor count 的**参考集合**从全体 `N(i)` 换成 `C_i`：D1 使用核心成员的 Poisson-binomial 分布；D2 使用给定本人 treatment 后的超几何分布；D3 使用两组条件超几何分布的卷积。原来的 `SupportEngine` 和 POINT theorem 不需要改变。E1/E2 保留原来的分配与结果语义。

## 3. 使用公共接口

```python
from pfn_pipeline import identify, make_two_group_quota_arm_task, replay_population_identification
from pfn_pipeline._internal.identification.schemas import NetworkExposureSpec

network = NetworkExposureSpec(
    network_id="pre-treatment-example",
    node_ids=["0","1","2","3","4"],
    undirected_edges=[("0","1"),("0","2"),("0","3"),("0","4")],
)
core = {"0":["1","2","3"], "1":["0"], "2":["0"], "3":["0"], "4":["0"]}
task = make_two_group_quota_arm_task(
    network,
    groups=(("0","1"),("2","3","4")), treated_quotas=(1,1),
    node_id="0", own_treatment_value=0, exposure_value=1,
    exposure_definition="pretreatment_core_collaborator_majority",
    core_collaborators=core,
    source="synthetic pre-treatment protocol", evidence="declared fixed C_i and quotas",
    synthetic=True, admitted=True, query_authority="TRUSTED_FIXTURE",
)
result = identify(task)
assert (result.status, result.verification_status) == ("POINT", "VERIFIED")
assert result.result["certificate"]["joint_arm_support_probability"] == "1/3"
assert result.estimation_request is None
assert replay_population_identification(result).verification_status == "VERIFIED"
```

`TRUSTED_FIXTURE` 只用于有明示生成过程的合成测试；真实场景需要记录来自实验协议/领域负责人的证据，并经人确认随机化和固定核心名单等条件，不能让 LLM 自动把 proposed assumptions 变为 certified。

## 4. 验证边界

- **Proposer：** `AssignmentSpec` 只对选定 `C_i` 计算 treated count；`ExposureSpec` 做 E3 多数分箱；`SupportEngine` 给出精确联合 arm 概率。
- **独立 verifier：** D1 以独立多项式乘法、D2/D3 以合法完整分配计数核查 support；未调用 proposer 的 Poisson-binomial DP、条件超几何卷积或 SupportEngine。
- **小图真值：**遍历所有合法完整分配，直接用原实验律 `q(t|W)` 加权；覆盖跨组核心伙伴、结构性零 support、`p_i=0/1`、边界配额和证书篡改。
- **强制拒绝：** `C_i` 为空、丢失节点、包含非邻居/自身/重复成员、未承认关键 assumptions、零 support 或更改 `C_i` 却沿用旧 target fingerprint 时，不得宣称 POINT。
- **handoff 边界：** E3 的 `POINT / VERIFIED` 仍然是总体识别结果；当前冻结 PFN 不支持 E3 的估计，故 `estimation_request=None`，状态 `IDENTIFIED_NO_ESTIMATION_ADAPTER`。原有 ER300 iid-Bernoulli E1 全链路演示不变。

复现：

```bash
python -m examples.run_core_collaborator_arm
python -B -m unittest discover -s tests -p 'test_core_collaborator_exposure_arm_integration.py' -v
python -B -m unittest discover -s tests -p 'test_*.py' -q
```
