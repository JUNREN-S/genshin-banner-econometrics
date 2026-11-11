import os
import pandas as pd
import numpy as np

# 仓库根目录 / Repo root (parent of scripts/)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, 'data')

# 读取数据
banner_df = pd.read_csv(os.path.join(DATA_DIR, 'banner_ratios.csv'))
dual_df = pd.read_csv(os.path.join(DATA_DIR, 'dual_banner_ratios.csv'))

# 结果列表
records = []

# 遍历所有卡池
for _, row in banner_df.iterrows():
    banner_id = row['banner_id']
    banner_name = row['banner_name']
    revenue = row['revenue']
    
    # 判断是否为双角色池（名称中包含 "&"）
    if '&' in banner_name:
        # 从 dual_banner_ratios.csv 查找对应数据
        dual_data = dual_df[dual_df['banner_id'] == banner_id]
        
        if len(dual_data) > 0:
            dual = dual_data.iloc[0]
            char_a = dual['char_a']  # 中文名
            char_b = dual['char_b']
            ratio_a = dual['ratio_a']
            ratio_b = dual['ratio_b']
            
            # 拆分为两个独立观测
            records.append({
                'banner_id': banner_id,
                'banner_name': banner_name,
                'character': char_a,
                'character_en': dual['char_a_en'],
                'revenue': round(revenue * ratio_a, 2),
                'pool_type': '双角色池',
                'ratio': ratio_a,
                'total_revenue': revenue
            })
            
            records.append({
                'banner_id': banner_id,
                'banner_name': banner_name,
                'character': char_b,
                'character_en': dual['char_b_en'],
                'revenue': round(revenue * ratio_b, 2),
                'pool_type': '双角色池',
                'ratio': ratio_b,
                'total_revenue': revenue
            })
        else:
            # dual_banner_ratios 中没有，跳过或保留原样
            print(f"Warning: 双角色池 {banner_name} (ID: {banner_id}) 在 dual_banner_ratios 中未找到")
    else:
        # 单角色池：从 banner_name 提取五星角色名
        # 移除括号内容如 (Rerun), (New) 等
        char_name = banner_name.split('(')[0].strip()
        
        # 手动映射一些常见的英文名
        char_en_map = {
            'Raiden Shogun': 'raiden_shogun',
            'Yae Miko': 'yae_miko',
            'Itto': 'arataki_itto',
            'Ayaka': 'kamisato_ayaka',
            'Hu Tao': 'hu_tao',
            'Kokomi': 'sangonomiya_kokomi',
            'Klee': 'klee',
            'Eula': 'eula',
            'Yoimiya': 'yoimiya',
            'Zhongli': 'zhongli',
            'Tartaglia': 'tartaglia',
            'Kazuha': 'kaedehara_kazuha',
            'Wriothesley': 'wriothesley',
            'Lyney': 'lyney',
            'Neuvillette': 'neuvillette',
            'Furina': 'furina',
            'Navia': 'navia',
            'Clorinde': 'clorinde',
            'Sigewinne': 'sigewinne',
            'Emilie': 'emilie',
            'Mualani': 'mualani',
            'Kinich': 'kinich',
            'Xilonen': 'xilonen',
            'Chasca': 'chasca',
            'Mavuika': 'mavuika',
            'Citlali': 'citlali',
            'Mizuki': 'yumemizuki_mizuki',
            'Varesa': 'varesa',
            'Escoffier': 'escoffier',
            'Skirk': 'skirk',
            'Ineffa': 'ineffa',
            'Lauma': 'lauma',
            'Flins': 'flins',
            'Nefer': 'nefer',
            'Arlecchino': 'arlecchino',
            'Durin': 'durin',
            'Columbina': 'columbina',
            'Zibai': 'zibai',
            'Varka': 'varka',
            'Linnea': 'linnea',
            'Nicole': 'nicole',
        }
        
        char_en = char_en_map.get(char_name, char_name.lower().replace(' ', '_'))
        
        records.append({
            'banner_id': banner_id,
            'banner_name': banner_name,
            'character': char_name,
            'character_en': char_en,
            'revenue': round(revenue, 2),
            'pool_type': '单角色池',
            'ratio': 1.0,
            'total_revenue': revenue
        })

# 创建 DataFrame
result_df = pd.DataFrame(records)

# 按 revenue 降序排序
result_df = result_df.sort_values('revenue', ascending=False).reset_index(drop=True)

# 添加排名
result_df.insert(0, 'rank', range(1, len(result_df) + 1))

# 保存为 CSV
output_path = os.path.join(DATA_DIR, 'character_revenue_ranking.csv')
result_df.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f"✅ 完成！共生成 {len(result_df)} 条角色-流水记录")
print(f"📁 保存至: {output_path}")
print(f"\n🏆 Top 20 角色流水排名:")
print(result_df.head(20)[['rank', 'character', 'pool_type', 'banner_name', 'revenue', 'ratio']].to_string(index=False))

# 统计信息
print(f"\n📊 统计摘要:")
print(f"   总角色数: {len(result_df)}")
print(f"   单角色池: {len(result_df[result_df['pool_type']=='单角色池'])}")
print(f"   双角色池拆分: {len(result_df[result_df['pool_type']=='双角色池'])}")
print(f"   总流水: {result_df['revenue'].sum():,.2f}")
print(f"   平均流水: {result_df['revenue'].mean():,.2f}")
print(f"   中位数流水: {result_df['revenue'].median():,.2f}")
