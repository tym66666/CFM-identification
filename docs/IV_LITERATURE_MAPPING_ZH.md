# IV 文献与实现映射

本路线实现的是二元工具变量的经典潜在响应类型合同，而非一般工具变量识别器。

| 数学内容 | 实现 | 依据与限制 |
|---|---|---|
| Wald 比率与遵从者 LATE | `cfm_id/iv_late_solver.py` | Imbens & Angrist (1994), *Identification and Estimation of Local Average Treatment Effects*, Econometrica 62(2), 467–475. 需要独立性、排除限制、单调性与一致性。 |
| 16/12 类潜在响应模型 | `cfm_id/iv_types.py` | 二元 `D(0),D(1),Y(0),Y(1)` 的穷举表示；单调性删去四类 defier 类型。 |
| ATE sharp bounds | `cfm_id/iv_ate_solver.py` | Balke & Pearl (1997), *Bounds on Treatment Effects from Studies with Imperfect Compliance*, JASA 92(439), 1171–1176. 当前实现范围限定于二元 Z/D/Y 和完整条件总体分布。 |
| 证书复核 | `cfm_id/iv_ate_verify.py`, `iv_late_verify.py` | 本项目独立重放义务；证书只证明声明 LP/代数合同的数值结论，不证明工具变量科学假设。 |

文献映射说明数学来源，不代表每个更广泛模型都已实现。非二元变量、额外约束、网络干扰、弱工具变量推断和估计推断均不在当前路线范围内。

公开链接：[LATE工作论文条目（与1994期刊版本区分）](https://www.nber.org/papers/t0118)、[Balke–Pearl作者托管期刊PDF](https://ftp.cs.ucla.edu/pub/stat_ser/r199-jasa.pdf)。本次联网核对书目信息和摘要，未声称完成全文证明审计；有限类型表示、LATE消去与sharpness推导见本项目IV_MATH_ZH.md。
