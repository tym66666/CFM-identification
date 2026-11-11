# 任务 2 push 前审计

日期：2026-11-11

## 1. 分支与工作区

- 分支：`task2-literature-cases`
- 工作区：干净（除本文件更新）
- 老师 main：`992fdf9`，本地不需要 rebase
- 本地领先：15 个 commit

## 2. 校验与测试

```text
validate_cases.py: errors: []
tests_gateway.test_literature_cases: 13 passed
check_framework quick: 110 passed
check_framework chain: 1086 passed
```

- quick 输出：`outputs/final_quick_20261111/SUMMARY.json`
- chain 输出：`outputs/final_chain_20261111/SUMMARY.json`
- `outputs/` 已被 `.gitignore` 忽略，不进入 PR。

## 3. 体积

- 相对老师 main 的变更：376 个路径
- 变更总大小：约 0.88 MB
- 最大单文件：`LIT-NET-01/structured_runs/original/result.json`，约 190 KB
- `evaluation/literature_cases` 约 1.9 MB
- `literature_support/cases` 约 204 KB

已删除：

- 完整 plan/business/fact/source catalog；
- 重复的 `source_*.md`；
- 历史 saved run 的中间字段。

## 4. 敏感信息与禁止文件

- 没有 `sk-...`、API Key、Token、密码类字符串；
- 没有 `.venv`、`outputs`、`local_results`、`__pycache__` 被跟踪；
- 没有提交论文 PDF；
- 没有提交 `TASK2_任务说明.md` 个人说明；
- public 目录没有参考答案、目标指纹、证书。

## 5. 新增评测底座

- `benchmark/cases.jsonl`：36 条公开输入；
- `research_only/benchmark/references.jsonl`：36 条参考索引；
- `schema.json`；
- `export_benchmark.py` / `score_benchmark.py`；
- 测试检查：公开 JSONL 不含 `expected_status`，参考答案隔离，holdout 标记一致。

## 6. 剩余风险

- 12 个案例仍为 `PENDING_TEACHER`；
- 4 个 holdout 是 development holdout，不是仓库历史盲测；
- `LIT-NET-07` 改动版作为 holdout 未运行；
- 全仓库 full 套件和安装/发布验收未跑；
- 真实 LLM API 评测未跑，属于任务 6 / 后续统一评测；
- CI 首次失败原因已定位：`evaluation/framework_acceptance.json` 引用了上游已改名的测试 `test_other_readers_do_not_silently_drop_explicit_conditions`；已改为 `test_single_policy_reader_preserves_explicit_conditions_for_native_review`。full pytest 本身为 `3009 passed, 133 subtests passed`。

## 7. push 前结论

代码、材料、测试和体积审计通过。  
外部阻塞：需要用户 Fork 老师仓库并开启 VPN；当前直接 push 老师仓库没有权限，默认 GitHub 网络也不通。
