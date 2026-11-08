# Causal-IDFM 最简核心维护 P2 — 限时诊断与停重构决定

日期：2026-10-18。基线：`v2.9.2 Minimal Correct Core Stabilization + Maintenance P1`。

## 一、决策：不增加数学路线，不做 R3 全局重构

- 原 R1a 3 节点 Golden、原 R3 相同 p-standardized Target 三种 A4 表示验证，以及所有独立证书均应保持现有语义和快照。
- 对照的 R3 模块中，一些验证字段相似，但独立精确支持核对与不同 Target（p-standardized / shared-stratum adjusted / nodewise adjusted）属于**有意保留的复杂度**。
- 目前只能证明**一个特定小图和处理律**下的 FULL/FACTORIZED/ONE-COMPONENT MIXTURE 三种 A4 可以表达同一数学目标。它不是全域程序等价的证明。因此**没有数学与验收依据去合并 R3 solver / verifier**。
- 这轮源码差异应只涉及 CI、Golden 维护入口、旧 PFN smoke 诊断及新测试；`pfn_pipeline/`、`cfm_id_bridge/`、`cfm_id_llm/` 不应改动。

## 二、问题最小化与实际对照

- 旧的 PFN-smoke 偶发停在训练/验证附近，不能由退出不稳定就断言 Core 数学有错。
- 固定 `tests.test_pipeline_smoke.PipelineSmokeTest.test_migrated_checkpoint_evaluation`、同一种子、同一 checkpoint 训练参数；每次使用**新进程**。
- 两种线程环境：`controlled` 在子进程设置 `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=1`；`inherited` 不覆盖现有调用环境的线程配置。对照试验应在清掉父进程相应变量后进行。
- 运行了两种环境各 2 次 checkpoint smoke；两组均 PASS，不足以确认线程数量是历史停顿原因。
- 完整 9 项 smoke 的单次有界子进程也 PASS。**没有定位偶发根因**，更不能声称已经修复训练器。

## 三、诊断代码的新增正确性合同

`python -B -m scripts.diagnose_legacy_pfn_smoke --test checkpoint|full --thread-mode controlled|inherited --repetitions 1..10 --timeout SECONDS --stack-after SECONDS --report PATH`

1. 每次 repetition 必须创建**新的**子进程；不同 repetition 的日志分隔记录。
2. 只靠 `returncode == 0` **不能**判 PASS；还必须观察请求的 unittest 数量、`OK` 终态、`train_model` 和 `evaluate_checkpoint` 的 BEGIN/END 事件。
3. 任意 repetition 超时 → 聚合状态 `TIMEOUT`、返回非零 124；任意失败/缺标记 → `FAIL`、返回非零 1。不得隐式跳过失败。
4. 自动保存机器 JSON 和完整 stdout/stderr 合并日志，失败可从 Python faulthandler 堆栈定位在哪个阶段。
5. `thread-mode` 只是诊断环境对照，不是科学假设，也不是已证明的故障修复。

### 开发命令

```bash
# 核心最小测试，通常在一秒内完成
bash scripts/run_minimal_stabilization_checks.sh fast
bash scripts/run_minimal_stabilization_checks.sh r3-ablate

# 受控诊断：每组2个独立子进程，约20秒完成（环境相关）
bash scripts/run_minimal_stabilization_checks.sh pfn-ablate /tmp/cfm_id_thread_ablation

# 单次完整旧 smoke，强制明确 9/9 与 train/eval 阶段完成
python -B -m scripts.diagnose_legacy_pfn_smoke --test full --timeout 360 --stack-after 90 --report /tmp/pfn_full.json

# 全部数学 Core 和 A0，PFN 单独验收
bash scripts/run_minimal_stabilization_checks.sh core-split
bash scripts/run_minimal_stabilization_checks.sh gateway
```

## 四、CI 可复现性

- 原 CI 中容易长时间无输出的 `timeout 900 bash ... pfn-smoke` 已替换成上述**有终态约束**的有界诊断命令。
- 无论 PASS/FAIL，CI 均尝试上传 `/tmp/cfm_id_legacy_pfn_full.json` 和 `.log`。这只能提高可调查性，不保证远端 CI 一定通过。
- Python 3.11 远端 GitHub Actions 当前**没有在这次会话内得到通过证据**。本地 `yaml.safe_load` 只能确认语法。

## 五、下一轮门槛

只有同时具备稳定复现的故障、最小改动、独立支持/证书正反例、固定快照不变及完整回归证据，才动训练或数学 Core。如果多次对照不能重现卡顿，本轮保持**不修一个未经证明的猜测**。后续如需排查系统环境，优先记录机器线程配置、BLAS 版本、PyTorch 版本、共享资源负载及失败时进程堆栈，而非通过增加训练轮次、改模型结构规避。
