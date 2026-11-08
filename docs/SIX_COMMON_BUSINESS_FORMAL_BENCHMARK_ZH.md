# Post-release P0：六类常用网络业务的真实 Core Formal-backed 验收

## 定位与证据边界

本轮不改变 `pfn_pipeline/` 的任何识别定理、独立 verifier 或估计器。以 v2.9.2 为正式基线，新增可重复运行的**受限、合成、事先固定的数学业务验收**。业务语言是实验协议的示意，不是在线 LLM 解析的样本；因果 A5、总体信息 A4 不是来自真实企业的已审核证据；没有数值估计。

**这 6 类是人为选出的高频风格场景，不是从市场业务任务中按概率抽样。因此 7/18 POINT 绝不是现实业务识别成功率。**

运行命令：

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
python -B -m examples.run_common_business_benchmark --output-dir common_business_assets
python -B -m examples.build_supervisor_business_atlas --output-dir showcase_v293
python -B -m unittest tests.test_common_business_formal_backed -q
```

每个正例都实际构造 `ArmInquiryV21` 或 `ObservationalNodewiseAdjustedEffectsInquiryV28`，调用 `identify_network_business_query`，对 POINT 运行 `replay_verified_business_outcome`。每个反例状态由 Core 运行得到，事先的 `expected_status` 只在事后比对。业务合同的 SHA-256 是本地合成夹具防篡改提示，**不等于外部审核签名**。

## 六种业务协议与所需数学条件

| 编号 | 高频场景 | 真实调用 | Exposure | 数学前提/重点缺口 |
|---|---|---|---|---|
| S1 | 账号级独立 A/B | D1 R1a Arm | E5 及另一 E4 正例 | 全向量随机化、已知每节点 Bernoulli 概率、arm A4、正支持 |
| S2 | 企业 AI 固定 3 人名额 | D2 R1a Arm | E4 | 星型 hub 自身 treated 时，由固定配额导致准确处理邻居数只能为 2；目标数 3 则为零支持 |
| S3 | 团队/门店整组随机 | D4 R1a Arm | E5 | 簇内 treatment 相同；自己 treated 与没有任何 treated 邻居的组合可能零支持 |
| S4 | 多部门分别固定配额 | D5 R1a Arm | E4 | 分组配额及跨部门网络边；自己的同组邻居可能强制 untreated |
| S5 | 两阶段随机饱和度 | D6 R1a Arm | E5/E4 | 明确 profile 混合分配律 + **第一阶段没有超出最终 treatment 的直接结果效应** |
| S6 | 员工自选择 AI，邻居协变量调整 | R3 Nodewise Adjusted Effects | E5 | 相关观测处理律的 A4 可表示，但必须另行接受 exposure sufficiency + 局部交换性 + 逐调整层支持 |

本轮计数：18 个实际 Core 案例，7 POINT（均 VERIFIED+replay）、7 NEEDS_INPUT、4 UNSUPPORTED（均来自各自定理的零支持）。这些拒绝不是通用数学非识别证明。原本 v2.9.1 的九-route JSON 白名单与 v2.9.2 A0 审核流程**没有在这批六场景测试中重新执行**，不能把此套件包装成自然语言端到端产品准确率。

## 正确验收与后续要补的部分

1. 旧 21 张 NBIB `RAW_BUSINESS_TRACK` 仍须由独立业务审核人员做语义金标准；不允许让模型自己生成并验证唯一正确答案。
2. 对每个高频业务收集实际分配协议、treatment 版本、网络定义、A4 来源及 A5 的科学依据。在不满足条件时正确拒绝，而非强行添加数学假设。
3. 扩展 benchmark 至 D3 两组配额、R1a 正式 contrast、R1b 有支持政策、R2 有结构充分性政策，以及 E2/E3 的合法/非法节点案例；优先实现能明显影响常见业务覆盖的矩阵，不为凑数填空。
4. 与 v2.9.2 的 A0 受审核 JSON 入参对齐，需要设计真实风格目标坐标与 A4/A5 的独立审批，并验证不存在跨层错配。`POINT` 不等于已估计数值。

## 与既有 Coverage Atlas 的关系

现有 `assets/coverage_fixtures` 展示**组件及适用域**，不承诺某个节点/arm 为 POINT。新增 `showcase_v293` 把六类实际 Core 验收和元数据能力地图分开展示。两者互补：不能用 `6 Designs × 5 Exposures=30` 代替完整业务可识别率分母。
