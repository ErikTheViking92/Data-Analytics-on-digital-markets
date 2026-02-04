"""
Create DiD Coefficient Over Time Plot for February 2025 Analysis
================================================================

Generates coefficient estimates over time periods with confidence intervals
and treatment timing indicator.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf

sns.set_style("whitegrid")

def create_february_coefficient_plot():
    """Create DiD coefficient plot for February analysis"""
    
    print("="*80)
    print("FEBRUARY 2025 - DiD COEFFICIENT OVER TIME PLOT")
    print("="*80)
    
    # Load panel data
    try:
        df = pd.read_csv('february_2025_panel_data_improved.csv')
        print(f"\nData loaded: {len(df)} observations from {df['appid'].nunique()} games")
    except FileNotFoundError:
        print("\nError: february_2025_panel_data_improved.csv not found.")
        print("Please run the improved February analysis first.")
        return None
    
    # Check available time variables
    print(f"Available columns: {df.columns.tolist()}")
    print(f"Unique weeks/periods: {sorted(df['week'].unique())}")
    
    # Create time dummy variables if they don't exist
    if 'timedum_1' not in df.columns:
        print("\nCreating time dummy variables...")
        for w in df['week'].unique():
            df[f'timedum_{int(w)}'] = (df['week'] == w).astype(int)
    
    # Run Model 1: Pooled OLS with time interactions
    print("\n" + "-"*80)
    print("MODEL 1: Pooled OLS with Control Variables")
    print("-"*80)
    
    time_vars = [col for col in df.columns if col.startswith('timedum_')]
    time_vars_sorted = sorted(time_vars, key=lambda x: int(x.split('_')[1]))
    
    # Drop first time dummy to avoid multicollinearity
    time_vars_for_formula = time_vars_sorted[1:]  # Drop timedum_1 as reference
    
    interaction_terms = ' + '.join([f'treated:{tv}' for tv in time_vars_sorted])
    time_str = ' + '.join(time_vars_for_formula)
    
    control_vars = []
    if 'age_years' in df.columns:
        control_vars.append('age_years')
    if 'price_usd' in df.columns:
        control_vars.append('price_usd')
    if 'review_score' in df.columns:
        control_vars.append('review_score')
    if 'genre_category' in df.columns and df['genre_category'].nunique() > 1:
        control_vars.append('C(genre_category)')
    
    control_str = ' + '.join(control_vars) if control_vars else ''
    formula1 = f'ln_players ~ treated + {time_str} + {interaction_terms}'
    if control_str:
        formula1 += f' + {control_str}'
    
    # Add intercept suppression to avoid multicollinearity
    formula1 += ' - 1'
    
    print(f"Formula: {formula1}")
    print(f"Running regression...")
    model1 = smf.ols(formula1, data=df).fit(cov_type='cluster', 
                                            cov_kwds={'groups': df['appid']})
    
    # Run Model 2: Two-way fixed effects with time interactions
    print("\n" + "-"*80)
    print("MODEL 2: Two-Way Fixed Effects")
    print("-"*80)
    
    # Drop first time dummy for Model 2 as well
    formula2 = f'ln_players ~ {interaction_terms} + {time_str} + C(appid)'
    
    print(f"Running regression...")
    model2 = smf.ols(formula2, data=df).fit(cov_type='cluster', 
                                            cov_kwds={'groups': df['appid']})
    
    # Extract coefficients for both models
    def extract_coefficients(model, model_name):
        params = model.params
        conf_int = model.conf_int()
        
        coefs = []
        for param_name in params.index:
            if 'treated:timedum_' in param_name:
                time_num = param_name.split('timedum_')[1]
                try:
                    time_idx = int(time_num)
                    coefs.append({
                        'time_idx': time_idx,
                        'estimate': params[param_name],
                        'conf_low': conf_int.loc[param_name, 0],
                        'conf_high': conf_int.loc[param_name, 1],
                        'se': model.bse[param_name]
                    })
                except ValueError:
                    continue
        
        coefs = sorted(coefs, key=lambda x: x['time_idx'])
        return pd.DataFrame(coefs)
    
    coefs_model1 = extract_coefficients(model1, "Model 1")
    coefs_model2 = extract_coefficients(model2, "Model 2")
    
    # Determine time labels based on actual data
    unique_weeks = sorted(df['week'].unique())
    if 'month' in df.columns:
        # Use month labels if available
        month_map = df.groupby('week')['month'].first().to_dict()
        time_labels = [month_map.get(w, f'Period {w}') for w in unique_weeks]
    else:
        time_labels = [f'Week {w}' for w in unique_weeks]
    
    # Treatment timing: between pre and post periods
    # Find the transition point
    post_values = df.groupby('week')['post'].mean()
    treatment_week_idx = None
    for i in range(len(unique_weeks) - 1):
        if post_values[unique_weeks[i]] < 0.5 and post_values[unique_weeks[i+1]] >= 0.5:
            treatment_week_idx = i + 0.5
            break
    
    if treatment_week_idx is None:
        # Default to middle
        treatment_week_idx = len(unique_weeks) / 2
    
    # Create plots for both models
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    
    for idx, (coefs, model_name, ax) in enumerate([
        (coefs_model1, "Model 1 (Pooled OLS with Controls)", axes[0]),
        (coefs_model2, "Model 2 (Two-Way Fixed Effects)", axes[1])
    ]):
        if len(coefs) == 0:
            ax.text(0.5, 0.5, 'No coefficients to plot', 
                   ha='center', va='center', transform=ax.transAxes)
            continue
        
        # Plot points and error bars
        x_positions = range(len(coefs))
        ax.errorbar(x_positions, coefs['estimate'], 
                   yerr=[coefs['estimate'] - coefs['conf_low'],
                         coefs['conf_high'] - coefs['estimate']],
                   fmt='o', markersize=8, capsize=5, capthick=2,
                   color='steelblue', ecolor='steelblue', label='DiD Estimate')
        
        # Add horizontal line at zero
        ax.axhline(y=0, linestyle='--', color='gray', linewidth=1, alpha=0.7)
        
        # Add vertical line at treatment time
        if treatment_week_idx is not None:
            ax.axvline(x=treatment_week_idx, linestyle='--', color='red', 
                      linewidth=2, alpha=0.8, label='Treatment Time')
        
        # Formatting
        ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
        ax.set_ylabel('Coefficient Estimate', fontsize=12, fontweight='bold')
        ax.set_title(f'DiD Coefficients Over Time\n{model_name}', 
                    fontsize=13, fontweight='bold')
        ax.set_xticks(x_positions)
        ax.set_xticklabels([time_labels[coefs.iloc[i]['time_idx']-1] 
                           for i in range(len(coefs))], rotation=0)
        ax.legend(loc='best', framealpha=0.9)
        ax.grid(True, alpha=0.3)
        
        # Print coefficient table
        print(f"\n{model_name} - Coefficient Estimates:")
        print("="*70)
        print(f"{'Period':<15} {'Estimate':>10} {'Std Err':>10} {'95% CI Lower':>12} {'95% CI Upper':>12}")
        print("-"*70)
        for _, row in coefs.iterrows():
            period_label = time_labels[row['time_idx']-1]
            print(f"{period_label:<15} {row['estimate']:>10.4f} {row['se']:>10.4f} "
                  f"{row['conf_low']:>12.4f} {row['conf_high']:>12.4f}")
        print("="*70)
    
    plt.tight_layout()
    
    # Save plot
    save_path = 'february_2025_did_coefficients_plot_improved.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"\n[OK] Plot saved to: {save_path}")
    
    return fig

if __name__ == "__main__":
    create_february_coefficient_plot()
    
    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print("\nGenerated file:")
    print("  - february_2025_did_coefficients_plot_improved.png")
    print("="*80)
