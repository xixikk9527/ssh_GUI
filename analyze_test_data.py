import pandas as pd

# 读取门架车牌识别设备捕获率明细 sheet
df_a = pd.read_excel('temp_doc/运行监测统计数据-260107(9).xlsx', sheet_name='门架车牌识别设备捕获率明细')
df_b = pd.read_excel('temp_doc/运行监测统计数据-260108(1).xlsx', sheet_name='门架车牌识别设备捕获率明细')

# 清理列名（去除空格）
df_a.columns = df_a.columns.str.strip()
df_b.columns = df_b.columns.str.strip()

print('=== 文件A (260107) - 门架车牌识别设备捕获率明细 ===')
print(f'行数: {len(df_a)}')
print(f'列名: {list(df_a.columns)}')
print(f'前5行:')
print(df_a.head())

print('\n=== 文件B (260108) - 门架车牌识别设备捕获率明细 ===')
print(f'行数: {len(df_b)}')
print(f'列名: {list(df_b.columns)}')
print(f'前5行:')
print(df_b.head())

# 检查省份列的唯一值
print('\n=== 省份列分析 ===')
print(f'文件A 省份唯一值数量: {df_a["省份"].nunique()}')
print(f'文件A 省份列表: {sorted(df_a["省份"].dropna().unique())}')
print(f'\n文件B 省份唯一值数量: {df_b["省份"].nunique()}')
print(f'文件B 省份列表: {sorted(df_b["省份"].dropna().unique())}')

# 计算交集和差集
set_a = set(df_a['省份'].dropna().unique())
set_b = set(df_b['省份'].dropna().unique())
print(f'\n共同省份数量: {len(set_a & set_b)}')
print(f'共同省份: {set_a & set_b}')
print(f'\n只在A中的省份数量: {len(set_a - set_b)}')
print(f'只在A中的省份: {set_a - set_b}')
print(f'\n只在B中的省份数量: {len(set_b - set_a)}')
print(f'只在B中的省份: {set_b - set_a}')

# 统计各省份的行数
print('\n=== 各省份行数统计 ===')
print('文件A 省份分布:')
print(df_a['省份'].value_counts().head(10))
print('\n文件B 省份分布:')
print(df_b['省份'].value_counts())