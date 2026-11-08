# 原文摘录与边界：Manski (2013) 的均值顺序背景

> 这不是论文全文，只保留本案例核对所需的背景。
>
> 版本：Manski (2013), *Econometrics Journal* 16:S1–S23，作者公开稿。  
> 核对位置：§2.1、§3.1（pp. S8–S9）、§3.2（pp. S9–S10）。

## 1. 论文中的相关概念

- constant treatment response (CTR)：用 effective treatment 概括干扰；
- semi-monotone treatment response：对响应函数施加方向限制；
- reinforcing interactions / componentwise treatment order：对多个处理维度分别施加顺序。

论文的核心思想是：在部分识别中，额外的形状限制可以收窄识别集，但限制的适用范围必须说清楚。

## 2. 与本案例的区别

本案例使用的是**均值顺序**，不是论文的逐个响应函数单调性：

- 本店均值顺序：只约束 \(m_i(1,s)\ge m_i(0,s)\)；
- 同伴均值顺序：只约束邻居处理增加时本店均值不降低；
- 不声称每个个体的结果函数逐点单调；
- 不把均值顺序自动升级为论文的 semi-monotone response。

## 3. 本案例的有限模型

四家门店，完全图，原试点每轮恰好 2 家启用。

已知：

\[
m_i(1,0)=3/5,\qquad m_i(0,1)=2/5.
\]

采用本人和同伴均值顺序后：

\[
m_i(1,1)\ge 3/5,\qquad m_i(0,0)\le 2/5.
\]

四家等权的“全用减全不用”：

\[
\frac{1}{4}\sum_i\left[m_i(1,1)-m_i(0,0)\right].
\]

逐项下界为 \(3/5-2/5=1/5\)，逐项上界为 \(1-0=1\)。因此：

\[
[1/5,\,1].
\]

这是项目有限模型的推导，不是论文的数值例子。

## 4. 没核对的内容

- 论文全部证明与应用；
- 出版版与作者稿的逐页差异。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
