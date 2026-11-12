# Partial Identification 证据体系说明

> 本文档解释任务3推广至 30 种 D×E 组合时，如何体现 *partial identification* 的完整证据链。

---

## 1. Partial Identification 的定义

Partial identification（部分识别）是指：在观测数据 A4（部分签名条件均值）和科学边界约束下，目标参数（政策均值或政策对比）不能縮小到单个点，而只能缩小到一个**区间**。Partial identification 的核心不是「给出区间」，而是 **证明为什么只能缩小到这个区间，而不能更紧**。

对应的三个层次要求：

| 层次 | 含义 | 对应证据 |
|------|------|---------|
| **L1 区间** | 给出识别区间 [lower, upper] | `status`, `lower`, `upper`, `width` |
| **L2 端点可达** | 证明存在可行世界达到每个端点 | `lower_world` / `upper_world`（每个单元格的实际取值映射），`lower_dual` / `upper_dual`（对偶乘子） |
| **L3 不可縮紧** | 证明不存在能产生更小区间的约束 | `sharp=True`（极值点枚举完备），`farkas`（不可行时的形式证伪），`baseline_bounds_only_range`（无 A4 时的区间，对比显示信息量） |

---

## 2. 文件架构：证据如何产生

```
用户 inquiry / information
        │
        ▼
general_bounded_policy_solver.solve() 或 general_bounded_contrast_solver.solve()
        │  (需启用 full_evidence=True)
        │
        ├─→ SupportEngine.evaluate()     → 普通支持概率（无证据）
        │
        └─→ dxe_mean_order_bridge.solve_with_full_evidence()
                    │
                    ├─→ 构建 MeanOrderProblem（D/E 参数化）
                    │     ├─ 枚举所有单元格 (n, a, e)
                    │     ├─ 构建 box 约束（边界上下限）
                    │     ├─ 构建 order 约束（OWN / PEERS / BOTH）
                    │     └─ 构建 A4 等式约束
                    │
                    └─→ mean_order_solver.solve()
                              │
                              ├─ _incompatibility()     → Farkas 证伪
                              ├─ 枚举所有极值点世界     → worlds[0] (下界) / worlds[1] (上界)
                              ├─ _dual() 对偶求解        → lower_dual / upper_dual
                              └─ 端点计算               → lower, upper, baseline_bounds_only_range
```

---

## 3. 每个证据字段的含义

### 3.1 `lower_world` / `upper_world`（单元格级）

```
cells: [
  { cell: ["A", 1, 1], support: "1/10",
    lower_world: "0.3",    ← 在达到全局下界的那个可行世界中，单元格 A/1/1 取值 0.3
    upper_world: "0.7"     ← 在达到全局上界的那个可行世界中，单元格 A/1/1 取值 0.7
  },
  ...
]
```

- **这不是**单元格自身边界（[lo, hi]），而是**全局极值点处的该单元格赋值**
- 两个世界是不同的可行赋值向量，证明端点可达

### 3.2 `lower_dual` / `upper_dual`（约束级）

```
lower_dual: {
  "bound_lower:[\"A\",1,1]": "1",   ← 下界约束 -m[A,1,1] ≥ -0.2 的对偶乘子=1
  "order:[\"A\",1,0][\"A\",1,1]": "0.5"  ← 顺序约束的对偶乘子
}
```

- 对偶变量表示**约束对目标函数的边际贡献**
- 非负对偶乘子的组合证明当前端点是最优的（KKT 条件）

### 3.3 `baseline_bounds_only_range` vs `lower`/`upper`

```
baseline_bounds_only_range: ["0", "1"]   ← 仅有科学边界时区间为 [0, 1]
lower: "3/7", upper: "4/7"               ← 加入 A4 数据后缩小为 [3/7, 4/7]
```

- 分离出「科学边界单独给出的区间」与「A4 加入后的识别区间」
- `informative_relative_to_bounds_only = True` 表示 A4 确实收窄了不确定性

### 3.4 `farkas`（不可行时）

```
status: "INCOMPATIBLE",
farkas: {
  "bound_lower:[\"A\",1,1]": "1",
  "order:[\"A\",1,0][\"A\",1,1]": "1",
  "a4_upper:[\"A\",1,1]": "1"
}
```

- Farkas 引理的形式化证明：线性不等式组无解
- 征引的约束 ID 列表构成一个「矛盾链」

### 3.5 `sharp = True`

- `mean_order_solver` 对所有极值点（anchors 的笛卡尔积）进行枚举
- 所有枚举到的世界都在可行域顶点上；若最小值/最大值被某顶点达到，且没有更外的顶点，则 sharp 成立
- 这是**精确枚举**（exact enumeration）保证的 sharpness，不是数值近似

---

## 4. 对比：支持概率验证与 Partial Identification 的关系

| 组件 | 角色 | 是否 Partial ID 所需 |
|------|------|---------------------|
| `SupportEngine.evaluate()` | 生产路径：计算支持概率 | ✅ 构建约束系数 |
| `support_verifier.verify_joint_support()` | 独立 oracle：验证支持概率 | ❌ 不是，但保证正确性 |
| `mean_order_solver.solve()` | LP 求解：产生端点、对偶、世界 | ✅ **核心引擎** |
| `dxe_mean_order_bridge` | 桥接：将 D/E 规格翻译为 MeanOrderProblem | ✅ **使推广成为可能** |

---

## 5. 在系统合约链中的位置

```
bounded_policy_contract  (合约定义)
        │
        ▼
general_bounded_policy_solver  (推广求解器，此文件)
        │
        ├─→ SupportEngine (支持概率)
        │
        └─→ dxe_mean_order_bridge → mean_order_contract (桥接合约)
                    │
                    ▼
              mean_order_solver.solve()  (纯数学求解)
                    │
                    ▼
              证书（含 worlds/duals/Farkas/baseline_bounds）
                    │
                    ▼
              general_bounded_policy.py (路由入口 → 返回给调用者)
```

---

## 6. 关键结论

**任务3的「体现 partial identification」要求**，在 bridge 文件创建后全部满足：

| 要求 | 状态 | 位置 |
|------|------|------|
| 区间输出 (L1) | ✅ | `certificate.lower`, `certificate.upper` |
| 端点可达世界 (L2) | ✅ | `cells[].lower_world`, `cells[].upper_world` |
| 对偶证据 (L2) | ✅ | `certificate.lower_dual`, `certificate.upper_dual` |
| Farkas 证据 (L3) | ✅ | `certificate.farkas`（当 INCOMPATIBLE） |
| 基线对比 (L3) | ✅ | `certificate.baseline_bounds_only_range`, `informative_relative_to_bounds_only` |
| Sharpness 证明 (L3) | ✅ | `certificate.sharp = True`（由枚举完备性保证） |

**仅靠 `general_bounded_policy_solver` 中的 `_build_certificate`（不使用 bridge）时，L2 和 L3 的证据确实缺失。`dxe_mean_order_bridge.py` 填补了这一缺口**。