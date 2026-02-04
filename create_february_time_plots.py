"""
Create DiD Coefficient Over Time Plots for February 2025 Analysis
==================================================================

Generates two plots showing DiD coefficient estimates for each week
with confidence intervals for both Model 1 and Model 2.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf

sns.set_style("whitegrid")

# Load improved data
df = pd.read_csv('february_2025_panel_data_improved.csv')

print("="*80)
print("FEBRUARY 2025 - DiD COEFFICIENTS OVER TIME")
print("="*80)
print(f"\nData: {len(df)} observations from {df['appid'].nunique()} games")
print(f"Weeks: {sorted(df['week'].unique())}")

# Create time dummy variables
if 'timedum_1' not in df.columns:
    print("\nCreating time dummy variables...")
    for w in df['week'].unique():
        df[f'timedum_{int(w)}'] = (df['week'] == w).astype(int)

# Get time variables
time_vars = sorted([col for col in df.columns if col.startswith('timedum_')], 
                   key=lambda x: int(x.split('_')[1]))
time_vars_for_formula = time_vars[1:]  # Drop first as reference
interaction_terms = ' + '.join([f'treated:{tv}' for tv in time_vars])
time_str = ' + '.join(time_vars_for_formula)

# MODEL 1: Pooled OLS with Controls
print("\n" + "="*80)
print("MODEL 1: Pooled OLS with Control Variables")
print("="*80)

control_vars = ['age_years', 'price_usd', 'review_score', 'C(genre_category)']
control_str = ' + '.join(control_vars)
formula1 = f'ln_players ~ treated + {time_str} + {interaction_terms} + {control_str} - 1'

print(f"Running regression...")
model1 = smf.ols(formula1, data=df).fit(cov_type='cluster', 
                                        cov_kwds={'groups': df['appid']})

# Extract coefficients for Model 1
params1 = model1.params
conf_int1 = model1.conf_int()

coefs1 = []
for param_name in params1.index:
    if 'treated:timedum_' in param_name:
        time_num = param_name.split('timedum_')[1]
        time_idx = int(time_num)
        coefs1.append({
            'week': time_idx,
            'estimate': params1[param_name],
            'conf_low': conf_int1.loc[param_name, 0],
            'conf_high': conf_int1.loc[param_name, 1],
            'se': model1.bse[param_name],
            'pvalue': model1.pvalues[param_name]
        })

coefs1_df = pd.DataFrame(sorted(coefs1, key=lambda x: x['week']))

print("\nCoefficient Estimates:")
print("-"*80)
print(f"{'Week':<10} {'Estimate':>10} {'Std Err':>10} {'P-value':>10} {'95% CI Lower':>12} {'95% CI Upper':>12}")
print("-"*80)
for _, row in coefs1_df.iterrows():
    print(f"Week {row['week']:<5} {row['estimate']:>10.4f} {row['se']:>10.4f} "
          f"{row['pvalue']:>10.4f} {row['conf_low']:>12.4f} {row['conf_high']:>12.4f}")

# MODEL 2: Two-Way Fixed Effects
print("\n" + "="*80)
print("MODEL 2: Two-Way Fixed Effects")
print("="*80)

formula2 = f'ln_players ~ {interaction_terms} + {time_str} + C(appid) - 1'

print(f"Running regression...")
model2 = smf.ols(formula2, data=df).fit(cov_type='cluster', 
                                        cov_kwds={'groups': df['appid']})

# Extract coefficients for Model 2
params2 = model2.params
conf_int2 = model2.conf_int()

coefs2 = []
for param_name in params2.index:
    if 'treated:timedum_' in param_name:
        time_num = param_name.split('timedum_')[1]
        time_idx = int(time_num)
        coefs2.append({
            'week': time_idx,
            'estimate': params2[param_name],
            'conf_low': conf_int2.loc[param_name, 0],
            'conf_high': conf_int2.loc[param_name, 1],
            'se': model2.bse[param_name],
            'pvalue': model2.pvalues[param_name]
        })

coefs2_df = pd.DataFrame(sorted(coefs2, key=lambda x: x['week']))

print("\nCoefficient Estimates:")
print("-"*80)
print(f"{'Week':<10} {'Estimate':>10} {'Std Err':>10} {'P-value':>10} {'95% CI Lower':>12} {'95% CI Upper':>12}")
print("-"*80)
for _, row in coefs2_df.iterrows():
    print(f"Week {row['week']:<5} {row['estimate']:>10.4f} {row['se']:>10.4f} "
          f"{row['pvalue']:>10.4f} {row['conf_low']:>12.4f} {row['conf_high']:>12.4f}")

# CREATE PLOTS
fig, axes = plt.subplots(1, 2, figsize=(16, 7))

week_labels = ['Week 1\n(Feb 1-7)', 'Week 2\n(Feb 8-14)', 'Week 3\n(Feb 15-21)', 'Week 4\n(Feb 22-28)']
treatment_week = 2.5  # Treatment occurs between Week 2 and Week 3

# Plot 1: Model 1 (Pooled OLS)
ax1 = axes[0]
x_positions = range(len(coefs1_df))

ax1.errorbar(x_positions, coefs1_df['estimate'], 
            yerr=[coefs1_df['estimate'] - coefs1_df['conf_low'],
                  coefs1_df['conf_high'] - coefs1_df['estimate']],
            fmt='o', markersize=10, capsize=6, capthick=2,
            color='coral', ecolor='coral', label='DiD Estimate')

ax1.axhline(y=0, linestyle='--', color='gray', linewidth=1.5, alpha=0.7)
ax1.axvline(x=treatment_week, linestyle='--', color='red', 
           linewidth=2, alpha=0.8, label='Treatment Time\n(Feb 15)')

ax1.set_xlabel('Time Period', fontsize=12, fontweight='bold')
ax1.set_ylabel('Coefficient Estimate', fontsize=12, fontweight='bold')
ax1.set_title('Model 1: Pooled OLS with Control Variables\nDiD Coefficients Over Time',
             fontsize=13, fontweight='bold')
ax1.set_xticks(x_positions)
ax1.set_xticklabels(week_labels, fontsize=10)
ax1.legend(loc='best', framealpha=0.9, fontsize=10)
ax1.grid(True, alpha=0.3)

# Plot 2: Model 2 (Two-Way FE)
ax2 = axes[1]

ax2.errorbar(x_positions, coefs2_df['estimate'], 
            yerr=[coefs2_df['estimate'] - coefs2_df['conf_low'],
                  coefs2_df['conf_high'] - coefs2_df['estimate']],
            fmt='o', markersize=10, capsize=6, capthick=2,
            color='steelblue', ecolor='steelblue', label='DiD Estimate')

ax2.axhline(y=0, linestyle='--', color='gray', linewidth=1.5, alpha=0.7)
ax2.axvline(x=treatment_week, linestyle='--', color='red', 
           linewidth=2, alpha=0.8, label='Treatment Time\n(Feb 15)')

ax2.set_xlabel('Time Period', fontsize=12, fontweight='bold')
ax2.set_ylabel('Coefficient Estimate', fontsize=12, fontweight='bold')
ax2.set_title('Model 2: Two-Way Fixed Effects\nDiD Coefficients Over Time',
             fontsize=13, fontweight='bold')
ax2.set_xticks(x_positions)
ax2.set_xticklabels(week_labels, fontsize=10)
ax2.legend(loc='best', framealpha=0.9, fontsize=10)
ax2.grid(True, alpha=0.3)

plt.tight_layout()

save_path = 'february_2025_did_coefficients_over_time.png'
plt.savefig(save_path, dpi=300, bbox_inches='tight')
print(f"\n[OK] Plot saved to: {save_path}")

print("\n" + "="*80)
print("COMPLETE!")
print("="*80)
print("\nGenerated file:")
print("  - february_2025_did_coefficients_over_time.png")
print("="*80)
