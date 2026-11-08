# A0（另一 GPT）与 Identification 合并前的接口准备说明

此文件是**只读协作协议建议**，本轮**没有实施或修改 A0**，也没有修改 Estimation/Policy。

## 1. 合并的正确理由

可以因为已有稳定 typed Business Inquiry、明确 A1–A6 合同和独立 replay，而开展**有限场景的接口对接**。不能因为已经“覆盖大多数网络干扰问题”而决定合并——我们没有这种经验覆盖率证据。

## 2. 两边的责任分离

- A0：业务自然语言 → 结构化候选问题 (proposed) → 研究者对因果假设、测量模型、图时点、处理版本等逐项确认，保留 provenance。
- Identification：接受合法 typed inquiry + 明确声明的已准入 A4/A5 + A6 exact support，输出形式化 POINT 泛函与证书，或 NEEDS_INPUT / UNSUPPORTED。它不能凭自然语言或变量齐全而创造总体算子或科学因果许可。
- Estimation/Policy：本轮不接入。Identification 返回的数学表达不代表有数值 estimator。

## 3. 联调 Gate（建议共同确认 20 张标注任务）

1. Scope：研究单位、节点顺序、固定网络、处理前条件 \(W\)，观测/随机实验来源，处理/结果单位与语义。
2. Target：`p-standardized`、`design-standardized`、`exposure potential-outcome adjusted`、`fixed-assignment policy` 等严格分开。`Direct`、`Spillover`、`Total` 本身不足以唯一指定目标。
3. A4：typed population operator、availability、provenance 与 admission；**finite sample != population law**。有表达能力 != 科学真实性。
4. A5：LLM 输出一律 proposed；有权人员确认 exposure sufficiency、full-vector 或 local mean exchangeability 及 D6 特殊排除条件后才进入正式路线。不能因选择了 E1–E5 自动批准充分性。
5. A6：自动核验全部非零目标项逐节点、逐调整层 support，不能把 UNSUPPORTED 说成已证明 non-identification。
6. Output：正式 `identify_network_business_query` 和 `replay_verified_business_outcome`；保留 proof、target fingerprint、study scope、A4/A5 证据、拒绝原因与 `NO_ADAPTER`。
7. Negatives：未确认 A5、只有样本均值、不同 source 协议、错误 Target 含义、混合律提供但潜在混杂、全网支持正而局部层零支持、报告冒充 outcome values。

## 4. 版本与适用范围

当前 Production Core 是 v2.8，含 post-release P1.1 数学兼容增量；9+/10 条历史 business routes 按原 typed 接口版本使用。新增 conditional mixture **沿用** `ObservationalNodewiseAdjustedEffectsInquiryV28` 和 `R3_NODEWISE_EXPOSURE_ADJUSTED_EFFECTS`；仅 A4 builder 新增 `declare_nodewise_correlated_arm_population_v28p2`。不增加 Family/Route 数量、没有新科学 A5。

建议先在独立 feature branch 做 A0 API 联调（不修改 theorem backend），通过手工已标注的金标准问题集合和安全拒绝测试后再合并主分支。
