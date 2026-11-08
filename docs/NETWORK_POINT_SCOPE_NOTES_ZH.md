# 网络 POINT 范围与扩展备忘（历史研究范围）

本页保留早期网络 POINT 范围讨论，不代表当前全部路线或开发计划；现状请以根目录 README、研究路线目录及相应离线验收为准。

技术与定理细目见 `IDENTIFICATION_POINT_CAPABILITY_STATUS_ZH.md`，源代码直接生成的数量见 `showcase_r3_mixture_v28p1/CFM_ID_v2_8_P1_Verified_Identification_Capability_Snapshot.json`。本页只列尚未完成的实际差距。

| 优先 | 缺口 | 优先于新增 Family 的原因 |
|---|---|---|
| P0 | Identification → Estimation **可执行 typed adapter** | 识别泛函与有限样本观测、checkpoint、训练目标和政策计算不能自动对接 |
| P0 | 跨来源真实 outcome A4 数据一致性及研究总体审核接口 | 软件可核对 A4 声明模型和目标，不等于外部真实值匹配或假设科学可信 |
| P1 | **局部/节点协变量条件化后的相关 p(T\|X,W)** | 本轮只把相关性纳入 p-standardized，没打通弱于 full-vector exchangeability 的 nodewise adjusted 目标 |
| P1 | 常见多类型个体与邻居协变量的调整 | 当前 nodewise 仅 X_i 二元与邻居正值 X 计数，不是通用高维 GPS |
| P1 | 多个 W 层及目标总体标准化 | 单个固定 W=w 的结果不能直接推广到其他企业、人员构成或总体 |
| P1 | 一般 `r << q` 的随机政策 kernel | 已有 R1b 有限固定政策混合，不是任意随机 policy |
| P1 | Weak support 的 estimation feasibility 诊断 | 极小正支持≠有限样本可稳健估计，应向下游提供困难度而非改写 POINT |
| P1 | 真实业务需求预注册 Benchmark | 59 卡或 300 节点合成案例不能代表商业任务成功率 |
| 工程 | Python 3.11 远端 CI / 浏览器实际交互 / checkpoint smoke 偶发卡住 | 本地回归不代表跨环境可靠性已验收 |

**建议下一轮**：与 Estimation 负责人先完成 typed target-to-adapter 合同，再选一类与 `C_i` 绑定的相关处理律，写出严格局部 exchangeability/Exposure assumptions 的 R3 数学合同和独立反例，之后再扩大生产子域。A0 留给另一 GPT；不做 R4/R5。
