"""
Create DiD Coefficient Plot for February 2025 - Simplified Version
===================================================================

Creates a simple plot showing the main DiD estimate with confidence interval.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf

sns.set_style("whitegrid")

# Load data
try:
    df = pd.read_csv('february_2025_panel_data_improved.csv')
    print("Using improved February data with real SteamCharts player counts")
except FileNotFoundError:
    df = pd.read_csv('february_2025_panel_data.csv')
    print("Using original February data")

print("="*80)
print("FEBRUARY 2025 - DiD ANALYSIS WITH VISUALIZATION")
print("="*80)
print(f"\nData: {len(df)} observations from {df['appid'].nunique()} games")
print(f"Weeks: {sorted(df['week'].unique())}")

# Fill missing values
if df['review_score'].isnull().all():
    print("\nAll review scores missing - filling with default (7.0)")
    df['review_score'] = 7.0

# Model 1: Pooled OLS
print("\nModel 1: Pooled OLS with Controls")
formula1 = 'ln_players ~ treated + post + treated:post + C(genre_category) + age_years + price_usd'
model1 = smf.ols(formula1, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})

did_coef1 = model1.params['treated:post']
did_se1 = model1.bse['treated:post']
did_p1 = model1.pvalues['treated:post']
did_ci1 = model1.conf_int().loc['treated:post']

print(f"  DiD Coefficient: {did_coef1:.4f}")
print(f"  Std Error: {did_se1:.4f}")
print(f"  P-value: {did_p1:.4f}")
print(f"  95% CI: [{did_ci1[0]:.4f}, {did_ci1[1]:.4f}]")

# Model 2: Two-way FE
print("\nModel 2: Two-Way Fixed Effects")
formula2 = 'ln_players ~ treated:post + C(appid) + C(week)'
model2 = smf.ols(formula2, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})

did_coef2 = model2.params['treated:post']
did_se2 = model2.bse['treated:post']
did_p2 = model2.pvalues['treated:post']
did_ci2 = model2.conf_int().loc['treated:post']

print(f"  DiD Coefficient: {did_coef2:.4f}")
print(f"  Std Error: {did_se2:.4f}")
print(f"  P-value: {did_p2:.4f}")
print(f"  95% CI: [{did_ci2[0]:.4f}, {did_ci2[1]:.4f}]")

# Create visualization
fig, ax = plt.subplots(figsize=(10, 7))

models = ['Model 1\n(Pooled OLS)', 'Model 2\n(Fixed Effects)']
estimates = [did_coef1, did_coef2]
errors = [[did_coef1 - did_ci1[0]], [did_ci1[1] - did_coef1],
          [did_coef2 - did_ci2[0]], [did_ci2[1] - did_coef2]]

x_pos = [0, 1]
colors = ['coral', 'steelblue']

for i, (model, est, color) in enumerate(zip(models, estimates, colors)):
    ax.errorbar(x_pos[i], est,
               yerr=[[estimates[i] - [did_ci1, did_ci2][i][0]],
                     [[did_ci1, did_ci2][i][1] - estimates[i]]],
               fmt='o', markersize=12, capsize=8, capthick=3,
               color=color, ecolor=color, label=model, linewidth=2)

# Add horizontal line at zero
ax.axhline(y=0, linestyle='--', color='gray', linewidth=1.5, alpha=0.7)

# Formatting
ax.set_ylabel('DiD Coefficient Estimate', fontsize=13, fontweight='bold')
ax.set_title('February 2025 DiD Analysis\nEffect of Major Patches on Player Counts',
            fontsize=14, fontweight='bold')
ax.set_xticks(x_pos)
ax.set_xticklabels(models, fontsize=11)
ax.set_xlim(-0.5, 1.5)
ax.grid(True, alpha=0.3, axis='y')
ax.legend(loc='best', framealpha=0.9, fontsize=10)

# Add significance stars
for i, pval in enumerate([did_p1, did_p2]):
    sig = '***' if pval < 0.001 else '**' if pval < 0.01 else '*' if pval < 0.05 else 'ns'
    y_pos = estimates[i] + ([did_ci1, did_ci2][i][1] - estimates[i]) * 1.2
    ax.text(x_pos[i], y_pos, sig, ha='center', va='bottom', fontsize=12, fontweight='bold')

plt.tight_layout()

save_path = 'february_2025_did_coefficient_plot.png'
plt.savefig(save_path, dpi=300, bbox_inches='tight')
print(f"\n[OK] Plot saved to: {save_path}")

print("\n" + "="*80)
print("COMPLETE!")
print("="*80)
