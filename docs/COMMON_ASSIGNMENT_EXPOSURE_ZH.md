# Causal-IDFM 数学合同：Common Assignment & Exposure Expansion

> 版本：2026-10-17 · v2.4 · Network-first POINT · **增量复用既有 R1a/R1b/R2 theorem family**

## 1. 本版范围与分类

- **D4 `cluster_bernoulli_binary_v2_4`**：研究前确定有限、非空、互不重叠的节点簇分区 $\mathcal C=(C_1,\ldots,C_J)$，每个簇独立抽一次 $B_c\sim\operatorname{Bernoulli}(p_c)$，对所有 $i\in C_c$ 设置 $T_i=B_c$。$p_c$ 可异质、精确有理数，也可为 0/1。簇内节点 treatment **完全相关**。这**不是**随机选固定数量簇、两阶段饱和度设计或簇内再次随机分配。
- **E4 `exact_treated_neighbor_count`**：$g_i(\mathbf t,G)=\sum_{j\in N(i)}t_j$，目标状态 $s\in\{0,\ldots,d_i\}$。孤立节点唯一有效状态为 0；Batch 采用 $0,\ldots,\max_i d_i$ 矩形状态轴，非本节点有效坐标显示 `UNSUPPORTED`，不允许伪认证。
- **E5 `any_treated_neighbor`**：$g_i(\mathbf t,G)=\mathbf 1\{\sum_{j\in N(i)}t_j>0\}$。孤立节点仅有有支持的低暴露状态 0。

原 D1/D2/D3 与 E1/E2/E3 的既有代码、序列化与指纹保持兼容。D4 的簇排序和簇内顺序不改变设计身份，但每个簇的 $p_c$ 保留绑定。

## 2. 没有创造新的 R1a 识别原理

已知固定预处理网络 $G$、处理前条件 $W$、完整分配律 $q(\mathbf t\mid W)$、consistency、相对于全体潜在结果表的完整向量随机化、可积性，以及目标 arm 的正支持

$$\pi_i^q(a,s\mid W)=\sum_{\mathbf t}q(\mathbf t\mid W)\mathbf1\{t_i=a,g_i(\mathbf t,G)=s\}>0,$$

则

$$\mu_i^q(a,s\mid W)=E[Y_i^{obs}\mid W,T_i=a,g_i(\mathbf T,G)=s].$$

**这一结论不要求 $Y_i(\mathbf t)$ 只取决于 $t_i,g_i(\mathbf t,G)$。** $q$ 是因果目标标准化的一部分；D4 虽然簇内关联，只要已知完整 q 并满足完整向量随机化，仍适用同一 theorem。R1a 只输出总体符号 functional、A4 条件信息与验证证书，不虚构效应估计值。

D4 支持概率的一种计算方式：令 $c(i)$ 为包含 $i$ 的簇，$h_{ic}=|N(i)\cap C_c|$，固定 $T_i=a$ 后 $K_i$ 的概率生成多项式为

$$x^{a h_{i,c(i)}}\prod_{c\ne c(i)}(1-p_c+p_c x^{h_{ic}}).$$

然后乘以 $P(T_i=a)=p_{c(i)}$（若 $a=1$）或 $1-p_{c(i)}$（若 $a=0$），按 E1–E5 将计数概率相加。生产路径使用簇级序列 DP；独立 verifier 使用均衡生成函数乘法；小图 Oracle 再按完整分配穷举 $q(\mathbf t)$。**不能**用节点级独立 Bernoulli 的邻居概率代替簇级条件分布。

## 3. R1b 与 R2 的边界

- **R1b**：固定政策 $\mathbf z$ 仅在 $q(\mathbf z)>0$，并有足够 full-assignment-resolution A4 条件结果信息与已接受随机化时可识别；D4 下，同簇不同 treatment 的政策 $q(\mathbf z)=0$。
- **R2**：对每个节点显式接受 **mean-signature sufficiency**，即 $E[Y_i(\mathbf t)\mid W]=h_i(t_i,g_i(\mathbf t,G),W)$，且每个目标政策签名的实验支持严格正、A4 充分、随机化及 consistency 等条件成立，才允许 POINT。单纯定义了 E4/E5 不构成结果充分性证明。
- **R3**：v2.3 中的有限观测网络后端仍保留原适用域；本版 D4 是随机实验，不声明已经完成通用 observational exposure 扩展。

## 4. “Signature support 为零”的精确例子

七节点 Star 中心有六个邻居，原实验为均匀固定处理 $m=3$。目标全员 treatment：

- E1 majority：中心需要本人 treated 且四个以上邻居 treated（至少总共五人），签名支持 $0$。
- E4 exact-count：中心需要本人 treated 且六个邻居 treated，签名支持 $0$。
- E5 any-treated：中心需要本人 treated 且至少一个邻居 treated，总处理三人的设计下该类别概率正，**$3/7$**。但是 E5 比 E4 是更强的关于结果均值的“被 treated 邻居人数没有进一步影响”假设，必须由研究者确认；不能因为 $3/7>0$ 就自动选择 E5。

解决 zero-support 的合法策略：修改**未来**实验设计；提供确有科学根据的新结构限制；改为原设计支持的另一因果目标（明确不是原目标）；获得额外信息/新研究；或未来使用 PARTIAL identified sets。不能修改已经观察的 $q$ 或把 $0$ 当成小正数。

## 5. 可复现测试与使用限制

```bash
python -B -m unittest discover -s tests -p 'test_*.py' -q
python -B -m unittest tests.test_common_design_exposure -v
python -B -m examples.run_common_design_exposure --output-dir showcase_v24
python -B -m examples.run_large_ring_cluster --output-dir showcase_v24
```

展示文件 `showcase_v24/CFM_ID_v2_4_Assignment_Exposure_Showcase.html` 与相应 JSON 来自**真实 theorem 调用及 certificate replay**。9 张固定网络 × 4 类设计 × 5 类 exposure = 180 组合；每个正向组合仅证明其中至少一个指定 arm 被认证，**不等于所有节点所有 arms 均 POINT，也不等于 180 种真实商业使用场景或估计能力**。

资源限制：R1a single-arm 的全局 N/degree/DP 限制沿用既有版本；E4 Batch 的最大度数轴上限为 64（可对更高节点度数用单 arm）；非简单无向固定网络/动态有向加权网络没有因本次扩展获得通用支持。**旧 PFN 的四臂适配只认证原 D1 + E1 特定设置，新 D4/E4/E5 未获得自动 Estimation adapter。**

已知未覆盖：随机固定个数簇、双阶段设计、簇内再次随机、更多群组配额、连续与多级 treatment、任意 exposure 函数、观测网络一般调整、多期/有向/加权图、结构假设真实性的统计检验。远端 Python 3.11 CI 需实际触发确认。

## 6. 非 ER 大网络运行证明

300 节点无向 Ring 图，150 个两节点固定簇，簇级 Bernoulli(1/2)，研究节点 node-0。在 E4 精确邻居 treated 数量为 2 时 joint support=1/4；E5 任一邻居 treated 时为 1/2；E1 strict-majority 时为 1/4。三个调用都经真实 R1a `identify()` 及独立证书重放，输出 `showcase_v24/CFM_ID_v2_4_Ring300_D4_Proofs.json`。这仅为单 arm 大网络验证，**不是**宣称 Ring300 的每个 arm 均 POINT。
