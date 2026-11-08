# 业务分配规则的共同语义

本次修改解决读取合同中同一分配方式使用不同名称、而判定边界没有集中说明的问题。它属于 A0 和网络事实读取层，不新增识别定理，不按关键词替模型改答案。

实验选项 `business_intake.start(..., assignment_semantics="joint-assignment-law-1")` 会保存该说明版本。默认仍为历史说明（None）：本轮真实对照没有证明新增说明稳定提升，不能直接替换默认。共同说明位于 `cfm_id_llm/assignment_semantics.py`，由 compact A0 和网络固定政策事实请求共同使用；返回 JSON 的字段及枚举保持原样。DAG 事实请求不加入网络分配字典。

| 材料说明 | A0 候选类别 | 当前网络固定政策事实类别 |
|---|---|---|
| 全体对象中恰好 m 个，所有大小为 m 的名单等概率 | COMPLETE_RANDOMIZATION | UNIFORM_FIXED_QUOTA |
| 逐对象独立抽签，各自概率已给出 | INDEPENDENT_BERNOULLI | INDEPENDENT_BERNOULLI |
| 分组各有固定名额 | STRATIFIED_FIXED_QUOTAS | OTHER，保留组别和分配限制 |
| 整簇抽签、簇内共同处理 | CLUSTER_RANDOMIZATION | OTHER，保留簇级机制 |
| 固定人数但各名单概率明确不相等 | OTHER | OTHER，保留非均匀概率机制 |
| 仅有人数上限、平均数、一次实现或未来计划，历史机制不明 | UNRESOLVED | UNKNOWN，保留缺项 |

这里的 OTHER 是当前事实入口的表达/适配限制，不是识别不可能的证明。原生 Core 的其他设计能力仍保留，不能把这一桥接范围写成整个项目只支持两类设计。

## 数学含义与文献

对于完整处理向量 \(Z\in\{0,1\}^N\)，均匀固定名额描述的是联合分配律：

\[
P(Z=z)=\frac{\mathbf{1}\{\sum_i z_i=m\}}{\binom{N}{m}}.
\]

无需用户另外给出逐对象边际概率。尤其不能要求对象独立抽签：非退化的固定总数分配下，各分配坐标一般相关。“有网络干扰”描述结果对他人处理的依赖，与分配坐标是否独立是不同问题。

完全随机、分层、成对和簇随机的标准区分见 Athey 与 Imbens, *The Econometrics of Randomized Experiments*, §§3.2.1–3.2.4，特别是 §3.2.1 的均匀固定名额概率式和 §3.2.2 的分层支持限制：[作者公开稿](https://arxiv.org/html/1607.00698#S3.SS2)。分类体系也见 Imbens 与 Rubin (2015), *Causal Inference for Statistics, Social, and Biomedical Sciences*, Chapter 4：[出版社章节](https://www.cambridge.org/core/books/abs/causal-inference-for-statistics-social-and-biomedical-sciences/taxonomy-of-classical-randomized-experiments/640B80EA1E1B85F9C3CC3268FBB67114)。这些文献支持分配机制的区分；项目的枚举命名和桥接范围是软件合同，不是文献中的识别定理目录。

文献中的随机实验还带有相应科学条件。我们仅从业务材料读取声明的名单概率机制，不能因此自动批准完整处理向量与所有潜在结果独立、一致性、外推到未来期间或均值暴露充分性。有限样本也不会变成已知总体信息。

## 兼容与验收范围

旧 intake 没有该字段时，序列化仍不增加空字段，原请求和旧审核绑定保持不变。低层 `make_compact_request` / `network_policy_reading.make_request` 默认保留历史请求；业务入口按存储的选项传递说明版本。研究对照显式选用实验说明，不能把新说明静默附加到旧候选。读取报告也显示实际选用的说明版本。

A0 重读和专门事实重读沿用该 intake 的说明版本；来源目录、旧回答、反馈和审核仍按原有规则保存。更改说明版本不能复用旧请求和批准。共同说明没有业务案例答案，不作为可引用的事实来源。

自动回归见 `tests_gateway/test_assignment_semantics.py`，检查旧请求、绑定失效、原文和输出合同保持不变及两次重读的传递。真实准确率需另行以冻结业务材料、原始模型回答和独立来源审核评估；测试代码通过不代表模型必然遵循说明。

2026-10-26 完成六题、25 次实际请求：DeepSeek 的旧/新说明分配类别均为 5/6，新说明修正一题同时误读一个非均匀反例；LongCat 新说明为 6/6。后续七次分配字段正确，但三份回答补出了未明确声明的潜在结果独立性，均未获得科学批准。所有事实流程因总体信息缺失停住。因此本选项继续用于受控实验，不据此宣称完整读取或端到端识别已稳定。完整原始记录位于仓库外 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`。
