# 原文摘录与边界：Balke & Pearl (1997)

## 1. 本案例核对范围

- 题录、摘要/问题设定和项目文献卡。
- 未逐页核对全部闭式界、线性规划构造和 sharpness 证明。

## 2. 论文问题

二元工具 \(Z\)、二元处理 \(D\)、二元结果 \(Y\)，存在不完全遵从。目标不是 LATE，而是全体 ATE：

\[
\mathrm{ATE}=\mathbb{E}[Y(1)-Y(0)].
\]

仅靠 \(P(Y,D\mid Z)\) 通常不能点识别 ATE；论文给出 sharp bounds。

## 3. 与 LATE 的区别

- LATE：工具能诱导改变参与状态的那群人的平均效应；
- ATE：全体人的平均效应；
- LATE 的点识别不自动给出 ATE 的点识别；
- 不能把 LATE 公式直接当成 ATE。

## 4. 本案例

沿用 LIT-IV-01 的 200 人计数表，目标改为全体 ATE 的上下界。

这是合成数据，不是论文数据；本包不声称复现论文的闭式界。

## 5. 不支撑

- 不支撑当前软件已实现 IV/ATE bounds；
- 不支撑把 LATE 当 ATE；
- 不支撑把有限样本计数当作总体分布。

## 6. 阅读级别

`metadata_and_abstract_alignment`，不是 `full_text_verified`。
