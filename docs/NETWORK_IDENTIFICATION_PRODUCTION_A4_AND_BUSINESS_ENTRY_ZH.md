# Causal-IDFM Randomized-Network A4 正式门禁与统一业务识别入口

版本：2026-10-17。基线：用户提交的 v2.0 正式源码 ZIP。此轮没有修改 Estimation / Policy 的数值算法，没有引入 PARTIAL 或自动推断 DAG。**本文件记录已经实现并经实测的功能，而非全部网络业务问题均已支持。**

## 1. 解决了什么

- **先前风险：** legacy Randomized-Network Arm `identify()` 的 A4 检查仅看变量名，容易将边际信息误当联合/条件 arm mean，也可能拒绝有完整联合律却未显式列出 exposure 列的输入。
- **当前修复：** 在 `InformationObject` 上引入可选的 `randomized_arm_observable` 严格声明（`RandomizedArmObservableV21`）。声明涵盖 operator、明确 provenance/admission、`SYMBOLIC_POPULATION_OPERATOR` 等 availability、研究网络指纹、节点顺序、outcome nodes、`W`、`q`、`g` 及覆盖的 arm cells。
- 官方 `make_heterogeneous_bernoulli_arm_task`、`make_complete_randomization_arm_task` 和 `make_two_group_quota_arm_task` 自动写入合法 typed 信息声明。旧 API 的函数签名及现有 ER300 流程保持不变。
- 只提供 `variables=(T,S,Y)`，但**没有可验证的 observable operator**，不再能让这条正式随机网络定理通过。
- 声明 `NODE_FULL_LAW` 或 `FULL_JOINT_LAW` 的来源，不必另行列出派生的 exposure 列；已知 `S_i=g_i(T,W)`、正确 q 和正支持时，可从较强信息派生 arm 条件均值。
- 批量 `identify_randomized_network_batch` 在单 arm 许可基础上，还要核查源信息覆盖所认证的**全部节点和 arms**；不能用某一个 seed arm 信息冒充全网覆盖。
- 这个修复作用于 **Randomized-Network Arm 生产门禁**；少数旧历史 backend 的较粗信息门禁本轮没有全部翻新，不能宣布全仓库任意 query 的 A4 检查都已严格化。

## 2. 数学与职责边界

固定随机化设计 `q(t|W)`、处理前网络/特征 `W` 和给定的 exposure `g_i`。当 `pi_i(a,s|W)=P_q(T_i=a,S_i=s|W)>0`，且 full-vector randomization、consistency 等已确认时，

```text
mu_i^q(a,s|W) = E[Y_i^obs | T_i=a, S_i=s, W].
```

A4 只验证右侧 observable functional 是否属于已声明的总体信息；A5 检查实验处理的潜在结果独立性；A6 检查 arm support 及有效域；正式定理才有资格输出 POINT。**A4 SATISFIED 本身不是因果 POINT。**

`SYMBOLIC_POPULATION_OPERATOR` 是理论上可用的总体算子声明，**不是**真实测量了那些总体均值，也不是样本估计；更不意味着单次固定网络随机实验能够准确估计某个极稀有固定政策。

## 3. 业务路由与已实现边界

| Inquiry | 正式委托路由 | 保证 | 缺失时的行为 |
|---|---|---|---|
| `ArmInquiryV21` | R1a 原 arm theorem + replay | POINT conditional mean | 缺 A4/A5/support 则拒绝 |
| `EffectsInquiryV21` | R1a VerifiedCompositionBundle + replay | 已识别 arm 的线性 contrast/聚合 | 不充分 arm/cell source 时拒绝 |
| `FixedPolicyInquiryV21` | 优先 R1b full assignment | 已知随机化且 `q(z)>0` + full-assignment A4 的真实固定政策均值 | 不适用时返回原因，并在**明确提供** R2 的 admitted mean-signature sufficiency 时再尝试 R2 |
| `FixedPolicyInquiryV21`（R2） | R2 官方 signature policy theorem/verifier | 特定结构限制、signature support 正的政策均值 | 没有结构许可不能推出 off-support 的 POINT |
| `FinitePolicyInquiryV21` | R1b 已验证有限固定政策的混合 | 有限混合的 POINT | 不能用混合绕过任何组件的零支持 |

业务入口只接受 typed inquiry：`identify_network_business_query(query)` 返回 `VerifiedBusinessOutcomeV21`，其中区分 `POINT`、`NEEDS_INPUT`、`UNSUPPORTED` 和原因；`replay_verified_business_outcome` 委托原 theorem verifier。入口不会把 `UNSUPPORTED` 判成数学 NON-ID，也不会把 `POINT` 当成已有下游 PFN adapter。

## 4. 稳定、可复现的 ER300 Showcase

请从源码根目录**依次、分别执行**：

```bash
python -B -m examples.run_network_identification_showcase --part r1a --er300 --output-dir showcase
python -B -m examples.run_network_identification_showcase --part r1b --er300 --output-dir showcase
python -B -m examples.run_network_identification_showcase --part r2 --er300 --output-dir showcase
python -B -m examples.run_network_identification_showcase --part assemble --er300 --output-dir showcase
```

前三步分别执行真实证明器及独立校验、输出 `r1a_verified.json`、`r1b_verified.json`、`r2_verified.json`；第四步检查 graph fingerprint，汇总成可离线打开的 `network_identification_v21.html` 和机器可读 `network_identification_v21.json`，**汇总不是证明验证器**，因此不能拿一个被篡改的 JSON 当作正式识别证书。

共享原 ER300：300 节点、D1 iid Bernoulli(1/2)、strict majority；示例 Batch 认证 1,200/1,200 arms POINT，附 node×arm population support 热图。R1b 查询原实验 D1 下全员处理：`q(1...1)=2^-300>0`，数学上 POINT，但对有限样本估计不现实。R2 **在同一真实 ER300 图上另设假设性 D2（固定 150 人 treated）实验**，全员 treated 不在设计 support 内，只有额外明确接受的 mean signature sufficiency + 每节点 signature support 才得到 POINT。两种实验**不能借用彼此的 q 或观测数据证书**。

六张业务卡由真实记录生成：三个 POINT（R1a 复合查询、R1b 固定政策、R2 假设 D2 政策），三个安全拒绝（只有变量名单、只有 arm mean 的政策、off-support 无额外结构许可）。

## 5. 性能、来源与安全限制

- ER300 的 D1 高密度图需要高精度 support 验证；在精确 `(degree, p)` 上共享**已验证的**二项/独立生成多项式概率结果，避免重复工作；**不是**用未经核验的近似值取代原公式。
- 同进程串行执行全部大网络证明与多轮 replay，在当前执行环境偶有长时间停滞；因此 README 提供分步运行命令。本轮的完整 ER300 演示已用此方式复现，不把不稳定的一键执行算作通过。
- 本地验证 Python 3.13.x；远端 GitHub Actions Python 3.11 尚需 PR 实际运行。
- 检查 `admission`、provenance 和指纹不能独立证明外部协议真实；用户/领域专家必须审核声明。
- 旧历史后端、动态/有向/不确定网络、DAG、IV、一般 observational POINT 和 PARTIAL 等没有因此成为正式支持。
- 本次展示只有 symbolic identified functional 与支持概率，不提供通过 PFN 实测得到的业务 effect value。

## 6. 运行/发布验收

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -q
python -B -m unittest discover -s tests -p 'test_production_a4_and_business.py' -v
python -B -m unittest discover -s tests -p 'test_network_showcase.py' -v
```

正式发布应将完整源码 ZIP、发布验证报告、三份 theorem 运行原始 JSON、合并后的 HTML/JSON 和变更哈希清单一起交付。
