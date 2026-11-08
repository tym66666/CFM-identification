# 原文摘录：Aronow & Samii (2017) §8 与相关条件

> 这不是论文全文，只保留本案例核对所需的短摘录和公式。引用请回到原文。
>
> 版本：arXiv:1305.6156v3，2017-07-14。  
> 位置：§3、§4、§8；式 (16) 在 arXiv PDF 第 20 页，Corollary 8.1 在第 21 页。

## 1. 设计与暴露映射（§3）

论文把分析框架分成三个组件：

1. 实验设计：处理向量 \(Z\) 在支持集 \(\Omega\) 上的已知概率 \(p_z\)；
2. 暴露映射：\(D_i=f(Z,\theta_i)\)，把处理安排和单位特征映射为暴露；
3. 目标：用实验回答的因果量。

暴露概率为：

\[
\pi_i(d_k)
=
\sum_{z\in\Omega}p_z\mathbf{1}\{f(z,\theta_i)=d_k\}.
\]

## 2. 两个核心条件（§4）

### Condition 1（Properly specified exposure mapping）

如果两个处理安排 \(z,z'\) 对单位 \(i\) 给出相同暴露，即

\[
f(z,\theta_i)=f(z',\theta_i),
\]

则单位 \(i\) 的随机化潜在结果相同：

\[
y_i^r(z)=y_i^r(z').
\]

### Condition 2（Consistent potential outcomes）

观察结果等于实际暴露对应的潜在结果：

\[
Y_i=\sum_{k=1}^{K}\mathbf{1}\{D_i=d_k\}\,y_i(d_k).
\]

## 3. 平均潜在结果与效应（§4）

\[
\mu(d_k)=\frac{1}{N}\sum_{i=1}^{N}y_i(d_k),
\]

\[
\tau(d_k,d_l)
=
\frac{1}{N}\sum_{i=1}^{N}
\left[y_i(d_k)-y_i(d_l)\right].
\]

## 4. 错分暴露下的设计加权目标（§8）

论文在 §8 讨论暴露映射不充分（misspecification）时的解释。原文的 Condition 7 允许：

\[
f(z,\theta_i)=f(z',\theta_i)
\quad\text{但}\quad
y_i^r(z)\ne y_i^r(z').
\]

在这个较弱条件下，式 (16) 给出：

\[
\mathbb{E}\left[\widehat{y_{HT}^{T}}(d_k)\right]
=
\sum_{i=1}^{N}
\sum_{z:\,f(z,\theta_i)=d_k}
w_{i,z}\,y_i^r(z),
\qquad
w_{i,z}=\frac{p_z}{\pi_i(d_k)}.
\]

Corollary 8.1 给出两个暴露条件之差：

\[
\mathbb{E}\left[\widehat{\tau_{HT}}(d_k,d_l)\right]
=
\frac{1}{N}
\sum_{i=1}^{N}
\left[
\sum_{z:\,f(z,\theta_i)=d_k} w_{i,z} y_i^r(z)
-
\sum_{z':\,f(z',\theta_i)=d_l} w_{i,z'} y_i^r(z')
\right].
\]

原文紧接着说明：

> Under Condition 7, the estimator ... is unbiased for the population mean of what Hudgens and Halloran (2008, p. 834) refer to as the "individual average potential outcome" given \(D_i=d_k\).

## 5. 对本案例的含义

N60 的三个目标采用式 (16)/Corollary 8.1 的设计加权形式：

\[
\bar\mu_i^q(d)
=
\sum_{z:\,f(z,\theta_i)=d}
\frac{q(z)}{\Pr_q(D_i=d)}\,\mu_i(z).
\]

因此：

- 它保留原设计 \(q\) 下“其余门店安排”的条件平均；
- 它不是把其他门店全部固定为某个完整政策的政策价值；
- 在没有额外暴露充分性时，不能把它改称为与设计无关的结构参数；
- 目标需要每个暴露条件的正支持 \(\Pr_q(D_i=d)>0\)。

## 6. 没有核对的内容

- §5–§7 的方差估计与渐近性质；
- §9–§10 的模拟和实地实验；
- 附录 A 的全部证明；
- 出版版页码与 arXiv 版的逐页差异。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
