# Task 1 组合查找表（网络拓展 / POINT 拓展）

> 本表由 `examples/generate_task1_combination_lookup.py` 自动生成，逐格运行真实
> `SupportEngine` 与四类目标，可复现。固定小网络：`N=4` 节点 `{a,b,c,d}`，
> 边 `(a,b),(a,c),(b,d),(c,d)`；支持矩阵取节点 `a`（degree=2）。

## 设计参数

- **D1** — 独立 Bernoulli：p=(a:1/3, b:1/2, c:2/3, d:1/4)
- **D2** — 固定总配额 m=2（均匀）
- **D3** — 两组固定配额：{a,b}:1, {c,d}:1
- **D4** — 簇 Bernoulli：{a,b}:1/3, {c,d}:1/2
- **D5** — 多组固定配额：{a}:1, {b,c}:1, {d}:1
- **D6** — 两阶段配额混合：profiles (1,1):1/3, (0,2):2/3
- **D7** — 不等概率固定配额 m=2：{a,b}:1/2, {a,c}:1/4, {c,d}:1/4
- **D8** — 重随机化平衡：均匀 base m=2 + 协变量 x 均值差 ≤ 1/2

## 暴露参数

- **E1** — 严格多数（平票=0）
- **E2** — 邻居比例三档
- **E3** — 核心合作者多数
- **E4** — 精确处理邻居数
- **E5** — 任一处理邻居
- **W** — 加权暴露（和，w_b=1,w_c=2）
- **G** — 分组暴露（g1={b}, g2={c}，元组按 g1,g2 顺序）

## 表 1 · 联合支持矩阵（节点 a 的正支持 (a,s) 状态）

| 设计 \ 暴露 | E1 | E2 | E3 | E4 | E5 | W | G |
|---|---|---|---|---|---|---|---|
| **D1** | a=0:{0,1}; a=1:{0,1} | a=0:{0,1,2}; a=1:{0,1,2} | a=0:{0,1}; a=1:{0,1} | a=0:{0,1,2}; a=1:{0,1,2} | a=0:{0,1}; a=1:{0,1} | a=0:{0,1,2,3}; a=1:{0,1,2,3} | a=0:{(0,0),(0,1),(1,0),(1,1)}; a=1:{(0,0),(0,1),(1,0),(1,1)} |
| **D2** | a=0:{0,1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{0,1}; a=1:{0,1} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0,1} | a=0:{1,2,3}; a=1:{0,1,2} | a=0:{(0,1),(1,0),(1,1)}; a=1:{(0,0),(0,1),(1,0)} |
| **D3** | a=0:{0,1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0,1} | a=0:{1,3}; a=1:{0,2} | a=0:{(1,0),(1,1)}; a=1:{(0,0),(0,1)} |
| **D4** | a=0:{0}; a=1:{0,1} | a=0:{0,1}; a=1:{1,2} | a=0:{0}; a=1:{1} | a=0:{0,1}; a=1:{1,2} | a=0:{0,1}; a=1:{1} | a=0:{0,2}; a=1:{1,3} | a=0:{(0,0),(0,1)}; a=1:{(1,0),(1,1)} |
| **D5** | a=1:{0} | a=1:{1} | a=1:{0,1} | a=1:{1} | a=1:{1} | a=1:{1,2} | a=1:{(0,1),(1,0)} |
| **D6** | a=0:{0,1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{0,1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0,1} | a=0:{1,2,3}; a=1:{0,2} | a=0:{(0,1),(1,0),(1,1)}; a=1:{(0,0),(0,1)} |
| **D7** | a=0:{0}; a=1:{0} | a=0:{1}; a=1:{1} | a=0:{0}; a=1:{0,1} | a=0:{1}; a=1:{1} | a=0:{1}; a=1:{1} | a=0:{2}; a=1:{1,2} | a=0:{(0,1)}; a=1:{(0,1),(1,0)} |
| **D8** | a=0:{0,1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0} | a=0:{1,2}; a=1:{0,1} | a=0:{1}; a=1:{0,1} | a=0:{1,3}; a=1:{0,2} | a=0:{(1,0),(1,1)}; a=1:{(0,0),(0,1)} |

## 表 2 · 四类目标接入矩阵（节点 a，按原设计平均）

**条件与结论分开**：以下数值是**按原设计平均的效应**（design-standardized），只需
`random_assignment` + `consistency` + 目标 arm 正支持；**不**以暴露充分性为前提。
若另**额外采用暴露充分性**，同一数值可升级为「暴露的因果效应」解释
（`causal_effect_under_exposure_sufficiency`），但那是更强的解释层，不改变本表数值，
也不是本表成立的条件。未单独标注时本表即 `design_standardized_contrast`。

坐标按暴露类型取**合法状态**：E1–E5 为整数；W 为精确有理加权值；G 为**成组计数元组**
（如 `(1,0)`、`(0,1)`），**不**统一用单个 0/1。`POINT` 给出该坐标下的符号值，
`UNSUP` 记录正支持缺失或条件未确认。

### 2a · local_direct_mean（固定一个合法 s 坐标，比较 a=1 减 a=0）

| 设计 \ 暴露 | E1 | E2 | E3 | E4 | E5 | W | G |
|---|---|---|---|---|---|---|---|
| **D1** | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) |
| **D2** | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) |
| **D3** | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) |
| **D4** | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) |
| **D5** | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) |
| **D6** | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) |
| **D7** | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) | POINT (4) |
| **D8** | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | POINT (4) | POINT (4) | UNSUP (no common (a=0,a=1) coordinate at node a) | UNSUP (no common (a=0,a=1) coordinate at node a) |

### 2b · peer_spillover_mean（own=0，比较高坐标减低坐标）

| 设计 \ 暴露 | E1 | E2 | E3 | E4 | E5 | W | G |
|---|---|---|---|---|---|---|---|
| **D1** | POINT (1) | POINT (2) | POINT (1) | POINT (2) | POINT (1) | POINT (3) | POINT (2) |
| **D2** | POINT (1) | POINT (1) | POINT (1) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (2) | POINT (1) |
| **D3** | POINT (1) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (2) | POINT (1) |
| **D4** | UNSUP (<2 peer coordinates at node a) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (1) | POINT (1) | POINT (2) | POINT (1) |
| **D5** | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) |
| **D6** | POINT (1) | POINT (1) | POINT (1) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (2) | POINT (1) |
| **D7** | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) | UNSUP (<2 peer coordinates at node a) |
| **D8** | POINT (1) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (1) | UNSUP (<2 peer coordinates at node a) | POINT (2) | POINT (1) |

### 2c · policy_mean 与 policy_contrast（仅设计维度）

政策值/两政策差值同样是**按原设计（完整分配律）平均**的 `design_standardized_policy_value`，
不涉及暴露映射或暴露充分性。

| 设计 | policy_mean (E[2|A|]) | policy_contrast (vs D2) |
|---|---|---|
| **D1** | POINT (7/2) | POINT (-1/2) |
| **D2** | POINT (4) | POINT (0) |
| **D3** | POINT (4) | POINT (0) |
| **D4** | POINT (10/3) | POINT (-2/3) |
| **D5** | POINT (6) | POINT (2) |
| **D6** | POINT (4) | POINT (0) |
| **D7** | POINT (4) | POINT (0) |
| **D8** | POINT (4) | POINT (0) |

## 关键查找验证（D7 × E1，节点 a）

- 单位概率之和为 1：`是`
- 所有概率非负：`是`
- 条件概率 P(S|T=1) 归一为 1：`是`
- 例：P(T_a=1, S_a=0) = `3/4`

> 说明：加权/分组暴露（W/G）在证书后端属明确缺项（见缺项表），其 POINT 识别由内部精确
> 枚举层 `randomized_arm_family` 提供，本表表 1 已记录其正支持状态。表 2a/2b 统一用整数
> 状态 0/1 查询目标，对 W（加权和）有意义，对 G（元组状态）无对应状态故记为 UNSUP；
> W/G 的四类目标接入见内部层测试 `tests/test_task1_targets.py`。新设计（D7/D8）精确支持
> 为全排列枚举，N≤8。
