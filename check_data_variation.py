import pandas as pd
import numpy as np

df = pd.read_csv('staggered_panel_2025.csv')

print("="*80)
print("DATA VARIATION ANALYSIS")
print("="*80)

print("\nChecking time variation for first 10 games:")
for i, appid in enumerate(df['appid'].unique()[:10]):
    game_df = df[df['appid']==appid][['appid', 'name', 'period', 'players', 'ln_players']].copy()
    std = game_df['players'].std()
    print(f"\nGame {i+1} - {appid}: {game_df['name'].iloc[0][:40]}")
    print(f"  Players range: {game_df['players'].min():,.0f} - {game_df['players'].max():,.0f}")
    print(f"  Std dev: {std:,.2f} (CV: {std/game_df['players'].mean():.2%})")
    print(game_df[['period', 'players']])

print("\n" + "="*80)
print("SUMMARY STATISTICS")
print("="*80)

# Calculate within-game variation
game_variation = df.groupby('appid')['ln_players'].agg(['std', 'mean']).reset_index()
game_variation['cv'] = game_variation['std'] / game_variation['mean']

print(f"\nWithin-game variation (ln_players):")
print(f"  Mean std: {game_variation['std'].mean():.4f}")
print(f"  Median std: {game_variation['std'].median():.4f}")
print(f"  Games with NO variation (std=0): {(game_variation['std'] == 0).sum()} of {len(game_variation)}")
print(f"  Games with variation (std>0): {(game_variation['std'] > 0).sum()}")

print(f"\nControl variables:")
print(df[['genre_category', 'age_years', 'price_usd', 'is_free', 'review_score']].describe())

print(f"\nGenre distribution:")
print(df.groupby('genre_category')['appid'].nunique())

print(f"\nReview score - missing:")
print(f"  Total rows: {len(df)}")
print(f"  Missing review_score: {df['review_score'].isna().sum()}")
print(f"  Non-missing: {df['review_score'].notna().sum()}")
