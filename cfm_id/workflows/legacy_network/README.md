# 旧网络协议的兼容运行层

这是 `business_entry`、`intent_submission` 原来间接使用的网络读取和审核实现。它不建立新的业务入口，也不是给新能力复制使用的模板。新应用仍走 `business_intake → business_dispatch → business_case`。

## 为什么保留多个小模块

历史协议逐层改变字段和请求，旧记录的请求摘要、审核绑定及研究会话仍依赖这些组合。本次按实际使用的定义抽取，保留函数体与请求内容；没有把历史版本拼成一份新 Prompt。这里的模块数不代表业务类别或数学路线数。

| 模块组 | 职责 |
|---|---|
| `question_intent*`、`frozen_reading*`、`condition_evidence*` | 旧意图/条件分离协议、字段检查和引用检查 |
| `core_peers_staged*`、`staged_d1_d2`、`d1_staged` | 绑定先前读取的研究候选，保持当前目标独立；绑定不是科学许可 |
| `d1_submission`、`d2_submission`、`core_peers_base`、`arm_submission` | 检查显式审核和原生目标绑定，然后调用现有 Core 并重放证书 |
| `materials*`、`remaining_transfer`、`evidence_entries` | 既有材料字段、来源选择、投影及适配组合 |
| `target_model`、`review_context` | 旧目标类型、阻断条件与已有审核上下文类型 |
| `group_adapter` | 保留的合成分配适配：构造原生输入，不实现新求解器 |
| `result_view`、`submission` | 原结果表达和待审核预览；这里不包含库外候选续接 |

`evaluation` 旧模块继续重新导出这些同一函数和类型。默认 NBIB 选题/材料加载、旧数值实验、合成审核构造、候选研究调用和独立网页生成保留在实验或示例侧，不随正常业务提交导入。

“运行实现”不代表生产许可。这些适配器保留原有显式合成研究限制；只有真实提供、逐项绑定的审核才能授权执行。不能从模块名、源码中存在编译函数或测试夹具推定科学条件成立。

## 修改规则

修复兼容行为应先冻结受影响协议的请求、审核与证书，保留旧公开导入。新共同入口能力在专门业务适配器及 `capability_registry` 中维护；不要继续把新协议层叠到此目录。

边界验收在 `tests_gateway/test_legacy_network_runtime_boundary.py`：先在测试进程构造显式合成审核，再在独立进程禁止导入 `evaluation`、`examples`、`student_work`，实际检查待审核、缺项、拒绝及成功重放。测试中的 pickle 只传递本地生成的可信测试对象，产品接口不接收这种文件。
