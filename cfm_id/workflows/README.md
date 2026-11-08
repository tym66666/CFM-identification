# 运行工作流与已有证书的组合

- `mean_order.py`、`mean_order_review.py`：均值顺序研究运行与独立准入；求解、验证仍在 `cfm_id.mean_order_*`。
- `legacy_network/`：从评测侧抽出的必要旧网络运行链。兼容旧入口，不作为复制新路线的模板。
- `policy_difference.py`：两个已验证 R2 政策均值的有序差值回执及核对。原生 R2 求解和重放仍在 `pfn_pipeline`；这里不发明新科学假设或新 Core 定理。

本目录不得依赖 `evaluation`、`examples` 或 `tests` 的参考答案、自动合成审核。新能力的公开配对放在 `cfm_id.capability_registry`；新测试和显式合成示例放回其所属目录。数学合同与文献导航见 [说明](../../docs/MATH_AND_EVIDENCE_ZH.md)。
