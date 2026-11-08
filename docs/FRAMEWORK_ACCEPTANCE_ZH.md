# 固定框架验收

最新一次完整验收和安装结果统一见 [学生交接验收](DELIVERY_READINESS_ZH.md)。以前的分轮实验、模型首答和复查成绩保存在 历史记录（历史记录不随发布），不累计成当前版本准确率。

## 清单与职责

- `evaluation/framework_acceptance.json`：必须实际执行的测试节点，以及数学 / 审核 / 会话义务。
- `evaluation/framework_suites.json`：每个固定测试文件的唯一主要责任，quick / chain 的选择。
- `evaluation.framework_acceptance`：实际收集、执行并核对节点，检查失败、跳过、漏收集、重复收集与执行期间源码变化。
- `scripts/check_framework.py`：薄入口。不带 suite 参数仍为 full，旧命令不静默缩短。

```powershell
python scripts/check_framework.py --suite quick --output outputs/quick_check
python scripts/check_framework.py --suite chain --output outputs/chain_check
python scripts/check_framework.py --suite full --output outputs/full_check
```

每次使用新目录。层级选择和代表测试见[测试指南](TESTING_ZH.md)。全仓其余原生数学与兼容检查由 `scripts/check_offline.py` 运行；三个下游集成测试需显式选择 `--integration`，本轮未修改下游。

## 不可丢失的验收边界

| 维度 | 需要证明什么 |
|---|---|
| 读取合同 | 请求、Schema、解析、来源、诊断和重读使用配套组件；未知协议不悄悄回退 |
| 业务目标 | 政策、比较方向、评价对象、权重、背景和所问量不跨阶段改变 |
| 科学审核 | 待审、拒绝、缺项、撤回、旧批准错配继续阻断；模型不能自批 |
| 数学执行 | 调用原生方法；POINT 目标一致，PARTIAL 模型与 joint bounds 正确 |
| 证书与整题 | 真实独立重放；伪造结果、错目标证书拒绝；单问通过不替代整题覆盖 |
| 停止与恢复 | 读错、缺材料、覆盖缺口各有独立状态；重读后审核完整变化 |
| 历史兼容 | 旧接口、旧请求和保存会话仍按原合同恢复；明确记录有意修复的异常 |
| 安装 | wheel 在源码之外运行，不借用源码或测试夹具路径 |

S83 / S84 / S85 分别对应 R3、政策均值、两政策差值的读取配套；S86 保留实验性的定义引用义务；S87 对应本次公共入口、五类组件登记和三个教学示例。它们是测试索引，不是数学路线分类。

S92–S95对应政策均值、两政策差值、局部效应、R3观察性政策的共同诊断验收：只读视图、目标/范围/条件保持、原生证据与审核不绕过。当前full已包含这些义务；实际通过数及环境重跑记录仍统一在上述交接验收中维护。

离线示例固定草稿和合成审核，不计算为真实 LLM 首答成功；可选在线历史档案不随包交付，缺档跳过需单独报告。本轮没有新增模型调用。
