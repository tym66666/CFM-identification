# NBIB × A0 规范化质量验收协议

## 数据集与分区

来源：用户给出的 Causal-IDFM v2.9.1 包内 `assets/benchmark_assets` 中的 NBIB v0.1，保留其 21 个公开业务提交文件夹和经审核的 query target-type 参考标签。文件已复制至独立 Gateway：

- `evaluation/nbib/public/cases/NBIB-*`：业务问题及公开方案、网络/实验 CSV；**这是唯一送入模型的资料**。
- `evaluation/nbib/research_only/target_reference.json`：21 个案例的目标类别 gold，仅在模型调用完毕后用于目标评分。
- `evaluation/nbib/research_only/query_taxonomy_reference.json`：逐查询研究审查标签，不是正式 typed Core 识别证书。

**重要已知限制：** NBIB v0.1 的业务附件中仍包含 A4/A5 等研究术语，且原审查有七个优先修订案例。该集合不能声称已经是严格盲测、业务人员自然材料的最终版本。

## 自动评分可以测什么

- JSON Schema 及所有填写语义字段的来源原文引用是否有效；
- 21 个业务的多查询目标类别是否齐全，重复/遗漏目标数量及类别 F1；
- 哪些 case 标记了材料缺失、业务澄清和科学审核；
- 生成未预填的逐查询专家语义审查模板。

**不能自动测：** 处理/对照、全员政策坐标、暴露、聚合与总体信息是否在数学上语义正确；也不能凭当前有限样本业务轨道给出 POINT、NOT IDENTIFIED 或正式识别覆盖率。`reference-fixture` 的目标 F1=1.0 只表明我们手写的目标标签能往返通过 Schema，不是模型得分。

## 专家审核模板如何使用

```bash
python -m evaluation.nbib_semantic_eval --provider reference-fixture \
  --human-review-template /tmp/nbib_review.json --output /tmp/nbib_offline.json
```

专家应逐项阅读原业务材料及预测草稿，再把 `human_labels` 中对应字段赋值为 `true`/`false`，不适用或无法判断保持 `null`。尤其关注用户问“所有人使用”但预测写“部分使用”这种**重大语义错误**。

```bash
python -m evaluation.nbib_semantic_eval \
  --score-human-review /tmp/nbib_review.json \
  --output /tmp/nbib_human_scores.json
```

所有手工评分应记住评审者身份、审核日期与候选模型版本；当前脚本负责计算已填字段的比例，不具备审核授权认证功能。

## 最重要的消融和成对评测

建议学生继续横向扩展三种成对材料：**相同业务目标，不同 assignment 协议；相同目标与实验，不同 A4/A5 信息；相同政策目标，但 full assignment 支持与 mean signature 支持不同。** 第一轨检验业务语义能否恢复，第二轨待数学研究者建设合法 typed reference 后，再审查 Core 真正输出及 Replay。切勿把有限样本样本数与总体信息许可混淆。
