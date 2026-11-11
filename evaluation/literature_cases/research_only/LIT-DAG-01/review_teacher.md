# LIT-DAG-01 老师复核表

状态：**PENDING_TEACHER**

## 1. 来源核对

- [ ] 论文信息正确：Pearl (1995), *Biometrika* 82(4):669–688，DOI 10.1093/biomet/82.4.669。
- [ ] 核对版本明确：作者公开稿 `R218-B.pdf`。
- [ ] Definition 3、Theorem 1、式 (6) 的位置和抄录正确。
- [ ] 没有把 §3.2 前门、§4 do-calculus 或一般图 ID 写成已核验。
- [ ] 区分了原文事实、自拟合成场景和人工整理。

## 2. 业务输入核对

- [ ] 变量是资深员工、参加培训、业绩达标，三者都有观测。
- [ ] 图是 `资深员工 → 参加培训`、`资深员工 → 业绩达标`、`参加培训 → 业绩达标`。
- [ ] 目标明确是 `p(业绩达标 | do(参加培训=x))`。
- [ ] 公开目录没有公式、参考答案或预期状态。
- [ ] 总体信息是完整符号总体分布，不是有限样本。
- [ ] 正性声明明确。

## 3. 参考答案核对

- [ ] 论文公式与式 (6) 一致：
  \[
  p(y\mid do(x))=\sum_z p(y\mid x,z)p(z).
  \]
- [ ] 调整集合 `["资深员工"]` 满足后门条件：
  - 不是处理的后代；
  - 阻断 `参加培训 ← 资深员工 → 业绩达标`。
- [ ] 公式按 `p(资深员工)` 加权，不是按治疗组分布加权。
- [ ] 软件预期与当前 DAG 后门适配器一致。

## 4. 两个改动版核对

- [ ] 缺条件版确实删除了图完整性/所有共同原因声明。
- [ ] 缺条件版预期 `NEEDS_INPUT`，不是“证明不可识别”。
- [ ] 目标变化版把调整变量改成治疗后的“资深资格”。
- [ ] 目标变化版预期 `UNSUPPORTED`，原因是 `ADJUSTMENT_CONTAINS_TREATMENT_DESCENDANT`。
- [ ] 没有把控制中介后的结果当成总效应。

## 5. 运行记录核对

- [ ] `structured_runs/original/result.json` 是 POINT 且重放通过。
- [ ] `structured_runs/missing_condition/result.json` 是 NEEDS_INPUT。
- [ ] `structured_runs/changed_target/result.json` 是 UNSUPPORTED。
- [ ] `api_calls=0`，没有伪造 LLM 结果。
- [ ] 没有把合成图当作现实医学/管理事实。

## 6. 复核结论

- 复核人：
- 日期：
- 结论：`PENDING` / `ACCEPTED` / `NEEDS_REVISION`
- 需要修改的地方：

## 7. 备注

本案例是 DAG 后门模板。复核通过前不能标成“已验收”。
