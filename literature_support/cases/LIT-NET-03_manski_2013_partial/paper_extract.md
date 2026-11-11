# 原文摘录与边界：Manski (2013)

> 这不是论文全文，只保留本案例核对所需的背景。
>
> 版本：Manski (2013), *Identification of Treatment Response with Social Interactions*, *Econometrics Journal* 16:S1–S23，作者公开稿。  
> 核对位置：§2.1、§3.1（pp. S8–S9）、§3.2（pp. S9–S10）、§5.1–§5.2（pp. S19–S20）。

## 1. 论文关注什么

论文研究社会互动下的处理反应识别：

- 个体的结果可能依赖其他人的处理；
- 可以用 effective treatment 概括干扰；
- 在没有完整结构限制时，通常得到部分识别而不是点识别；
- 额外的形状限制（如单调性）可以收窄识别集。

## 2. 原文事实

- §2.1 讨论 constant treatment response (CTR)。
- §3.1 讨论 semi-monotone treatment response，式 (3.1)–(3.5)。
- §3.2 讨论 reinforcing interactions 和 componentwise treatment order。
- §5.1–§5.2 讨论 Proposition SI 和式 (5.3)。

本卡没有逐条核验论文全部证明，也没有把论文的任一命题直接当作本案例的 sharp 证明。

## 3. 本案例与论文的关系

本案例的 `[3/7, 4/7]` 是**项目自建有限均值模型**的结果：

- 七个网点、星形网络、固定 3 个名额；
- 七个精确总体条件均值；
- 每个对象的上下界 [0,1]；
- 全安排均值暴露充分性；
- 无额外耦合限制。

它借用 Manski 的部分识别思想，但：

- 不是论文的实证数据；
- 不是论文的原始数值例子；
- 不是论文定理的逐字复制；
- 不能把论文引用当作 sharpness 证明。

Sharp 性由项目有限模型的求解和证书重放单独检查。

## 4. 没核对的内容

- 论文全部结构交互推导；
- 所有证明和附录；
- 出版版与作者稿的逐页差异。

因此本来源卡的阅读级别是 `selected_full_text_sections`，不是 `full_text_verified`。
