# 运行逻辑与评测材料的边界

业务执行代码负责处理调用方明确提供的输入；评测代码负责选择题目、参考答案、统计和实验。业务执行不应因为复用一段解析代码而依赖某个 Benchmark 的默认目录或金标准。

## 已整理的材料层

`cfm_id.materials` 负责既有公开合成材料协议：CSV 结构校验、问题片段定位、来源行号、文件字节摘要和供模型读取的材料视图。它只依赖 Python 标准库，不导入 `evaluation`，不调用数学后端或模型，也不生成科学批准。

```python
from cfm_id.materials import load_bundle, prompt_materials

bundle = load_bundle("my-case", public_root="/explicit/materials")
request_materials = prompt_materials(bundle)
```

`public_root` 是必填参数，程序不会把未提供的业务材料替换成 NBIB 示例。协议仍要求原有 `submission_manifest.json`、显式对象与网络表，以及 `synthetic: true`；此次没有放宽为真实企业资料准入。旧的问题分段约定也保持不变，不将它解释为任意自然语言的完整目标识别器。

`evaluation.business_materials_intake` 保留 NBIB 的默认路径和历史函数入口，委托同一份运行实现。评测调用方继续使用旧入口即可；新的运行代码直接依赖 `cfm_id.materials`。原始结果观测值仍不进入模型材料视图，文件哈希、对象标识、边、问题顺序及澄清文字均保留。

## 已迁出的固定政策读取和均值顺序工作流

2026-10-28 整理将 7 个运行模块移入 `cfm_id_llm.readers` 和 `cfm_id.workflows`。固定政策的类型、投影、当前请求及历史兼容说明归读取层；均值顺序的读取和人数说明也归读取层，完整读取审核和工作流归运行层。旧 `evaluation` 路径保留兼容导入，共用同一函数和类，不复制第二套算法。

`reference_wire` 与 `wire_metrics` 留在 `evaluation.mean_order_factored_reading`，运行 reader 不导出参考生成或评分。均值顺序能力登记和命令 `cfm-id-mean-order` 已指向 `cfm_id.workflows.mean_order`。旧命令模块仍可使用。

固定政策读取在禁止导入整个 `evaluation` 包的独立进程中可运行。均值顺序工作流在禁止导入本轮迁出的七个旧模块时仍可运行；这是第一批的检查范围；第二批进一步拆开了准入层，见下文。

## 旧网络运行链已独立

第二批从原 38 个模块中抽取实际运行需要的 131 个函数、19 个类及 67 个赋值定义，放入 `cfm_id.workflows.legacy_network` 与历史 JSON 摘要工具 `cfm_id.serialization`。函数体保持原实现，仅有一处函数内 import 改为新的同一审核类型路径。原模块剩余的 69 个实验定义保持原实现。

`business_entry`、`intent_submission` 使用这些运行实现；旧 `evaluation` 模块重新导出同一函数和类。参考/默认 NBIB 材料加载、旧数值实验、候选研究调用和网页生成保留在原评测或示例侧。运行兼容层不增加真实业务准入，也不自动生成科学批准。

运行包对 `evaluation` 的直接静态导入由第一批剩余的 2 文件／11 条降为 0。四组实际提交还在独立进程中禁止导入 `evaluation`、`examples`、`student_work`，验证未审核、缺项、拒绝和实际 Core 重放；不是仅检查 import 成功。原案例有两问识别、一问优化的 MIXED 状态也保持。

静态边界清单 [runtime_dependency_baseline.json](../tests_gateway/runtime_dependency_baseline.json) 现为空，禁止以刷新白名单放行新的混放。它是架构检查，不是安全沙箱。显式候选研究、合成重放 CLI 与评测命令仍使用自己的实验路径，不能把本次结果扩大为“所有命令都不需要评测包”，也不能删除旧兼容模块。

## 每次迁移的验收要求

- 旧公开调用入口保留；新实现不暗中使用 Benchmark 目录、参考答案或合成批准。
- 冻结业务材料、请求文本、审核绑定、正式结果和证书重放保持兼容。
- 缺项、越界路径、不适用模型和未批准科学条件继续阻断。
- 数学求解器、独立验证器、Estimation／Policy 不随目录整理改写。

已有能力与入口的登记已集中到 [capability_registry](CAPABILITY_REGISTRY_ZH.md)，共同分派使用实际绑定并核对计划。读取质量、其他内部组织和更多原生能力接入仍需继续完善。移动或登记代码不会自动提升模型准确率，也不新增识别能力。

## 第一批迁移验收（保留历史记录）

- 7 个迁移模块中的 30 个函数和类以 AST 核对保持原实现；参考生成、评分函数在评测层保留原实现。数学 Core、Estimation/Policy 和 Prompt／Schema 定义未改。
- 34 组迁移前后对照记录的请求、检查、审核及实际结果一致。其中含均值顺序 POINT/PARTIAL、缺条件及未支持情况，以及 14 个既有共同入口案例。这是兼容性对照，不是 34 道新的 LLM 业务测试。
- 研究目录仅修改均值顺序的业务入口地址，其余目录内容和会话列表不变。
- 新增迁移测试及原材料边界检查 18 项通过；固定框架 1428 项、133 个子测试在全量运行中逐项通过。全量中的 5 项本机 HTTP 测试因沙箱权限失败，随后与前述 18 项一起复测，23 项全部通过。历史档案跳过和原失败保留，详见[验收清单](FRAMEWORK_ACCEPTANCE_ZH.md)。
- 安装包在源码之外完成 10 个入口案例及 4 次新旧 CLI 调用，236 个加载的项目模块全部来自安装目录。结果包括实际 POINT/PARTIAL 重放和缺项阻断；新旧命令导出的请求一致。

本轮没有调用模型，未改原始模型回答，也未把当前阅读质量标为已解决。全部改动保留本地。迁移源码备份、原结果、校验和安装证据在仓库外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。

## 第二批迁移证据

16 组旧网络请求／审核／结果及 14 个共同入口案例迁移前后完全相同。243 份受保护的数学、桥接和 LLM 源码摘要不变；其他既有 cfm_id 文件仅两个入口改导入。新增边界验收为 S57，完整结果见 [框架验收](FRAMEWORK_ACCEPTANCE_ZH.md)。公共工具与扩展职责见 [维护入口](EXTENSION_MAINTENANCE_ZH.md)。证据保存在仓库外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。
