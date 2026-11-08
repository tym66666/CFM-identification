# Causal-IDFM Identification — Non-arm Network Inquiry Shadow 

> **版本定位：** 基于 v1.5 的**最小只读侧路集成**，承接 v1.6 NetworkStudyContext 跨 Family 兼容性审计。发布日期：2026-10-16。没有新增 identification theorem，没有修改旧 `identify()`、Batch、Estimation 或 Policy 行为。

## 1. 为什么需要它

旧 v1.5 `assess_family_route()` 在判断目标之前强制 `_require_arm(TaskSpec)`。这样一个固定完整分配的政策均值，即使不需要 exposure，也必须先构造无关的 randomized arm 查询；observational network 的政策问题根本无法通过当前通用路由入口。

现在新增 **`pfn_pipeline.network_inquiry_shadow`** 独立可选模块，可直接声明 network study 与固定政策查询，不需要 fake arm。该模块只给出：目标是否可表达；所需总体 observable 是否可得；已声明设计下事件支持；已确认因果假设是否适合**随机化候选路线**；以及有没有已经注册的正式定理。**路由模块绝不返回 POINT/PARTIAL 的因果数学结论。**

### 输入边界

```text
NetworkStudyContextV17 = (network/node order, treatment/outcome/W, observation regime,
                          optional exact declared D1/D2/D3 assignment law, provenance)
TargetSemanticsV15       = fixed-full-assignment policy mean V(z) with node weights
NetworkA4SourceV17      = explicitly reviewed population observable operator
Assumption              = existing typed A5 assumption records, separate from q
    ↓
assess_nonarm_network_inquiry(...)   (non-authoritative diagnostic only)
    ↓
NonArmRouteAssessmentV17 + replay_nonarm_network_inquiry(...)
```

StudyContext **不保存** Q、exposure mapping、assumptions、识别状态、PFN checkpoint 或 finite-sample outcomes。仅 `fixed_policy_target_from_context` 使用它创建 A1 目标；其他 target classes 暂不接入此新侧路。

## 2. 当前明确支持的两个 candidate route

- `randomized_full_assignment_policy_mean_candidate_v0`（沿用 v1.5 的 family ID）：要求 `experimental` study。若提供已知 D1/D2/D3 law，可计算精确 `q(z|W)`，但这**不是**独立 policy theorem verifier。当前最多返回 `THEOREM_BACKEND_UNAVAILABLE`、`INFORMATION_BLOCKED`、`NEEDS_INPUT` 或 `OFF_SUPPORT_ALTERNATE_THEOREM` 等。即使条件全满足，也不能返回 `POINT`。
- `observational_network_fixed_policy_research_candidate_v0`：允许 observational study **不提供实验 q、arm 或 exposure**；不会从观测 treatment 比例推断随机化。即使声明了 `E[Y_i^obs|T=z,W]`，也只说明 A4 可观测条件算子存在，不自动给出 `E[Y_i(z)|W]`。需要新的因果识别理论与 A5 许可，目前没有正式注册的后端。

该入口**没有将旧仓库的 specialized `NetworkPolicyValueBernoulliBackend` 等直接注册为一般固定分配定理**；此处 `backend_capability=CANDIDATE_NOT_REGISTERED` 只针对本次候选路由。

## 3. 现有对象复用和新对象

| 对象 | 复用或新增 | 职责 |
|---|---|---|
| `TaskSpec` / `IdentificationSpec` | **原样保留** | 仍是正式 randomized arm 与 legacy pipeline 的输入 |
| `TargetSemanticsV15`、`RequiredObservableV15` | **直接复用** | A1 数学 Q 与候选 theorem 的 A4 要求；固定政策身份独立于 q/g |
| `Assumption` | **直接复用** | A5 已接纳、未接纳、冲突与证据 |
| `NetworkStudyContextV17` | 新增、冻结的简单无向网络只读科学视图 | 明确节点顺序、网络、变量、W、研究方案声明 |
| `NetworkA4SourceV17` | 新增、显式声明 | A4 总体算子及其 study/protocol 绑定；**不升级旧变量名单** |
| `NonArmRouteAssessmentV17` | 新增 | 逐维诊断、阻塞原因、现有后端能力、同输入确定性 replay |

`study_from_legacy_arm(task)` 是**单向**安全投影，只为兼容检查或共用背景；**non-arm → legacy arm** 的强制回编译没有实现。所有新 Policy/Observational 示例直接声明 study，没有借用 arm anchor。

### 双层研究身份

`shared_scope_digest` 包括网络身份、坐标顺序、T/Y/W 等；`protocol_digest` 包括实验/观测 regime 和已经声明的完整设计律（如存在）；`study_digest=H(scope,protocol)`。同一 graph/outcome/W 下 experimental 与 observational study 可有相同 shared scope，但不能共用 protocol 或 A4 source。A1 fixed-policy `target_digest` 在这两种情形中可相同。

审计证书另外绑定 `study_declaration_digest`（包括来源声明和网络时间声明）、`assumption_evidence_digest`、A4 source digest、计算到的 `q(z)` 与 route blockers。Hash 只能检测重新审阅后的声明是否变化，**不能证明外部来源真实可靠**。

注：为兼容当前网络定理已有 `network_fingerprint`，内部使用现有 `NetworkExposureSpec` 的图/节点 fingerprint 方法，它的历史字段名中含 `treated_neighbor_count_1hop`。此处**仅复用其结构身份计算**，并没有宣称该 exposure mapping 充分、也没有要求 fixed policy 用户输入 exposure。

## 4. A4 信息判定与 A5/A6 的分界

对 `V(z)=Σ_i ω_i E[Y_i(z)|W]` 的候选随机化定理，所需 observable 是每个非零权重节点在完整 `T=z` 下的条件均值。已声明的 `ASSIGNMENT_NODE_MEANS` 可以直接满足；拥有足够节点 outcome 覆盖的 `NODE_FULL_LAW` / `FULL_JOINT_LAW` 只能在正支持确定时派生；单纯 `NODE_ARM_MEANS` 与 pairwise marginals 不可用于推出任意 `T=z` 的均值。多项弱源不会无根据拼成强源。

对于 **observational study**，`ASSIGNMENT_NODE_MEANS` 作为显式声明的观测算子，可以在 A4 层被接受，但这**不能提供因果识别许可**；它的 causal assumptions 和 theorem backend 仍然独立缺失。如果只有 full joint law 而完整分配事件是否有正支持未知，则 A4 条件化保持 `UNRESOLVED`。

**观测性信息 ≠ 随机化因果假设；已知 q ≠ full-vector randomization；POINT 识别 ≠ PFN 可以可靠估计。**

### 可诊断状态（绝不是新的 causal statuses）

- `THEOREM_BACKEND_UNAVAILABLE`：输入可表达，信息可能已满足，但候选研究路线没有正式 theorem/verifier。
- `INFORMATION_BLOCKED`：来源明确不足或不匹配需要的 observable。
- `NEEDS_INPUT`：尚未确认 target、信息、设计律或随机化 family 必需 A5。
- `SOURCE_CONFLICT`、`SPECIFICATION_CONFLICT`、`ASSUMPTION_CONFLICT`：各自独立的输入/证据冲突。
- `OFF_SUPPORT_ALTERNATE_THEOREM`：固定政策 Q 本身定义良好，但在实验 q 下 P(T=z)=0，当前直接条件均值 route 不能用；不能自动标 PARTIAL。

计算的 `q(z)` 是按**已经显式声明且严格校验的 D1/D2/D3** 得出的精确有理数；输出标记 `POSITIVE_UNDER_DECLARED_Q`，不是外部设计真实性证明，也不使用 ER300 指数枚举。

## 5. 实际验收方式

```bash
python -B -m unittest discover -s tests -p 'test_nonarm_network_inquiry_shadow.py' -v
python -B -m examples.run_nonarm_network_inquiry_shadow
python -B -m examples.run_nonarm_network_inquiry_shadow --er300
```

- 在 3 节点和真实 ER300 上运行：固定政策（assignment-node means）→ A4 `SATISFIED`，route `THEOREM_BACKEND_UNAVAILABLE`；同一 Q 只有 arm means → `INFORMATION_BLOCKED`；observational network 无随机 q → `THEOREM_BACKEND_UNAVAILABLE`，A5 明确没有已注册 observational theorem。
- **另外**使用旧 `TaskSpec` 作为 legacy regression fixture，单独运行旧 `identify()` 与 RouteAssessment：应仍是 `POINT / VERIFIED` 和 `CANDIDATE_READY`。旧 `TaskSpec` 不参与上面三个 non-arm 查询的构造。
- 新结果可 `replay_nonarm_network_inquiry()`；它只对重新输入的 typed 声明做确定性比对，不验证外部数据来源。

## 6. 验收门槛（的 T1–T8）

| 门槛 | 结果 |
|---|---|
| T1 原 ER300 arm 与 Batch/handoff 不变 | 旧 arm 实测 POINT/VERIFIED；生产代码未改；旧 Batch/handoff 测试通过 |
| T2 独立固定政策，不填 dummy exposure/arm | 实现并通过 |
| T3 观测研究，不填假定 q/randomization | 实现并通过；不输出 POINT/PARTIAL |
| T4 相同 G/W/Y、不同 Q | 同 study 与独立 A1 digest；通过 |
| T5 相同 G/W/Y、实验与观察方案不同 | scope 同而 protocol 不同；来源跨用拒绝；通过 |
| T6 不同节点顺序/W/outcome | 身份变化，信息来源错误绑定拒绝；通过 |
| T7 只有 arm means 不能识别任意 fixed policy | 新 A4 明确阻断；通过 |
| T8 来源 PROPOSED/UNRESOLVED | 新入口保留 NEEDS_INPUT；通过 |

## 7. 上线与后续研究的边界

**上线：** 此版本只新增独立 opt-in 文件和对应 CI test entry；`pfn_pipeline.__init__`、`TaskSpec`、`identify()`、Batch、Estimation 和 Policy 均未变。强制生产门禁尚未启用。

**尚未解决：** 真实多来源证据相容性；与旧 arm A4Source 的互操作；W/人群/时点的完整 typed semantic reference；非简单无向网络；observational causal identification theorem；任意固定政策的正式 theorem/verifier。新入口现在**仅适用于固定完整分配平均值的候选路由**，不是通用网络推理器。

**下一步优先级：** 在 T1–T8 已满足后，应停止继续为没有新数学问题的接口扩张；优先选定一个非平凡、文献边界明确的第二条 Network Identification family（例如固定 policy value 下的 nested assumption regimes）验证整个链路。学生承担 setting/support 的横向扩展和复现，负责人主导新的模型类、identified-set 定义、sharpness、witness 与 theorem family 划分。
