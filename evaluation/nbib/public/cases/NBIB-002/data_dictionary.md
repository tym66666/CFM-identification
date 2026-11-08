# 数据字典与使用边界

- 本案例主要结果指标：`delivery_delay`，单位为 `分钟/订单`，方向：越低越好。CSV使用通用列名 `metric_before` / `metric_after` 以便自动处理。
- `units.csv`：试验前已知的单位特征。`unit_group` 在分层/簇设计中是分配单位，否则只是业务分组；`baseline_metric` 是有限样本前期记录，不是总体潜在结果。
- `network_edges.csv`：若存在，试验前冻结的无向协作边，每条仅保存一次。模拟文件不会包含隐藏的潜在结果机制。
- `network_after.csv`：仅动态网络场景存在，记录试验后观察到的合作关系，**不能当作处理前网络**。
- `treatment.csv`：各独立市场实例中实际获得处理的单位。`tool_received=1` 表示接受处理；观察性研究中它不是随机分配。
- `outcomes.csv`：每个单位的有限观察结果；单位仍有反事实潜在结果没有被观测到。
- `market_episodes.csv`：每行是一个独立模拟市场实例。`environment_before_treatment` 是整个网络层面的处理前环境 B，**不是每个单位各自的 B_i**。对非分层场景只有一个市场。
- `design_probabilities.csv`：如果存在，仅是研究设计中的已知抽签概率，不能把它当成观测倾向得分或因果许可。
- `core_collaborators.csv`：如果存在，试验前指定每个单位的核心伙伴集合，且必须是原图邻居的非空子集。
- `candidate_policies.csv`：如果存在，表示业务人员提出的明确政策，**不是在本轮数据里实施的处理**。

所有 CSV 都是有确定随机种子的仿真样本。有限样本、可见列名、抽签日志、显著差异都**不能自动代替**总体 A4 信息和科学 A5 许可；也不代表已获 POINT / Estimation 认证。
