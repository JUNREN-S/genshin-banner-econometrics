# 原神卡池流水计量分析 / Genshin Impact Banner Revenue Econometrics

基于**角色级别拆分流水**的面板数据 OLS 回归，量化分析"复刻疲劳"——角色 UP 次数对卡池流水的影响。

> **EN TL;DR:** Panel-data OLS on character-level banner revenue (Genshin Impact) with character fixed effects and HC1 robust standard errors. Each additional rerun (UP) of the same character is associated with a **~20.1% revenue decline** (β = −0.224, p = 0.049). Fan-made academic exercise; revenue figures are third-party estimates, not official data.

## 核心发现

| 变量 | 系数 | 稳健 SE (HC1) | t 值 | p 值 | 95% CI |
|------|------|------|------|------|--------|
| **up_count**（第几次 UP） | **−0.224** | 0.114 | −1.970 | **0.049** | [−0.447, −0.001] |
| is_dual（双角色池） | −0.369 | 0.272 | −1.361 | 0.174 | [−0.902, 0.163] |
| is_second_half（版本下半） | −0.053 | 0.185 | −0.288 | 0.773 | [−0.416, 0.309] |

**经济含义**：在控制"角色是谁"（角色固定效应）之后，同一角色每多复刻一次，其拆分流水显著下降约 **20.1%**（1 − e^(−0.224)）。复刻疲劳不仅存在于角色之间，也存在于**角色内部**。

## 模型设定

```
ln(revenue_ij) = α_j + β₁·up_count + β₂·is_dual + β₃·is_second_half + ε_ij
```

- 分析单位：角色 × 卡池（86 个观测，33 名角色）
- 双角色池流水按抽取比例（pull ratio）拆分到角色级别
- 角色固定效应 `C(character)`，**HC1 稳健标准误**

## 快速开始

```bash
pip install -r requirements.txt

# 1.（可选）从卡池总流水 + 抽取比例重建角色拆分流水
python3 scripts/split_dual_banner_revenue.py

# 2. 主回归分析（输出 数据xlsx + 报告txt + 核心图png）
python3 scripts/run_regression_final.py

# 3.（可选）导出 EViews 可直接导入的数据做交叉验证
python3 scripts/generate_eviews_files.py
```

结果输出到 `output/`。

## 仓库结构

```
├── data/
│   ├── banner_ratios.csv                  # 卡池总流水（51 个卡池）
│   ├── dual_banner_ratios.csv             # 双角色池抽取比例
│   └── character_revenue_ranking_v3.csv   # 角色拆分流水（86 obs，清洗后）
├── scripts/
│   ├── split_dual_banner_revenue.py       # 数据准备：总流水 × 比例 → 角色流水
│   ├── run_regression_final.py            # 主回归（角色 FE + HC1）
│   └── generate_eviews_files.py           # EViews 交叉验证数据导出
├── docs/
│   └── methodology.md                     # 实证分析格式规范
└── output/                                # 运行后生成
```

## 方法学要点（踩坑记录）

1. **角色名称统一**：原始数据中同一角色存在不同命名（如 `Kaedehara Kazuha` vs `Kazuha`），不统一会导致虚拟变量共线性。清洗后唯一角色数 37 → 33。
2. **HC1 而非 HC3**：8 名角色仅出现 1 次，对应观测杠杆值 hat = 1.0，HC3 的 `1/(1−hat)²` 权重会产生 inf/nan 标准误。小样本务必用 HC1/HC0。
3. **共线性陷阱**：`revenue = total_revenue × ratio` 是定义式，`ln(total)` 与 `ln(ratio)` 不能同时进模型，否则 R² ≈ 1.0。
4. **FE 选择**：角色 FE 优先于版本 FE——流水差异主要来自"角色本身是谁"。

## EViews 交叉验证

`output/eviews_data.xlsx` 含 32 个角色虚拟变量，可直接导入 EViews：

1. `File → New → Workfile` → Unstructured/Undated，86 obs
2. `Quick → Estimate Equation`：`ln_revenue c up_count is_dual is_second_half D_*`
3. Options → 勾选 **Huber-White** 稳健标准误
4. 预期：up_count β ≈ −0.224，SE ≈ 0.114，t ≈ −1.97

## 数据说明与免责声明

- 流水数据为**第三方估算值**（非官方披露），仅供学术研究/课程作业使用。
- 卡池历史与角色信息来自公开 Wiki。
- 本项目为粉丝制作的计量经济学练习，与 HoYoverse / miHoYo 无任何关联。Genshin Impact 及相关角色名称版权归 HoYoverse 所有。

## License

MIT（代码与分析方法）。数据仅为第三方估算的汇编，请自行判断使用范围。
