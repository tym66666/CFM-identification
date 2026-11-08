# 两种固定政策的差值：接入统一业务链

用户可以问：“原来考虑甲乙两店启用；如果改为丙丁两店启用，同一个考核周这四家店的平均准时开门率会增加多少？”系统保留一个有方向的比较问题，不要求用户先选择POINT／PARTIAL，也不把它拆成两个无关的水平问题。

本轮连接已有数学能力，未修改数学Core、R1b证书与重放、联合有限均值界求解器与验证器。

明确固定背景的 A0 目标现已配套[跨阶段交接与条件审核](FIXED_BACKGROUND_CONTRAST_ZH.md)：复用 `study.context`，不重复要求模型输出背景；给定该背景的分配律、A4 和 A5 必须另审，不能由无条件声明推定。正式推荐配置未替换。

## 目标和适用范围

第一方案为完整向量 $z^A$，基准方案为 $z^B$，共同评价集合为 $S$，背景为 $w$：

\[
\Delta=\frac{1}{|S|}\sum_{i\in S}\{E[Y_i(z^A)\mid w]-E[Y_i(z^B)\mid w]\}.
\]

“从甲改为乙增加多少”对应乙减甲，不能按文字出现顺序排序。两端分别读取完整安排、评价名单和汇总方式；名单顺序可不同，但评价集合及等权口径必须相同。单个对象、指定子集、全体均可表达。相同结果定义、单位、期间和背景须有原文声明，并独立审核。

未提及的对象不默认处理为0；一端名单不代填另一端。不同人群、跨期间或不同结果、非等权汇总、随机政策、优化目标、对其余安排按设计平均的效应不硬套本合同。

| 已审核的信息与模型 | 原生调用 | 发布结果 |
|---|---|---|
| 符号总体信息，双方满足原R1b条件 | 两端 `identify_network_business_query`；`fixed_comparison.compose/replay` | 有向可观测泛函POINT，保留两端证书与组合记录；不是新Core定理或数值估计 |
| 符号总体信息、全安排均值充分性已审、两端所需节点签名均有正支持 | 两端原生 R2；`workflows.policy_difference.compose/replay` | 有向可观测泛函 POINT；完整安排本身可无支持，不能省略节点支持检查 |
| D2/E1、精确总体均值、逐节点界限、全安排均值充分性及完整无额外耦合模型 | `bounded_contrast_solver.solve`；`bounded_contrast_verify.replay` | 联合sharp区间；退化为POINT；保留informative及其本层基准 |

POINT读取沿用单政策桥支持的独立Bernoulli／均匀固定名额；支持与信息覆盖由各自原生定理检查。R2 两端组合现已接入，详细合同见 [R2 差值](R2_POLICY_DIFFERENCE_CONTRACT_ZH.md)。有限数值模型沿用D2/E1、最多12节点等原合同，参见[联合差值数学推导](BOUNDED_CONTRAST_MATH_ZH.txt)及[文献定位](../literature_support/routes/bounded_policy_contrast.json)。上述比较接点均保留现有 **SYNTHETIC_TEST合成研究限制**，没有生产准入或Estimation/Policy交接。

联合界先合并同一节点、同一签名的正负系数，不能分别求两个区间再相减。例如两端为 $x/2+3/10$ 和 $x/2+1/10$，$x\in[0,1]$：各自水平不唯一，差值却恰为 $1/5$。原联合求解器和独立验证负责这一抵消；读取器不能因此省略完整政策，所有已提供A4仍须相容，系数为零也不允许丢弃矛盾信息。

## 实现与审核

| 环节 | 代码接点及边界 |
|---|---|
| 初步业务目标 | `business_intake`沿用现有A0类别及Prompt；当前连接审核后的网络TOTAL_EFFECT中明确完整政策比较的子域。类别只是粗提示，不是形式目标或证明 |
| 分派 | `business_dispatch.prepare_reader`选择内部NETWORK_POLICY_CONTRAST_FACTS；不是用户菜单 |
| 比较事实 | `network_contrast_reading`扩展两端target，复用六种已有网络读取协议的共同字段、来源、声明状态与解析器 |
| 计划检查 | `network_contrast_dispatch.inspect_methods`保留原候选、显式投影两个目标；生成PENDING审核表，不求解 |
| 独立审核 | 意图、读取、科学及计划审核分开；增加“两端完整与有向比较”“共同人群、等权、结果及背景”项目；同一科学审核绑定共同模型 |
| 执行 | 全部审核通过后复用原生编译，两端仅目标不同；求解及重放前后核对输入摘要和证据 |
| 整题、恢复与重读 | `business_case`仍将比较计为一问；原intake保存与恢复不改写；候选变化使旧审核失效，重读后需审核变化 |

A0为OTHER、UNRESOLVED或其他未接目标时保持阻断／覆盖缺口，不按关键词重新分类。如果A0把一问误拆成两问，需要重读或独立纠正，不能拼接两个成功标记冒充原问完成。当前并不等于所有效应类型已经自动接通。

共同备注保留在两个显式投影中。当前 `note_review` 以 `first`／`second` 提供各自绑定的记录，两端都须通过；worksheet在 `endpoint_plans` 中。备注放行不授予科学许可。审核哈希保证内容一致性，不证明现实审核人身份或假设为真。

两政策差值现复用 `network_information_evidence.prepare/check` 的独立来源角色审核。同一张精确均值表可以分成多条不重复的记录，并保留名单、编码或网络定义的辅助引用。比较专用审核绑定完整原答及两端目标；所有引用必须恰好分到“同一原表”或“辅助定义”，每条信息记录都要引用该表。原表数值与辅助材料的语义归属仍由独立审核者核对，程序不靠文档名称判定。不同真实信息表、缺表引用、重复格子、额外等式、来源拒绝与未批准科学条件均不因此放行。

这一步不修改 LLM 原答，不填引用，不授予 A4/A5 许可，也不改变联合求界。单政策旧审核格式保持兼容；比较审核使用独立版本 `network-contrast-information-evidence-review-1`。首次读取指标与修复接入层后重跑保存原答的结果须分别报告。定向检查位于 `tests_gateway/test_network_information_evidence.py`。

## 停止状态

- NEEDS_INPUT：方向、安排、评价名单、共同背景或模型范围未明确；有支持但缺少必需总体均值也保留缺项。
- CHECK_BLOCKED／READING_RECHECK_REQUIRED：来源、格式、审核、绑定、科学声明冲突或证书检查失败。
- ADAPTER_NOT_CONNECTED：不同人群、非等权、额外限制、未连接的方法组合等，不声称不可识别。
- UNSUPPORTED：原 R1b／R2 未识别两端；没有补界或自动PARTIAL回退，也没有不可识别证明。
- INCOMPATIBLE：原有限模型报告矛盾，保持诊断，不伪造不可行证书。

## 复现

```powershell
python -m examples.network_contrast_dispatch_reference --allow-synthetic-reviews --output outputs/contrast_reference_001
```

保存原材料及符号POINT、sharp PARTIAL、抵消后POINT三个完整合成结果。示例读取与审核是人工编写的测试夹具，不是LLM成绩。共同业务CLI继续使用原命令，不新增用户选方法参数。

新 R2 接入与正负例记录见 [R2 差值验收](R2_CONTRAST_INTEGRATION_ZH.md)，新增 S76；旧固定验收为 S30 及 `tests_gateway/test_network_contrast_dispatch.py`。实际运行数和真实模型探针见[框架验收](FRAMEWORK_ACCEPTANCE_ZH.md)。
