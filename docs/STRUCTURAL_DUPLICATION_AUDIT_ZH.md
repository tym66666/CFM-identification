# Identification 结构负担审计：只读、暂不重构

**目标**：区分数学上必需的不同定理与历史工程包装；不按文件行数粗暴合并。

## 核心结论

- **保留**：`randomized_arm_family` 的 Assignment / Exposure / Support 分离；R1a/R1b/R2/R3 的不同数学合同；A4/A5/A6；独立 verifier。
- **显式划分职责**：`cfm_id_bridge/bridge.py` 是业务/审核关口；`identification_business.py` 是已确认 typed 查询路由；`pfn_pipeline/identification.py` 仍有 TaskSpec 兼容入口。默认教新同学从 Golden 的 typed Inquiry 开始，不让他们改 legacy。
- **先审计、暂不收敛**：R3 p-standardized 的 `identification_observational_effects.py`（231 行）、`identification_observational_factorized_a4.py`（370 行）、`identification_observational_mixture_a4.py`（344 行）均服务相同识别思想，但各自 A4、支持及 replay 边界并非已证明可互换。必要时先补小图跨表示等价和不等价测试，再考虑抽公共算术；不得先替换旧证书。
- **Nodewise**：`identification_observational_nodewise_adjustment.py`（602 行）与 `identification_observational_nodewise_mixture_a4.py`（79 行）有依赖关系，不因相同前缀就算两条 Family。
- **历史 schema**：`pfn_pipeline/_internal/identification/schemas.py`（3011 行），这是潜在维护风险，不建议现在拆为多个新公共 package。
- **静态资产**：历史 README、发布快照、日志和大量看板可以归档或改变浏览入口，但这些并不等于生产算法本身的重复；本轮保持所有文件不删。

## 下一阶段风险最小的候选整理（不是本轮代码变更）

| 优先 | 目标 | 允许实施的前置证据 | 当前决策 |
|---|---|---|---|
| P0 | 给团队统一唯一 Golden 命令与输出 | 3 节点正反例 + verifier + snapshot | 已落地 |
| P0 | Core/A0/历史 PFN 三段测试单独执行 | 测试无互相污染 | 已落地 |
| P1 | R3 多表示 A4 的公共检查 | 同一 Target 的跨表示等价及冲突负例 | 只调研，暂不合并 |
| P1 | 统一文档入口 | 保留旧功能可定位 | 增加 `00_MINIMAL_CORRECT_CORE_START_HERE_ZH.md`，不删除 README |
| P1 | 精简历史 schema 与 compatibility classes | 模块级 API diff + replay 无回归 + 明确收益 | 冻结，暂不操作 |
| P2 | 新 Family/新 D/E/R4 | 独立高频真实业务需求 + 可证明反例 + 最小复杂度预算 | 不在稳定化阶段做 |

**负责人与任务拆分建议**：核心成员保留数学合同、目标同一性与独立 verifier 的最后签字；学生可以在现有 API 下贡献性能 profile、小图 oracle、HTML 文案改进和更多消融数据，而无需改动 R1a/R2/R3 内核。
