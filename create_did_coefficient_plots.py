"""
Generate DiD Coefficients Over Time Plots
==========================================

This script creates the "DiD Coefficients Over Time" plots with vertical treatment lines
and 95% confidence intervals for both February and Staggered analyses.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import statsmodels.formula.api as smf
from datetime import datetime

def load_panel_data(filepath):
    """Load panel data from CSV"""
    return pd.read_csv(filepath)

def run_did_model_with_time_interactions(df, model_type='pooled'):
    """
    Run DiD regression with time period interactions
    
    Parameters:
    -----------
    df : DataFrame
        Panel data
    model_type : str
        'pooled' for basic model, 'fe' for fixed effects
    """
    # Create interaction terms for each time period
    time_vars = [col for col in df.columns if col.startswith('timedum_')]
    
    # Build formula
    if model_type == 'pooled':
        # Basic DiD with time interactions
        interaction_terms = ' + '.join([f'treated:{tv}' for tv in time_vars])
        control_vars = []
        
        # Add control variables if they exist
        if 'age_years' in df.columns:
            control_vars.append('age_years')
        if 'price_usd' in df.columns:
            control_vars.append('price_usd')
        if 'review_score' in df.columns:
            control_vars.append('review_score')
        if 'genre_category' in df.columns:
            control_vars.append('C(genre_category)')
            
        control_str = ' + '.join(control_vars) if control_vars else ''
        time_str = ' + '.join(time_vars)
        
        formula = f'ln_players ~ treated + post + {time_str} + {interaction_terms}'
        if control_str:
            formula += f' + {control_str}'
            
    else:  # Fixed effects
        # Include game and time fixed effects
        interaction_terms = ' + '.join([f'treated:{tv}' for tv in time_vars])
        time_str = ' + '.join(time_vars)
        
        formula = f'ln_players ~ {interaction_terms} + {time_str} + C(appid)'
    
    # Fit model with cluster-robust standard errors
    model = smf.ols(formula, data=df).fit(cov_type='cluster', 
                                          cov_kwds={'groups': df['appid']})
    
    return model

def plot_did_coefficients_over_time(model, time_labels, treatment_period_idx=None, 
                                     save_path=None, title="DiD Coefficients Over Time"):
    """
    Plot DiD coefficients for each time period with confidence intervals
    
    Parameters:
    -----------
    model : statsmodels regression results
        Fitted model with time interactions
    time_labels : list
        Labels for each time period
    treatment_period_idx : float
        Index position where treatment occurs (for vertical line)
    save_path : str
        Path to save the plot
    title : str
        Plot title
    """
    # Extract coefficients and confidence intervals for treated:timedum_ interactions
    params = model.params
    conf_int = model.conf_int()
    
    # Find all interaction terms
    did_coefs = []
    time_periods = []
    
    for param_name in params.index:
        if 'treated:timedum_' in param_name:
            # Extract time period number
            time_num = param_name.split('timedum_')[1]
            try:
                time_idx = int(time_num) - 1  # Convert to 0-indexed
                did_coefs.append({
                    'time_idx': time_idx,
                    'time_label': time_labels[time_idx] if time_idx < len(time_labels) else f't{time_num}',
                    'estimate': params[param_name],
                    'conf_low': conf_int.loc[param_name, 0],
                    'conf_high': conf_int.loc[param_name, 1]
                })
            except (ValueError, IndexError):
                continue
    
    # Sort by time index
    did_coefs = sorted(did_coefs, key=lambda x: x['time_idx'])
    plot_data = pd.DataFrame(did_coefs)
    
    if len(plot_data) == 0:
        print("No DiD coefficients found to plot")
        return None
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Plot points and error bars
    x_positions = range(len(plot_data))
    ax.errorbar(x_positions, plot_data['estimate'], 
                yerr=[plot_data['estimate'] - plot_data['conf_low'],
                      plot_data['conf_high'] - plot_data['estimate']],
                fmt='o', markersize=8, capsize=5, capthick=2,
                color='steelblue', ecolor='steelblue', label='DiD Estimate')
    
    # Add horizontal line at zero
    ax.axhline(y=0, linestyle='--', color='gray', linewidth=1, alpha=0.7)
    
    # Add vertical line at treatment time
    if treatment_period_idx is not None:
        ax.axvline(x=treatment_period_idx, linestyle=':', color='red', 
                  linewidth=2, alpha=0.7, label='Treatment Time')
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Coefficient Estimate', fontsize=12, fontweight='bold')
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x_positions)
    ax.set_xticklabels(plot_data['time_label'])
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"[OK] Plot saved to: {save_path}")
    
    return fig

def create_february_coefficient_plot():
    """Create DiD coefficient plot for February 2025 analysis"""
    print("\n" + "="*80)
    print("CREATING FEBRUARY 2025 DiD COEFFICIENTS OVER TIME PLOT")
    print("="*80)
    
    # Load data
    df = load_panel_data('february_2025_panel_data.csv')
    
    # Check what time variables exist
    print(f"Available columns: {df.columns.tolist()}")
    
    # February uses 'week' variable (1-4), not timedum variables
    # Create timedum variables from week
    if 'week' in df.columns and 'timedum_1' not in df.columns:
        print("Creating timedum variables from week...")
        for w in df['week'].unique():
            df[f'timedum_{int(w)}'] = (df['week'] == w).astype(int)
    
    # Time labels for February analysis (4 weeks)
    time_labels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
    
    # Treatment occurs at week 2/3 boundary (after week 2)
    treatment_period_idx = 1.5  # Between week 2 and 3
    
    # Run model with time interactions
    print("Running DiD model with time interactions...")
    model = run_did_model_with_time_interactions(df, model_type='fe')
    
    # Create plot
    fig = plot_did_coefficients_over_time(
        model, 
        time_labels, 
        treatment_period_idx=treatment_period_idx,
        save_path='february_2025_did_coefficients_plot.png',
        title='DiD Coefficients Over Time - February 2025'
    )
    
    return fig

def create_staggered_coefficient_plot():
    """Create DiD coefficient plot for Staggered analysis"""
    print("\n" + "="*80)
    print("CREATING STAGGERED DiD COEFFICIENTS OVER TIME PLOT")
    print("="*80)
    
    # Load data
    df = load_panel_data('staggered_panel_2025.csv')
    
    # Time labels for Staggered analysis (5 months)
    time_labels = ['Dec 2024', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025']
    
    # Treatment occurs at different times for different cohorts
    # We'll mark the first treatment time (January cohort at month 2)
    treatment_period_idx = 1.5  # Between Dec and Jan (when first cohort gets treated)
    
    # Run model with time interactions
    print("Running DiD model with time interactions...")
    model = run_did_model_with_time_interactions(df, model_type='fe')
    
    # Create plot
    fig = plot_did_coefficients_over_time(
        model, 
        time_labels, 
        treatment_period_idx=treatment_period_idx,
        save_path='staggered_did_coefficients_plot.png',
        title='DiD Coefficients Over Time - Staggered Design'
    )
    
    return fig

def main():
    """Main function"""
    print("="*80)
    print("DiD COEFFICIENTS OVER TIME PLOT GENERATOR")
    print("="*80)
    
    # Create February plot
    try:
        feb_fig = create_february_coefficient_plot()
        print("✓ February plot created successfully")
    except Exception as e:
        print(f"✗ Error creating February plot: {e}")
    
    # Create Staggered plot
    try:
        stag_fig = create_staggered_coefficient_plot()
        print("✓ Staggered plot created successfully")
    except Exception as e:
        print(f"✗ Error creating Staggered plot: {e}")
    
    print("\n" + "="*80)
    print("COMPLETE!")
    print("="*80)
    print("\nGenerated files:")
    print("  - february_2025_did_coefficients_plot.png")
    print("  - staggered_did_coefficients_plot.png")
    print("="*80)

if __name__ == "__main__":
    main()
