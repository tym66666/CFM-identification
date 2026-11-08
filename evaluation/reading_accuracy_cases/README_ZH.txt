业务读取补充回归集：四个新业务场景和两个子集目标对照。

public 中为合成业务文字、CSV、目标说明和经过程序读取的 public_bundle.json；没有规范化标准答案或科学许可。
references 中为离线评分标签，禁止放入模型请求。原 NBIB 21 题及其历史结果未修改。

准备请求：读取 public/<案例>/public_bundle.json，调用 cfm_id.business_entry.prepare_request(bundle, "D1_EFFECTS")。
收到模型回答后调用 business_entry.preview；本集未提供科学审批包，正例应为 REVIEW_REQUIRED，缺项或明确相关的情况为 NEEDS_INPUT。
public_bundle.json 是此次验证的准确输入。CSV/Markdown 为材料来源；如重新读取或编辑文字，应生成新 bundle 并重新审核，不能沿用旧证书。

评分必须同时核对业务字段、evaluation.reading_target_audit 的完整目标坐标，以及已标注的来源。
evaluation.reading_semantics.semantic_payload 仅允许在当前固定名册上把“全体”和“逐个列全名册”等价比较；子集、人群变化、权重和其他事实不因此等价。
不得仅因最终状态相同而判对，也不得只删去 source 字段后比较：这可能漏掉已经明确的其余安排。
这些工具只用于评分，不改写模型回答，不批准 A4/A5，也不替代识别证明。

四个基础场景已经参加过开发验收；后续只能称回归集，不能再当作未见的新题报告泛化准确率。

完整识别链路补充验收（2026-10-22）：
references/SCIENTIFIC_PROTOCOLS.json 为三个正例另行声明的合成科学协议，不属于 public 输入，不会被 prepare_request 发送给模型。
recorded/ 是可选历史档案，原开发目录中保存两个模型各六条真实历史回答及出处哈希。本源码包不分发这些回答；缺少档案时，相应历史重放测试明确跳过，不能计作通过。
仅在自行恢复完整历史档案后，才可在源码根目录运行：
python -X utf8 -B -m evaluation.reading_science_acceptance --output local_science_acceptance_run
输出目录必须不存在。该命令离线复现正例审核→POINT→证书重放，并检查负例停止、完整目标、来源和独立枚举。
合成科学审核仅用于这三个冻结案例；不能用于批准未知企业数据或其他模型输出。完整说明见源码根目录 SCIENTIFIC_CHAIN_ACCEPTANCE_ZH.txt。
