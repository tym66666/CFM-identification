# 有限样本记录（不能替代总体信息）

有限样本单独记录如下：

- 处理前特征：60 × 20 的合成特征矩阵；本公开案例不展开具体数值。
- 邻接矩阵：60 × 60，对应 `network_edges.csv` 的 120 条无向边。
- 处理：含 33 个 1 和 27 个 0；逐店处理向量未随本公开案例提供。
- 结果：仅以下 30 家门店有回访结果，按 `observed_indices` 顺序为：

```text
node-57, node-12, node-3, node-1, node-19, node-39, node-53, node-54,
node-47, node-41, node-31, node-37, node-9, node-36, node-50, node-7,
node-33, node-59, node-24, node-15, node-56, node-46, node-58, node-52,
node-32, node-22, node-44, node-51, node-45, node-42
```

- `outcomes_observed[j]` 对应原始行 `observed_indices[j]`，不得排序后丢失对应关系。
- 其余 30 家结果未提供，不插补。
- 回访名单独立随机确定；既有合成协议记录其与独立生成流一致。

## 重要边界

这 30 条回访记录是有限样本，不是 60 家门店的总体均值。即使表格看起来完整，也不能把样本均值升级为已知总体均值。

本案例的识别目标使用 `study_protocol.md` 声明的总体条件平均；具体结果数值不参与识别公式的推导。
