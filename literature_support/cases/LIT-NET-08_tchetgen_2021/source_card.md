# LIT-NET-08 来源卡：Tchetgen Tchetgen et al. (2021) Auto-G

## 1. 文献信息

- Tchetgen Tchetgen, E. J., Fulcher, I. R., & Shpitser, I. (2021). *Auto-G-Computation of Causal Effects on a Network*. *JASA* 116(534):833–844。
- DOI/链接：项目文献卡记录为 JASA 2021；本卡核对范围仅为题录、摘要和项目路线说明。
- 核对版本：arXiv:1709.01577v3（2019-08-22），实际读到 Abstract、§3.1 chain graph representation、auto-G-computation algorithm 相关段落；未逐页核对全部证明、模拟和估计细节。

## 2. 论文问题

论文研究网络干扰下，如何利用网络联合分布和 chain graph / Auto-G 计算，识别并估计干预效应。

关键思想：

- 网络上的结果与处理存在复杂依赖；
- 不能简单把每个对象当成独立；
- 需要声明网络联合律、干预目标和可分解结构；
- Auto-G 计算依赖图结构和条件分布。

## 3. 本案例

四节点小型网络，处理 \(X\)、结果 \(Y\)、观测到的网络联合分布。目标：

> 对指定节点的干预 \(do(X=x)\)，结果分布或平均结果如何？

本案例只测试：

- 系统是否知道 Auto-G 尚未实现；
- 是否会把 Auto-G 误接到现有网络 POINT 方法；
- 是否如实报告 `UNSUPPORTED`。

## 4. 论文支撑什么 / 不支撑什么

支撑：

- 网络联合律和干预目标的区分；
- Auto-G 是网络识别的一种专门路线；
- 网络依赖不能默认忽略。

不支撑：

- 不支撑当前软件已实现 Auto-G；
- 不支撑把四节点合成案例当作论文数据；
- 不支撑把 Auto-G 的结果与现有 R1/R2/R3 路线混同。

## 5. 当前软件

`cfm_id.research_route_catalog.inventory()` 没有登记 Auto-G / 网络联合律路线。  
本案例软件预期：`UNSUPPORTED`。
