# NBIB v0.1 Benchmark 数据

这份目录可直接作为未来 CFM-ID 公开仓库下的 `benchmarks/network_business_identification/`。

- `public/` 是业务问题和仿真 CSV，允许提交给 Gateway。
- `gold/` 是研究者参考目标和严格数学支持概率；`conditional_route_only` 不等于 theorem 执行结果。
- `oracle/` 是模拟器隐藏变量，禁止当作业务可见信息或因果假设证明。
- `gateway_target_only_cases.json` 仅提供旧版 Gateway 单文本目标抽取的兼容题，**没有覆盖附件解析**。
- 全部文件均为合成数据，基于有限样本不能自动确认 A4、A5，更没有由此得到 POINT/VERIFIED。

如需重生成与验证，请保留上级独立项目的 `scripts/` 与 `catalog.json`。
