# 历史兼容示例

这里用于复现旧接口，不是新同学的默认开发模板。新的入门示例是 [student_handoff.py](../student_handoff.py)。

- `configs/compatibility_default.json`：保持 `ReadingConfig()` 的历史默认值。
- `configs/previous_research.json`：旧研究组合，不是学生推荐配置。
- `business_extension/`：原 `student_work/business_extension/`，含两份离线回放所需的真实模型输出。保留原答案；合成审核不代表真实企业许可。

当前推荐配置唯一位于 [cfm_id/configuration/reading.json](../../cfm_id/configuration/reading.json)。协议内部标识保留，不按数字大小挑配置。
