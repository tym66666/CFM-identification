# 集成数学合同与正确性整改

## 1. 所在层次与适用范围

本轮没有修改 `pfn_pipeline` 的 R1a/R1b/R2/R3 识别定理；新增的是 **独立人工科学审核记录 ↔ Core Typed Inquiry ↔ Core POINT 证书** 三者之间严格的可追溯绑定。软件检查审核记录与数学对象一致，不自行论证现实中的因果科学假设。

## 2. 绑定合同

`ApprovedScienceBindingV291` 必须包含：

- 业务审核内容摘要、已确认的目标摘要和原业务证据短句（A1）；
- 从真实 Core-owned typed inquiry 提取的数学目标坐标：节点顺序、完整政策向量、预先指定单位权重、效应 kind、exposure 状态及对应研究范围；
- A4 总体算子的 `source_id`、`operator`、完整 typed source 内容 SHA-256 及审核参考；
- A5 typed assumption / scoped license 的名称与内容摘要、审核参考；
- 被明确批准的**具体** theorem route，例如 `R3_FULL_ASSIGNMENT` 或 `R3_MEAN_SIGNATURE`；
- 人工审核人与科学说明、研究目标范围 digest。

在 Core 调用前重新从实际 inquiry 计算并核对上述字段。完整政策 `(1,1,1)` 不能在审核记录保持原样的情况下被换成 `(1,0,0)`；不能替换批准过的 A4 来源、A5 科学许可；正式定理结果 route 与批准 route 不同不能返回 POINT。原始 v2.9 只有自由文本和布尔确认的 `ScientificAdmissionV29` **fail closed**。

## 3. 原数学定理边界不变

| 数学路线 | 典型 A4/A5/A6 要求 | 新 v2.9.1 JSON 能力 |
|---|---|---|
| R1a | 已知随机化 q、arm 结果总体算子、随机化/一致性、目标 arm 正支持 | 限定 D1/E1 Arm 与指定 D1 Effect 受审包 |
| R1b | 完整政策分配支持、assignment-level 总体结果及随机化许可 | 固定政策、有限混合的显式审核包 |
| R2 | 已接受均值签名充分性、每个节点签名正支持与签名算子 | 仅明确提供 signature + 额外 A5 的固定政策 |
| R3-Full / Signature | 观测 p、完整向量条件交换性，Signature 另需结构许可 | 小网络完整律的固定政策 |
| R3 p-standardized | 观测 p、arm 支持、完整向量交换性、总体 arm 均值 | 有限总体显式律的 Effects |
| R3 adjusted | 潜在结果 exposure sufficiency、条件交换性、每个正质量层支持 | Shared-B 或 Nodewise 有限有界配置 |

同名 Direct 可能是不同的数学 estimand。软件 route 注册数量也不等于已覆盖所有现实网络干扰问题。

## 4. 安全拒绝与验证方法

- 不符合业务审阅、缺 A4/A5 的结构批准、审批来源变化、未经许可 route 切换，输出 `INCOMPATIBLE` 或其他安全拒绝，不能输出 POINT。
- 有人类业务确认但没有合法科学 packet，输出 `NO_ADAPTER`（这里是缺**formal binding** 的历史枚举名，不代表 Estimation adapter）；不允许用 LLM 自动补充。
- `POINT` 要求 `CORE_REPLAY_VERIFIED`，所用的识别公式和支持检查来自未改动的 Core。政策数值、实际销售收益与有限样本估计均不由本层产生。
- 科学审批记录可由同一方伪造，因此不是身份认证或密码学签名。真正部署时必须加入权限、密钥、不可篡改日志与独立审核流程；本轮仅提供数学对象绑定与本地可审计研究合同。

## 5. 两个离线评测轨道

`RAW_BUSINESS_TRACK`：21 项历史 NBIB，只考察引用、歧义发现、query 分类、A4 缺口警示。其金标准并不含正式认定的总体 A4，不能计算 Core POINT 正确率。

`FORMAL_BACKED_TRACK`：9 个受控的合成 route 类型 × 四种科学审查结果，共 36 条。使用人工构造且明确标记为合成的 A4/A5，真实调用 theorem 和 replay；这些合成案例不能被解读为统计代表性，也不能证实真实世界假设。准确数量：9 个正例，27 个 A4/A5/route 违约拒绝。独立异常测试额外包含错误政策坐标与 typed source/license 篡改。

## 6. 仍未完成

- 从真实非结构化商业语言到精确处理向量、节点权重、Exposure、总体范围的自动机器级语义等价证明；目前仍必须人工确认。
- 科学来源真实性、审核者认证和现实因果假设有效性；摘要只能检测记录相互不一致。
- D2–D6 等所有现有数学子域的 JSON adapter 全覆盖；当前只对规定的九类有受限入口。
- 21 个真实业务题的正式独立 A4/A5 金标准数据；正式线上 LLM 端到端 Benchmark。
- Estimation/Policy 数值，R4/PARTIAL、R5/IV、一般动态或未知网络识别。
- GitHub Actions Python 3.11 远端通过记录及真正的线上 LLM 验收（本地 CI 配置可解析但远端尚需触发）。

## 7. 回归/交付原则

所有修改须保证旧数学 Core 文件逐字节不变；新 JSON 适配、科学交叉验证和 Gateway 测试进入 CI；测试以隔离 wheel 安装后在源码目录外的两个已批准路线为代表性安装证明，不能把这两个安装 smoke 误称为九条 route 全部在 wheel CLI 逐项测试。
