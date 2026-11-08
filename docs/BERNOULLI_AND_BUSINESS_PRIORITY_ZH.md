# 常见网络干扰业务：Design 优先级与 POINT 边界（）

## 结论

个体级独立 Bernoulli A/B（D1）是实务中很重要的基线，并不“过于玩具”。在线平台可能用确定的哈希分桶工程实现随机分配；数学上必须审查其真实分配机制而不能看到哈希就假定所有分配独立。LinkedIn 对个体与图簇 A/B 直接做过真实对照；Airbnb 的市场干扰元实验说明个体随机化下的干扰偏差可能影响估计。

**不应把 D1 设计在数学上覆盖很多 target 等价成它对所有网络干扰业务都最佳。** 对于网络干扰大、业务可按团队/门店整体投放的场景，D4 簇级随机可能更贴近执行；固定补贴名额、公司预算时选 D2/D5；希望比较组内不同 saturation 时考虑 D6。

| 常见场景 | 先考虑 | 实现判断 | 必须提醒 |
| --- | --- | --- | --- |
| 在线功能灰度/账号 AB | D1 | 已有正式定理及门禁 | 全量政策可识别不等于有限样本易估计 |
| 限定处理人数/实验名额 | D2 | 已有正式定理及门禁 | 完整全员政策可能零支持 |
| 部门分层固定配额 | D3 或 D5 | 已有正式定理及门禁 | 处理前分组必须确定 |
| 整个班级/门店一起处理 | D4 | 已有正式定理及门禁 | 簇内一些处理/暴露组合不可能出现 |
| 两阶段随机政策饱和度 | D6 | 有限配额混合子域 | U 没有超出最终 T 的直接结果效应必须另行接受 |
| 自愿采用 AI/员工自选 | R3（非 D） | 已有正式有限子域 | 无未测量混杂不能由模型形式自动证明 |

## Exposure 优先级

对导师沟通最容易理解的是 E5“至少一个同伴使用”、E1“同伴严格多数”、E4“精确多少同伴使用”。E2“三档比例”适合饱和度问题，E3“核心合作者”适合业务上明确存在特殊强关系且**已经在处理前确定集合**的企业情形。这只是叙事优先级，不等于某个 exposure 比别的结构假设更可信。

## 数学合同必须保留

1. R1a 的标准化 Effect 不要求 exposure sufficiency；R2 对 off-support 固定政策才额外需要 mean-signature sufficiency。
2. D1 / D4 / D6 实验设计下的支持集合不同；任何“D×E 能配置”都不代表每一个节点状态必然正支持。
3. D6 在已实现子域要求第一阶段 quota profile 对最终处理以外没有额外直接结果效应。
4. R3 的观测总体处理概率形式并不自行消除混杂，且目前调整变量范围很有限。
5. 因果 POINT（总体函数）与有限样本估计、现实业务政策收益数值必须分开。

## 研究与行业证据

- Aronow & Samii (2017), *Estimating Average Causal Effects Under General Interference, with Application to a Social Network Experiment*: https://arxiv.org/abs/1305.6156
- Hudgens & Halloran (2008), *Toward Causal Inference with Interference*: https://pmc.ncbi.nlm.nih.gov/articles/PMC2600548/
- LinkedIn Engineering, *Detecting interference: An A/B test of A/B tests*: https://www.linkedin.com/blog/engineering/ab-testing-experimentation/detecting-interference-an-a-b-test-of-a-b-tests
- LinkedIn Engineering, *A/B testing at LinkedIn: Assigning variants at scale*: https://www.linkedin.com/blog/engineering/ab-testing-experimentation/a-b-testing-variant-assignment
- Airbnb: *Reducing Interference Bias in Online Marketplace Experiments Using Cluster Randomization*, Management Science (2024): https://pubsonline.informs.org/doi/10.1287/mnsc.2020.01157
- *Statistical Inference and Power Analysis for Direct and Spillover Effects in Two-Stage Randomized Experiments*, Biometrics: https://academic.oup.com/biometrics/article/79/3/2370/7513883

**证据解释边界：** 这些文献和平台案例说明上述设计在研究或实务中被使用，不提供各种设计的全球使用频率排序；看板中的“优先级”是面向本项目常见业务目标的定性研发建议。
