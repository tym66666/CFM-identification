# 原文摘录：Hudgens & Halloran (2008) §3.3 与 §5.2

> 这不是论文全文，只保留本案例核对所需的短摘录和公式。
>
> 版本：PMC2600548 作者稿，*JASA* 103(482):832–842, 2008。  
> 核对位置：§2、§3.1、§3.3、§4.1、§5.2。

## 1. 组内干扰、组间无干扰

论文允许同一组内的个体之间存在干扰，但假定不同组之间没有干扰：

> “Implicit in this notation is the assumption that the potential outcomes for individuals in group \(i\) do not depend on treatment assignments of individuals in group \(i'\) for \(i'\ne i\). In other words, we assume no interference between individuals in different groups but allow for interference between individuals within the same group.”

这不是从图上没有组间边自动推出的；它是需要声明和审核的假设。

## 2. 两阶段随机化

第一阶段：把组分配到不同的个体处理策略 \(\phi\) 或 \(\psi\)。  
第二阶段：在组内按该策略随机抽取处理名单。

论文的疫苗示例（§5.2）使用：

- 5 个地理上分离的组；
- 3 个组分配到 \(\phi\)，2 个组分配到 \(\psi\)；
- \(\phi\) 组内 30% 接种，\(\psi\) 组内 50% 接种；
- 随访一年检测霍乱。

## 3. 个体平均潜在结果（§3.1）

\[
\bar Y_{ij}(z;\psi)
=
\sum_{\omega\in R_{n_i-1}}
Y_{ij}(z_{i(j)}=\omega,z_{ij}=z)
\Pr_\psi(Z_{i(j)}=\omega\mid Z_{ij}=z).
\]

含义：在策略 \(\psi\) 下，给定本人处理 \(z\)，对其余组内安排按设计分布平均。

## 4. 间接效应（§3.3）

\[
CE^I(\phi,\psi)
=
\bar Y(0;\phi)-\bar Y(0;\psi).
\]

含义：本人不处理时，比较策略 \(\phi\) 与 \(\psi\) 下的平均结果。疫苗场景中，就是“本人未接种，组内高覆盖率 vs 低覆盖率”的感染风险之差。

## 5. 估计量（§4.1）

在混合分配策略下，论文给出组内观测均值：

\[
\hat Y_i(z;\psi)
=
\frac{\sum_{j=1}^{n_i}Y_{ij}(Z_i)\mathbf{1}\{Z_{ij}=z\}}
{\sum_{j=1}^{n_i}\mathbf{1}\{Z_{ij}=z\}}.
\]

并给出总体直接、间接、总效应和总体效应的无偏估计量。注意：不同组之间不能直接配对，因此估计量依赖设计。

## 6. 本案例的对应关系

本案例保留：

- 两阶段名额方案；
- 组内均匀抽取；
- 本人未接种时，比较组内接种人数 3 vs 1；
- 全部 8 人等权。

本案例不保留：

- 论文的 5 组、30%/50% 覆盖率和 Table 2 感染数据；
- 论文的方差估计和渐近性质；
- 论文对霍乱疫苗的现实解释。

## 7. 没核对的内容

- Theorem 4–9 的方差估计与证明；
- 住房券示例；
- 附录；
- 出版版与作者稿的逐页差异。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
