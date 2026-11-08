# 均值顺序两政策差值：共同业务入口

本次接通已有 `MEAN_ORDER_D2_E1`，不增加定理，不修改数学 Core。原专门研究入口仍可使用。

用户描述两种完整安排及希望评价的对象。系统从共同业务入口读取第一政策减第二政策，读取科学声明，经来源、目标、完整模型和逐对象条件审核，交给既有均值顺序求界器；独立重放成功后才报告结果。用户不需要先选 PARTIAL 或求界方法。

## 范围与审核

- 现有 D2：等概率固定名额；E1：严格多数、平票低、孤立点为零。处理前固定简单无向网络、单期二元处理、至多12个对象，二元或连续数值结果。
- 两个完整政策、第一减第二、共同评价名单和等权平均、同一结果与固定背景。其他聚合不自动替换。
- 精确总体签名均值及其完整性；逐对象科学界限及类型、单位、期间；全部对象、全部完整安排的均值充分性。样本均值不能作为精确 A4。
- 每个对象的 OWN / PEERS 分别说明：采用均值非减条件，或明确不作该假设。未提及不等于 NONE；观察到正相关不等于科学假设；“每次结果不降低”“无影响”“不提高”不擅自改成当前均值模型。
- 模型只包含声明的基础条件、均值充分性、界限和顺序，无其他限制。审核保留每个对象、每个轴的独立决定。

两个完整性字段含义不同：`bounded_model.no_additional_coupling_constraints` 是没有额外耦合；`mean_order_model.no_additional_constraints_beyond_declared_orders` 是除所列顺序外无其他限制。有顺序时前者不能填 true。矛盾、未知和额外限制分别阻断，不能改写候选以通过。

当前仍限显式合成研究审核；`production_admission`、`estimation_handoff_allowed` 保持 false。核实科学条件与校验证书是两件事。

## 一条共同链路

```text
project / business_intake
  → TOTAL_EFFECT 的原两政策事实读取家族
  → 可选 mean_order_model（复用 OrderReading）
  → 来源与变更复核 → 共同目标、A4/A5、逐对象顺序审核
  → MeanOrderProblem + ReviewedMeanOrder
  → mean_order.submit → 原精确求界器 → 原独立验证器
  → POINT / sharp PARTIAL / 带矛盾证书的 INCOMPATIBLE，或明确缺项
```

直接优化共同模型中的有向差值，不相减两个独立识别区间。`sharp` 相对于完整审核模型；空可行集是 `INCOMPATIBLE`，不能给区间或说成“不可点识别”。`baseline_bounds_only_range` 只是仅有界限时的参考范围，不能称为“去掉顺序但仍保留所有 A4 后的识别区间”。

## 文件归属与兼容

| 位置 | 责任 |
|---|---|
| `cfm_id_llm/network_mean_order_reading.py` | 新字段 Schema；复用既有顺序读取投影；不批准假设 |
| `cfm_id_llm/network_contrast_reading.py` / `network_fact_protocols.py` | 请求、解析、来源、格式诊断和重读的配置配对 |
| `cfm_id/network_mean_order_dispatch.py` | 将已审核记录连接到原数学合同，核对结果和输入绑定 |
| `network_contrast_dispatch` / `network_bounded_dispatch` | 复用两端目标及有限 A4、界限检查，不伪造无耦合模型 |
| `mean_order_contract.py` / `mean_order_solver.py` / `mean_order_verify.py` | 原有数学 Core，本次未改 |
| `capability_registry` / `method_requirements` / `contrast_diagnostics` | 登记实际能力、展示原审核与结果，不产生证明 |
| `examples/network_mean_order_dispatch_reference.py` | 可运行的合成材料、人工构造读取和显式合成审核；不是 LLM 评测 |
| `tests_gateway/test_network_mean_order_dispatch.py` | 接入正负例、假设阶梯、重读和证书防篡改 |

本次能力接入时的配置为 `network-source-selections-mean-orders-1`，它沿用原 alignment 读取组件，为两政策问题增加可选均值顺序字段。2026-11-03 的推荐起点已更新为保留这项能力的 `network-shared-definitions-1`，见[推荐配置](BUSINESS_READING_CONFIG_ZH.md)。旧 profile 的请求、Schema、解析默认保持原状，旧记录仍按原配置重建。没有顺序字段的普通 POINT / mean-box 继续走原数学方法。

## 运行与预期

在已安装项目依赖的工作源码根目录运行，输出目录须未存在：

```powershell
python -m examples.network_mean_order_dispatch_reference --allow-synthetic-reviews --output outputs/mean_order_entry
python -m pytest tests_gateway/test_network_mean_order_dispatch.py -q
```

四店完整合作网，每轮随机选两店；固定相同的 A4 和 `[0,1]` 条件均值界限，比较全部使用与全部不用的平均差值：

| 明确采用的均值顺序 | 已有求界器输出 |
|---|---|
| 本人和同伴均值均非减 | `[1/5, 1]` |
| 仅本人均值非减，同伴明确不假定 | `[-1/5, 1]` |
| 两轴都明确不假定 | `[-1, 1]` |

三份条件版本保持目标、A4、界限不变，均需重新审核并重放。该例没有承诺 POINT→PARTIAL 的完整阶梯；另有原试点支持内、不同政策的 POINT 正例 `[1/5,1/5]`。缺少同伴条件声明的材料返回 `NEEDS_INPUT`。

本次离线验收不说明 LLM 首读准确率提高。文献与原数学合同沿用 [均值顺序证据记录](../literature_support/routes/mean_order_research.json)，不是通过新接线扩大文献结论。

## 本地验收记录（2026-11-01）

- 新接入文件的39项测试通过，包括缺轴、拒绝、来源错误、复查后旧审核失效、共同范围、比较反向、支持内 A4 缺失及证书篡改。
- 原均值顺序数学和专门接口118项测试、137个子测试通过。
- 完整框架运行2780项通过、1项失败：文献数学导航遗漏了新增业务方法编号。补齐非执行导航后，相关36项检查通过；期间运行源码与测试源码没有再次改变。保留最初失败记录，不声称整套首次全绿。
- 另用当前 `project.start` 推荐配置走完业务字段审核、事实来源审核、科学审核、求界、重放及整题汇总，得到 PARTIAL。
- 数学合同、求界器、独立验证器及原网络数学代码未改。没有调用真实LLM；新字段的模型读取效果尚待单独实测。
