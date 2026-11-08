# 业务读取字段与逐项审核

本页面向维护者。普通用户仍提交业务问题和材料，不选择内部识别路线或字段协议。

## 一份字段定义，三项独立检查

字段定义集中在 `cfm_id_llm/business_field_contract.py`，供既有输出Schema、缺项目标提问和新的审核表共同使用。原System Prompt和字段描述文本保持相同，历史请求与检查点不重写。新增字段时必须同步注册，运行时会拒绝Schema与字段集合不一致，固定验收也检查覆盖。

可选 `a0_response_contract='explicit-field-roles-1'` 将同一份字段meaning/excludes直接附到模型可见Schema，不再只让审核者看到完整定义。它继承explicit-sections-1的区域要求，补充枚举字符串与claim格式区别、缺失陈述与已知值、历史规则与网络时序、对象关系与变量图、暴露定义与目标口径的边界。现有目标说明仍保留，不覆盖其字段描述。JSON类型、默认值、缺项规则和审核定义未改变；不按关键词迁移候选、不自动审批，旧协议/默认不变。

这是开发端实验响应协议，普通业务用户不用选择。真实业务验收发现它可以减少部分字段误放，但仍有“未提供”被标为STATED、协变量混入处理以及比较符号相反的问题，因此未升级为默认。冻结结果见[框架验收](FRAMEWORK_ACCEPTANCE_ZH.md)；通用字段解释有助于维护，不等于证明LLM可靠。

另有实验协议 `a0_response_contract='evidence-slots-1'`，继承共享职责说明，并增加两个模型候选位置：顶层 `missing_information` 保存原文明示的缺失说明、对应字段及引用；每问 `comparison_order` 保存有向比较运算及引用。前者只能指向当前UNKNOWN的claim字段，不能补值；后者区分主方案减基准、基准减主方案、方向未定与无需比较。普通用户继续提交业务原文，不填写这些机器字段。

该协议中的aggregation只记录结果量、汇总与权重。程序将已声明的运算标注到下游aggregation，并合并运算本身的引用，不交换主方案/基准，不读取关键词猜方向；原始候选单独保留。来源缺失记录、运算及原有字段全部进入逐项审核；原文明示“未提供”也不自动证明其他材料没有给出该值。已知值与缺失记录冲突、未知路径、无引用、缺少区域或不匹配的运算会拒绝。差值方向未定先要求核对原文，不能自行选符号。

这是新的输出及审核合同，不是单纯加长Prompt，也不是新的识别路线。模型仍可能把缺失说明放错位置、选择错误运算或引用不足；结构检查不能判定自然语言含义正确。默认保持原样，真实效果以独立冻结实验为准。

后续可选实验 `a0_response_contract='inline-evidence-1'` 将确定值与缺失原因放回同一字段，互斥返回：

| 原文情况 | 候选表示 | 审核与后续含义 |
|---|---|---|
| 给出确定事实 | `STATED/INTERPRETED + value + refs` | 核对实际含义、职责和引用，不自动批准科学条件 |
| 明确说本字段未提供或尚未决定 | `MISSING + reason + refs`，不能带value | 原字段上审核一次；后续投影为UNKNOWN，不补值 |
| 没有找到内容，也没有明确缺失声明 | `UNKNOWN` | 仍需区分材料缺失与模型漏读，不能编造原因 |

该格式禁止另附顶层missing_information清单，避免两个位置互相矛盾。MISSING仅适用于common及semantics中的单个claim字段，不用于goal、枚举、协变量列表或comparison_order；比较运算及方向未定规则与evidence-slots-1相同。缺失原因只是模型对原文的理解，不是材料确实缺失的证明。没有抽签但负责人决定，仍是已知分配规则；名单没有调整，仍是已知时间稳定性，不能按否定词一律改成MISSING。

原始回答中的状态、原因及引用完整保存，审核时显示在原字段上。投影层只按显式类型转换，不通过关键词猜测或修复语义。各输出合同的请求、解析、审核由 `compact_response_contract.evidence_contract` 中封闭的源码引用配对，配置不能加载任意模块。旧会话和旧请求不迁移；新格式尚未成为默认。

`inline-target-roles-1` 是后续的局部字段解释实验：在比较运算、基准内容、暴露定义、目标同伴条件及政策字段旁说明彼此的区别，复用inline-evidence-1的全部JSON类型、解析函数、状态规则与审核函数。它不新增字段或识别方法。该协议也强制完整逐项审核；旧来源上下文与审核不能复用到新请求。

该实验**目前不推荐替换现有配置**。2026-10-27十条业务新旧配对中，新说明整份读取3/10，旧inline-evidence-1为4/10；新说明改善了原仓库题的方向/基准区分，但出现四份格式或绑定失败。无网络超时，不能以重新发送请求掩盖这些失败。结果见[框架验收](FRAMEWORK_ACCEPTANCE_ZH.md)，完整实验保存在源码包外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。后续优先研究模型可见格式说明的精简与字段适用范围，而不是继续累计提示规则；这些尚未实现，不应写成已修复。

新合同进入后续政策差值读取时，专门说明first/second是运算位置，不能固定理解成主方案/基准。问主方案使结果下降多少时，first应为基准、second为主方案；仍由原始业务材料和独立目标审核确定具体名单。旧合同的专门请求不变；数学模块只接收已审核的两端坐标，不读取这些自然语言解释。

| 内容 | 应该记录什么 | 不应当混入什么 |
|---|---|---|
| 目标字段 | 评价谁、哪项政策/干预、结果量、权重、时间 | 从可用数据替用户选择目标；把尚未决定写成已定值 |
| 对象关系与变量图 | 对象间关系放unit_network，变量因果关系放variable_causal_graph | 从对象间干扰或均值暴露充分性自行生成变量DAG |
| 历史设计与信息 | 实际分配机制、样本、声明的总体信息分别记录 | 用未来政策替代历史设计，把样本当总体，或把没有总体信息当成可用值 |
| 暴露与科学限制 | 提取已声明的暴露定义；科学条件另行读取、审核 | 暴露定义自动意味着A5成立，或来源陈述直接获得A4/A5许可 |

每个字段独立审核三个方面：

1. **field_role**：内容是否属于该字段。真句子也可能填错位置。
2. **value_state**：字段值及已知/未知/不适用状态是否忠实于原文。认可一个UNKNOWN正确，不会把目标补齐。
3. **source_coverage**：该字段实际选中的引用是否支持整个value。审核者找到其他原文，不会自动补进模型引用。

已定值使用STATED或INTERPRETED。UNKNOWN只表示候选没有给出值，可能是资料未提供、用户未定，也可能是模型漏读；须对照原材料再区分，不能自动证明资料缺失。NOT_APPLICABLE沿用既有目标类型限制，仅适用于相应对照/政策字段。没有提供总体信息这类否定说明保留在原文，不把它当作可用总体信息值。

assignment_family与kind是原接口中的枚举，没有独立refs位置；审核表明确显示其历史分配描述或goal作为枚举判断依据。不能因此给其他claim借用引用。协变量逐项列出；空列表与省略字段会明确显示，不能隐藏未经审核内容。

## 接入位置与调用

`cfm_id/business_field_review.py` 在现有compact A0与query review之间提供细化审核。它不调用模型，不选择定理，不批准科学条件，不推断自然语言真假。

```python
from cfm_id import business_field_review, business_dispatch

sheet = business_field_review.prepare(current_intake, "q1")["field_worksheet"]
record = {
    "version": sheet["version"],
    "binding_sha256": sheet["binding_sha256"],
    "authority": sheet["expected_authority"],
    "reviewer": "填写独立审核者",
    "evidence": "填写审核所依据的原始材料与核查说明",
    "decisions": sheet["decisions"],  # 全部PENDING；由独立审核者逐项填写。
}
# 每项填写三项决定、reason及当前source_ids；这些审核来源不改写候选refs。
reviewed = business_field_review.submit(current_intake, "q1", record)
# 只有ready且获得有效query_review时，才按原流程准备后续事实读取。
```

离线CLI：

```powershell
python -m cfm_id.business_field_review worksheet --intake intake.json --query q1 --output field_worksheet.json
python -m cfm_id.business_field_review submit --intake intake.json --query q1 --record independent_field_review.json --output field_review_result.json
```

输出文件须不存在。合成实验必须明确使用 `authority='SYNTHETIC_TEST'` 或CLI的 `--authority SYNTHETIC_TEST`，不能把夹具批准当成真实科学批准。

全部适用字段、全部三个维度都必须记录；不接受漏项、替代字段、未知来源、重复来源、过期记录或空白的非待审理由。审核表给出实际候选、实际引用和完整原始材料，所有默认决定为PENDING。不是由被测模型自批，也不提供一键全通过函数。

## 与现有流程的兼容边界

细化记录归纳到原query review的三项决定，并作为可选field_review随记录保留。业务分派重新检查内层绑定及归纳结果，不能把内层REJECTED改成外层ACCEPTED。后续请求绑定包含完整记录；改动/删除明细会改变请求，不能复用旧事实回答及审核。

原来的简表审核仍是兼容接口；未附细化记录时序列化与请求保持原样。此处没有悄悄要求旧会话迁移。调用方如采用逐字段审核，应保存完整返回记录，不自行剥离明细再改用简表。系统没有外部身份认证或签名，记录正确性仍依赖可信审核者；检查结构和绑定不等于验证审核意见真实。

显式选择evidence-slots-1、inline-evidence-1、inline-target-roles-1、inline-output-guide-1或inline-unified-contract-1的新会话必须附完整逐项审核，简表或剥离明细不能进入事实读取。共有字段的缺失说明属于各问的共同审核范围，某问专属缺失说明及运算不自动批准其他问题。新会话、候选、运算或缺失原因变化都会使旧审核失效。更早的协议保留原兼容行为。

原A0若仍有缺项目标、格式错误、未完成的重读变化审核等，细化审核不解除这些阻断。因较早阻断而无法形成query review时，返回原停止状态和 `query_review=None`，同时保留逐字段决定；不能把“字段未知是准确的”误解为“可以回答此目标”。

只覆盖选定query及全部共有字段；其他query不自动获批，但其原始材料仍属于绑定范围。材料、候选、会话历史、当前字段定义或审核范围变化使旧明细失效。仅仅有真实来源编号，不会自动将任何维度变为ACCEPTED。

通过此审核最多到达已有事实读取准备阶段。后续仍需typed事实读取、来源/意图审核、独立科学条件审核、适用性检查、数学Core与独立证书重放。当前不新增识别覆盖、不改数学Core；也未宣称修正了LLM本身的误读。

## 维护与验收

新增字段先修改共享定义和对应Schema，再处理规范化映射与必要的后续适配；不得只加一个Prompt字段而漏掉审核。现有System Prompt保留为兼容文本；若改变其实际语义，需另做显式合同迁移和真实模型验收，不能改完继续使用旧请求哈希。

测试为 `tests_gateway/test_business_field_review.py`，纳入固定清单S28。覆盖职责/状态/引用否决、错误的上层通过、缺项仍阻断、明细丢弃导致旧绑定失效、范围和版本变化、长短引用、多个query、协变量逐项审核、DAG和网络POINT链及科学审核前禁止执行。

互斥表示另由 `tests_gateway/test_inline_evidence_slots.py` 和S34验收：长短引用、值与缺失冲突、不合法位置、原因/来源缺失、独立审核不可绕过、重读绑定、分问范围，以及原生DAG POINT和网络POINT/PARTIAL重放。离线合成通过不代表真实模型准确率。
