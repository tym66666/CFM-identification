# LIT-NET-05 来源卡：Paluck et al. (2016) + Aronow & Samii (2017)

## 1. 文献信息

- Paluck, E. L., Shepherd, H., & Aronow, P. M. (2016). *Changing climates of conflict: A social network experiment in 56 schools*. PNAS. DOI: 10.1073/pnas.1514483113。
- Aronow, P. M., & Samii, C. (2017). *Estimating Average Causal Effects Under General Interference, with Application to a Social Network Experiment*. *Annals of Applied Statistics* 11(4):1912–1947. DOI: 10.1214/16-AOAS1005。

## 2. 阅读范围

阅读级别：`selected_sections_and_demo_alignment`。

- Paluck et al.：项目 demo 的文献对照说明；未逐页核对原文全部表格。
- Aronow–Samii：§8 式 (16)、Corollary 8.1；§10 手环/间接暴露讨论。
- 未核对：Paluck 全部实验设计细节、Arronow–Samii 全部证明和附录。

## 3. 论文问题

Paluck et al. 研究学校反冲突项目中的同伴传播；Aronow–Samii 提供设计、暴露和设计加权目标的框架。

本案例保留：

- “邀请”不等于“实际出席”；
- 学校已经开展项目，不比较学校是否开展；
- 12 名学生、两组各 6 人，每组独立抽 2 人获邀；
- 朋友网络固定；
- 目标：本人未获邀时，至少一位朋友获邀 vs 没有朋友获邀，佩戴手环概率之差；
- 全部 12 人等权。

## 4. 论文支撑什么 / 不支撑什么

支撑：

- 邀请与出席要分开；
- 网络溢出效应可以按设计加权目标定义；
- 组内固定名额、组间独立的设计。

不支撑：

- 不支撑把邀请当成实际出席；
- 不支撑把合成 12 人校园当成论文 56 所学校数据；
- 不支撑把论文表 2 的数值直接搬到本案例。

## 5. 改编说明

- 原文事实：邀请/出席区分、设计加权暴露目标、校园网络溢出背景。
- 自拟：12 人、两组各 6 人、每组抽 2 人、具体朋友边、手环结果。
- LLM：业务材料以 demo `lit_school` 为底稿，人工整理；参考答案不由 LLM 生成。

## 6. 当前软件

原题使用 2026-11-04 的 demo 保存运行：`POINT`，独立重放通过。  
改动版目前只有参考答案和预期状态，尚未实际运行。
