# 原文摘录：Imbens & Angrist (1994) Condition 1–2 与 Theorem 1

> 这不是论文全文，只保留本案例核对所需的短摘录和公式。
>
> 版本：JSTOR 扫描版，*Econometrica* 62(2), March 1994, pp. 467–475；本地另有 NBER t0118 扫描 PDF。  
> 核对位置：pp. 468–470（Condition 1、Condition 2、Theorem 1）。

## 1. 潜在参与与工具变量

论文定义 \(Z_i\) 为工具变量，\(D_i(z)\) 为单位 \(i\) 在 \(Z_i=z\) 时会否参与的潜在指示变量。观察到的参与为：

\[
D_i=D_i(Z_i).
\]

## 2. Condition 1（Existence of instruments）

原文：

> Let \(Z\) be a random variable such that (i) for all \(w\in\mathcal{Z}\) the triple \((Y_i(0),Y_i(1),D_i(w))\) is jointly independent of \(Z_i\), and, (ii) \(P(w)=\mathbb{E}[D_i\mid Z_i=w]\) is a nontrivial function of \(w\).

要点：

- 工具变量与潜在结果、潜在参与独立；
- 工具变量必须实际影响参与概率；
- 随机分配 \(Z\) 不自动保证第 (i) 部分。

## 3. Condition 2（Monotonicity）

原文：

> For all \(z,w\in\mathcal{Z}\), either \(D_i(z)\ge D_i(w)\) for all \(i\), or \(D_i(z)\le D_i(w)\) for all \(i\).

直观上：工具变量不会让某些人反向改变参与状态。论文明确说这个条件本质上不可检验，必须按应用逐案论证。

## 4. Theorem 1

原文：

> If Conditions 1 and 2 hold, then we can identify the following average treatment effect:
>
> \[
> \alpha_{z,w}=\mathbb{E}[Y_i(1)-Y_i(0)\mid D_i(z)\ne D_i(w)]
> \]
>
> from the joint distribution of \(Y,D,Z\), for all \(z,w\) in the support of \(Z\) such that \(\mathbb{E}[Y_i\mid Z_i=z]\) and \(\mathbb{E}[Y_i\mid Z_i=w]\) are finite, and \(P(z)\ne P(w)\).

证明的关键一步：

\[
\mathbb{E}[Y_i\mid Z_i=z]-\mathbb{E}[Y_i\mid Z_i=w]
=
(P(z)-P(w))\,
\mathbb{E}[Y_i(1)-Y_i(0)\mid D_i(z)-D_i(w)=1].
\]

两边除以 \(P(z)-P(w)\)，得到 LATE 的矩表达式。

## 5. 二值工具变量的公式

当 \(Z\in\{0,1\}\)：

\[
\mathrm{LATE}
=
\frac{\mathbb{E}[Y\mid Z=1]-\mathbb{E}[Y\mid Z=0]}
{\mathbb{E}[D\mid Z=1]-\mathbb{E}[D\mid Z=0]}.
\]

分母是参与概率之差，必须非零且为正。

## 6. 论文的边界

论文明确区分：

- LATE：工具变量能诱导改变参与状态的那群人的平均效应；
- ATE：全体的平均效应。

仅有工具变量有效性（Condition 1）不足以识别 ATE，也不足以识别 LATE；单调性是额外条件。

## 7. 没核对的内容

- Theorem 2、Theorem 3 的完整证明；
- 第 4 节应用；
- 渐近方差与弱工具问题；
- 连续工具、多个工具、网络 IV 等扩展。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
