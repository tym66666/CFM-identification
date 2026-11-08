# 集成边界对抗验收矩阵

**在业务审核之前：** 修改 BusinessCase、Gateway Query 草稿、证据引用、query ID，必须重新审核，不能复用旧的 source/draft/target SHA。

**在数学识别之前：**

| 对抗输入 | 预期状态 | 证明边界 |
|---|---|---|
| 业务全员处理 `(1,1,1)`，Core 类型改为 `(1,0,0)` | `INCOMPATIBLE` | A1 exact target coordinates，不仅类别同为 FixedPolicy |
| 改变目标权重或 contrast exposure | `INCOMPATIBLE` | A1 正式目标分量与审核数学坐标 |
| 将审核 A4 来源文字指向其他总体算子 | `INCOMPATIBLE` | A4 reviewer-reference 绑定 |
| 保留 A4 来源 ID，但篡改 typed source 内容 | `INCOMPATIBLE` | A4 typed source SHA |
| 将审核 A5 假设文字改为另一个许可 | `INCOMPATIBLE` | A5 reviewer-reference 绑定 |
| 篡改 scoped A5 license typed 内容 | `INCOMPATIBLE` | A5 typed license SHA |
| 仅有旧 v2.9 自由文本/布尔科学批准 | `INCOMPATIBLE` | v2.9.1 fail-closed 迁移 |
| R3-policy 审核 Full，但实际调用 Signature | `INCOMPATIBLE` | route-specific admission |
| 未在正式总体 A4 配置显式声明 admission / availability | typed packet `ValueError` 安全拒绝 | 不能由 JSON adapter 赋予 A4 许可 |
| JSON 包含未知键、任意 Python 类路径或复杂的未经白名单对象 | `ValueError` 安全拒绝 | 闭合构造器、无动态执行 |

**正式识别之后：** `Core.status=POINT` 仍需实际执行 `replay_verified_business_outcome()`，并核对 route 和 core-owned summary。非 POINT 不能返回 theorem certificate。科学来源的内容真实性、假设科学有效性、授权者身份仍需系统外独立治理。

**Formal-backed 的量词：** 9 个合成有效正例和 27 个错绑负例，仅对这个预定义的受限有限验证集有意义。不能以 36/36 推断真实网络业务的成功识别率。
