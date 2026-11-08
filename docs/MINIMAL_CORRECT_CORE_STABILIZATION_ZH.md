# 最简正确问题：识别定理、一次只改一项的消融与发布门禁

**冻结基线**：v2.9.2 Post-release P0；此版仅添加一个可运行最小样板、测试分层、HTML 回放、研究维护说明。所有结论均限定在明确接受的数学合同内。

## 1. 数学对象只有一个

网络 `V={0,1,2}, E={(0,1),(1,2)}`（固定于处理前），已知 D2 `q(t)=1/3` 当且仅当 `sum(t)=2`，否则为 0。E1 暴露：`S_i(t)=1{sum_{j in N(i)}t_j > deg(i)/2}`。A1 目标是 **D2 设计标准化** 节点 0 arm：

\[
\mu_0^q(1,1\mid W)
= \sum_{\mathbf t: t_0=1,S_0(\mathbf t)=1}
   \frac{q(\mathbf t\mid W)}{\Pr_q(T_0=1,S_0=1\mid W)}
   \mathbb E[Y_0(\mathbf t)\mid W].
\]

三个可能的 treated sets：`{0,1}`, `{0,2}`, `{1,2}`。仅 `{0,1}` 进入目标 arm，因此支持为 `1/3`。在完整向量随机化、consistency、足够的 typed 总体 A4 与有限一阶矩下：

\[
\boxed{\mu_0^q(1,1\mid W)=\mathbb E[Y_0^{obs}\mid T_0=1,S_0=1,W]}. 
\]

**不是**固定所有其他节点处理的 controlled effect；并未假设同 arm 全部完整分配的潜在结果相同。尽管本最小样例该 arm 只有一个分配，这个定理本身也不需要 exposure sufficiency。

## 2. 消融输入与真实 API 输出（固定其余条件）

| 改动 | 期望结果 | 一眼看懂的原因 |
|---|---|---|
| Base 完整 | `POINT` + replay，支持 `1/3` | 合法 A4/A5/A6 |
| 删除 typed A4 | `NEEDS_INPUT` | 变量名单不等于总体条件均值 |
| A4 改为 PROPOSED | `NEEDS_INPUT` | 未批准不能生产 POINT |
| Full-vector randomization 改为待确认 | `NEEDS_INPUT` | A5 缺许可 |
| Full-vector randomization 改为 NOT_ADMITTED | `UNSUPPORTED` | 明确不满足当前路线要求；不证明普遍 NON-ID |
| quota `m:2→1` | `UNSUPPORTED / ZERO_ARM_SUPPORT` | 节点 0 与邻居 1 不可能同时 treated |
| 增加网络边 `(0,2)` | `UNSUPPORTED / ZERO_ARM_SUPPORT` | 0 号度数从 1 到 2，strict majority 需同时处理两位邻居，但自己还占一个名额 |
| E1 改 E2，目标暴露从 1 改为 2 | `POINT`，仍 `1/3` | 数值同，但目标指纹必须变化 |
| 查询授权 PROPOSED | `UNSUPPORTED / QUERY_NOT_CONFIRMED` | LLM 提议不是审核 |
| 伪造 support 证书为 `999/1000` | verifier 拒绝 | 结果不能替换独立重算 |
| 修改路由包装为 R2 | verifier 拒绝 | Route 不能代替数学证明 |

消融程序：`examples/minimal_correct_core_golden.py`。测试：`tests/test_minimal_correct_core_stabilization.py`。锁定的可机读结果：`assets/benchmark_assets_stabilization/minimal_golden_expected.json`。该快照不得因为测试失败就自动刷新；更新需先说明为何数学合同改变。

## 3. 单一定理的大网络检查

`tests/test_stabilization_scaling.py` 使用 Ring300、D2 名额 `m=150` 和 E1，仍调用相同 R1a 的 `ArmInquiryV21` / verifier。节点度数 2，高暴露要求自身和两个邻居全部 treated。组合计数给出

\[
\Pr(T_0=1,S_0=1)=\frac{150\cdot149\cdot148}{300\cdot299\cdot298}=\frac{37}{299}.
\]

无需枚举 `2^300`，但仍不意味着其他 300 节点 arms 都有支持，也不意味着有限样本容易估计。

## 4. 单一权威路径，其他入口只是边界

```text
A0 Gateway (可选; 仅提出/审核业务规格)
      │
      ▼
已确认的 typed business inquiry
      │
      ▼
identify_network_business_query (统一业务入口)
      │
      ▼
A4 typed 信息 + A5 因果许可 + A6 support
      │
      ▼
现有独立数学定理 R1a/R1b/R2/R3
      │
      ▼
原 verifier / replay_verified_business_outcome
      │
      ▼
POINT 识别泛函或有原因的拒绝（不输出真实估计数值）
```

- `pfn_pipeline.identification.identify(TaskSpec)` 是既有任务/历史接口；不能把它当成自动决定所有 business targets 的第二套权威路由。
- `cfm_id_bridge.bridge.run_verified_multiquery_v29` 是可选的 A0 审核与安全包装层，不是因果数学证明器。
- `pfn_pipeline.identification_business.identify_network_business_query` 将 **已审核 typed inquiry** 路由到正式定理；`replay_verified_business_outcome` 负责相应结果重放。
- 当业务层与数学对象冲突时，应拒绝，而不是由 LLM 修改目标以凑出 POINT。

## 5. 四步定位 Bug，永远优先缩小问题

1. 用固定 Golden 3 节点复现；若仍出现，优先排查 Core/typed A4/A5/A6。
2. 仅开启一个高层因素（Batch、Effects、A0、R3 观测律表示），观察异常是否出现。
3. 先建立独立 oracle 或相容世界反例，再做最小补丁；禁止在失败时随机更换 Design/Exposure/Target。
4. `fast → integration → scale → core-split → gateway → pfn-smoke` 分层验收；对性能问题记录规模、线程数及是否发生超时。

## 6. 稳定阶段的完成条件

- [x] 一个确实调用正式 Core 的最小 POINT 样例 + 精确 support + replay。
- [x] 最少八类一次只变一项的数学消融 + 两类证书篡改拒绝。
- [x] 快速快照、独立枚举小图和 Ring300 单定理对拍。
- [x] CI 将 `fast` 放在历史慢测试之前。
- [ ] 远端 Python 3.11 绿色 CI 回执（未由本地文件证明）。
- [ ] 旧 checkpoint smoke 偶发停顿的根因诊断（分组通过不等于故障已消失）。
- [ ] 基于复现的最小公共代码收敛：先评估、再一处处改，绝不大重构。
