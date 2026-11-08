# Network Business Identification Benchmark（NBIB）v0.1.0

本文件保留原始独立资料包的历史说明。下文的版本、未合并状态、目录树和生成命令描述当时的完整发布包；其中的 `scripts/` 和辅助 `docs/` 没有随当前资产目录分发，不能在这里直接执行这些旧命令。当前仓库的评测入口见 [NBIB 语义评测说明](../../docs/NBIB_A0_SEMANTIC_EVALUATION_ZH.md)。业务题与参考数据保持原样。

**发布日期：2026-10-17 | 独立 Benchmark 资料包 | 尚未合并 CFM-ID-LLM-Gateway v0.9 与 Identification Library。**

## 核心目的

这不是让业务人员填写专业数学 JSON 的题库。每个案例先给出 **约 185–260 字的自然中文业务问题**，再配上真实企业可能提供的项目方案、固定/动态合作网络、单位基础表、实施名单和处理后的观察结果（全为仿真数据）。

它主要检验 LLM 是否能从完整业务资料中：

1. **忠实找出全部业务目标**：Own/direct、spillover、fixed-policy、finite-policy mixture、policy optimization 等不能互相替换。
2. **正确识别实验/观察机制**：D1/D2/D3/D4/D5/D6 与几种观察性采纳；不能以“有名单”冒充随机实验。
3. **正确识别 network / exposure**：E1/E2/E3/E4/E5，处理前无向图与干预后动态网络不同。
4. **区分真实数学条件与文件描述**：CSV 中只有有限样本，不自动获得 A4 总体算子和 A5 因果许可。
5. **区分三类不同的不成功**：所需信息缺失、当前定理路线不适用、构造性的真正非识别证据。
6. **在成对案例中保留数学语义**：更换设计/假设/支持条件时，模型的输出应正确变化，而不是随便猜 route。

## 交付规模

- **21 个**中文完整业务案例，8 类图拓扑：ER、环、社区/SBM、网格、二部图、小世界、星形、梯形；节点数 **14–300**。
- D1/D2/D3/D4/D5/D6 以及观察性/分层采纳场景，E1–E5 均有覆盖。
- **5,706 行**模拟结果记录（跨 21 案例和部分案例的独立市场复制）；本版附件采用 UTF-8-SIG CSV 与 Markdown；PDF/XLSX 文件变体可在后续扩展。
- **3 组成对/多联对照**：NBIB-005/006；NBIB-008/009；NBIB-013/014/015/016。
- NBIB-019 含观察等价、干预效应不同的两因果世界数学反例。
- 生成器与数值检查器均使用 Python 标准库，不需要 API Key。

## 文件布局（适合移入公开仓库）

```text
Network-Business-Identification-Benchmark-v0.1/
  README_ZH.md
  README_EN.md
  catalog.json                    # 人工设计的合成场景/数学参考元数据，研究者可用，不可当作 LLM 输入
  scripts/
    build_catalog.py             # 21 张业务卡的可编辑人工种子
    generate.py                  # 可复现生成图/分配/表格/私有参考数据
    validate.py                  # 数据完整性 + exact support 的小图独立穷举
    score_predictions.py         # 结构化输出的初级评分器
  examples/
    two_structured_predictions_EXAMPLE.json
  docs/
    CASE_MATRIX_ZH.md            # 21 个任务类型与科学边界
    EVALUATION_PROTOCOL_ZH.md    # 阶段/保留集/人工评分标准
    MATH_ALIGNMENT_ZH.md         # 与 v2.7 数学合同的对齐情况
    validation_report.json       # 本地数据/算术验证报告
    benchmark_overview.html      # 离线可打开的案例研究导航页
  benchmarks/
    network_business_identification/
      public/
        case_index.json
        cases/NBIB-001/...       # **业务端可见：业务问题、方案和 CSV**
        ...
        cases/NBIB-021/...
      gold/
        references/NBIB-001.json # **研究端：目标语义/路线候选/阻断条件/精确支持**
        ...
        nonidentification_witness_NBIB-019.json
        summary.json
      oracle/
        generator_worlds/...     # **模拟器内部变量/隐藏 U，永不送 LLM**
      gateway_target_only_cases.json
      MANIFEST.json              # SHA-256 + seed + 文件清单
```

移入公开仓库时可将整个项目文件夹放进 `benchmarks/network_business_identification/`；若想让 benchmark 的公共题与标准答案部署于不同机器，只复制 `public/` 到业务端，再把 `gold/`、`oracle/` 保留在研究者/评分端。**仅复制 public/ 不包括生成器；可复现构建时保留 scripts/ 和 catalog.json。**

## 一键复现

在项目根目录运行：

```bash
python scripts/build_catalog.py        # 可选：从可编辑Python原始目录重建catalog.json
python scripts/generate.py --seed 20261017
python scripts/validate.py --reproduce
```

`--reproduce` 会使用同一个 seed 重新生成一次并比较全部文件 SHA-256。

## 使用 Gateway v0.9

仅测试 **自然语言业务目标类别**（忽略附件）的兼容入口：

```bash
python -m evaluation.multiquery_eval \
  --case-set /path/to/benchmarks/network_business_identification/gateway_target_only_cases.json \
  --provider oracle-fixture --max-cases 3
```

注意 `oracle-fixture` 是人工参考草稿的格式自检，不是在线 LLM 成绩。

**完整文件联合评测尚未适配 v0.9 现有运行器**：应当从 `public/cases/NBIB-xxx/submission_manifest.json` 中读取业务文本和附件，并运行实际 Gateway 的 document intake，**不能把 gold/ 或 oracle/ 放进 Prompt**。

研究者结构化回答可以用：

```bash
python scripts/score_predictions.py \
  --predictions examples/two_structured_predictions_EXAMPLE.json \
  --output /tmp/nbib_scoring.json
```

现有评分器可算目标类型、精确目标语义和设计类别匹配，但科学证据归纳、A5 假设合理性与数学证书仍需独立审查。

## 数学正确性说明（必读）

- 严格 Identification v2.7(+P1/P2) 是**参考合同**，不是本 Benchmark 21 案例的已运行 typed core 结果；所有 `gold/references/*.json` 都标明 `identification_library_status = NOT_RUN_ON_THIS_GENERATED_CASE`。
- **实际提交的有限 CSV 不提供 A4 总体算子**，故不能只因为模型输出了一个已知定理名称或正 support，就对业务问题宣称 `POINT/VERIFIED`。
- R1a 的 q-standardized arm 不要求 exposure sufficiency；R1b 的完整分配正支持不能由 R1a 四臂均值代替；R2 的 mean-signature sufficiency 是额外科学许可；R3 P2 的 individual-level exposure sufficiency 与 R2 的均值版本不同。
- NBIB-008/009 的全员政策 `q(z)=0`，但 E5 签名对全部节点可正支持；二者不同。NBIB-016 在需求旺盛的正权 B 层，对 treated arm 支持为 0。
- NBIB-019 单独构造“同观测律、不同因果目标”的双世界反例。它证明指定无 A5 模型类下存在非识别，**不**代表已有一般 network non-ID 自动求解器。
- `gold` 内条件性 route 不是从仿真潜在结果推导出已认证的 A4 或 A5。任何未来要称为正式 POINT 的案例，必须由最新版数学库 typed spec 调用并独立 replay。

## 研究与开源边界

- 数据是完全仿真，机构和场景为虚构，不能用于声称真实行业因果发现。
- 这是 **公开诊断题库**，公开 gold 的测试不能被当成训练污染隔离的盲测成绩。以后若训练模型，另建不公开原始案例/种子的严格 held-out 集合。
- 源码库更新时应建立 `math_core_contract_version` 和每个案例的 `core_replay_verified` 独立验收表，不能靠 route 标签保持兼容。
- 本版不修改 Gateway v0.9 或数学库任何源码；尚无生产 Adapter、API LLM 真实准确率、数值 Estimation 或 Policy 认证。
