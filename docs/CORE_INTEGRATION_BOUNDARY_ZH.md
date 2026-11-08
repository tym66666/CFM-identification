# Gateway — Identification Library 连接边界

## 当前完成范围

`CoreIdentificationPort`、`HumanReviewV02`、`route_formulation()` 与 `MockCorePort` 已实现。

**真正的 R1a/R1b/R2 Production Adapter 没有实现**。本仓库不导入或修改 `pfn_pipeline`，不包含任何新的 Identification 证明或 Estimation adapter。`MOCK_ONLY` 不能作为数学证明使用。

## Core Port（未来实际适配器所需）

```python
class CoreIdentificationPort(Protocol):
    @property
    def mode(self) -> Literal['MOCK','PRODUCTION']: ...
    def describe_capabilities(self) -> CoreCapabilitiesV02: ...
    def identify(self, confirmed: ConfirmedProblemV02) -> CoreDecisionV02: ...
    def replay_verify(self, confirmed: ConfirmedProblemV02,
                      decision: CoreDecisionV02) -> CoreReplayV02: ...
```

- `ConfirmedProblemV02` 包含 A1–A6 草稿、原始输入与草稿的 SHA、研究者的显式审核记录；不等于数学库正式 `TaskSpec`。
- 未来适配器**必须**构建和验证正式数学规格。不能因用户勾选某个假设便把真实世界中的该假设视为已经科学证实。
- `describe_capabilities()` 供声明路由名称和版本，并非证明定理可以适用。若 Core 输出的定理路线没有出现在 manifest 中，Gateway 拒绝该结果。
- `identify()` 的每条回复必须绑定完整 confirmed problem 指纹。不能用两个输出形状相同的结果相互替代。
- `POINT/PARTIAL/NOT_POINT/NO_USEFUL_ID` 必须携带 route 和 certificate。Gateway 对数学结论**再次调用** `replay_verify()`，并核对 problem 与 decision digest。
- 正式 adapter 的 `replay_verify()` 必须调用真实、独立的数学验证逻辑；仅返回 True、校验散列、Mock 回放，都不是足够的数学验证。当前 Gateway 只信任显式安装的开发者受控 production adapter，而不能由 LLM 提供其代码或认证许可。
- `NEEDS_INPUT` 不触发 LLM fallback，`UNSUPPORTED` 仅指当前 theorem 库覆盖不足，`NO_ADAPTER` 只指缺转换器；这三者都不意味着数学非识别。
- 当前 v0.2 没有将任何结果交给 Estimation。未来 Estimation 还要独立检查 target、q、g、A4、节点顺序、权重、checkpoint 和统计能力。

## 安全状态

| 状态 | 含义 | 处理 |
|---|---|---|
| `NEEDS_CLARIFICATION` | 问题还有关键缺口 | 提问，不调用 Core |
| `AWAITING_HUMAN_REVIEW` | 仅是待审核草稿 | 等待真实审核 |
| `NO_CORE_CONNECTED` | 尚未安装数学库适配器 | 不宣称任何识别结论 |
| `MOCK_CORE_RESULT` | 只做模拟分流 | 没有严格数学认证 |
| `CORE_VERIFIED` | 可信 Core 的数学结论且已重放 | 表达结论；不自动放行 Estimation |
| `CORE_UNSUPPORTED` | 现有定理库无覆盖 | 未来 v0.3 可探索 LLM 候选推理 |
| `CORE_NEEDS_INPUT` | 缺少数学条件或 A4/A5 信息 | 要求补充；阻止 fallback |
| `CORE_NO_ADAPTER` | 规格转换尚未完成 | 修复对接；不假装定理缺失 |
| `CORE_INCOMPATIBLE` | 当前输入约束矛盾 | 先处理冲突 |
| `CORE_VERIFICATION_FAILED` | 独立验证失败 | 停止，不允许 LLM 覆盖 |
| `CORE_BINDING_FAILED` | 目标/结果指纹不一致 | 停止，不允许替换证书 |
| `CORE_ERROR` | 软件执行故障 | 停止，不认定数学不可识别 |

## 尚需完成

1. 阅读未来最终数学库接口与实际业务路由，确定如何把经确认的 target、信息、假设、安全证据映射为其正式 `IdentificationSpec`。
2. 针对核心路由做五类交叉测试：完整认证、信息缺失、定理未覆盖、假设冲突、证书篡改。
3. GitHub Actions Python 3.11/3.12/3.13 的实际远程运行确认；当前只有本地验证。
4. v0.3 Candidate Reasoner 与正式 Estimation capability 的独立接口。

`human-reviewed` ≠ `scientifically verified assumptions` ≠ `mathematical theorem certificate` ≠ `validated estimator`。
