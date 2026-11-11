# 原文摘录：Pearl (1995) §3.1 后门准则与式 (6)

> 这不是论文全文，只保留本案例核对所需的短摘录和公式。
>
> 版本：Pearl (1995), *Causal Diagrams for Empirical Research*, *Biometrika* 82(4):669–688，作者公开稿。  
> 核对位置：§3.1, pp. 674–675。

## 1. Definition 3（Back-door criterion）

原文：

> A set of variables \(Z\) satisfies the back-door criterion relative to an ordered pair of variables \((X_i,X_j)\) in a directed acyclic graph \(G\) if: (i) no node in \(Z\) is a descendant of \(X_i\), and (ii) \(Z\) blocks every path between \(X_i\) and \(X_j\) which contains an arrow into \(X_i\).

要点：

- 调整变量不能是处理的后代；
- 调整变量必须阻断所有从 \(X\) 进入的后门路径。

## 2. Theorem 1

原文：

> If a set of variables \(Z\) satisfies the back-door criterion relative to \((X,Y)\), then the causal effect of \(X\) on \(Y\) is identifiable and is given by the formula
>
> \[
> p(y\mid \hat{x})=\sum_z p(y\mid x,z)\,p(z). \tag{6}
> \]

其中 \(\hat{x}\) 表示 \(do(X=x)\)。

## 3. 公式的含义

- 先按 \(Z\) 分层，计算每个治疗状态下的结果概率 \(p(y\mid x,z)\)；
- 再按干预前 \(Z\) 的分布 \(p(z)\) 加权平均；
- 不是按治疗组各自的 \(Z\) 分布加权，也不是简单比较治疗组和对照组的边际结果。

## 4. 本案例的三变量图

```text
Z（资深员工） → X（参加培训）
Z（资深员工） → Y（业绩达标）
X（参加培训） → Y（业绩达标）
```

\(Z\) 不是 \(X\) 的后代，且阻断 \(X\) 与 \(Y\) 之间唯一进入 \(X\) 的路径 \(X\leftarrow Z\rightarrow Y\)。所以 \(Z\) 满足后门准则：

\[
p(y\mid do(x))=\sum_z p(y\mid x,z)p(z).
\]

## 5. 论文的边界

论文的后门准则是一个充分条件，不是一般图 ID 的完备算法。若没有观测变量集合满足后门准则，不能由这条定理推出“不可识别”；需要单独的失败证据或一般 ID 分析。

## 6. 没核对的内容

- §3.2 前门准则的完整证明；
- §4 的 do-calculus；
- 附录与讨论；
- 出版版与作者稿的逐页差异。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
