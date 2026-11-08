# 仓库范围

本仓库负责 **Identification**：业务理解与审核、已有数学方法的适用域检查、识别表达式或界限、证书与独立重放。

`demo/` 提供与该范围一致的本地实时网页。它复用已有读取、审核和数学入口，支持九个合成／文献改编示例，不包含效应估计、策略优化或相应模型资产。

当前能力和未完成部分分别见[范围说明](docs/CURRENT_SCOPE_ZH.md)、[限制清单](docs/KNOWN_LIMITATIONS_ZH.md)。IV 或一般 ID 等未来扩展不属于当前已实现能力。

`pfn_pipeline/` 包含原生网络识别，也保留部分 Estimation/Policy 兼容实现；后者不是本仓库新增研究功能的目标。本次采用根目录平铺的独立包结构，不搬动数学文件或改公开导入来模拟完全分离。

目录职责见[仓库布局](docs/REPOSITORY_LAYOUT_ZH.md)及[代码地图](docs/DEVELOPMENT_ENTRY_ZH.md)。当前推荐入口是 `cfm_id.project`，而不是早期单独的 `pfn_pipeline.identification` 或原型目录。

正式运行不得依赖实验金标准或自动合成批准；Skill/Prompt 不能代替科学审核；已有定理应用、候选推理、数学验证和估计结果应明确区分。独立证书重放不等于通用形式化证明系统。
