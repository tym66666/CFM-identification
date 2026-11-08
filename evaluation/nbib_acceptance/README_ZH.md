# NBIB v0.26 验收目录

这里登记 **37 份输入**，分三组报告，不能合并为“原始 21 题通过率”。

| 分组 | 输入数 | 用途 |
| --- | ---: | --- |
| `NBIB_RAW` | 21 | 保留原始业务材料，逐题检查理解质量、歧义和缺失信息；共 29 个业务问题 |
| `NBIB_CONTROLLED_REVISION` | 3 | NBIB003、020、021 的明确版本，检验具体目标能否进入识别 |
| `SYNTHETIC_REGRESSION` | 13 | 两个新合成业务场景的回归用例，覆盖识别、缺失条件、含糊目标及支持外政策 |

13 道合成题应该加入，因为它们能持续检查此前修复的问题。但它们已经用于调试 Prompt，所以全部标记为 `DEVELOPMENT_REGRESSION`，**没有盲测或未见数据的含义**。其中有两个业务场景及多个目标/缺失条件变体，不是 13 个独立行业场景。

## 输入仍然是业务材料

`public/` 保存自然语言问题、试验说明、名册、网络边及政策清单。业务提交者不需要填写 Core 的数学 JSON。程序只把公开表格确定性加载为结构，LLM 仍负责阅读业务目标；模型结果通过契约、目标语义、科学准入和 Core 检查后，才可能产生识别证书。

例如 NBIB003 的明确版本是：

> 只评价名册中编号为unit_037的那家门店。  
> 如果这家店自己不发券、相邻门店至少一家发券，它的平均营业额是多少？  
> 其余门店的安排仍按原商圈抽签规则，在满足这些条件的方案中平均。

这些说明比原始口语问题更精确，但仍是人能阅读的业务语言。它们明确评价对象、状态及其余安排；没有把识别结论写进问题。

三个明确版本均与原题分开。特别是 `NBIB-020-whole-regions` 把“每区半数仓库上线”改为“两个区域整体上线”，并增加区域抽签独立的公开声明；**它改变了政策目标和已知设计条件，不能声称只是润色原句，更不能用其成功替代原题成功。**

## 评分与证据边界

- 原始题：按 [21 题验收表](RAW_ACCEPTANCE_ZH.md) 检查业务目标及缺失条件。合法 JSON、触发科学准入拦截，都不能单独算语义正确。
- 明确版本及合成题：检查设计、全部目标坐标、出处、预期识别状态；每个 POINT 还必须通过独立证书重放。
- 每次请求保留失败、耗时、输入 Prompt 摘要和固定运行配置摘要。不同版本分开，重复尝试不取“最好一次”。
- `research_only/` 是研究侧参考与合成科学许可。模型输入加载器不能读取这里的参考答案或许可包。研究评分在模型返回之后进行。
- 当前 `v0243` 业务材料适配器主要覆盖 D3/D4 的已实现分支；本目录登记 21 道原题，并不表示该适配器已覆盖所有设计。原始 A0 输入可用 `original_a0_input` 加载。
- 合成许可只用于研究回归，不表示真实企业已经接受 A4/A5；`production_admission` 保持 false。观察数据文件不是总体律证书。
- 原始材料的数据字典中已有部分假设/机制提示，因此原始数据也不宜宣称为完全盲测。

## 本地离线复核

在项目根目录执行（无需 Key，不发 API 请求）：

```powershell
python -B -m evaluation.nbib_acceptance --replay-references --output nbib_v026_validation.json
python -B -m unittest tests_gateway.test_nbib_acceptance -v
```

第一条检查所有公开文件摘要，并重放 16 份参考输入。预期结果为：21 原题、3 明确版本、13 合成回归输入；16 份参考输入重放，其中 11 个 POINT 证书重放。**这不是 16 次真实 LLM 测试。**

编程入口：

```python
from evaluation.nbib_acceptance import (
    registry, original_a0_input, material_input, material_request, summarize_attempts,
)

original = original_a0_input("NBIB-003")
bundle = material_input("NBIB-003-single-store")
system, user = material_request("NBIB-003-single-store")
```

`material_request` 对字典键顺序作稳定序列化；不改变文字、列表顺序、编号、概率或目标。相同材料不会因为 Python 字典插入顺序不同而得到不同请求。

传给 `summarize_attempts` 的 `query_count` 指模型保留的业务问题数，不能用 Core 实际执行数替代。缺少设计条件可能在 Core 执行前整体返回 `NEEDS_INPUT`；此时模型仍应保留原问题。`semantic_passed` 必须来自目标语义检查，`expected_decision_passed` 必须来自独立的预期状态检查；不能从“接口未报错”推导这两个值。

验收证据补丁 v0.28：`query_count` 必须为整数，布尔值和浮点数不算有效计数。明确版本和合成题必须显式记录布尔型 `point_present`；缺失、null 或其他类型返回 `IDENTIFICATION_EVIDENCE_NOT_SCORED`，不能跳过证书检查而算 PASS。存在 POINT 时，`point_replay_passed` 必须严格为 true；显式确认没有 POINT 的预期结果仍按原规则验收。原始题只报告业务语义结果。

可用 `python -B -m unittest tests_gateway.test_nbib_acceptance tests_gateway.test_acceptance_evidence -v` 复核此边界。旧实验的源文件摘要和结果继续保留；包含旧评分器摘要的冻结计划不能直接在修改后的源码上续跑，应建立新配置。

## 本轮真实调用记录与后续

具体调用证据在交接包的 `local_results/nbib_acceptance_20261020*` 下，仓库中的参考文件不冒充线上结果。

本轮先比较同一 Key、同一 NBIB020 请求体的 Gateway 与最小标准库客户端。两条均在 300 秒截止；均已收到 HTTP 200 和部分内容，但未完成 JSON。这个结果说明仅绕开 Gateway 的活动流解析未消除迟缓，单次对照仍不能判定服务端、网络或全部客户端层的根因。

之后冻结三个明确版本的小批验收，遇到首个传输、契约或语义失败即停止，不自动重试。原题的完整同版本语义验收仍须单独进行，不能拿历史版本或明确版本替代。

后续顺序：先解决实际业务响应的持续迟缓，再完成这三个明确版本；随后按设计族补齐原题逐题理解检查。只有开发回归稳定后，再新建未用于调试的自然语言留出题，并在首次调用前冻结答案。
