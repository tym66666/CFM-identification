# 显式请求参数与完整响应检查

`OpenAICompatibleChatProvider` 支持两个互斥的输出预算参数：

- `max_tokens`：DeepSeek 官方 Chat Completions 文档采用的名称。
- `max_completion_tokens`：保留已有兼容接口的参数名称。

调用者必须选择服务支持的名称，不能同时设置。程序不根据模型名猜测，也不会在失败后自动换参数重试。两者都不设置时，保留原有请求行为。

官方参考：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/)。
学校代理的参数支持以实际测试为准；官方接口行为不能直接当成学校代理的保证。

## CLI

A0、自然语言输入入口和 NBIB 评测入口共享以下选项：

```text
--max-tokens 2048
--require-finish-reason
```

`--max-tokens` 与 `--max-completion-tokens` 互斥。`--require-finish-reason` 额外要求非流式响应必须明确返回 `finish_reason=stop`。缺少标记、`length` 截断或其他非正常结束均不通过。

流式响应本来就必须具备正常结束原因和 `[DONE]` 标记，该要求保持不变。收到可解析的半成品或完整 JSON 字符串，并不能绕过正常结束检查。

原非流式兼容默认值保留；需要严格验收时显式设置 `--require-finish-reason`。输出上限只是服务端生成预算，不是请求耗时保证。

## 超时与诊断

`--timeout` 是 socket 操作超时，`--max-stream-seconds` 在流读取边界检查。它们不等于精确的进程总截止；研究评测使用独立父进程在总截止时终止请求子进程并保留次数记录。

诊断只增加返回模型名（有字符集和长度约束）、token 用量、思考内容字符数和首次思考内容时间。Provider 不保存思考文本或 HTTP 头部。返回模型名只是服务的自报字段，不证明底层权重版本。

默认 Provider 使用系统代理设置。本次诊断发现旧实验 runner 显式禁用了代理；新的对照 runner 分别登记直连与系统代理路径。未修改用户的系统代理配置，也没有配置自动切换或失败回退。

这些参数及诊断只影响模型请求与完整性检查，不接受科学假设，不替代 Identification Core，不触发 Estimation/Policy。
