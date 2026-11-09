# LIT-IV-02 来源卡：Balke & Pearl (1997)

## 1. 文献信息

- Balke, A., & Pearl, J. (1997). *Bounds on Treatment Effects From Studies With Imperfect Compliance*. *JASA* 92(439):1171–1176。
- DOI：10.1080/01621459.1997.10474074。
- 作者公开稿：https://ftp.cs.ucla.edu/pub/stat_ser/r199-jasa.pdf。
- 本卡核对范围：题录、摘要/问题设定和项目文献卡；已下载 UCLA 作者扫描 PDF（6 页），但该 PDF 没有可提取文字层，OCR 尚未完成；未逐页核对全部闭式界与 sharpness 证明。

## 2. 论文问题

在不完全遵从的二元 IV 设置中，LATE 只识别遵从者效应；如果目标是全体 ATE，通常不能点识别，只能求 sharp 上下界。

论文给出二元结果/二元处理/二元工具下 ATE 的经典界限，并说明界限依赖潜在响应类型的可行组合。

## 3. 本案例

沿用 LIT-IV-01 的 200 人 \(Z,D,Y\) 计数表，但目标改为：

> 全体 200 人的平均培训效应 ATE 的上下界。

这不是 LATE。LATE 公式不能回答 ATE。

本案例只测试：

- 系统是否知道 IV/ATE bounds 尚未实现；
- 是否会把 LATE 公式误当 ATE；
- 是否如实报告 `UNSUPPORTED`。

## 4. 论文支撑什么 / 不支撑什么

支撑：

- LATE 与 ATE 是不同目标；
- 不完全遵从下 ATE 通常只能部分识别；
- 二元 IV 模型中存在经典 sharp bounds。

不支撑：

- 不支撑当前软件已实现 IV/ATE bounds；
- 不支撑把 LATE 公式当 ATE；
- 不支撑把本案例的样本计数当作总体数据。

## 5. 当前软件

`cfm_id.research_route_catalog.inventory()` 明确把 IV 列为 `NO_REGISTERED_CONTRACT_IN_THIS_ENTRY`。  
软件预期：`UNSUPPORTED`。
