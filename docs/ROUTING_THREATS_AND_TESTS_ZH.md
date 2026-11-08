# 风险与验收标准

| 风险 | 代码约束 | 测试/剩余问题 |
|---|---|---|
| LLM 把“随机一半”自动确定为 Bernoulli | 复用 v0.1 deterministic audit | 7 个 v0.1 业务模拟案例；不能保证真实 LLM 全对 |
| 草稿被篡改后沿用旧审核 | 人工审核 hash + 重新审查原文证据 | 篡改业务、草稿、review status 的拒绝测试 |
| 自动让 LLM 承认随机化或签名充分性 | 只有 reviewer 显式列出 accepted names | 测试不允许出现凭空接受的假设；人类真假身份尚未核实 |
| 尚无 Core 却直接回答“不可识别” | `NO_CORE_CONNECTED` | 离线测试通过 |
| Core 缺定理时错误说成非识别 | `UNSUPPORTED` 与数学状态分离 | Mock 与测试中的生产 Port 协议模拟验证 |
| Core 需要信息却转交 LLM 猜答案 | `NEEDS_INPUT` 阻止 fallback | 负例测试 |
| Core 适配器没有实现却转交 LLM 猜答案 | `NO_ADAPTER` 阻止 fallback | 负例测试 |
| 回放错误或目标串号 | 双 hash 绑定、路由清单、独立 replay 请求 | 拒绝回放、错误问题指纹、伪造路由负例测试 |
| Mock 错误宣称通过数学认证 | Mock 返回始终 `MOCK_ONLY` | 路由负例和 CLI 测试 |
| 证书是外部伪造、但形式上含正确 hash | 正式 verifier 必须独立检查数学内容 | **未解决**：生产 Adapter 尚未连接；hash 不是数学证明 |
| 显式 reviewer id 被程序伪造 | 文件式审核只提供审计记录 | **未解决**：正式 UI 应使用真正的人机确认交互 |
| 估计器没有训练该 target | 全部 v0.2 `estimation_handoff_allowed=false` | 此阶段不接 Estimation |
| Python 版本兼容性 | CI 配 3.11/3.12/3.13 | 本地检查已完成；远端 CI 待推送 |

v0.2 原有 FormulationReport 和业务输入输出仍能使用。新增所有正式科学认证状态都必须来自未来可信 Core Adapter 的数学 verifier；本轮模拟器和自动化测试不验证真实定理正确性。
