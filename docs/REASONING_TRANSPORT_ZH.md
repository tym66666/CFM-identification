# 数学候选的流式观测与等待上限

本版本只新增可选 Provider，不改变 Identification Core、A4/A5 许可或候选验证规则。业务接线沿用 `evaluation.business_candidate_constraints`；主 CLI 的默认 Provider 和超时未被全局替换。

## 配置

`cfm_id_llm.providers.reasoning_stream.ReasoningStreamProviderV036` 接受：

- `thinking="enabled"` 或 `"disabled"`，必须显式区分；
- `reasoning_effort="high"`，仅开启思考时发送；
- `max_tokens=16384`，使用一个输出 token 参数；
- `connect_seconds=30`、`read_seconds=900`、`total_seconds=900`；
- `before_send(request)`，可在发出请求前校验冻结请求、预扣次数并保存无认证头的请求体；
- 保留原 JSON/SSE 严格验证；不补全 JSON，不截取字段，不自动重试，不跟随重定向。

`connect_seconds` 用于建立 TCP/TLS（包括适用时的代理隧道）；完成后切换 socket 读取超时。
DNS 和阻塞读取无法由解析循环及时取消，所以 **total_seconds 不是独立的硬取消保证**，必须在父进程中使用墙钟时限。
本地实验的 `run_one.py` 使用 900 秒父进程上限，终止后保留已预扣次数、Core 结果及最后进度。

## 能观察什么

`progress()` 仅返回允许的状态、时间、计数：

- 连接完成、响应头、第一条响应体行；
- 首个非空思考字段、首个最终回答字段；
- 思考字符数、最终回答字符数、SSE 事件数、最后响应体行时间；
- 返回模型标签、结束原因和可用的 token 用量。

第一条响应体行可以是心跳，不等于首个内容 token；字符数也不等于 token 数。
读取到非空 `reasoning_content` 是接口确实返回思考字段的证据，不是对后端内部实现的证明。
不记录或显示思考文本、认证头、密钥或密钥散列。响应体中的最终候选 JSON 可按原有脱敏规则保存。

## 如何解释失败

- 连接前失败：先用不携带认证的 DNS/TCP 检查区分执行环境限制。
- 连接很快，输出持续很慢：已知不是一直停在建连阶段；仍无法仅凭客户端判断服务端计算、转发节流与网络传输各占多少。
- 总时限耗尽：没有完整答案可评价，不能记为数学错误。
- `finish_reason=length`：输出被截断，即使当前内容能解析成 JSON，也不能接收为完整候选。
- 格式与许可检查通过：仍不等于数学证明通过。

## 2026-10-21 冻结实验

同一道 G32-08，沿用先前真实业务阅读，数学目标、图、设计、A4/A5 与 v0.35.3 提示词不变。没有重新调用规范化模型。

原计划最多两次开启/关闭思考对照。第一笔预扣请求在受限执行环境下连接前失败；无认证网络检查确认可联网环境能连接，因此剩余一次用于显式开启思考的受控请求。关闭思考的本轮对照取消。两笔预扣都计入额度。

结果文件位于 `LOCAL_EVIDENCE_NOT_DISTRIBUTED`，最终结果以该目录报告和请求账本为准。原失败目录保留。没有将离线两世界审查构造发给模型。

## 离线验证

新增测试文件 `tests_gateway/test_reasoning_stream.py` 覆盖请求参数、超时切换、思考文本不落盘、截断与未完整结束的拒收、发送前预算拦截及禁止重复请求。另有本地父进程超时记录测试。

官方参数参考（学校转发是否支持仍以实际响应为准）：

- https://api-docs.deepseek.com/guides/thinking_mode/
- https://api-docs.deepseek.com/api/create-chat-completion/

