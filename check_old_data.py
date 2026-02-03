import pandas as pd
import numpy as np

print("="*80)
print("CHECKING OLD PANEL DATA")
print("="*80)

# Check first folder
df1 = pd.read_csv('staggered_DiD_Dec24-Apr25/staggered_panel_2025.csv')
print('\n1. staggered_DiD_Dec24-Apr25:')
print(f'   Rows: {len(df1)}, Games: {df1["appid"].nunique()}')
game_var1 = df1.groupby('appid')['ln_players'].std()
print(f'   Games with variation (std>0): {(game_var1 > 0).sum()} of {len(game_var1)}')
print(f'   Columns: {list(df1.columns)}')
print(f'\n   First game sample:')
appid1 = df1['appid'].iloc[0]
print(df1[df1['appid']==appid1][['appid', 'period', 'players', 'ln_players']].head(10))

# Check second folder
df2 = pd.read_csv('staggered_incl_FTandControlVariables/staggered_panel_2025.csv')
print('\n2. staggered_incl_FTandControlVariables:')
print(f'   Rows: {len(df2)}, Games: {df2["appid"].nunique()}')
game_var2 = df2.groupby('appid')['ln_players'].std()
print(f'   Games with variation (std>0): {(game_var2 > 0).sum()} of {len(game_var2)}')
print(f'   Columns: {list(df2.columns)}')
print(f'\n   First game sample:')
appid2 = df2['appid'].iloc[0]
print(df2[df2['appid']==appid2][['appid', 'period', 'players', 'ln_players']].head(10))

# Check control variables
print('\n   Control variables in df2:')
if 'review_score' in df2.columns:
    print(f'   - review_score missing: {df2["review_score"].isna().sum()} of {len(df2)}')
if 'genre_category' in df2.columns:
    print(f'   - genre_category values: {df2["genre_category"].unique()}')

# Manual DiD calculation
print('\n' + '='*80)
print('MANUAL DiD CALCULATION (using df2)')
print('='*80)
pre = df2[df2['period']==1].groupby('treated')['ln_players'].mean()
post = df2[df2['period']>=2].groupby('treated')['ln_players'].mean()
print(f'Pre-treatment:  Treatment={pre.get(1, 0):.4f}, Control={pre.get(0, 0):.4f}, Diff={pre.get(1,0)-pre.get(0,0):.4f}')
print(f'Post-treatment: Treatment={post.get(1, 0):.4f}, Control={post.get(0, 0):.4f}, Diff={post.get(1,0)-post.get(0,0):.4f}')
did = (post.get(1,0) - post.get(0,0)) - (pre.get(1,0) - pre.get(0,0))
print(f'DiD Estimate: {did:.4f}')
print(f'Percentage change: {(np.exp(did) - 1) * 100:.2f}%')
