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

# ============================================================
# 2. 构建变量
# ============================================================
df['ln_revenue'] = np.log(df['revenue'])
df['is_dual'] = (df['pool_type'] == '双角色池').astype(int)

def version_group(bid):
    if bid <= 300020: return 'v_early'
    elif bid <= 300042: return 'v2'
    elif bid <= 300060: return 'v3'
    elif bid <= 300076: return 'v4'
    else: return 'v5'
df['version_group'] = df['banner_id'].apply(version_group)

version_order = {}
for _, row in df.iterrows():
    vg, bid = row['version_group'], row['banner_id']
    if vg not in version_order: version_order[vg] = []
    if bid not in version_order[vg]: version_order[vg].append(bid)

is_second_half_map = {}
for vg, bids in version_order.items():
    for i, bid in enumerate(sorted(bids)):
        is_second_half_map[bid] = 1 if i % 2 == 1 else 0
df['is_second_half'] = df['banner_id'].map(is_second_half_map)

# ============================================================
# 3. 生成EViews可直接使用的Excel文件
# ============================================================
# EViews-friendly: 纯数值，无中文列名，角色用虚拟变量
eviews_df = df[['ln_revenue', 'up_count', 'is_dual', 'is_second_half']].copy()

# 生成角色虚拟变量（EViews可以直接读）
char_dummies = pd.get_dummies(df['character'], prefix='D', drop_first=True).astype(int)
eviews_df = pd.concat([eviews_df, char_dummies], axis=1)

# 保存为Excel（EViews可直接导入）
eviews_excel_path = os.path.join(output_dir, 'eviews_data.xlsx')
eviews_df.to_excel(eviews_excel_path, index=False, sheet_name='data')

# 同时保存CSV格式
eviews_csv_path = os.path.join(output_dir, 'eviews_data.csv')
eviews_df.to_csv(eviews_csv_path, index=False)

# 保存原始面板数据（含中文，用于参考）
df.to_excel(os.path.join(output_dir, 'panel_data.xlsx'), index=False, sheet_name='panel')

# ============================================================
# 4. 运行Python回归（用于对比）
# ============================================================
formula = 'ln_revenue ~ up_count + is_dual + is_second_half + C(character)'
model = smf.ols(formula, data=df).fit(cov_type='HC1')
model_nonrobust = smf.ols(formula, data=df).fit()

# 提取结果
up_coef = model.params['up_count']
up_se = model.bse['up_count']
up_t = up_coef / up_se
up_pval = model.pvalues['up_count']

dual_coef = model.params['is_dual']
dual_se = model.bse['is_dual']
dual_t = dual_coef / dual_se
dual_pval = model.pvalues['is_dual']

second_coef = model.params['is_second_half']
second_se = model.bse['is_second_half']
second_t = second_coef / second_se
second_pval = model.pvalues['is_second_half']

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
# 5. 生成回归结果对比表（供EViews验证用）
# ============================================================
comparison = f"""
================================================================================
Python vs EViews 回归结果对照表
================================================================================

【Python 结果（HC1稳健标准误）】
变量          系数        SE         t值       p值
----------------------------------------------------------------------
up_count      {up_coef:10.4f}  {up_se:10.4f}  {up_t:8.3f}  {up_pval:8.4f}
is_dual       {dual_coef:10.4f}  {dual_se:10.4f}  {dual_t:8.3f}  {dual_pval:8.4f}
is_second_half {second_coef:10.4f}  {second_se:10.4f}  {second_t:8.3f}  {second_pval:8.4f}

拟合优度: R² = {r2:.4f}, 调整R² = {adj_r2:.4f}
F统计量 = {f_stat:.4f} (p = {f_pval:.2e})
观测数 n = {nobs}

残差诊断:
  Jarque-Bera: {jb_stat:.4f} (p = {jb_pval:.4f})
  Breusch-Pagan: {bp_stat:.4f} (p = {bp_pval:.4f})
  条件数: {cond_num:.2f}

【EViews 验证任务】
请在EViews中执行以下操作，将结果与上方Python结果对比：

1. 导入数据: File → Import → Import from file → 选择 eviews_data.xlsx
2. 估计方程: Quick → Estimate Equation
3. 输入方程: ln_revenue c up_count is_dual is_second_half D_* 
   （或逐个输入D_Ayaka D_Ayato D_Baizhu ...等32个角色虚拟变量）
4. 估计方法: Least Squares
5. 选项: 在Options中勾选 "Huber-White" 或 "HAC(Newey-West)" 稳健标准误
   （注意：因hat=1问题，HC3不可行，建议用HC1/White）

【预期结果对比】
  Python up_count: β={up_coef:.4f}, SE={up_se:.4f}, t={up_t:.3f}, p={up_pval:.4f}
  EViews up_count: [待填入] 应与Python结果高度一致（差异<0.001）

================================================================================
"""

with open(os.path.join(output_dir, 'eviews_comparison.txt'), 'w', encoding='utf-8') as f:
    f.write(comparison)

print("=" * 70)
print("✅ EViews数据文件和验证指南已生成")
print("=" * 70)
print(f"\n📁 输出文件:")
for f in sorted(os.listdir(output_dir)):
    fpath = os.path.join(output_dir, f)
    fsize = os.path.getsize(fpath)
    size_str = f"{fsize/1024:.1f} KB" if fsize > 1024 else f"{fsize} B"
    print(f"  • {f:<40s} {size_str:>10s}")

print(f"\n📊 Python核心结果（用于与EViews对比）:")
print(f"  • up_count: β={up_coef:.4f}, SE={up_se:.4f}, t={up_t:.3f}, p={up_pval:.4f}")
print(f"  • is_dual: β={dual_coef:.4f}, SE={dual_se:.4f}, t={dual_t:.3f}, p={dual_pval:.4f}")
print(f"  • is_second_half: β={second_coef:.4f}, SE={second_se:.4f}, t={second_t:.3f}, p={second_pval:.4f}")
print(f"  • R²={r2:.4f}, F={f_stat:.4f}(p={f_pval:.2e})")
print("=" * 70)
