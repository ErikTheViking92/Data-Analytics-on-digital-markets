"""
Create Event Study Plot for Staggered DiD Analysis
===================================================

Event study plot showing treatment effects over calendar time with:
- 5 months: Dec 2024 - Apr 2025
- Vertical dashed lines for each cohort's treatment timing
- 95% confidence intervals
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

def load_panel_data(filepath):
    """Load panel data from CSV"""
    return pd.read_csv(filepath)

def run_event_study_model(df, model_type='fe'):
    """
    Run event study regression with time period dummies interacted with treatment
    
    Parameters:
    -----------
    df : DataFrame
        Panel data
    model_type : str
        'fe' for fixed effects (Model 2), 'pooled' for pooled OLS with controls (Model 1)
    """
    # Create time dummies for all periods
    time_vars = [col for col in df.columns if col.startswith('timedum_')]
    
    # Create interaction terms for each time period
    interaction_terms = ' + '.join([f'treated:{tv}' for tv in time_vars])
    time_str = ' + '.join(time_vars)
    
    if model_type == 'pooled':
        # Model 1: Pooled OLS with control variables
        control_vars = []
        if 'age_years' in df.columns:
            control_vars.append('age_years')
        if 'price_usd' in df.columns:
            control_vars.append('price_usd')
        if 'review_score' in df.columns:
            control_vars.append('review_score')
        if 'genre_category' in df.columns:
            control_vars.append('C(genre_category)')
        
        control_str = ' + '.join(control_vars) if control_vars else ''
        formula = f'ln_players ~ treated + post + {time_str} + {interaction_terms}'
        if control_str:
            formula += f' + {control_str}'
    else:
        # Model 2: Game and time fixed effects
        formula = f'ln_players ~ {interaction_terms} + {time_str} + C(appid)'
    
    # Fit model with cluster-robust standard errors
    model = smf.ols(formula, data=df).fit(cov_type='cluster', 
                                          cov_kwds={'groups': df['appid']})
    
    return model

def create_event_study_plot(df, model_type='fe', save_path=None):
    """
    Create event study plot in calendar time with treatment timing indicators
    
    Parameters:
    -----------
    df : DataFrame
        Panel data
    model_type : str
        'fe' for Model 2 (fixed effects), 'pooled' for Model 1 (with controls)
    save_path : str
        Path to save the plot
    """
    model_name = "Model 2 (Fixed Effects)" if model_type == 'fe' else "Model 1 (Pooled OLS with Controls)"
    
    print("\n" + "="*80)
    print(f"CREATING EVENT STUDY PLOT - {model_name}")
    print("="*80)
    
    # Run event study model
    print("Running event study regression...")
    model = run_event_study_model(df, model_type=model_type)
    
    # Extract coefficients for treated:timedum_ interactions
    params = model.params
    conf_int = model.conf_int()
    
    # Get treatment effects for each time period
    time_effects = []
    
    for i in range(1, 6):  # 5 time periods
        param_name = f'treated:timedum_{i}'
        if param_name in params.index:
            time_effects.append({
                'month': i,
                'estimate': params[param_name],
                'conf_low': conf_int.loc[param_name, 0],
                'conf_high': conf_int.loc[param_name, 1],
                'se': model.bse[param_name]
            })
        else:
            # If not in model, it might be the reference category
            time_effects.append({
                'month': i,
                'estimate': 0.0,
                'conf_low': 0.0,
                'conf_high': 0.0,
                'se': 0.0
            })
    
    plot_data = pd.DataFrame(time_effects)
    
    # Determine pre/post treatment status for each month
    # In staggered design, Dec (month 1) is pre-treatment for all
    # Jan-Apr have mixed treatment status
    plot_data['is_pre'] = plot_data['month'] == 1
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Define month labels
    month_labels = ['Dec 2024', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025']
    
    # Plot pre-treatment points (orange circles)
    pre_data = plot_data[plot_data['is_pre']]
    if len(pre_data) > 0:
        ax.errorbar(pre_data['month'] - 1, pre_data['estimate'],
                   yerr=[pre_data['estimate'] - pre_data['conf_low'],
                         pre_data['conf_high'] - pre_data['estimate']],
                   fmt='o', markersize=10, capsize=6, capthick=2,
                   color='coral', ecolor='coral', 
                   label='Pre-Treatment', zorder=3)
    
    # Plot post-treatment points (blue squares)
    post_data = plot_data[~plot_data['is_pre']]
    if len(post_data) > 0:
        ax.errorbar(post_data['month'] - 1, post_data['estimate'],
                   yerr=[post_data['estimate'] - post_data['conf_low'],
                         post_data['conf_high'] - post_data['estimate']],
                   fmt='s', markersize=10, capsize=6, capthick=2,
                   color='steelblue', ecolor='steelblue',
                   label='Post-Treatment', zorder=3)
    
    # Add horizontal line at zero
    ax.axhline(y=0, linestyle='-', color='black', linewidth=1, alpha=0.5, zorder=1)
    
    # Add vertical dashed lines for treatment timing
    # January cohort: treated at month 2 (Jan 2025) - between Dec and Jan
    # February cohort: treated at month 3 (Feb 2025) - between Jan and Feb
    # March cohort: treated at month 4 (Mar 2025) - between Feb and Mar
    # April cohort: treated at month 5 (Apr 2025) - between Mar and Apr
    
    treatment_months = [
        (0.5, 'Jan Cohort'),
        (1.5, 'Feb Cohort'),
        (2.5, 'Mar Cohort'),
        (3.5, 'Apr Cohort')
    ]
    
    for x_pos, label in treatment_months:
        ax.axvline(x=x_pos, linestyle='--', color='red', 
                  linewidth=2, alpha=0.8, zorder=2, label='Treatment Time' if x_pos == 0.5 else '')
    
    # Add background shading for pre-treatment period
    ax.axvspan(-0.5, 0.5, alpha=0.15, color='yellow', zorder=0, label='Pre-Treatment Period')
    ax.axvspan(0.5, 4.5, alpha=0.08, color='lightblue', zorder=0, label='Post-Treatment Period')
    
    # Set y-axis limits to zoom in on the data range
    y_min = plot_data['conf_low'].min()
    y_max = plot_data['conf_high'].max()
    y_range = y_max - y_min
    y_margin = y_range * 0.3  # 30% margin
    ax.set_ylim(y_min - y_margin, y_max + y_margin)
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=13, fontweight='bold')
    ax.set_ylabel('Coefficient Estimate', fontsize=13, fontweight='bold')
    title = f'DiD Coefficients Over Time - {model_name}\nSTAGGERED (Jan-Apr 2025 Treatment Groups)'
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(range(5))
    ax.set_xticklabels(month_labels, fontsize=11)
    ax.legend(loc='upper left', fontsize=10, framealpha=0.9)
    ax.grid(True, alpha=0.3, zorder=0)
    
    # Add text annotations for treatment timing
    y_top = ax.get_ylim()[1]
    annotation_y = y_top - (y_range * 0.05)  # 5% down from top
    for x_pos, label in treatment_months:
        ax.text(x_pos, annotation_y, label, 
               rotation=90, verticalalignment='top', horizontalalignment='right',
               fontsize=9, color='red', alpha=0.9, fontweight='bold')
    
    plt.tight_layout()
    
    # Save plot
    if save_path is None:
        save_path = f'staggered_event_study_calendar_time_{model_type}.png'
    
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"[OK] Event study plot saved to: {save_path}")
    
    # Print coefficient table
    print("\nTreatment Effect Estimates by Month:")
    print("="*70)
    print(f"{'Month':<15} {'Estimate':>10} {'Std Err':>10} {'95% CI Lower':>12} {'95% CI Upper':>12}")
    print("-"*70)
    for _, row in plot_data.iterrows():
        print(f"{month_labels[row['month']-1]:<15} {row['estimate']:>10.4f} {row['se']:>10.4f} "
              f"{row['conf_low']:>12.4f} {row['conf_high']:>12.4f}")
    print("="*70)
    
    return fig

def main():
    """Main function"""
    print("="*80)
    print("EVENT STUDY PLOT GENERATOR - CALENDAR TIME")
    print("="*80)
    
    # Load staggered panel data
    df = load_panel_data('staggered_panel_2025.csv')
    
    print(f"\nData loaded: {len(df)} observations from {df['appid'].nunique()} games")
    print(f"Time periods: {sorted(df['period'].unique())}")
    print(f"Months: {sorted(df['month'].unique())}")
    
    # Create event study plot for Model 1 (Pooled OLS with Controls)
    fig_model1 = create_event_study_plot(df, model_type='pooled', 
                                         save_path='staggered_event_study_calendar_time_model1.png')
    
    # Create event study plot for Model 2 (Fixed Effects)
    fig_model2 = create_event_study_plot(df, model_type='fe',
                                         save_path='staggered_event_study_calendar_time_model2.png')
    
    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print("\nGenerated files:")
    print("  - staggered_event_study_calendar_time_model1.png (Pooled OLS with Controls)")
    print("  - staggered_event_study_calendar_time_model2.png (Fixed Effects)")
    print("="*80)

if __name__ == "__main__":
    main()
