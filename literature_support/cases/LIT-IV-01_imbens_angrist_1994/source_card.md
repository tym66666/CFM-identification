# LIT-IV-01 来源卡：Imbens & Angrist (1994)

## 1. 论文基本信息

- 作者：Guido W. Imbens, Joshua D. Angrist
- 年份：1994
- 题名：*Identification and Estimation of Local Average Treatment Effects*
- 发表：*Econometrica*, 62(2), 467–475
- DOI：10.2307/2951620
- 本卡核对版本：JSTOR 扫描版（Econometrica 62(2), March 1994, pp. 467–475）

## 2. 我实际读到的位置

阅读级别：`selected_full_text_sections`。不是全文核验。

- 第 468–469 页：工具变量、潜在参与 \(D_i(z)\)、Condition 1。
- 第 469 页：Condition 2（Monotonicity）。
- 第 470 页：Theorem 1 及其证明；LATE 的识别公式。
- 第 470 页起：IV 估计量与加权平均 LATE 的讨论（只读了开头）。

未核对：

- Theorem 2、Theorem 3 的完整证明；
- 第 4 节的实证例子；
- 渐近方差和后续估计细节；
- 出版版与扫描版的逐页差异。

## 3. 论文问什么

论文问：

> 在二元工具变量 \(Z\)、二元参与 \(D\)、结果 \(Y\) 的设置下，仅凭工具变量有效（Condition 1）能否识别一个有意义的平均处理效应？如果不能，还需要什么条件？

论文的答案：

- 仅 Condition 1 不够；
- 加上单调性 Condition 2 后，可以识别**遵从者**的平均处理效应，即 LATE；
- LATE 不等于全体 ATE。

## 4. 论文给出的公式

对工具变量的两个取值 \(z,w\)，令：

\[
P(z)=\mathbb{E}[D_i\mid Z_i=z].
\]

在 Condition 1 和 Condition 2 下，Theorem 1 给出：

\[
\alpha_{z,w}
=
\mathbb{E}[Y_i(1)-Y_i(0)\mid D_i(z)\ne D_i(w)]
=
\frac{\mathbb{E}[Y_i\mid Z_i=z]-\mathbb{E}[Y_i\mid Z_i=w]}
{\mathbb{E}[D_i\mid Z_i=z]-\mathbb{E}[D_i\mid Z_i=w]}.
\]

二值工具变量 \(Z\in\{0,1\}\) 时：

\[
\mathrm{LATE}
=
\frac{\mathbb{E}[Y\mid Z=1]-\mathbb{E}[Y\mid Z=0]}
{\mathbb{E}[D\mid Z=1]-\mathbb{E}[D\mid Z=0]}.
\]

分母必须非零，且遵从者比例为正。

## 5. 两个条件

### Condition 1（Existence of instruments）

- 对每个 \(w\)，\((Y_i(0),Y_i(1),D_i(w))\) 与 \(Z_i\) 联合独立；
- \(P(w)=\mathbb{E}[D_i\mid Z_i=w]\) 是 \(w\) 的非平凡函数。

### Condition 2（Monotonicity）

对任意 \(z,w\)，要么对所有 \(i\) 有 \(D_i(z)\ge D_i(w)\)，要么对所有 \(i\) 有 \(D_i(z)\le D_i(w)\)。

直观上：工具变量不会让某些人反向改变参与状态。论文明确指出这个条件本质上不可检验，必须逐案论证。

## 6. 论文支撑什么 / 不支撑什么

支撑：

- 仅工具变量有效不足以识别平均处理效应；
- 加上单调性后，可以识别遵从者的 LATE；
- LATE 的公式和 IV 估计量的概率极限；
- LATE 是特定遵从人群的效应，不是全体 ATE。

不支撑：

- 不支撑把 LATE 直接当成全体 ATE；
- 不支撑在没有单调性时继续用 LATE 公式；
- 不支撑网络 IV、连续工具、2SLS 弱工具推断等扩展；
- 不支撑“软件已实现 IV 后端”。

## 7. 本案例的改编

### 原文事实

- Condition 1、Condition 2、Theorem 1 和 LATE 公式；
- LATE 的遵从者解释；
- 仅 IV 有效不够的结论。

### 自拟改编

- 培训资格抽签、200 人、观测到的 \(Z,D,Y\) 计数表；
- 业务问题、缺失条件版和 ATE 目标变化版；
- 具体数值均为合成，不是论文数据。

### LLM 改写

业务材料为人工整理；参考答案来自论文 Theorem 1 和手工计算，不由 LLM 生成。

## 8. 当前软件边界

当前仓库 `cfm_id.research_route_catalog.inventory()` 明确把 IV 列为：

```text
route_id = IV
status = NO_REGISTERED_CONTRACT_IN_THIS_ENTRY
callable_here = false
```

所以本案例的软件预期是 `UNSUPPORTED`：论文能给出 LATE 公式，但当前软件没有 IV 数学后端和 IV 读取入口。不能为了成功把它接到网络或 DAG 方法上。
