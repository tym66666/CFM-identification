# CFM-ID LLM Gateway 业务说明与附件联合规范化合同

## 1. 目标与非目标

业务人员通常提供**相对完整的业务描述**（可以是 100–300 字，也可以更长）和一至三份附件，例如随机实验方案、合作关系网络、实际结果记录。用户不需要填写数学 JSON。

Gateway 先读取全部材料，再通过 LLM 生成**同一份** `DraftProblemSpec`；仅当缺少影响业务目标或实验设计的关键事实时，才提出少量通俗澄清。技术性的 A4/A5/A6 检查交由研究者/正式 ID Core，不向业务人员询问“是否满足某总体算子”。

**不做**：本模块不判定 POINT/PARTIAL，不进行正式定理认证，不估算收入，不优化真实政策，不导出任何 `EstimationRequest`。此版本尚未接入最新版数学识别库，也尚未运行真实在线 LLM。

## 2. 输入与处理流程

```
业务说明 + 本地协议 PDF / DOCX / TXT / MD + CSV / XLSX
          ↓ 本地安全读取；产生文件 SHA-256 与审查警告
BusinessCase（使用已有 v0.1 Schema，不另建 TaskSpec）
          ↓ ProblemFormulator（真实 Chat API 或 Mock）
DraftProblemSpec（A1–A6；所有确定项须附原文 source_id / quote）
          ↓ 独立 schema、引文、A4 保守审查
MultisourceReviewV07
          ├─ 缺关键业务含义 → 最多 2 个普通问题
          └─ 业务已足够明确 → 研究者核对 A4/A5/支持/数学目标
```

v0.2/v0.3 的正式 Core 优先和 LLM 未认证候选回退仍保留，但**本 v0.7 联合材料 Demo 不调用这两个阶段**。

## 3. 支持的文件类型、来源记录和隐私

| 类型 | 默认提取范围 | 限制 |
|---|---|---|
| `.pdf` | 可复制的文本片段，带页码 | 最多 15 页；图片/扫描 PDF 不做 OCR，提示无法提取 |
| `.docx` | 正文与表格中的文本段落 | 仅文档 XML；不加载外部超链接、宏或嵌入文件 |
| `.txt`, `.md`, `.json` | 文字摘录 | 每个来源最多 11,000 字符，截断显式报警 |
| `.csv` | 列名、数据行数 | **不将任何数据行发送给 LLM** |
| `.xlsx` | 工作表名、第一行表头、数据行数 | **不将任何逐行个人/销售数据发送给 LLM**；不执行公式 |

其他上限：最多 8 个文件；每个最多 8MB，合计最多 20MB；压缩档解包前检查总展开大小/条目数量；表格行数检查有明确扫描上限。超出限制拒绝或显式声明不完整，不能悄悄将“文件存在”理解为“完整读取”。

每个来源有稳定 `att_01`、`att_02` 等 ID，记录文件的 SHA-256、被发送的文本摘要 SHA-256、文件类型、来源标注和读取警告。`STUDY_PROTOCOL` 只表示上传者声称它是实验协议，**不表示随机化真的正确执行，也不等于 A4 或 A5 的认证**。

外部 API 需要用户自己配置 `CFM_ID_LLM_API_KEY`，并**同时**使用 `--allow-external --allow-document-sharing`。这样会发送业务描述、文档文本片段及表格结构摘要到指定的 Chat API；附件原始二进制与表格个人明细默认不发送。上传前应先确认是否有权分享这些业务材料。

## 4. 减少追问的规则

- 首先综合所有来源。协议已明确“恰好随机抽取 150 人”，则**不重复提问**“独立 Bernoulli 还是固定名额”。
- 不能因为尚未证明 A4 总体算子而询问公司业务员“你有 NODE_FULL_LAW 吗”；将其放在研究者审核项。
- 如果分配方式、treatment、outcome 或真正的业务目标仍不明确，最多选择两个普通问题。
- 两份文件对随机设计有**明确且相反**的说法，保守地标记研究者审查，不自动选择“最新文件为准”。该检测是基本规则，不是完备的冲突推理。
- CSV/XLSX 仅提供字段摘要，绝不据此断言网络 adjacency/具体配额/完整 treatment vector 已科学确认。

## 5. 实际运行

```bash
python -m pip install -e '.[documents]'

# 先只查看文件读取情况；无需密钥，也不调用 LLM
python -m cfm_id_llm.multisource_intake_cli --manifest examples/multisource/case.json --preview

# Mock：检查完整业务包能否进入同一份 DraftProblemSpec
python -m cfm_id_llm.multisource_intake_cli \
  --manifest examples/multisource/case.json \
  --provider mock --mock-response examples/multisource/mock_draft.json

# Mock JSON，保留完整引文以便人审；注意本地 JSON 会包含部分 PDF 原文
python -m cfm_id_llm.multisource_intake_cli \
  --manifest examples/multisource/case.json \
  --provider mock --mock-response examples/multisource/mock_draft.json \
  --format json --output demo_v07/multisource_mock_report.json

# 真正的模型调用（必须是经授权的材料，自备 API key）
export CFM_ID_LLM_API_KEY='YOUR_KEY'
python -m cfm_id_llm.multisource_intake_cli \
  --manifest examples/multisource/case.json \
  --provider openai-chat --model YOUR_JSON_CAPABLE_MODEL \
  --allow-external --allow-document-sharing \
  --format json --output /tmp/my_document_formulation.json
```

Manifest 里的附件 `path` 必须是相对于 manifest 所在目录的路径，不允许 `..` 上溯或符号链接越出目录。单独命令行 `--question` 加若干 `--attachment` 也可运行，附件默认来源类型是 `OTHER`。`--case-output` 可导出汇总的现有 `BusinessCase`，用于未来 Core Adapter。

## 6. Demo 的结论与限制

发布样例为**虚构**的 300 名销售员、恰好 150 名入组、8 周试验，并附协议 PDF、网络边表 CSV、销售记录 XLSX。

- Demo `FIXED_POLICY_VALUE` 只是业务目标的**规范化解释**，不是数学识别结论。
- PDF 中有“恰好随机抽取 150 人”的文字；Gateway 能引用这句话，但**不能证明试验实际执行满足 full-vector randomization**。
- 附件中有 CSV/XLSX 记录不等于拥有指定粒度的 population observable operator；A4 仍待严格理论判断。
- Excel 测试资料中故意加入一个敏感哨兵值；输入给 Mock/LLM 的字段摘要、输出报告与 HTML 都不包含这个值。
- PDF 图片与复杂布局、较大 XLSX、内容冲突等仍可能需要人工核查。
- Mock Fixture 是代码测试，不是 GPT 准确率，也不是联网业务演示。

## 7. 后续与最新 ID Library 的对接

继续沿用现有 `BusinessCase` / `DraftProblemSpec` 和未来 `CoreIdentificationPort`。当你提供最新 ID Library 时，我们只在适配层进行 `Draft → 经确认的 FormalTaskSpec` 转换，而不会让 LLM 自行给 A4/A5 授权。未经审核的草稿仍不得进入正式数学认证及 Estimation/Policy。
