# Causal-IDFM · Identification

纯 Identification 网页发布在[个人仓库的 demo/](https://github.com/zzyyLOGIC/CFM-identification/tree/main/demo)：业务输入与附件、必要追问、识别公式、科学条件与证书重放；不依赖估计／策略。在个人仓库根执行 `python demo/serve.py`，默认端口 8772。团队发布包不重复携带这份网页，使用外层 `demo/` 和 `serve_demo.py`。

从业务问题和材料，到经审核的因果识别结果。LLM 提出读取草稿；研究者确认目标、可用总体信息和科学条件；数学模块检查适用域、应用定理并独立重放证书。用户不需要先选择数学方法。

```text
业务材料 → A0 草稿 → 业务意图与来源审核 → 专门事实读取
                                              ↓
逐问和整题结果 ← 独立证书重放 ← 数学执行 ← A4 信息 / A5 条件审核
```

读错后显式复查；缺条件时追问；方法未覆盖时报告覆盖缺口。未验证的 LLM 候选不能替代正式结论。当前是**需要审核的研究框架**，业务首读准确率仍有不足。

## 个人版直接体验网页

下载完整个人仓库，在仓库根执行：

```powershell
python -m pip install -e ".[documents]"
python demo/serve.py
```

打开 `http://127.0.0.1:8772/`，可输入业务、上传材料、配置自己的模型连接，或选择九个示例。后台完成读取和复核，保留必要追问；结果显示公式、采用条件和独立证书重放。团队全流程网页请按团队根目录的 `LIVE_DEMO_ZH.md` 启动。

支持独立上传对象名单、关系表、字段说明表及 CSV／Excel 记录，并先在本地预览。按对象编号关联，保留孤立对象及实际结果覆盖；不会把有限记录当精确总体信息。格式、用途和边界见[文件输入说明](docs/FILE_INPUT_ZH.md)。

## 唯一源码与起点

团队仓库的识别源码位于 `identification/`；个人独立仓库以该包为仓库根，直接在根目录运行下方命令。个人版的纯 ID 网页在包内 `demo/`；团队全链路网页使用外层入口。不需要手动管理源码 hash，证书内部摘要仍用于防止材料或审核被替换。

新应用统一使用 [`cfm_id.project`](cfm_id/project.py)，读取唯一推荐配置 [`cfm_id/configuration/reading.json`](cfm_id/configuration/reading.json)。当前主方案为目标优先的新候选 `target-first-skill-1`，实际加载包内读取 Skill；网络事实阶段保留已审核意图并强制核对交接。它仍是需要独立审核的研究入口，不代表已证明稳定的自然语言准确率。旧 API 默认值和旧协议只为兼容保留，见[配置指南](docs/BUSINESS_READING_CONFIG_ZH.md)与[意图交接](docs/REVIEWED_INTENT_HANDOFF_ZH.md)。

固定政策均值和两政策差值现采用共同定义事实合同。10份冻结业务中，LongCat两轮完整链路通过9/10和8/10；DeepSeek两种设置均4/10。受测范围、失败与审核条件见[真实验收](docs/SHARED_DEFINITION_ACCEPTANCE_ZH.md)，不能将其外推为所有能力的准确率。

## 安装，运行三个完整示例

Python 3.11 或更新版本。在本目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
.venv\Scripts\python -m cfm_id.project config
.venv\Scripts\python -m examples.student_handoff --allow-synthetic-reviews --output outputs/first_run
```

Linux/macOS 将 `.venv\Scripts\python` 换成 `.venv/bin/python`。输出目录必须是新目录。以上**不联网调用模型、不需要 API Key、不需要 Torch**。

| 示例 | 业务目标与条件 | 实际输出 |
|---|---|---|
| `point` | 服务网点采用同一 AI 安排时的平均结果；已声明完整总体信息和所需科学条件 | `POINT`，识别表达式、证书、独立重放 |
| `partial` | 合作网络中一个固定推广方案的平均结果；有限总体均值和完整有界模型 | `PARTIAL`，相对该模型的 sharp 界 `[3/7, 4/7]`，证书、独立重放 |
| `missing_condition` | 与 PARTIAL 同类目标，但模型完整性条件未确认 | `NEEDS_INPUT`，列明缺项，不调用求解器 |

每个目录保存业务原文、两次读取请求与固定草稿、合成审核、计划、逐问结果及整题结果。**草稿是教学夹具，审核是显式合成审核，不是实时 LLM 结果或真实企业批准。** 源码见 [`examples/student_handoff.py`](examples/student_handoff.py)。

真实业务创建会话：

```python
from cfm_id import project
from cfm_id.business_intake import prepare_request
session = project.start(case)   # case 是含问题和材料的 BusinessCase / dict
request = prepare_request(session)  # 只准备请求；不调用模型、不自动审核
```

也可执行 `python -m cfm_id.project start --input case.json --output outputs/new_case`。后续接收回答、逐项审核、分派与执行见[会话操作](docs/BUSINESS_INTAKE_ZH.md)和[业务分派](docs/BUSINESS_DISPATCH_ZH.md)。

## 开发者按这个顺序阅读

分类的综述、定理依据与项目自定义边界见[分类与文献依据](literature_support/CLASSIFICATION_ZH.md)。内部任务分配不随源码发布。

1. [目录与代码地图](docs/DEVELOPMENT_ENTRY_ZH.md)：每个文件夹的职责，哪些文件属于数学 Core。
2. [读取配置](docs/BUSINESS_READING_CONFIG_ZH.md)：推荐起点、兼容默认和实验的边界。
3. [新增能力规则](docs/EXTENSION_MAINTENANCE_ZH.md)：能力登记、读取登记、原生证明和验收义务。
4. [当前范围](docs/CURRENT_SCOPE_ZH.md)、[数学与文献导航](docs/MATH_AND_EVIDENCE_ZH.md)：原生能力与自然语言接入并非同一范围。
5. [当前发布验收](docs/RELEASE_ACCEPTANCE_ZH.md)、[原交接验收](docs/DELIVERY_READINESS_ZH.md)、[未解决项](docs/KNOWN_LIMITATIONS_ZH.md)。

八类当前短引用读取家族已共用[读取组件登记](docs/FACT_READING_REGISTRY_ZH.md)：固定政策均值、两政策差值、局部效应、R3 观察性政策、变量 DAG、随机化单臂、有限政策及观察性效应。它们各自保持目标与科学审核，登记不是数学求解器，也不会自动批准条件。

观察性固定政策均值另提供[均值签名读取配置](docs/R3_POLICY_ENTRY_CONTRACT_ZH.md)，连接已有`R3_MEAN_SIGNATURE`：完整政策无支持时，需要独立审核全安排条件均值充分性及其评价范围，并由原生后端验证目标签名正支持。默认读取配置保持不变；此接入的离线验收不代表LLM准确率。

已有计划可通过 `project.diagnose_methods` 查看[方法条件诊断](docs/METHOD_DIAGNOSTICS_ZH.md)。覆盖固定政策均值、两政策有向差值、局部直接效应与同伴效应、R3观察性固定背景完整政策均值，分开显示审核、数学检查与原执行证据；不改变执行规则、不自动补假设。固定政策示例：`python -m examples.method_diagnostics --allow-synthetic-reviews --output outputs/method_examples`；差值示例：`python -m examples.contrast_method_diagnostics --allow-synthetic-reviews --output outputs/contrast_method_examples`；局部效应示例：`python -m examples.effect_method_diagnostics --allow-synthetic-reviews --output outputs/effect_method_examples`。差值保留比较方向、共同评价范围及联合求界；局部效应保留自身/同伴两端状态、固定评价名单及原设计条件平均，局部状态成功不能替代完整效应证据。 R3示例：`python -m examples.observational_method_diagnostics --allow-synthetic-reviews --output outputs/observational_method_examples`；固定背景、交换性审核和完整政策正支持分别显示。

## 修改后的检查

```powershell
python -m pip install -e ".[test,documents]"
python scripts/check_framework.py --suite quick --output outputs/quick_check
python scripts/check_framework.py --suite chain --output outputs/chain_check
python scripts/check_framework.py --suite full --output outputs/full_check
python scripts/check_offline.py
```

按改动范围选层级，具体见[测试职责](docs/TESTING_ZH.md)。`[test]` 中的 Torch 用于历史兼容夹具；三个入门示例无需它。离线检查不能替代真实 LLM 准确率测量。

## 历史内容

当前操作指南在 `docs/`，分轮实验与旧状态记录移到 `docs/history/`。旧学生演示移到 `examples/legacy/`；其中两份模型回答是必要的冻结兼容夹具。大批在线输入输出仍保存在源码外，不随此包交付。`predevelopment/`、`research_partial/` 是保留旧导入的原型，正式 PARTIAL 位置见代码地图。协议内部标识不随文件整理更名，以保持请求、审核和证书兼容。
