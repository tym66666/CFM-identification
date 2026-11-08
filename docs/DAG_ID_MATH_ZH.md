# 任务五：递归半马尔可夫图上的通用识别（`cfm_id/dag_id_*`）

## 1. 范围

- 模型：递归半马尔可夫图（ADMG）。有向边表示因果方向，双向边表示未观测的共同原因。
- 变量：有限、离散；目标是 P(Y | do(X = x))，X 单变量，Y 可为向量。
- 给定：完整的观察总体分布 P(V)，符号形式，不需要数值。
- 不做：自动学图、反事实、条件干预、图上的 PARTIAL 识别、连续变量、跨人群迁移。
- 不使用工具变量，也不假设其单调性。
- 图须由研究者确认为变量因果图；关系网络数据不能直接当变量因果图。

规模范围：观察节点数与隐藏共因条数之和不超过 14。 超过时返回 `RESOURCE_LIMIT`，不崩溃、不静默截断。

上限不能只看节点数。独立验证要在同一张联合分布上枚举全部 `2^n` 个取值，并枚举每条双向边背后隐变量的全部 `2^b` 种配置，实际代价是 `2^(n+b)`。六节点五条双向边和十二节点零双向边一样贵。因此判据写成：

- `len(nodes) > 12` → `RESOURCE_LIMIT / NODE_COUNT_OUT_OF_RANGE`
- `len(nodes) + len(bidirected) > 14` → `RESOURCE_LIMIT / MODEL_SIZE_OUT_OF_RANGE`

两者都是规模结论，不借用 `NEEDS_INPUT`（审核问题）或 `UNSUPPORTED`（数学结论）。

这个上限由独立检查的成本决定，不是求解器的成本。求解本身很便宜，代价在验证那一步：验证器要在同一张联合分布上枚举全部 `2^n` 个取值，每加两个节点成本约翻四倍。实测（链式图，单次调用，Windows / Python 3.12）：

| 节点数 | 求解 | 独立 replay | 合计 |
|---|---|---|---|
| 8 | 0.9 ms | 62.9 ms | 64 ms |
| 10 | 1.1 ms | 254.6 ms | 256 ms |
| 12 | 1.4 ms | 1384.6 ms | 1.39 s |

12 是"完整验证仍在一秒出头"的边界。要往上扩，先重测这张表，并说明验证策略是否需要改成按需枚举。

### 科学假设

结论只在下表假设下成立。每条都写了违背时会发生什么，不靠"读者自己清楚"：

| 假设 | 内容 | 违背或缺失时 |
|---|---|---|
| 递归（无环） | 有向边构成 DAG，不存在有向环 | `CHECK_BLOCKED / DIRECTED_CYCLE_NOT_RECURSIVE_MODEL`，不做近似 |
| 因果马尔可夫性 | 分布按 ADMG 因子化：每个 C 分量对应一个未观测共同原因 | 不可由数据检验，属建模承诺；写在证书的 `scope.model` 里 |
| 混杂显式化 | 所有未观测共同原因必须画成双向边；图上没画即声明不存在 | 靠 `graph_status = RESEARCHER_CONFIRMED` 闸门拦截；合作关系网络一类关系数据不得直接充当 |
| 正性 | 公式中出现的每个条件事件概率都为正 | `positivity_requirements()` 逐条列出分母；验证器遇到零分母报错，不把 0 当结果 |
| 有限离散 | 变量取值有限且可枚举 | 与 `MAX_NODES = 12`、`2^n` 枚举成本绑定 |
| 原子干预 | 干预形如 do(X = x)，单处理变量 | 契约只有单个 `treatment` 字段，多处理与动态处理无处表达 |
| 无选择节点 | 不建模样本选择偏倚 | 契约没有选择节点，问题对象无法声明 |

同样要说清楚不需要什么：不要求忠实性，不要求线性、正态、同方差或无交互，不要求工具变量及其单调性。算法只做代数改写，不估计参数，所以这些建模假设在这里既不检验也不借用。

## 2. 记号

| 记号 | 含义 | 实现 |
|---|---|---|
| `An(Y)_G` | Y 的祖先，含 Y 自己 | `dag_id_graph.ancestors` |
| `G_X` | 干预图：删掉所有指向 X 的边 | `dag_id_graph.remove_incoming` |
| `C(G)` | C 分量：只靠双向边连通的极大节点组 | `dag_id_graph.c_components` |
| `G \ X` | 删掉节点 X 及其所有关联边 | `dag_id_graph.without_nodes` |

两条容易读错的约定：

1. `An(Y)` 含 Y 本身。 若不含，算法第 2 行 `V = An(Y)` 永远不可能成立。
2. `G_X` 遇到双向边要整条删除。 `X ↔ W` 表示隐变量 U 同时指向 X 和 W。干预 X 切断了 `U → X`，剩下的 `U → W` 让 U 只影响一个可观测变量，可以积分掉，所以整条边消失。

## 3. 算法

论文 Fig. 3 的七行，逐行对应 `dag_id_solver._id`：

| 行 | 条件 | 动作 | 代码位置 |
|---|---|---|---|
| 1 | 干预集为空 | 对 `V \ Y` 求和 | `if not x` |
| 2 | `V ≠ An(Y)_G` | 缩到祖先集，分布换成边缘 | `if V - an` |
| 3 | `W = (V\X) \ An(Y)_{G_X} ≠ ∅` | 把 W 并入干预集 | `if w` |
| 4 | `C(G\X)` 多于一块 | 按块分解，块间相乘、对外求和 | `if len(blocks) > 1` |
| 5 | 只剩一块，且整图是一个 C 分量 | 不可识别，返回结构证据 + C-forest 对 | `if len(c_components(g)) == 1` |
| 6 | 这一块本身就是 C 分量 | 按拓扑序写成条件概率的乘积 | `if S in c_components(g)` |
| 7 | 这一块被更大的 C 分量包含 | 递归到那个分量，换用 π-乘积分布 | 末尾 |

### 每一步为何成立

任务书要求"输出应明确哪些变量求和、哪些因子相乘、每一步为何成立"。前两件事由表达式树承担（`SUM.over` 是求和变量，`PRODUCT.operands` 是相乘的因子），第三件事由 `derivation` 承担。每一步记录四项：

| 字段 | 内容 |
|---|---|
| `line` | 命中的行号（1–7），与论文 Fig. 3 对齐 |
| `rule` | 这一步在做什么（如 `RESTRICT_TO_ANCESTORS`） |
| `condition` | 判据的实际取值（如被丢掉的节点、存活块、分量、π 顺序） |
| `justification` | 为什么允许这样改写，以及依据的引理 |

例如后门图上第一步是第 4 行，`condition` 会写出 `C(G\X) = [[Z],[Y]]`，`justification` 写明"删掉干预变量后各块彼此分离，逐块求解再相乘（引理 4）"。这些理由是那一行为什么合法的理由，不是对输出表达式的事后描述——审阅者可以逐条对照论文的证明。

另外说明一点：`derivation` 记录的是每次递归调用的图快照与判据，不是最终公式的装配顺序。要看公式怎么长出来的，配合表达式树一起读。

### 三个分支判据的明确化

七行里有三个分支条件在紧凑记号下留有多种读法，落地成代码时必须选定一种。本实现的取法与论文正文的演算和示例一致，代码中每处都留了一行说明：

1. 第 2 行：判据取 `V ≠ An(Y)_G`。这一行的作用是"图上还有与结果无关的节点时，先把它们消掉"，因此判据是不等；若取等号，递归会在同一个图上原地循环。
2. 第 3 行：判据取 `W = (V \ X) \ An(Y)_{G_X} ≠ ∅`。W 定义为"既不在干预集、也不是结果在 `G_X` 中祖先的节点"，非空才需要把它们并入干预集。论文 Fig. 1(a) 的演算正是在 `W = {W1}` 时进入这一行。
3. 第 7 行：递归目标是包含 S 的那个 C 分量。删掉 X 之后得到的块是 `G` 中某个 C 分量的子集，所以要向上找回容器。理论上容器必然存在，代码仍保留一条防御性分支，找不到时报 `CHECK_BLOCKED / NO_CONTAINING_C_COMPONENT`。

### π-乘积（第 6、7 行共用）

递下去的分布不是边缘分布，而是：

```
π(S) = Π_{v ∈ S} P(v | 所有在 v 之前的变量)
```

条件变量取全图拓扑序的前缀，不是仅仅取父节点。第 6 行的链式法则和第 7 行的容器递推都必须用这个约定。

前门图上决定成败的是右支：`X` 不是 `Y` 的父，但给定 `M` 后两者仍通过双向边混杂，所以 `P(Y | M)` 与 `P(Y | X, M)` 是两个不同的数。

第 6 行也有同样的情形，只是更隐蔽：图 `V2→V0→V1`、`V0↔V1`，干预 `V2`，求 `V1`。`V1` 的父只有 `V0`，但 `V2` 排在 `V1` 之前，且干预改变了 `V0` 与 `V1` 共用的隐变量的后验，所以

```
P_{v2}(v1 | v0) = P(v1 | v0, v2) ≠ P(v1 | v0)
```

按父节点取条件会得到 `Σ_{v0} P(v0|v2)P(v1|v0)`，与真值差 1e-2 量级；按前缀取条件得到 `Σ_{v0} P(v0|v2)P(v1|v0,v2)`，数值验证通过。这个差别在六张手写图上都观察不到。

### 手工走一遍前门图

任务书第一步要求"按论文的 ID 步骤手工走一个小图，记录图怎样变化、怎样分解和最终表达式"。前门图 `X→M→Y, X↔Y`，目标 `P(y | do(x))`，`derivation` 里有五层：

| 层 | 目标 | 命中 | 发生了什么 |
|---|---|---|---|
| 0 | `P_x(y)` | 第 4 行 | `An(Y)` 是整个图，无从缩小；`C(G\X) = {{M}, {Y}}` 两块，按块分解 |
| 1 左 | `P_{x,y}(m)` | 第 2 行 | `Y` 不是 `M` 的祖先，缩到 `{X, M}` |
| 2 左 | `P_x(m)` | 第 6 行 | 只剩块 `{M}`，且它本身是 C 分量，链式法则给出 `P(m\|x)` |
| 1 右 | `P_{mx}(y)` | 第 7 行 | `G\{M,X}` 只剩 `{Y}`，但 `{Y}` 不是 `G` 的 C 分量；容器是 `{X, Y}`，换 π-乘积递下去 |
| 2 右 | `P_x(y)` | 第 2 行 | 缩到 `{X, Y}` 后 `An(Y) = {Y}`，`X` 被丢掉 |
| 3 右 | `P(y)` | 第 1 行 | 干预集空了，对联合分布求和 |

合起来就是左支 `P(m|x)` 乘右支 `Σ_x P(x)P(y|x,m)`，再对 `m` 求和：

```
P(y | do(x)) = Σ_m P(m|x) · Σ_x P(x) · P(y|x,m)
```

右支那个 `P(y|x,m)` 的条件里必须带 `x`，这正是 π-乘积的意义：`X` 不是 `Y` 的父，但它和 `Y` 通过双向边混杂，去掉 `x` 就错。

## 4. 表达式树

求解器只输出结构，不输出字符串，也不输出数字：

```python
{'operation': 'SUM',         'over': ['M'], 'scope': [...], 'operand': {...}}
{'operation': 'PRODUCT',     'operands': [{...}, {...}]}
{'operation': 'MARGINAL',    'keep': ['Y'], 'scope': [...], 'of': {...}}
{'operation': 'CONDITIONAL', 'outcome': ['Y'], 'given': ['X', 'M'], 'of': {...}}
{'operation': 'OBSERVED_JOINT'}
```

`scope` 是当前图的节点集。它的作用是区分两类变量：

- 图内变量：可以被 SUM / MARGINAL 消掉。
- 图外的条件变量：递归带下来、由图外的求和绑定，必须保留。前门公式里 `M` 就属于这一类。

## 5. 独立验证

`dag_id_verify` 不 import 求解器，也不 import 图模块。它做的事：

1. 按声明的图生成一个具体的 SCM（每个机制的概率固定在 0.15–0.85，避免退化）。
2. 对隐变量求和，得到观察联合 P(V)。
3. 按 do 的定义截断指向 X 的机制，算出真实的 P_x(Y)。
4. 用证书里的表达式树在同一个 P(V) 上求值。
5. 在 3 个 seed、2 个干预值、全部结果取值上比对，误差阈值 1e-9。

`replay` 返回九项检查：证书字段、状态为 POINT、证书摘要、题目绑定、问答绑定、公式只读取被问到的变量、推导逐步复算、表达式树结构、与新建 SCM 的数值一致性。

题目绑定只证明证书与题目摘要一致；问答绑定把治疗、结果和图逐项对照，防止"回答的是另一个问题"却因为证书自身摘要合法而通过。公式读取范围检查拒绝任何落在治疗与结果之外的自由变量：`P(C|A,B)` 这种把上游变量留在条件里的写法会被它拦下，即便某个数值上碰巧相等。推导复算按论文规则顺序重算每一步的前提，引用了一条并未适用的规则同样会被拒绝。

最后一项数值一致性负责抓"公式看起来对但语义错"，前面的结构检查负责抓"数值碰巧对但推理是编的"。两者不能互相替代。

这两句话都有测试守着，不是注释：

- "不 import"：`test_verifier_never_imports_the_solver_or_the_graph_module` 用 AST 读出 `dag_id_verify.py` 的全部 import 语句，出现 `dag_id_solver` / `dag_id_graph`（相对写法也算）立刻失败。文件头那句声明因此是可执行的，不是承诺。
- "只有第六项抓得住语义错"：`test_numeric_check_catches_a_formula_that_is_structurally_valid` 把前门公式里 `P(y|x,m)` 的 `x` 删掉——正是修复前那个缺陷的形状——然后重新签署证书摘要，于是字段、状态、摘要、绑定、树结构全部合法，失败的检查项只剩 `numeric_agreement_with_fresh_scm` 一个。

这一步在开发过程中抓到过五个真实缺陷：

- 干预值把 `P(X=1)` 的行也改写成了 `X=0`，分母混入错误的行；
- 条件化时丢掉了 `given` 变量，不同 `z` 的结果互相覆盖；
- 隐变量没有乘先验，联合分布总和是 2 而不是 1；
- 同一个 `X` 在公式里有两个角色（`P(m|x)` 的干预值、`Σ_x P(x)P(y|x,m)` 的求和变量），求值时被混为一谈；
- 第 6 行的链式乘积按父节点取条件，没有取全图拓扑序前缀，在 `V2→V0→V1, V0↔V1`、干预 `V2` 求 `V1` 的图上误差 1.1e-2（见下）。

最后这一条手写图抓不到：后门、链、前门、混合、Fig. 1(a)、bow-arc 六张图在修与不修时结果都一样。它是随机图测试抓到的——固定种子生成 160 张 3–6 节点的 ADMG（允许 bow-arc），逐张要求"必须给出 POINT 或 UNSUPPORTED，POINT 必须通过 replay，UNSUPPORTED 的证据必须通过 `check_failure`"。改之前 400 张图里有 9 张 replay 失败，改之后 0 张。这个用例留在 `RandomisedGraphTests` 里，是六张手写图之外的独立防线。

随机测试只在结构上随机，SCM 生成、求值、比对全部复用同一套验证器，所以它不是"自己验证自己"，而是把验证器铺到没被手写用例覆盖的形状上。

## 6. 非识别证据：C-forest 对

第 5 行触发时，除了失败条件本身，证据里还带一对真正构造出来的 C-forest：

```python
{
  'kind': 'FAILED_COMPONENT_CONDITION',
  'theorem': 'SHPITSER_PEARL_2006_THEOREM_6',
  'c_components_of_graph': [['X', 'Y']],
  'c_components_of_graph_minus_treatment': [['Y']],
  'surviving_component': ['Y'],
  'disjoint_from_treatment': True,
  'roots_contained_in_ancestors_of_outcome': True,
  'hedge': {
    'trimmed_forest': {'nodes': ['Y'], 'directed': [], 'bidirected': []},
    'grown_forest': {'nodes': ['X', 'Y'], 'directed': [['X','Y']], 'bidirected': [['X','Y']]},
    'roots': ['Y'],
    'nested': True,
    'grown_strictly_contains_trimmed': True,
    'trimmed_avoids_treatment': True,
    'roots_in_ancestors_of_outcome_after_intervention': True,
  },
  'hedge_materialised': True,
  'means': 'NO_UNIFORM_IDENTIFICATION_FORMULA_IN_THIS_GRAPH',
}
```

### 构造方式

论文定义 6 的画面是"先有被剪过的森林，再让干预之前的样子长出新枝"。照这个画面构造：

1. 被剪的森林（`trimmed_forest`）：`G \ X` 存活的那一块，按到根的有向可达性裁剪。它天然不含 X——干预把指向 X 的箭头都切了。
2. 长出新枝的森林（`grown_forest`）：`G` 中包含该块的 C 分量，按同一根集裁剪。它比前者大出来的部分，正是干预切掉的那些边。
3. 根集：森林中没有子节点的节点，两个森林必须相同，且落在 `An(Y)_{G_X}` 里。

bow-arc 上就是：被剪的森林 `{Y}`，长出的森林 `{X, Y}`（多出 X 和 `X→Y`、`X↔Y` 两条边），根集 `{Y}`。

### 独立检查

`check_failure(witness, problem)` 不采信证据里的 `True`，它从边的列表自己重算十三条：

| 检查 | 拦住什么 |
|---|---|
| `trimmed_forest.non_empty` / `grown_forest.non_empty` | 空森林冒充证据 |
| `*.one_c_component` | 拿两个不相连的块说成一个 C 分量 |
| `*.every_node_reaches_a_root` | 有节点其实没通向根 |
| `*.at_most_one_child` | 不是 C-forest（有节点分出两支） |
| `trimmed_avoids_treatment` | 被剪的森林碰到了 X |
| `nested` | 两个森林不是包含关系 |
| `grown_strictly_contains_trimmed` | 两个森林一样大——那样什么都没见证 |
| `same_root_set` | 根集不一致 |
| `roots_in_ancestors_of_outcome_after_intervention` | 根集不在 `An(Y)_{G_X}` 内 |

`roots_in_ancestors_of_outcome_after_intervention` 是从题目声明的图重算的：验证器自己删掉指向 X 的边、自己求祖先集，不读求解器给的答案。

### 措辞边界

任务书对此有明确要求，这四条是边界，不是补充说明：

- 这表示"在指定的图模型里不存在统一的识别公式"，不是"每个特殊数值分布都同样有歧义"。
- 反过来，如果递归因资源上限中断，状态是 `RESOURCE_LIMIT / DAG_ID_RECURSION_LIMIT`，与"不可识别"分开报告。
- 如果某张图上"每节点至多一个子节点"的裁剪不唯一，构造会返回 `hedge_materialised = False` 并说明原因，而不是硬拼一对出来。
- 在这种情况下状态不是 `UNSUPPORTED` 而是 `NO_FORMULA_YET / NO_IDENTIFICATION_FORMULA_DERIVED_YET`：证据没过检查，就只能说"尚未给出识别式"。这是阶段成果，不是非识别结论。

## 7. 复现结果

| 图 | 结构 | 结果 |
|---|---|---|
| 后门 | `Z→X, Z→Y, X→Y` | POINT，数值验证通过 |
| 链 | `X→M→Y` | POINT，数值验证通过 |
| 前门 | `X→M→Y`, `X↔Y` | POINT，得到 `Σ_m P(m\|x) Σ_x P(x)P(y\|x,m)` |
| 平行双中介 + 直接混杂 | `X→M1→Y, X→M2→Y`, `X↔Y` | POINT，得到 `Σ_{m1,m2} P(m1\|x)P(m2\|x) Σ_x P(x)P(y\|x,m1,m2)`；三条专用路线在同一张图上全部拒绝 |
| 混合 | `Z→X, Z→Y, X→M, M→Y`, `X↔Y` | POINT，数值验证通过 |
| 论文 Fig. 1(a) | `W1↔X↔W2, X→Y1, W2→Y2` | POINT，双结果联合分布通过 |
| bow-arc | `X→Y`, `X↔Y` | UNSUPPORTED，C-forest 对通过十三条检查 |

前门那一行的公式不是手抄的：`test_frontdoor_formula_matches_the_documented_shape` 把表达式树里的三个条件原子逐个对出来——`P(m|x)`、`P(x)`、`P(y|x,m)`，少一个 `x` 就失败。数值验证只能证明"等价"，这条测试证明它是文档里写的那一个。

### 平行双中介那一行，为什么它才算超出三条专用路线

混合那张图早先被当作范围证据，但它其实落在前门之内：`Z` 不拦截任何东西，`M` 是唯一中介，前门判据对它成立。所以它不能证明新能力。能证明的是平行双中介这张图：

- 后门：`M1`、`M2` 都是 `X` 的后代，不能进调整集；空集挡不住 `X↔Y`。判据返回 `NO_CLASSICAL_BACKDOOR_SET`。
- 前门：单中介前门要求该中介拦截所有有向路径。`M1` 拦不住 `X→M2→Y`，`M2` 拦不住 `X→M1→Y`，两个都不合格。判据返回 `NO_SINGLE_VARIABLE_FRONTDOOR`。
- 调整集：同样要面对 `X↔Y`，返回 `NO_OBSERVED_DAG_ADJUSTMENT_SET`。
- ID 算法：`C(G) = {{X,Y},{M1},{M2}}`，第 4 行按 `G_X` 的分量分解成三块分别求，`M1`、`M2` 各自是单点 C-分量，直接得到 `P(m1|x)`、`P(m2|x)`；`Y` 所在的块递归进 `C(G)` 的 `{X,Y}`，第 2 行剥掉 `X`，第 1 行落回联合分布的边际，于是 `X` 被求和而不是被条件化。

关键就在最后一步。化简后的式子是

```
P(y|do(x)) = Σ_{m1,m2} P(m1|x) P(m2|x) · Σ_{x'} P(x') P(y|x',m1,m2)
```

最后一个因子对 `x'` 求和，不是条件在 `x` 上。这一步正是把未观测共因还原回来：`M1`、`M2` 只依赖 `X`、不含共因，所以给定 `m1,m2` 后

```
Σ_{x'} P(x') P(y|x',m1,m2) = Σ_u P(y|m1,m2,u) · Σ_{x'} P(x') P(u|x') = Σ_u P(u) P(y|m1,m2,u)
```

中间那个等号用到 `Σ_{x'} P(x')P(u|x') = P(u)`，也就是"用 `X` 的边际把 `u` 的分布积回去"。写成 `P(y|x,m1,m2)` 就错了——那是条件分布，与干预分布相差一个共因项。

这一点专门有测试盯着：`test_parallel_mediators_with_a_direct_confounded_edge` 断言条件原子恰好是 `P(m1|x)`、`P(m2|x)`、`P(y|x,m1,m2)`，外加一个无条件的 `P(x)`（被求和的那一项）。`test_the_three_dedicated_routes_all_refuse_that_graph` 把同一张图改写成显式隐变量，逐个跑三条专用求解器，断言三者都拒绝并核对拒绝原因，这样一来"超出现有路线"是被跑出来的，不是写在文档里的。

文献对应：这一步就是 Shpitser & Pearl (2006) Fig. 3 第 4 行（按 `G_X` 的 C-分量分解）、第 7 行（递归进 `C(G)` 的组件）、第 2 行（剥掉非祖先）、第 1 行（落回联合分布）串起来的结果；该文 Theorem 4 指出其递归在递归半马尔可夫图上完备，前门与后门都是它的特例，因此存在它们都判否而它仍能识别的图，这张就是其中最小的一个。

复现命令：

```
D:/python/python.exe -m unittest tests.test_dag_id tests.test_dag_id_route -v
D:/python/python.exe examples/dag_id_demo.py
D:/python/python.exe examples/dag_id_route_reference.py
```

预期：两个测试文件共 59 个测试全部 OK（数学 44 个，含一组 160 张随机图的检查；业务入口 15 个）。

### 实际执行的测试范围

按 `docs/TESTING_ZH.md` 的分档报告，不把没跑的写成通过：

| 档位 | 命令 | 本次是否执行 | 结果 |
|---|---|---|---|
| 定向 | `python -m unittest tests.test_dag_id tests.test_dag_id_route` | 是 | 59 passed |
| 定向（门禁） | `python -m unittest tests_gateway.test_framework_acceptance tests_gateway.test_business_packets` | 是 | 8 passed |
| quick | `python -m evaluation.framework_acceptance --suite quick --output outputs/checks/quick.json` | 是 | 110 passed，40.5 s |
| chain | `python -m evaluation.framework_acceptance --suite chain --output outputs/checks/chain.json` | 是 | 1086 passed，354.9 s |
| full | `python -m evaluation.framework_acceptance --suite full` | 否 | 本批不改公共接口，按 `TESTING_ZH.md` 的触发条件未选 full |
| 真实 LLM 首答与复查 | `python examples/dag_id_llm_reading.py` | 是 | 3 个案例，deepseek-chat，见下方小节 |

full 未运行的理由是选择而非结论：本批对既有文件零改动（`git diff` 为空），触发 quick、chain 的条件是"新增数学能力 + 复用公共审核入口"，full 的触发条件是公共接口或历史配置变化，本次没有发生。这一条属于未验证，不能读作"full 会通过"。

### 真实模型走查（脱敏记录）

材料是三段合成的业务描述：连锁咖啡的会员复购、发券与下单金额、门店排班，不含任何真实会员数据。三个案例的预期结果在运行之前写进脚本，运行后不修改。

模型用 `deepseek-chat`，端点 `https://api.deepseek.com/v1`，每题一次调用，未重试。

| 案例 | 预期 | 首次回答 | 是否重读 | 是否人工修改 | 最终结果 |
|---|---|---|---|---|---|
| 条件齐全、可识别 | POINT | 读出中介与共同原因，POINT 且重放通过 | 否 | 否 | 正确 |
| 图内不可识别 | UNSUPPORTED | 读出 `发券→下单金额` 与 `发券↔下单金额`，UNSUPPORTED 且证据十三条通过 | 否 | 否 | 正确 |
| 材料缺关键条件 | NEEDS_INPUT | 读出空图，管线仍给出 POINT 与 `P(门店表现)` | 否 | 是，修了管线 | 正确，由闸门拦下 |

第三行必须如实写：第一次它没对，模型没有错。模型两次都把"门店表现口径未定""排班方式与自由度说法相反"列进 `unresolved`，第二次更直接把目标结果填成 `None`；错在脚本当时写死了 `researcher_confirmed=True`，等于替研究者给草稿盖章，空图因此变成"干预无效果"的结论。修掉盖章后重跑，闸门返回 `NEEDS_INPUT / NO_CAUSAL_STRUCTURE_READ` 并列出两条追问，才与预期一致。

闸门规则只有一条，且不看预期答案：草稿里一条有向关系、一条共同原因都没有时，不得确认。理由是空图不是"没有信息"，而是断言该人群没有因果结构，这是最强的断言，也最需要人确认。由 `tests/test_dag_id_route.py` 的 `ReadingConfirmationGateTests` 守住。

另有一处观察值得记下：三次运行中模型对 `scope` 六项几乎全填 `null`，不肯替材料断言"图已完整""潜在原因已计"。所以闸门不能依赖模型自报完整性，只能看它实际读出了什么结构。

复现：

```
set CFM_ID_LLM_API_KEY / CFM_ID_LLM_BASE_URL / CFM_ID_LLM_MODEL
python examples/dag_id_llm_reading.py
```

原始输出由脚本自动落到仓库根下的 `dagid_runs/`，每个案例一个 JSON：发出的材料原文、模型首答的完整 JSON（原样保存，不做修补）、解析后的读取结果、最终状态与独立重放，以及这次调用的传输诊断（返回的模型名、token 数、finish_reason）。目录不入库，已写进本地 `.git/info/exclude`；要换位置设 `CFM_ID_LLM_SAVE_DIR`。每写完一个文件打印一行 `saved :`，可以直接看出三份是否齐全。这些是运行记录而非交付物，提交的仓库里不含该目录，本地跑一次即生成。重跑会覆盖同名文件；要同时保留多轮记录，就换一个 `CFM_ID_LLM_SAVE_DIR`。记录里的 `run_at` 与 `provider` 两栏写明这次用的时间和端点，换了模型或日期时可以直接对照本节表格。

局限：只用一个模型、每题一次调用，没有做第二模型对照，也没有统计首答与复查的正确率；三个案例的样本量不支持任何准确率结论，只能说明这条链路在真实模型上跑通了。

## 8. 验收标准对照

每一条要求后面都写了守着它的测试。

| 任务书要求 | 实现 | 守着它的测试 |
|---|---|---|
| 算法：递归半马尔可夫图、有向/双向边 | `dag_id_solver._id` 七行 | `test_c_components_follow_bidirected_chains_only`、`test_backdoor_graph` |
| 明确公式所需分母 | `positivity_requirements()` | `test_positivity_requirements_cover_every_conditioning_event`（前门图精确等于 `[['X'], ['X','M']]`） |
| 明确规模范围 | 节点上限 12、节点数加双向边数上限 14，两者都报 `RESOURCE_LIMIT` | `test_resource_limit_is_reported_separately`、`test_model_size_counts_shared_causes_not_just_nodes` |
| 结构化公式与步骤 | 表达式树 + `derivation`（含理由） | `test_derivation_trace_is_recorded`、`test_every_step_says_why_it_is_legal` |
| 独立检查图操作、最终目标 | `replay` 九项检查，含问答绑定与推导复算 | `test_replay_reports_the_nine_documented_checks`、`test_replay_compares_three_seeds_and_two_interventions`、`test_a_correct_answer_to_a_different_question_is_rejected`、`test_a_step_that_cites_the_wrong_rule_is_rejected` |
| 普通问题可运行 | `A→B→C` 求 `P(C|do(B))`，得到 `P(C|B)` | `test_intervening_mid_chain_does_not_leak_the_upstream_variable` |
| 不能两次调用同一求解器 | 验证器不 import 求解器/图模块，自建 SCM | `test_verifier_never_imports_the_solver_or_the_graph_module`（AST 扫 import）、`test_numeric_check_catches_a_formula_that_is_structurally_valid` |
| 检查 hedge 等非识别证据 | C-forest 对 + 十三条独立检查 | `test_failure_materialises_a_c_forest_pair`、`test_hedge_evidence_is_the_documented_thirteen_checks`、`test_altered_hedge_is_rejected` |
| 复现后门 / 前门 | 第 7 节 | `test_backdoor_graph`、`test_frontdoor_graph`（均含数值 replay） |
| 至少一个超出现有专门路线的可识别例 | 平行双中介 + `X↔Y` 图，三条专用路线均拒绝 | `test_parallel_mediators_with_a_direct_confounded_edge`、`test_the_three_dedicated_routes_all_refuse_that_graph` |
| 成功 / 非识别 / 程序异常 / 资源超限分开 | `STATUSES` 六态，外加 `INTERNAL_ERROR` 兜底 | `test_the_six_outcomes_are_distinct_states`、`test_resource_limit_is_reported_separately`、`test_an_unexpected_defect_becomes_a_structured_state`、`test_cyclic_graph_is_rejected` |
| 图例、推导、正负测试 | `examples/`、本文、`tests/` | `test_random_graphs_are_total_and_numerically_sound`（160 张随机图，正负两侧同时覆盖） |
| 业务接入 | `cfm_id/dag_id_route.py` + 15 个测试 | `test_mixed_graph_is_answered_end_to_end`、`test_pending_condition_blocks_before_the_solver`（适配器完成；注册不在本次交付范围，见第 9 节） |
| 专属读取 | `cfm_id_llm/dag_id_reading.py`，沿用 `dag_reading` 的类型，只补 `common_causes` 一组 | `ReadingConfirmationGateTests`（草稿无结构不得确认）、`examples/dag_id_llm_reading.py` 三个案例 |
| 兼容检查 | 未运行旧请求对照 | 未验证，见第 10 节 |

两类例外，如实标注：

- 纯测量值（第 1 节的耗时表、`12` 这个上限的理由）不是断言，是 2026-11-06 在 Python 3.12 / Windows 上跑出来的数，换机器要重测。
- "零改动" 是仓库状态，不是代码性质，靠 `git status` 核对，不能写成测试。


## 9. 业务接入的边界

`cfm_id/dag_id_route.py` 是一个完整的业务适配器：问题契约（含图来源声明）、审核契约（逐条件接受/待定/驳回）、`prepare` / `submit`、以及 `research_route_workflow.run_route` 需要的 `claim` / `replay` / `verify_claim`。它已经在 `research_route_workflow.run_route` 上端到端跑通（未经注册表登记），15 个测试覆盖成功、非识别、三种拦截、超限、环图，以及读取草稿的确认闸门。

但它没有注册进 `capability_registry`。那是项目的闭合显式注册，按 `docs/EXTENSION_MAINTENANCE_ZH.md` 的归属属于路线维护者；学生直接往里加等于自己给自己开门。本批不提交任何注册改动，也没有预留插入位置。交付边界与留给维护者的问题清单写在 `docs/DAG_ID_INTEGRATION_ZH.md`。

两层闸门在适配器里已经生效，不依赖注册：

1. `graph_status != 'RESEARCHER_CONFIRMED'` → `NEEDS_INPUT / GRAPH_NOT_CONFIRMED_BY_RESEARCHER`，求解器完全不被调用。这就是任务书"合作关系网络不能直接当变量因果图"的代码实现。
2. 审核必须绑定当前题目摘要，且有 `PENDING` → `REVIEW_REQUIRED`、有 `REJECTED` → `CHECK_BLOCKED`，同样不进求解器。

## 10. 未完成

本批定位为数学阶段成果。按任务书的分档口径，数学模块完成这一档齐全；约定范围完整验收还差兼容检查与注册两项，其余是外部输入或规模问题。

- 读取层只到草稿。 `cfm_id_llm/dag_id_reading.py` 已经能把业务材料读成变量、有向关系、共同原因和目标，并跑通读取、审核、求解、检查整条链路（第 7 节的真实模型走查）。但它没有扩共用层的 `Relation.kind`：该字段仍只有 `DIRECT_CAUSE / ASSOCIATION / UNCERTAIN`，表达不了未观测共同原因，所以双向边由新增的 `common_causes` 单独承载，属于本模块自己的约定。要并进公共阅读链路，需要先提交扩 `Relation` 的最小接口提案，这一步不在本批。
- 读取草稿的确认仍由调用方做。 读取层只产出候选，不批准；示例脚本按结构判断能否确认，真实接入时这一步必须是人看着 `unresolved` 清单来做。规则写在 `examples/dag_id_llm_reading.py` 的 `confirmation`，由测试守住，但它不是审核，不产生审核记录。
- 兼容检查未运行。 本批全部是新增文件，`git diff` 对既有文件为空，既有四条路线的行为不可能改变；但没有跑过旧请求的逐字节对照，也没有留下记录。属于未验证，不是已知风险。
- 注册不在本次交付范围。 见第 9 节。路线要进入共用入口需要维护者登记，本批不做。
- 研究者确认的变量因果图未到。 要求"图须经过研究者确认，合作关系网络不能直接当变量因果图"。现有测试图全部来自论文或仓库参考例，用于验证代码，不用于回答业务问题。
- 更大规模。 上限 12 已实测；再往上需要先决定验证策略（是否按需枚举），否则 replay 会变成主要成本。

## 11. 文献

算法与证据不是自创的，逐条对应如下。代码里的 `theorem` 字段写的就是这里的编号，审阅时可以对照原文。

| 用途 | 出处 |
|---|---|
| 七行递归算法（本文第 3 节的逐行表） | Shpitser, I., & Pearl, J. (2006). *Identification of Joint Interventional Distributions in Recursive Semi-Markovian Causal Models.* AAAI-06, 1219–1226. Fig. 3 |
| 非识别判据与 C-forest 对（hedge，第 6 节） | 同上，Theorem 6 与定义 6 |
| 按 C 分量分解、块间相乘（第 4 行、第 7 行的依据） | Tian, J., & Pearl, J. (2002). *A General Identification Condition for Causal Effects.* AAAI-02, 567–573. |
| 停在第 5 行即完备（不存在遗漏的可识别情形） | Shpitser, I., & Pearl, J. (2008). *Complete Identification Methods for the Causal Hierarchy.* JMLR 9, 1941–1979. |
| ADMG 记号、双向边语义、do 算子 | Pearl, J. (2009). *Causality: Models, Reasoning, and Inference* (2nd ed.). Cambridge University Press, 第 2、7 章。 |

需要说明边界：本实现只覆盖上述第一条的算法与其失败判据，不涉及该文献之后的扩展（如条件干预、counterfactual、surrogate 结果、selection 图）。第 1 节的不做清单就是这条边界的落地形式。
