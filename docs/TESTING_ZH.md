# 测试职责与运行层级

测试数量不是业务覆盖数或LLM准确率。每项测试应说明保护什么合同、由哪个文件维护，以及何时需要运行。

当前发布检查见[发布收尾记录](RELEASE_ACCEPTANCE_ZH.md)，原安装基线保留在[交接验收](DELIVERY_READINESS_ZH.md)。下文测试整理与真实 LLM 小节保留当时计数，不作为当前源码通过数。

## 三个运行入口

在项目根目录、已安装测试依赖的Python环境中运行；每次使用新的输出目录：

Windows 下先与 CI 对齐 UTF-8 和线程设置，避免中文 CLI 输出被系统 GBK 编码、以及多个小矩阵测试过度并行：

```powershell
$env:PYTHONUTF8 = '1'
$env:OMP_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
```

```powershell
python -m evaluation.framework_acceptance --suite quick --output outputs/checks/quick_001
python -m evaluation.framework_acceptance --suite chain --output outputs/checks/chain_001
python -m evaluation.framework_acceptance --suite full --output outputs/checks/full_001
```

| 层级 | 职责 | 使用时机 | 不代表什么 |
|---|---|---|---|
| `quick` 快速检查 | 配置配对、关键缺项与科学条件阻断、比较方向交接、验收计分完整性 | 日常小改动；另外运行直接涉及的测试 | 全部数学路线或历史接口通过 |
| `chain` 完整链路 | 包含quick；代表业务的审核、真实求解、证书重放、整题与恢复；九类专门会话的共同义务 | 连接层、审核、重读或公共接口变化后 | 全部历史配置通过；真实LLM稳定 |
| `full` 全量兼容回归 | 全部固定框架文件，包括历史配置、旧接口、条件版本和各类负例 | 一组修改收尾、发布前、广泛依赖变化后 | 全仓库数学测试穷尽、现实假设成立或模型理解准确 |

不提供`--suite`时仍为full，旧命令不会默默变短。加`--list`可查看实际选择。chain包含quick，同一测试只执行一次；不要把不同层级的重叠测试相加。

较小层级的结果包含`full_framework_scope=false`、`full_framework_passed=false`及`unselected_required_nodes`；未运行不当通过。必需节点漏掉、意外过滤、跳过、xfail、子测试失败、重复收集或运行期间源码变化均使相应验收失败。合成审核只用于离线测试。

## 每项测试放在哪里

完整归属在[`evaluation/framework_suites.json`](../evaluation/framework_suites.json)：所有固定测试文件各有一个主要职责；具体测试可以保护多个边界，但维护位置只有一个。

| 职责 | 内容 | 代表文件（tests_gateway下） |
|---|---|---|
| 原材料与来源 | 材料读取、切分、编号、样本范围 | `test_material_reading_contract`、`test_paragraph_sources` |
| A0业务合同 | 所问量、目标两端、字段归属和原句引用 | `test_target_shape_contract`、`test_compact_evidence_slots` |
| 事实读取合同 | Schema、解析器、配置登记、条件交接 | `test_fact_reading_contracts`、`test_policy_reading_contracts`、`test_contrast_reading_contracts` |
| 审核与恢复 | 来源审核、拒绝、追问、重读及旧批准失效 | `test_fact_source_review`、`test_fact_reading_revision` |
| 业务执行 | 目标与数学输入绑定、真实求解、证书篡改拒绝 | `test_network_dispatch`、`test_network_bounded_dispatch`、`test_network_contrast_dispatch`、`test_network_r2_contrast` |
| 会话生命周期 | 保存恢复、撤回、条件版本、跨路线共同义务 | `test_framework_contract`、`test_research_versions` |
| 工程维护 | 能力登记、依赖边界、验收本身 | `test_capability_registry`、`test_framework_acceptance` |
| 历史显式入口 | 老业务调用兼容 | `test_business_entry` |

该分类只管理测试，不增加业务入口或数学路由。原生数学测试保留原位置；修改数学方法时，必须另运行相应原生合同、求解和独立验证测试。本轮不修改数学Core。

## 本轮合并的重复

| 原重叠 | 现在的行为维护位置 | 保留的检查 |
|---|---|---|
| 登记测试再次检查两端缺失、范围冲突、样本误作总体 | `test_network_contrast_dispatch::test_missing_conflicting_or_unsupported_comparison_blocks_before_compilation` | 原19类负例，并入完整信息未确认及alignment配置下三类冲突；都不得调用数学编译 |
| 两处检查反向比较 | 同文件的`test_reversed_direction_requires_new_reviews_and_negates_the_joint_answer` | 旧批准拒绝、同会话重新审核、新建反向业务、正确反号、目标摘要与重放 |
| 政策登记在13种配置下再次求差值抵消 | 登记文件核对格式／端点配对，原差值文件负责完整计算 | 全配置保留输入一致性检查，默认与alignment配置保留真实抵消及证书检查 |
| 配置兼容与数学执行交叉重复 | 两个读取登记文件检查输入；原业务执行文件检查真实求解 | 13种配置×4条均值路径、13种配置×4条差值路径，共104组Schema和数学输入比较；对应原生执行组合从104组收敛为16组 |

登记文件继续检查公共消费者是否真的使用登记组件，以及首次与重读的配置一致性。不能只看最终POINT字样。

输入比较覆盖完整规范化事实、目标、A4投影、方法、来源索引和逐项审核要求；只排除已逐请求核对的`reference_context`，不笼统去掉哈希或来源。104组输入比较组织在26个配置测试节点内，所以pytest节点数并非检查组合数。默认协议与alignment协议保留真实求解及重放，独立的缺项、拒绝、旧批准失效、反向比较、sharp界限、联合抵消和证书篡改测试保留。此比较仅针对固定回归输入，不保证任意模型输出等价。

这轮先收拢明确重叠的部分，不宣称其余测试已经全部去重。测试数量不是优化目标。

## 新增／调整测试

1. 先找同职责已有测试，补充缺陷或参数；新合同才新增独立函数。
2. 配置兼容尽量直接比较请求与解析；数学连接才运行求解。Schema相同不能代替数学输入一致性证明。
3. 新固定测试文件须登记职责，按风险加入quick／chain，full仍覆盖全部固定文件。
4. 更新`framework_acceptance.json`的必需节点。旧S编号保留追溯；多个义务可引用同一个规范测试，不复制实现。
5. 选择规则按已登记文件／函数／参数边界匹配。重命名导致失效必须修正，不能靠宽泛关键词过滤取得通过。
6. 发布前运行full，报告实际范围。真实LLM验收另记原文、原答、人工语义与引用审核、执行及停止原因。

## 真实LLM验收接续

先冻结业务、正负条件、配置和审读标准。参考答案不发送给模型，不按回答补条件。实际A0通过独立审读后才能进入真实端到端事实读取；参考A0下的事实读取只算组件诊断。首答、重读、格式、语义、引用及最终执行分别报告。

整理阶段记录留在维护者本机，不随源码分发。整理前为2470项；第一阶段实际完成quick 87、chain 565、full 2468项（另133子测试）。配置／数学职责拆分后的收集范围为quick 87、chain 554、full 2380；**收集数不当通过数**。整理阶段状态为`CONSOLIDATION_STATUS.json`，此前全量结果仅对应第一阶段源码。

随后已进行真实LLM验收，另见同目录`LIVE_SUMMARY.json`和[最新验收记录](FRAMEWORK_ACCEPTANCE_ZH.md)。本次只针对实际暴露的非法空状态定位缺口补充3个测试节点；相关88项定向检查通过，未再次运行全量。不要将不同源码版本或诊断、重读与首答的分母混算。

## 学生入门链路

`python -m examples.student_handoff --allow-synthetic-reviews --output outputs/first_run` 离线运行 POINT、sharp PARTIAL 与缺条件阻断；它使用固定草稿和合成审核，不是模型准确率。`test_student_handoff` 归事实合同职责，公共配置和家族登记进入 quick，三个完整示例进入 chain / full。原生公式、审核否决及证书测试继续由对应专门测试负责。安装验收还须在源码外运行这三个示例，确认加载的是安装包。
