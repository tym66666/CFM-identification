# Causal-IDFM Identification — Business Coverage & Correctness Hardening

**日期：2026-10-17；正式代码基线：v2.1；本轮目标：32 卡真实路由审计 + 跨拓扑支持验证 + Network legacy A4 安全收口。**

这份文档是**可执行的测试集与代码风险说明**，不是广覆盖的市场统计；所有新实测源为合成固定网络和明确声明的总体算子。软件确认的是**给定假设与声明时的符号总体识别公式**，不是因果假设的现实真实性，也不是 PFN 估计精度。没有引入任何新 POINT theorem。

## 1. 三个独立维度：D / E / G

- **Assignment**：D1 independent heterogeneous Bernoulli，D2 complete fixed quota，D3 exactly two pre-treatment-group fixed quotas。缺 cluster randomization、two-stage saturation、arbitrary-many strata/quota、rerandomization、longitudinal adaptive。
- **Exposure**：E1 strict majority (ties low)、E2 three-level treated-neighbor fraction、E3 predeclared core-collaborator majority。缺 exact neighbor count、any treated neighbor、arbitrary/weighted thresholds、multihop、multivariate, directed and dynamic exposure。R1a **无需 exposure sufficiency**；R2 **必须单独确认 mean-signature sufficiency**。
- **Topology**：当前已知固定简单无向网络不要求 ER 分布。Path、Ring、Star、Complete、Bipartite、Community、Small-world-like、Hub-like、Disconnected-with-isolate 已纳入运行验证。`small_world_like` 等是确定性构造拓扑，**不是对 WS/BA/SBM 随机生成总体的保证**。有向/加权/动态/未知网络不受支持。

在具体网络上，support 由 **q + exposure + topology** 联合决定；一类图能输入，不等于上面所有 arm 在该图上有正概率。

## 2. 32 张原始业务审计卡 -> 实际测试

四层报告：L0 数学目标是否可形式化，L1 是否存在/匹配正式 theorem 路由，L2 证书是否真实 verified 或为何拒绝，L3 是否真正验证过相应数值估计能力。业务问题的标题与 B-ID 与原 R1/R2 Business Coverage Audit v1.0 保持一致。

| L2 audit status | 张数 | 精确含义 |
|---|---:|---|
| `NEEDS_INPUT` | 2 | 存在尚待确认的假设或关键输入 |
| `NOT_CERTIFIED` | 5 | 信息不充分、零支持或其他已有路线条件阻断；不是数学非识别证明 |
| `NO_REGISTERED_THEOREM` | 6 | 当前没有实现该识别路线或目标；不是 non-ID 证明 |
| `POINT_TOY_LIVE_ER300_PREVIOUS_RELEASE` | 1 | 本轮重跑小图 Batch，真实 ER300 的 1,200 arms 仅引用 v2.1 归档证据 |
| `POINT_VERIFIED` | 15 | 本轮实际运行 theorem + 独立 replay 的合成小图 POINT |
| `PROXY_NOT_POLICY` | 1 | 代理分数不可冒充真正的固定政策福利 |
| `RE_SPECIFY` | 2 | 业务目标/暴露定义不完整或不一致，需要重述 |

**重要精细修正 B32：** 原业务问题只有 finite sample statistics 而没有已接受的总体算子。在真实 v2.1 生产门禁中必须 `NOT_CERTIFIED`，不能借用另一个合成的 symbolic A4 源替它通过；只有**重新声明不同且适当的总体 A4** 时，抽象数学定理才给出 POINT 公式。本轮为此专门改造失败测试。

以下表格由实际运行 JSON 自动生成，没有手工篡改状态。`A4/A5/A6` 是所需**数学合同**，只有 LIVE/replay 的那一部分才是经过此次实际执行的结果。

| ID | 业务目标 | L0 | L1 | L2 | L3 | 实际观察到的拒绝代码 |
|---|---|---|---|---|---|---|
| B01 | 本人AI且同事严格多数AI：员工平均结果 | TYPED_EXECUTABLE | R1A_RANDOMIZED_ARM | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B02 | 固定m人处理、邻居处理比例中档的结果 | TYPED_EXECUTABLE | R1A_RANDOMIZED_ARM | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B03 | 两组各固定处理名额、核心合作者多数处理 | TYPED_EXECUTABLE | R1A_RANDOMIZED_ARM | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B04 | ER300四臂完整批量识别 | TYPED_EXECUTABLE | R1A_BATCH | POINT_TOY_LIVE_ER300_PREVIOUS_RELEASE | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B05 | 本人AI设计标准化直接效应 | TYPED_EXECUTABLE | R1A_COMPOSITION | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B06 | 邻居多数AI带来的设计标准化溢出效应 | TYPED_EXECUTABLE | R1A_COMPOSITION | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B07 | 低暴露无AI至高暴露有AI的总效应 | TYPED_EXECUTABLE | R1A_COMPOSITION | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B08 | 预先指定部门平均Direct | TYPED_EXECUTABLE | R1A_COMPOSITION | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B09 | 核心与非核心员工的平均Direct差 | TYPED_EXECUTABLE | R1A_CUSTOM_LINEAR | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B10 | 预先指定的基准销售权重加权Direct | TYPED_EXECUTABLE | R1A_COMPOSITION | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B11 | 把不同随机化设计的两个arm直接命名为同实验Direct | RE_SPECIFY | NOT_REGISTERED | RE_SPECIFY | NOT_APPLICABLE_NO_POINT | CROSS_DESIGN_ARM_NOT_A_SINGLE_DIRECT_EFFECT |
| B12 | 随机化三人网络固定(1,1,0)政策价值 | TYPED_EXECUTABLE | R1B_FULL_ASSIGNMENT | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B13 | 同一个固定政策只有四臂means | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NOT_CERTIFIED | NOT_APPLICABLE_NO_POINT | INFORMATION_BLOCKED |
| B14 | 从0.5变为0.75的独立随机政策均值 | TYPED_EXECUTABLE | R1B_FINITE_POLICY | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B15 | 完整固定配额实验中受支持的特定名单 | TYPED_EXECUTABLE | R1B_FULL_ASSIGNMENT | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B16 | 两组各有处理quota的受支持名单 | TYPED_EXECUTABLE | R1B_FULL_ASSIGNMENT | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B17 | 五人固定处理四人、全员处理且无额外结构 | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NOT_CERTIFIED | NOT_APPLICABLE_NO_POINT | OFF_SUPPORT_ALTERNATE_THEOREM |
| B18 | 同样off-support政策加已接受mean-majority sufficiency | TYPED_EXECUTABLE | R2_MEAN_SIGNATURE | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B19 | 同样off-support政策仅局部干扰 | TYPED_EXECUTABLE | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | NO_EXACT_LOCAL_OR_COUNT_SIGNATURE_BACKEND |
| B20 | 同样off-support政策仅exact neighbor count sufficiency | TYPED_EXECUTABLE | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | NO_EXACT_LOCAL_OR_COUNT_SIGNATURE_BACKEND |
| B21 | LLM提出但尚未接受的mean-sufficiency | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NEEDS_INPUT | NOT_APPLICABLE_NO_POINT | NEEDS_INPUT |
| B22 | off-support政策所需节点signature类别零支持 | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NOT_CERTIFIED | NOT_APPLICABLE_NO_POINT | ZERO_POLICY_SIGNATURE_SUPPORT |
| B23 | 存在孤立节点时E2邻居比例 | RE_SPECIFY | NOT_REGISTERED | RE_SPECIFY | NOT_APPLICABLE_NO_POINT | EXPOSURE_UNDEFINED_FOR_ISOLATED_NODE |
| B24 | 观测网络自主选择AI的直接效应 | TYPED_EXECUTABLE | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | NO_GENERAL_OBSERVATIONAL_NETWORK_POINT |
| B25 | 网络结构尚未确认 | NEEDS_NETWORK | BLOCKED_PRECONDITION | NEEDS_INPUT | NOT_APPLICABLE_NO_POINT | NETWORK_STRUCTURE_UNRESOLVED |
| B26 | 销售结果95%分位数目标 | FORMAL_ONLY | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | QUANTILE_TARGET_NOT_REGISTERED |
| B27 | 政策结果转移到另一张网络 | FORMAL_ONLY | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | NETWORK_TRANSPORT_NOT_REGISTERED |
| B28 | ER300某具体完整分配且q>0 | TYPED_EXECUTABLE | R1B_FULL_ASSIGNMENT | POINT_VERIFIED | NO_NUMERIC_ESTIMATOR_VERIFIED_IN_THIS_AUDIT | — |
| B29 | 将majority proxy score冒充固定政策福利 | PROXY_NOT_POLICY | NOT_REGISTERED | PROXY_NOT_POLICY | NOT_APPLICABLE_NO_POINT | PROXY_SCORE_NOT_TRUE_POLICY_VALUE |
| B30 | 部分节点arm零支持仍求整体平均Direct | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NOT_CERTIFIED | NOT_APPLICABLE_NO_POINT | ZERO_ARM_SUPPORT |
| B31 | 局部充分性下的任意随机政策 | FORMAL_ONLY | NOT_REGISTERED | NO_REGISTERED_THEOREM | NOT_APPLICABLE_NO_POINT | R2_STOCHASTIC_POLICY_KERNEL_UNIMPLEMENTED |
| B32 | 总体POINT但仅有样本统计无法报告真实数值 | TYPED_EXECUTABLE | BLOCKED_PRECONDITION | NOT_CERTIFIED | NOT_APPLICABLE_NO_POINT | CONDITIONAL_ARM_POPULATION_INFORMATION_REQUIRED |

详细每卡 `target_class / a4_required_information / a5_required_assumptions / a6_support_and_validity / existing_estimation_adapter / evidence_type / evidence_note` 见 `showcase/CFM_ID_Business_Coverage_32_Cards.json`，也可在 HTML 点开每行查看。

### 不能被成功数掩盖的边界

- B14：N=3 的 Bernoulli(3/4) 随机政策可拆为 **8 个固定分配**，由 R1b finite mixture 验证；**不等于 N=300 的一般可计算 stochastic policy kernel**。
- B17/R1b 与 B18/R2：五节点 Star、固定四人处理时全员 treated 完整分配支持为零；B18 只有**显式已接受 majority mean-sufficiency 且每个目标 signature 有支持**才通过。B19/B20 不能把 local/count sufficiency 与 majority sufficiency 换名复用。
- B24：可作 observational Network 的结构化 precheck，但没有通用的 R3 因果 POINT 认证。已隔离的旧 Threshold Direct 路线不能计入 R3 完成。
- B04/B28：原 ER300 的数学识别支持在 v2.1 已记录，本轮没有重新计算完整 1,200-arm ER300 或重新训练 PFN。
- B29：`majority_score` 是 proxy score，不能被当成固定政策 rollout welfare。
- B32：统计估计量不能替代总体可观测信息。`POINT / VERIFIED` 与 `estimator available` 两层严格分开。

## 3. 非 ER 固定图 × D/E 验证

- 9 张确定性构造固定简单无向图，3×3 个 D/E 设置，**81 个组合**。
- 75 个组合**至少一个** arm 经正式 identify + replay 返回 POINT。
- 含孤立节点的一张图上，3 个 E2 设置和 3 个 E3 设置不能直接做全网 exposure 目标。

| 网络拓扑 | 9 个 D/E 中通过的组合数 | 7人固定处理3人、全员处理 R2 POINT? | 失败原因 |
|---|---:|---|---|
| path | 9/9 | 是 | — |
| ring | 9/9 | 是 | — |
| star | 9/9 | 否 | ZERO_POLICY_SIGNATURE_SUPPORT |
| complete | 9/9 | 否 | ZERO_POLICY_SIGNATURE_SUPPORT |
| bipartite | 9/9 | 否 | ZERO_POLICY_SIGNATURE_SUPPORT |
| community | 9/9 | 否 | ZERO_POLICY_SIGNATURE_SUPPORT |
| small_world_like | 9/9 | 是 | — |
| hub_scale_free_like | 9/9 | 否 | ZERO_POLICY_SIGNATURE_SUPPORT |
| disconnected_with_isolate | 3/9 | 是 | — |

所有上述 policy 对照的 R1b `q(alltreated)=0`，R2 的 A5 mean-majority sufficiency 是**合成假设**，并非由数据得到或由软件验证其真实性。成功 / 失败由各图节点度数和 quota 下 signature support 共同决定。

## 4. Legacy A4 正确性收口

| 识别入口 | v2.2 安全措施 | 风险剩余 |
|---|---|---|
| 新 R1a / Batch | 保持 v2.1 typed A4 production gate，查节点/arm 覆盖 | 实际来源真伪依靠研究设计审查，而非哈希 |
| PFN 旧 MajorityResponse | **新增强制 typed A4**，校验观测总体算子、来源 admission、network/order、q/g、节点覆盖；支持 NODE_ARM_MEANS、NODE_FULL_LAW 与 FULL_JOINT_LAW；原官方构造器显式声明合法合成总体算子 | 数值 Estimation 仍仅限既有 D1/E1 共识场景，来源不能软件自动认证 |
| 旧 NetworkDirectEffectThresholdPoint | **主动隔离、拒绝路由、拒绝直接 solve，历史 solve 方法直接 raise；旧结果凭证 verifier 拒绝** | 正式 R3 仍未实现 |
| 旧 NetworkPolicyValueBernoulli | **同样隔离**，避免变量名单冒充条件总体信息 | 新 R1b/R2 正式 typed 识别 API 不受此限制 |
| 非网络 ATE/Manski/有限混合等旧识别后端 | 不做 Network POINT 广覆盖承诺；旧接口保留 | 本轮未把所有非网络后端更新到同一 A4 数据模型 |

**为什么不是将所有历史后端都关掉？** 旧 MajorityResponse 是现有 PFN/Estimation 对接路径，关闭会不必要地破坏跨模块协议，因此通过无歧义的 typed A4 审查迁移。其余两个旧 Network POINT theorem 采用狭窄 legacy variable-name 检查，当前数学合同和接口不支持安全的增量改写，因此直接禁用，保留新版 R1b/R2 独立 theorem 验证结果。

检验包含：错网、错 q、错 g、错 order、错 outcomes、有限样本冒充、来源未 admitted、重复来源语义冲突、缺少 arm/节点覆盖、证书篡改、旧结果规则 ID 拒绝 replay、旧路径直接调用隔离。

## 5. 总体审查结论与发布含义

- **可以如实发布研究版 v2.2**：Network-first POINT R1a/R1b/R2，已知固定简单无向图，D1–D3 × E1–E3，有明确假设与 typed 总体信息，提供大量业务 Target 的符号识别、证书与安全拒绝。
- **不能声称“已覆盖常见全部网络业务”**，不能以 75/81 或 16/32 声称真实市场覆盖率。该集合是人工选择的极端/边界任务。
- **下一阶段技术优先项**：根据需求确定 D4 cluster、D5 多组 strata、E4 exact-count、E5 any-treated；并优先设计正式 **R3 observational network POINT** 的一个严格受限 setting，确保 conditional exchangeability、joint positivity 和 A4 联合律语义可以核验。
- **老师 Demo**：先看 v2.1 ER300 全 arm 热图，再看 v2.2 的 32 卡覆盖/拒绝详情与九种拓扑对照。将“数学可识别”“当前信息满足”“估计器可用”分别显示；不同研究协议（例如假设性 D2）必须显式注明。

## 6. 从仓库根目录运行

```bash
python -B -m unittest discover -s tests -q
python -B -m unittest discover -s tests -p '*v22.py' -q
python -B -m examples.run_business_coverage_showcase --output-dir assets/business_coverage_fixtures
# 浏览器打开 assets/business_coverage_fixtures/CFM_ID_v2_2_Business_Coverage_Dashboard.html
```

此命令将在合成 fixture 中调用正式 Identification theorem + replay，生成 JSON 和 HTML。`CONTRACT_GAP` 绝不会伪造后端 `UNSUPPORTED` 为数学 non-identification 证明。

**仍未验证**：远端 GitHub Actions Python 3.11 环境及真实业务数据上的 assumptions/effect estimation performance。完整测试的数字以此版发布日志为准。
