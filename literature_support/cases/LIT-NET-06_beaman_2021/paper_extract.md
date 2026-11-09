# 原文摘录与边界：Beaman et al. (2021)

## 1. 本案例实际用到的原文位置

- 论文题录与项目 demo 的文献对照说明：示范农户培训、网络传播、技术采用。
- 没有逐页核对论文的扩散模型、最优种子算法和实证表。

## 2. 案例目标

四户网络：

```text
甲 — 乙 — 丙 — 丁
```

未来随机政策：

- 方案 A：培训甲和丙，概率 1/2；
- 方案 B：培训乙和丁，概率 1/2。

目标：

\[
\frac{1}{4}\sum_{i\in\{甲,乙,丙,丁\}}
\left[
\frac{1}{2}\bar\mu_i(A)+\frac{1}{2}\bar\mu_i(B)
\right].
\]

这是有限随机政策均值，不是“最优选人策略”。

## 3. 论文不支撑

- 不支撑四户合成数据是论文数据；
- 不支撑把 1/2、1/2 当作论文最优政策；
- 不支撑把有限政策均值当作完整扩散模型。

## 3.5 实际摘录

Abstract：

> “By combining social network data and a field experiment in 200 villages in Malawi, we find that targeting central farmers is important to spur the diffusion process... a diffusion process governed by complex contagion.”

Introduction：

> “we implement a field experiment in which we choose entry points of information (seeds) into a social network and introduce a productive new agricultural technology via those seeds across 200 villages...”

> “The experiment was implemented in 200 villages, with 50 villages in each of the four treatment groups.”

本案例只借用“示范农户培训 + 网络传播 + 名单/政策比较”的业务背景，不复制 200 村庄实验、复杂传染模型或最优种子算法。

## 4. 阅读级别

`selected_full_text_sections`。已核对作者稿 `BBMM_Jan2021.pdf` 的 Abstract 和 Introduction 中 200 个村庄、seed farmers、网络中心性相关段落；完整实证表和结构模型未逐页核验。
