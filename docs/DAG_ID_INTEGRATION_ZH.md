# 任务五业务接入：新增了什么、哪些没碰

本页说明通用 ID（`DAG_GENERAL_ID`）在业务层的交付边界：哪些是本次新增的文件，哪些能力已经在这些新文件里跑通，以及哪些动作本批没有做。

本页不包含对任何既有文件的改动方案。任务五的全部交付都是新增文件，仓库原有文件零改动。

## 0. 已有基础

这批不是从零起步，也不是复制既有路线。仓库里已经有三条专门识别路线和一套公共设施：

| 已有 | 位置 | 本批怎么用它 |
|---|---|---|
| 后门路线 | `cfm_id/dag_backdoor*.py` | 不调用。作为复现对照：后门图必须给出与它一致的结论 |
| 前门路线 | `cfm_id/dag_frontdoor*.py` + `cfm_id_llm/dag_frontdoor_reading.py` | 不调用。作为复现对照，另作为读取层的形态参照 |
| 调整集路线 | `cfm_id/dag_adjustment*.py` | 不调用。边界由此确定：它处理可调整情形，本批处理不可调整但可递归分解的情形 |
| 公共路由与工作流 | `research_route_workflow.run_route` | 直接复用：`claim` / `replay` / `verify_claim` 三个钩子按既有约定实现 |
| 审核与证书重放 | 既有问题/审核契约与 replay 机制 | 直接复用，不自建第二套 |
| 能力登记 | `cfm_id/capability_registry.py` | 不登记，理由见第 2 节 |

所以本批的定位是：在既有三条专门路线之外，补上"既不是后门也不是前门、但可以递归分解"的那一类图；其余全部走既有通道，没有第二套流程。

## 1. 新增的文件

| 文件 | 作用 |
|---|---|
| `cfm_id/dag_id_contract.py` | 数学问题的输入契约与五态枚举 |
| `cfm_id/dag_id_graph.py` | 图工具（祖先、C 分量、删入边、拓扑序） |
| `cfm_id/dag_id_solver.py` | 七行 ID 算法，输出表达式树与推导轨迹 |
| `cfm_id/dag_id_verify.py` | 独立验证器，不导入求解器 |
| `cfm_id/dag_id_route.py` | 业务适配器：问题契约、审核契约、`prepare` / `submit`、`claim` / `replay` / `verify_claim` |
| `tests/test_dag_id.py` | 数学层正负测试 |
| `tests/test_dag_id_route.py` | 业务入口端到端测试 |
| `examples/dag_id_demo.py` | 三张图的命令行演示 |
| `examples/dag_id_route_reference.py` | 业务入口的演示夹具与调用示例 |
| `docs/DAG_ID_MATH_ZH.md` | 数学推导与验收对照 |
| `docs/DAG_ID_INTEGRATION_ZH.md` | 本页 |

除上述 11 个文件外，仓库中没有任何文件被修改、删除或重命名。

## 2. 为什么没有注册进共享登记

`cfm_id/capability_registry.py` 是这个项目的闭合显式注册：哪条路线可用、能出哪类结论，全部写死在 `registrations()` 里，并由 `tests_gateway/` 那组防护测试盯着。按 `docs/EXTENSION_MAINTENANCE_ZH.md` 的归属约定，这类共享登记属于路线维护者的决定范围。

因此本批只交付适配器本身。注册不在本次交付范围：不提交注册改动，不在文档里预留"把这几行插进去"的操作说明。

在注册之前，适配器可以完全独立使用：调用方直接构造问题与审核对象，交给 `research_route_workflow.run_route` 即可，与注册表无关。`examples/dag_id_route_reference.py` 就是这么跑的。

## 3. 这一层现在能做什么

以下行为都在 `tests/test_dag_id_route.py` 里被断言过：

- 研究者确认的图 → `POINT` + 独立 replay 数值比对通过；
- `graph_status` 不是 `RESEARCHER_CONFIRMED` → `NEEDS_INPUT / GRAPH_NOT_CONFIRMED_BY_RESEARCHER`，不进入求解器；
- 审核有 `PENDING` → `REVIEW_REQUIRED`；有 `REJECTED` → `CHECK_BLOCKED`；同样不进入求解器；
- 审核绑错题（摘要与当前问题不符）→ `STALE_GENERAL_ID_REVIEW`；
- 不可识别的图 → `UNSUPPORTED` + C-forest 证据；
- 有环图 → `CHECK_BLOCKED / DIRECTED_CYCLE_NOT_RECURSIVE_MODEL`；超出节点上限 → `RESOURCE_LIMIT / NODE_COUNT_OUT_OF_RANGE`。两者不共用状态，也不抛异常。
- 求解器内部出现未预期异常 → `CHECK_BLOCKED / INTERNAL_ERROR`，并带上异常类型；不会冒充"不可识别"。

也就是说，"图必须经过研究者确认"这条红线在代码层是闸门：没标记确认的图连求解器都见不到。

## 4. 若将来要接入，需要维护者处理的三件事

以下三项都涉及既有文件的语义，本批一律不动。列在这里是为了说明差距在哪，不是待批事项：

1. 是否把通用 ID 登记为一条可路由的路线。 这决定它能否通过共用入口按 `route_id` 被调用。
2. 是否让分派层在三条专用路线都失败时回落到通用 ID。这不仅是一处新增分支：失败结论的含义会从"这三种方法都不适用"变成"这张图上不存在统一公式"，是两个不同的断言，属于分派语义的变更。
3. 导航索引如何登记这条新路线。 项目有 `MATH_AND_EVIDENCE_ZH.md` 约定的一致性检查，新增连接需要同步索引，这属于维护者对文献映射的组织方式。

## 5. 接入前还缺的输入

- 研究者确认的变量因果图：任务书要求"图须经过研究者确认，合作关系网络不能直接当变量因果图"。现有测试图全部来自论文或仓库参考例，仅用于验证代码。
- 阅读层的双向边表达能力：`Relation.kind` 只有 `DIRECT_CAUSE / ASSOCIATION / UNCERTAIN`，没有表达"未观测共同原因"的位置。因此半马尔可夫图目前只能由研究者声明式给出，不能由阅读候选生成。扩阅读层是比注册更大的改动，同样不在本批范围。

## 6. 与其它模块的边界

任务书与仓库规则里几条容易越线的要求，逐条交代本批的实际状态：

- LLM 是待审草稿，本批不接。 任务五没有读取层，图由研究者声明式给出（第 5 节），所以不存在"把模型输出当成图"的路径，也就不存在自动批准条件的风险。审核层仍逐条件记录 `PASS / PENDING / REJECTED`，任一 `PENDING` 阻断求解，任一 `REJECTED` 直接 `CHECK_BLOCKED`，没有"整体打个分就放行"的通道。
- 缺项、拒绝、读取错误、覆盖缺口分开。 缺项是 `NEEDS_INPUT`，拒绝是 `CHECK_BLOCKED`，未预期异常是 `CHECK_BLOCKED / INTERNAL_ERROR`，规模超限是 `RESOURCE_LIMIT`，非识别证据成立是 `UNSUPPORTED`。读取错误与覆盖缺口在本批不存在，因为不做读取。
- 不碰 Estimation / Policy。 本批 11 个文件全部是新增，`git diff` 对既有文件为 0 行。不涉及估计器、策略学习、PFN 训练或历史下游代码。
- 公共语义无变化，因此没有提接口提案。 新增的是独立求解器与适配器，通过既有 `run_route` 调用，既有请求的入参与返回不变。真正会改变公共语义的三件事写在第 4 节，本批不做，也不预留改动说明。
- 提交物干净。 11 个文件均为源码、测试与文档：没有密钥、没有个人运行环境、没有 checkpoint、没有原始 API 日志、没有生成目录。测试产物写到 `outputs/checks/`，该目录在 `.gitignore` 第 15 行，未进入暂存区。
