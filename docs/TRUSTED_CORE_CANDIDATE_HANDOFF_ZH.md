# Gateway — 真实 Core 覆盖诊断 → 候选 LLM 的可信接入合同

## 1. 版本定位

本仓库 **只发布独立 CFM-ID LLM Gateway v0.12.0**，向前兼容 v0.11 Candidate Reasoner 和 v0.10 A0。数学基线是单独安装/挂载的 **Causal-IDFM v2.9.1**。没有修改、复制或随 Wheel 发布 `pfn_pipeline/`、`cfm_id_bridge/`。

上轮暂停后，只有发布文档部分保存到 /mnt/data；实际 v0.12 模块由已保存的 v0.11 完整 ZIP 和数学 v2.9.1 完整 ZIP 重新构建并复测。本文件记录**重新构建**的代码真实能力。

## 2. 核心信任边界

1. A0 `MultiQueryQualityReportV010` 是可审查的业务规范化草稿，不是科学许可。
2. `BusinessQueryReviewV011` 是外部研究者明确批准的具体查询，绑定 **v0.10** 源和草稿摘要。
3. v2.9.1 `FormalQueryBindingV29` 包含真正的 typed 数学查询、独立科学审批和 A4/A5；本 Gateway 不从自然语言推断这些对象。
4. `ApprovedBusinessMathCrosswalkV012` 另外绑定目标哈希、查询级语义哈希、v0.10/v0.9 不同的草稿哈希对应关系、数学坐标、A4/A5 来源、路线许可。两项 reviewer 确认字段都是必填的 `Literal[True]`，不能默认通过。
5. `RealCoreCoveragePortV012.lookup()` 每次重新检查上述对象并**直接调用真实** `run_verified_multiquery_v29()`，从真实 Bridge 的返回生成 `CoreCoverageV011`。没有外部可提交的 `PRODUCTION` JSON 覆盖接口。
6. `CandidateReasonerV011` **仅**在 `status=UNSUPPORTED`、`fallback=ELIGIBLE_NOT_EXECUTED` 且 reason 属于已批准的定理覆盖缺口时调用候选模型。`POINT`、`NEEDS_INPUT`、`NO_ADAPTER`、`INCOMPATIBLE` 或证书失败都不会触发。
7. Candidate 输出一律 `LLM_UNVERIFIED`，不能产生证书，不能交 Estimation。

**重要限制**：哈希与结构一致性不是审核人身份签名，也不能证明现实中的 A4/A5 假设确实成立。保守的全员政策语义检查只防止少数明确矛盾，不能取代独立的数学目标审核。

## 3. 合成正反例（实际 Core + Mock LLM）

使用三节点星形合作网络 A–B、A–C，处理前网络固定，E1 严格多数暴露。

- `--supported`：A/B/C 都独立 Bernoulli(1/2)。q1 A 未处理且低暴露的臂均值获得真实 `R1A_RANDOMIZED_ARM/POINT`，q2 全员政策也由 `R1B_FULL_ASSIGNMENT/POINT` 认证。**候选调用 0 次**。
- 默认 `off_support`：A 永远未获 AI；B/C 分别 Bernoulli(1/2)。q1 仍有正支持、真实 Core 返回 POINT；q2 全员政策 `z=(1,1,1)` 零支持，真实 Core 返回 `UNSUPPORTED/OFF_SUPPORT_ALTERNATE_THEOREM`。**候选调用 1 次**，Mock 回答 `UNDETERMINED_UNVERIFIED`。

两份业务说明的随机化叙述与 typed design 一致；科学 A4/A5 是另行**假定**的测试资料，**不来自销售表格**。R1b 零支持不证明数学上的非识别：R2 仍可能需要额外科学结构假设，不能自动加入。

## 4. 运行方法

### 完整的真实-Core 可选联调（需要数学源码）

从此独立 Gateway 源码目录执行（不要将两个源码的旧 `cfm_id_llm` 包混合安装覆盖）：

```bash
export PYTHONPATH="$(pwd):/path/to/Causal-IDFM-v2.9.1"
python -m examples.run_candidate_real_core --output /tmp/v012_offsupport.json
python -m examples.run_candidate_real_core --supported --output /tmp/v012_supported.json
bash scripts/run_v012_real_core_tests.sh
```

**必须观察到**：默认案例 Core q1=POINT/q2=UNSUPPORTED，Mock 候选调用一次；supported 案例 q1/q2 均为 POINT，候选调用零次。如果无法 import 数学 Core，脚本应失败，而不是伪装数学测试通过。

### 只有 Gateway 时

```bash
python -m unittest discover -s tests -p 'test_*.py' -q
python -m evaluation.candidate_reasoning_eval
```

真实 Core 集成测试在数学库缺失时明确标为 `SKIP`。**不能**将 skipped tests 算作实际数学联调完成。

### 安装范围

本仓库在根目录使用 `python -m pip install -e .` 安装，包含 Gateway、数学模块、评价工具和教学示例，不需要另装旧 Gateway wheel。示例中的合成审核仅用于演示和测试；真实企业资料仍需明确授权后才能上传给外部服务。

## 5. 测试与下一阶段

- 关注源/草稿陈旧、业务审核错绑、A4/A5 摘要不符、路线与政策坐标错误、未批准检查表误当正式批准。
- 在真实 Core 路径，要求逐查询 POINT/UNSUPPORTED 的实际来源和证书状态；并检验模型调用次数。
- 本轮**没有在线 API 调用、没有模型数学准确率成绩、没有自由形式候选公式证明**；21 个 NBIB 尚未整体具有 formal-backed 科学许可证。
- v1.0 前还需真实 LLM 数据集评估、专家审查数学候选与更广数学版本适配。
