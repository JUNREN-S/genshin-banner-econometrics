import pandas as pd
import numpy as np
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
import warnings
import os
import shutil
warnings.filterwarnings('ignore')

# ============================================================
# 0. 输出目录
# ============================================================
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
output_dir = os.path.join(project_dir, 'output')

os.makedirs(output_dir, exist_ok=True)

# ============================================================
# 1. 读取数据并清洗角色名称
# ============================================================
df = pd.read_csv(os.path.join(project_dir, 'data', 'character_revenue_ranking_v3.csv'))

# 修复同一角色的不同命名（基于character_en统一）
name_fix = {
    'Arataki Itto': 'Itto',
    'Kaedehara Kazuha': 'Kazuha',
    'Kamisato Ayaka': 'Ayaka',
    'Kamisato Ayato': 'Ayato',
    'Sangonomiya Kokomi': 'Kokomi',
    'Raiden Shogun': 'Raiden',
}
df['character'] = df['character'].replace(name_fix)

print("="*60)
print("角色名称清洗后，唯一角色数:", df['character'].nunique())
print("="*60)

# ============================================================
# 2. 构建变量
# ============================================================
df['ln_revenue'] = np.log(df['revenue'])
df['is_dual'] = (df['pool_type'] == '双角色池').astype(int)

# 版本分组
def version_group(bid):
    if bid <= 300020: return 'v_early'
    elif bid <= 300042: return 'v2'
    elif bid <= 300060: return 'v3'
    elif bid <= 300076: return 'v4'
    else: return 'v5'
df['version_group'] = df['banner_id'].apply(version_group)

# 上下半
version_order = {}
for _, row in df.iterrows():
    vg, bid = row['version_group'], row['banner_id']
    if vg not in version_order:
        version_order[vg] = []
    if bid not in version_order[vg]:
        version_order[vg].append(bid)

is_second_half_map = {}
for vg, bids in version_order.items():
    for i, bid in enumerate(sorted(bids)):
        is_second_half_map[bid] = 1 if i % 2 == 1 else 0
df['is_second_half'] = df['banner_id'].map(is_second_half_map)

# 保存清洗后的数据
excel_path = os.path.join(output_dir, 'character_panel_data_cleaned.xlsx')
df.to_excel(excel_path, index=False, sheet_name='panel')

# ============================================================
# 3. OLS 回归（清洗后 + HC1稳健标准误）
# ============================================================
# 改用HC1而非HC3：因部分角色仅出现1次，hat=1导致HC2/HC3分母为0
formula = 'ln_revenue ~ up_count + is_dual + is_second_half + C(character)'
model = smf.ols(formula, data=df).fit(cov_type='HC1')

# 同时计算非稳健模型用于F检验
model_nonrobust = smf.ols(formula, data=df).fit()

# 提取核心结果
up_coef = model.params['up_count']
up_se = model.bse['up_count']
up_t = up_coef / up_se
up_pval = model.pvalues['up_count']
up_ci_low, up_ci_high = model.conf_int().loc['up_count']

dual_coef = model.params['is_dual']
dual_se = model.bse['is_dual']
dual_t = dual_coef / dual_se
dual_pval = model.pvalues['is_dual']
dual_ci_low, dual_ci_high = model.conf_int().loc['is_dual']

second_coef = model.params['is_second_half']
second_se = model.bse['is_second_half']
second_t = second_coef / second_se
second_pval = model.pvalues['is_second_half']
second_ci_low, second_ci_high = model.conf_int().loc['is_second_half']

# F检验
try:
    f_stat = model.fvalue
    f_pval = model.f_pvalue
except:
    f_stat = model_nonrobust.fvalue
    f_pval = model_nonrobust.f_pvalue

r2 = model.rsquared
adj_r2 = model.rsquared_adj
nobs = int(model.nobs)

# 残差诊断
jb_stat, jb_pval = stats.jarque_bera(model.resid)
bp_resid_sq = model.resid ** 2
bp_fitted = model.fittedvalues
bp_model = sm.OLS(bp_resid_sq, sm.add_constant(bp_fitted)).fit()
bp_stat = len(model.resid) * bp_model.rsquared
bp_pval = 1 - stats.chi2.cdf(bp_stat, 1)

cond_num = np.linalg.cond(model.model.exog)

# ============================================================
# 4. 生成文字报告
# ============================================================
report = f"""
{'='*80}
原神角色拆分流水 面板数据 OLS 回归分析报告（最终修正版）
{'='*80}

【重要修正说明】
1. 角色名称统一: 原数据中存在同一角色的不同命名方式：
     'Arataki Itto' → 'Itto', 'Kaedehara Kazuha' → 'Kazuha',
     'Kamisato Ayaka' → 'Ayaka', 'Kamisato Ayato' → 'Ayato',
     'Sangonomiya Kokomi' → 'Kokomi', 'Raiden Shogun' → 'Raiden'
   清洗后唯一角色数: {df['character'].nunique()} 个

2. 标准误选择: 改用HC1稳健标准误
   原因: 8个角色仅出现1次（Dehya, Furina, Lyney, Navia, Neuvillette,
         Tighnari, Wriothesley, Xianyun），导致对应观测值的杠杆值hat=1.0。
   HC2/HC3需计算 1/(1-hat)²，当hat→1时分母→0，产生无穷大标准误。
   HC1不受影响，因其使用 (n/df_resid) * resid² 作为异方差权重。

一、研究设计
{'-'*80}
分析单位: 角色-卡池组合 (character × banner)
样本量: {nobs} 条记录 | 唯一角色: {df['character'].nunique()} 个 | 卡池: {df['banner_id'].nunique()} 个
模型: 个体固定效应模型 (Character FE)
标准误: HC1 稳健标准误（替代HC3，原因见上文）
被解释变量: ln(角色拆分流水)

{'-'*80}
二、回归结果
{'-'*80}

模型: ln(revenue_ij) = α_j + β₁·up_count + β₂·is_dual + β₃·is_second_half + ε_ij

{'变量':<15} {'系数':>10} {'稳健SE':>10} {'t值':>8} {'p值':>8} {'95% CI':>20}
{'-'*70}
{'up_count':<15} {up_coef:>10.4f} {up_se:>10.4f} {up_t:>8.3f} {up_pval:>8.4f} [{up_ci_low:>7.3f}, {up_ci_high:>7.3f}]
{'is_dual':<15} {dual_coef:>10.4f} {dual_se:>10.4f} {dual_t:>8.3f} {dual_pval:>8.4f} [{dual_ci_low:>7.3f}, {dual_ci_high:>7.3f}]
{'is_second_half':<15} {second_coef:>10.4f} {second_se:>10.4f} {second_t:>8.3f} {second_pval:>8.4f} [{second_ci_low:>7.3f}, {second_ci_high:>7.3f}]

拟合优度:
  R² = {r2:.4f} | 调整R² = {adj_r2:.4f}
  F统计量 = {f_stat:.4f} (p = {f_pval:.4f})
  注: F检验p值实际为 {f_pval:.2e}，因极小在报告中显示为近似0

假设检验:
  H₀: β₁ = 0 (复刻次数不影响流水)
  t = {up_t:.3f}, p = {up_pval:.4f}
  {'拒绝H₀' if up_pval < 0.05 else '无法拒绝H₀'} (α = 0.05)

{'-'*80}
三、经济理论解读
{'-'*80}

1. 复刻疲劳效应 (up_count):
   系数 = {up_coef:.4f} {'***' if up_pval < 0.01 else '**' if up_pval < 0.05 else '*'}
   
   经济含义: 在控制"角色是谁"之后，该角色UP次数每增加1次，
            拆分流水 {'下降' if up_coef < 0 else '上升'}约 {abs((np.exp(up_coef) - 1) * 100):.1f}%。
   
   理论解释: 根据消费者行为理论，随着角色UP次数增加，玩家持有率
            逐渐饱和，边际需求递减。然而，本估计{'显著' if up_pval < 0.05 else '不显著'}，
            说明同一角色内部的复刻次数对个体流水的影响可能被
            角色固定效应所吸收——流水差异主要来自"角色本身是谁"
            而非"该角色第几次UP"。

2. 双角色池效应 (is_dual):
   系数 = {dual_coef:.4f} {'***' if dual_pval < 0.01 else '**' if dual_pval < 0.05 else '*'}
   
   经济含义: 双角色池 vs 单角色池的拆分流水差异 {'不显著' if dual_pval >= 0.05 else f'约 {(np.exp(dual_coef) - 1) * 100:.1f}%。'}

3. 上下半效应 (is_second_half):
   系数 = {second_coef:.4f} {'***' if second_pval < 0.01 else '**' if second_pval < 0.05 else '*'}
   
   经济含义: 版本下半 vs 上半的拆分流水差异 {'不显著' if second_pval >= 0.05 else f'约 {(np.exp(second_coef) - 1) * 100:.1f}%。'}

{'-'*80}
四、模型诊断
{'-'*80}
残差正态性 (Jarque-Bera): {jb_stat:.4f} (p = {jb_pval:.4f}) {'✅ 通过' if jb_pval > 0.05 else '⚠️ 未通过'}
异方差检验 (Breusch-Pagan): {bp_stat:.4f} (p = {bp_pval:.4f}) {'✅ 通过' if bp_pval > 0.05 else '⚠️ 未通过'}
条件数: {cond_num:.2f} {'✅ 正常' if cond_num < 30 else '⚠️ 共线性风险' if cond_num < 1000 else '❌ 严重共线性'}
设计矩阵秩: {np.linalg.matrix_rank(model.model.exog)} / {model.model.exog.shape[1]} 列

⚠️ 关于p值=0的说明:
  - 常数项p≈0: 正常。截距=ln(基准角色流水)，经济意义上显著不为0。
  - F统计量p≈0: 正常。F={f_stat:.2f}对应的p值={f_pval:.2e}，因极小显示为0.0000。
    这仅表示"模型整体显著"（至少有一个系数不为0），在FE模型中由角色虚拟变量
    驱动，不代表核心变量显著。

{'='*80}
"""

report_path = os.path.join(output_dir, 'regression_report_final.txt')
with open(report_path, 'w', encoding='utf-8') as f:
    f.write(report)

# ============================================================
# 5. 可视化
# ============================================================
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(12, 7))

multi_chars = df['character'].value_counts()
multi_chars = multi_chars[multi_chars >= 3].index.tolist()

for char in multi_chars[:6]:
    char_data = df[df['character'] == char].sort_values('up_count')
    ax.plot(char_data['up_count'], char_data['ln_revenue'], 
            marker='o', linewidth=2.5, markersize=8, label=char, alpha=0.8)

x_range = np.linspace(df['up_count'].min(), df['up_count'].max(), 100)
y_pred = model.params['Intercept'] + model.params['up_count'] * x_range
ax.plot(x_range, y_pred, 'k--', linewidth=2, alpha=0.5, 
        label=f'整体趋势 (β={model.params["up_count"]:.3f}{"***" if up_pval < 0.01 else "**" if up_pval < 0.05 else ""})')

ax.set_xlabel('角色 UP 次数', fontsize=13)
ax.set_ylabel('ln(角色拆分流水)', fontsize=13)
ax.set_title('复刻疲劳效应：典型角色的拆分流水轨迹（最终版）', fontsize=14, fontweight='bold')
ax.legend(fontsize=10, loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_xticks([1, 2, 3, 4, 5])
ax.set_xticklabels(['首次(1)', '1st复刻(2)', '2nd复刻(3)', '3rd复刻(4)', '4th复刻(5)'])

fig_path = os.path.join(output_dir, '01_regression_results_final.png')
plt.savefig(fig_path, dpi=300, bbox_inches='tight')
plt.close()

# ============================================================
# 6. 完成
# ============================================================
print("=" * 70)
print("✅ 最终修正版回归分析完成")
print("=" * 70)
print(f"\n📁 输出文件:")
for f in sorted(os.listdir(output_dir)):
    fpath = os.path.join(output_dir, f)
    fsize = os.path.getsize(fpath)
    size_str = f"{fsize/1024:.1f} KB" if fsize > 1024 else f"{fsize} B"
    print(f"  • {f:<40s} {size_str:>10s}")

print(f"\n📊 核心结果（最终版）:")
print(f"  • up_count: β={up_coef:.4f}, SE={up_se:.4f}, t={up_t:.3f}, p={up_pval:.4f}")
print(f"  • is_dual: β={dual_coef:.4f}, SE={dual_se:.4f}, t={dual_t:.3f}, p={dual_pval:.4f}")
print(f"  • is_second_half: β={second_coef:.4f}, SE={second_se:.4f}, t={second_t:.3f}, p={second_pval:.4f}")
print(f"  • R²={r2:.4f}, 调整R²={adj_r2:.4f}, F={f_stat:.4f}(p={f_pval:.2e})")
print(f"  • 条件数: {cond_num:.2f}")
print(f"  • 诊断: JB={'✅' if jb_pval > 0.05 else '⚠️'} BP={'✅' if bp_pval > 0.05 else '⚠️'}")
print("=" * 70)
