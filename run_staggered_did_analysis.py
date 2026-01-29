"""
Run Staggered DiD Analysis on 2025 Major Patches
Creates a google.csv-style dataset with explicit dummy variables
"""

import pandas as pd
import numpy as np
import json
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import ols
from statsmodels.iolib.summary2 import summary_col
from datetime import datetime
from scraper.steamcharts_scraper import fetch_monthly_series

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)


def fetch_current_players(appid: int):
    """Fetch current player count from Steam API."""
    import requests
    url = "https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/"
    try:
        resp = requests.get(url, params={"appid": appid}, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", {}).get("player_count")
    except Exception:
        return None


def load_staggered_groups():
    """Load all treatment groups and control group."""
    print("Loading staggered treatment groups and control...")
    
    with open("staggered_jan_group.json", "r", encoding="utf-8") as f:
        jan_group = json.load(f)
    
    with open("staggered_feb_group.json", "r", encoding="utf-8") as f:
        feb_group = json.load(f)
    
    with open("staggered_mar_group.json", "r", encoding="utf-8") as f:
        mar_group = json.load(f)
    
    with open("staggered_apr_group.json", "r", encoding="utf-8") as f:
        apr_group = json.load(f)
    
    with open("staggered_control_group.json", "r", encoding="utf-8") as f:
        control_group = json.load(f)
    
    print(f"  January group: {len(jan_group)} games")
    print(f"  February group: {len(feb_group)} games")
    print(f"  March group: {len(mar_group)} games")
    print(f"  April group: {len(apr_group)} games")
    print(f"  Control group: {len(control_group)} games")
    
    return jan_group, feb_group, mar_group, apr_group, control_group


def create_staggered_panel_google_style():
    """
    Create panel dataset similar to google.csv with explicit dummy variables.
    
    Time periods: Dec 2024 - Jun 2025 (7 months)
    Treatment timing:
    - Jan group: treated in Jan 2025 (month 2)
    - Feb group: treated in Feb 2025 (month 3)
    - Mar group: treated in Mar 2025 (month 4)
    - Apr group: treated in Apr 2025 (month 5)
    - Control: never treated
    """
    print("\n" + "="*80)
    print("CREATING STAGGERED DiD PANEL DATASET (GOOGLE.CSV STYLE)")
    print("="*80)
    
    jan_games, feb_games, mar_games, apr_games, control_games = load_staggered_groups()
    
    # Define analysis months
    months = pd.date_range('2024-12-01', '2025-06-01', freq='MS')
    month_labels = [m.strftime('%Y-%m') for m in months]
    n_periods = len(months)
    
    print(f"\nTime periods: {n_periods} months from {month_labels[0]} to {month_labels[-1]}")
    print(f"Treatment timing:")
    print(f"  - January group: Month 2 ({month_labels[1]})")
    print(f"  - February group: Month 3 ({month_labels[2]})")
    print(f"  - March group: Month 4 ({month_labels[3]})")
    print(f"  - April group: Month 5 ({month_labels[4]})")
    
    rows = []
    game_id = 1
    
    def process_group(games, group_name, treatment_month_idx):
        """Process a treatment or control group."""
        nonlocal game_id
        
        for game_entry in games:
            appid = game_entry["appid"]
            name = game_entry["name"]
            
            # Fetch historical monthly data
            monthly_data = fetch_monthly_series(appid)
            
            # Create lookup dict by month
            monthly_lookup = {}
            for entry in monthly_data:
                try:
                    date_str = entry.get("date", "")
                    if date_str:
                        date_obj = datetime.strptime(date_str, "%Y-%m")
                        month_key = date_obj.strftime('%Y-%m')
                        monthly_lookup[month_key] = entry.get("value", 0)
                except:
                    pass
            
            # Get current players as fallback
            current_players = fetch_current_players(appid)
            
            # Create row for each time period
            for period_idx, month in enumerate(months):
                month_key = month.strftime('%Y-%m')
                
                # Get player count
                players = monthly_lookup.get(month_key)
                if players is None or players == 0:
                    players = current_players if current_players else 1000  # Fallback
                
                # Treatment indicator (1 for treatment groups, 0 for control)
                treated = 1 if group_name != 'control' else 0
                
                # Post-treatment indicator
                if group_name == 'control':
                    post = 0  # Control never gets treatment
                else:
                    post = 1 if period_idx >= treatment_month_idx else 0
                
                # DiD interaction
                did = treated * post
                
                # Create time dummies (timedum_1 to timedum_7)
                time_dummies = {f'timedum_{i+1}': 1 if period_idx == i else 0 
                               for i in range(n_periods)}
                
                # Create DiD dummies (diddum_1 to diddum_7)
                did_dummies = {f'diddum_{i+1}': treated * time_dummies[f'timedum_{i+1}']
                              for i in range(n_periods)}
                
                # Build row
                row = {
                    'id': game_id,
                    'appid': appid,
                    'name': name,
                    'treatment_group': group_name,
                    'treated': treated,
                    'post': post,
                    'did': did,
                    'period': period_idx + 1,
                    'month': month_key,
                    'players': players,
                    'ln_players': np.log(players),
                }
                
                # Add time dummies
                row.update(time_dummies)
                
                # Add DiD dummies
                row.update(did_dummies)
                
                rows.append(row)
            
            game_id += 1
            
            if game_id % 50 == 0:
                print(f"  Processed {game_id-1} games...")
    
    # Process all groups
    print("\nProcessing games and collecting historical data...")
    process_group(jan_games, 'jan', treatment_month_idx=1)    # Treated in month 2 (Jan 2025)
    process_group(feb_games, 'feb', treatment_month_idx=2)    # Treated in month 3 (Feb 2025)
    process_group(mar_games, 'mar', treatment_month_idx=3)    # Treated in month 4 (Mar 2025)
    process_group(apr_games, 'apr', treatment_month_idx=4)    # Treated in month 5 (Apr 2025)
    process_group(control_games, 'control', treatment_month_idx=None)  # Never treated
    
    df = pd.DataFrame(rows)
    
    print(f"\n{'='*80}")
    print(f"Panel dataset created:")
    print(f"  Total observations: {len(df)}")
    print(f"  Unique games: {df['appid'].nunique()}")
    print(f"  Time periods: {df['period'].nunique()}")
    print(f"  Treatment groups: {df['treatment_group'].value_counts().to_dict()}")
    print(f"{'='*80}")
    
    # Save to CSV
    output_file = "staggered_panel_2025.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved panel data to: {output_file}")
    
    return df


def run_did_regression(df):
    """Run DiD regression models."""
    print("\n" + "="*80)
    print("STAGGERED DIFFERENCE-IN-DIFFERENCES REGRESSION ANALYSIS")
    print("="*80)
    
    # Model 1: Basic DiD with time fixed effects
    print("\nModel 1: Basic Staggered DiD")
    print("-" * 60)
    
    # Build formula with time dummies (exclude timedum_1 as reference)
    time_vars = [f'timedum_{i}' for i in range(2, 8)]
    formula1 = f"ln_players ~ treated + post + did + {' + '.join(time_vars)}"
    
    model1 = ols(formula1, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    print(model1.summary())
    
    # Model 2: With game fixed effects
    print("\n\nModel 2: Staggered DiD with Game Fixed Effects")
    print("-" * 60)
    
    formula2 = f"ln_players ~ did + C(appid) + {' + '.join(time_vars)}"
    model2 = ols(formula2, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    print(model2.summary())
    
    # Model 3: Event study with separate time period interactions
    print("\n\nModel 3: Event Study (Time-Period DiD Interactions)")
    print("-" * 60)
    
    # Use diddum variables (exclude diddum_1 as reference)
    did_vars = [f'diddum_{i}' for i in range(2, 8)]
    formula3 = f"ln_players ~ {' + '.join(did_vars)} + C(appid) + {' + '.join(time_vars)}"
    
    model3 = ols(formula3, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    print(model3.summary())
    
    # Extract and display key results
    print("\n" + "="*80)
    print("KEY RESULTS SUMMARY")
    print("="*80)
    
    did_coef = model1.params.get('did', np.nan)
    did_se = model1.bse.get('did', np.nan)
    did_pval = model1.pvalues.get('did', np.nan)
    did_ci = model1.conf_int().loc['did'] if 'did' in model1.params else [np.nan, np.nan]
    
    print(f"\nStaggered DiD Coefficient (Average Treatment Effect):")
    print(f"  Coefficient: {did_coef:.4f}")
    print(f"  Std. Error:  {did_se:.4f}")
    print(f"  P-value:     {did_pval:.4f}")
    print(f"  95% CI:      [{did_ci[0]:.4f}, {did_ci[1]:.4f}]")
    print(f"  Significant: {'Yes ***' if did_pval < 0.01 else 'Yes **' if did_pval < 0.05 else 'Yes *' if did_pval < 0.1 else 'No'}")
    
    percent_change = (np.exp(did_coef) - 1) * 100
    print(f"\nInterpretation:")
    print(f"  Major patches are associated with a {percent_change:.2f}% change in player counts")
    print(f"  (averaged across all treatment groups and post-treatment periods)")
    
    # Save results
    results = {
        "model": "Staggered DiD",
        "did_coefficient": float(did_coef),
        "std_error": float(did_se),
        "p_value": float(did_pval),
        "ci_lower": float(did_ci[0]),
        "ci_upper": float(did_ci[1]),
        "percent_change": float(percent_change),
        "n_observations": int(model1.nobs),
        "n_games": int(df['appid'].nunique()),
        "r_squared": float(model1.rsquared),
        "adj_r_squared": float(model1.rsquared_adj)
    }
    
    with open("staggered_did_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: staggered_did_results.json")
    
    print("="*80)
    
    return model1, model2, model3


def plot_event_study(df):
    """Create event study plot showing DiD coefficients over time."""
    print("\n" + "="*80)
    print("CREATING EVENT STUDY PLOT")
    print("="*80)
    
    # Run event study regression
    time_vars = [f'timedum_{i}' for i in range(2, 8)]
    did_vars = [f'diddum_{i}' for i in range(2, 8)]
    formula = f"ln_players ~ {' + '.join(did_vars)} + C(appid) + {' + '.join(time_vars)}"
    
    model = ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Extract coefficients
    coefs_data = []
    
    # Add reference period (diddum_1 = 0)
    coefs_data.append({
        'period': 1,
        'month': '2024-12',
        'coef': 0.0,
        'ci_low': 0.0,
        'ci_high': 0.0
    })
    
    # Extract other periods
    for i in range(2, 8):
        var_name = f'diddum_{i}'
        if var_name in model.params:
            coef = model.params[var_name]
            ci = model.conf_int().loc[var_name]
            
            # Get month label
            month_labels = ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06']
            
            coefs_data.append({
                'period': i,
                'month': month_labels[i-1],
                'coef': coef,
                'ci_low': ci[0],
                'ci_high': ci[1]
            })
    
    coefs_df = pd.DataFrame(coefs_data)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Determine pre/post treatment colors
    # Treatment starts at different times for different groups
    # We'll color based on average treatment timing (around month 3-4)
    colors = ['coral' if p < 3 else 'steelblue' for p in coefs_df['period']]
    
    # Plot coefficients with error bars
    for idx, row in coefs_df.iterrows():
        color = 'coral' if row['period'] < 3 else 'steelblue'
        marker = 'o' if row['period'] < 3 else 's'
        
        ax.errorbar(row['period'], row['coef'],
                   yerr=[[row['coef'] - row['ci_low']], [row['ci_high'] - row['coef']]],
                   fmt=marker, markersize=10, capsize=6, capthick=2,
                   color=color, ecolor='gray', linewidth=2, alpha=0.9)
    
    # Add reference lines
    ax.axhline(y=0, color='black', linestyle='-', linewidth=2, alpha=0.8, zorder=1)
    ax.axvline(x=2.5, color='red', linestyle='--', linewidth=3, alpha=0.7,
              label='Treatment Period (Staggered)', zorder=1)
    
    # Shaded regions
    ax.axvspan(0.5, 2.5, alpha=0.1, color='orange', label='Pre-Treatment')
    ax.axvspan(2.5, 7.5, alpha=0.1, color='lightblue', label='Post-Treatment (Staggered)')
    
    # Formatting
    ax.set_xlabel('Time Period (Months)', fontsize=14, fontweight='bold')
    ax.set_ylabel('Treatment Effect on Log(Player Count)', fontsize=14, fontweight='bold')
    ax.set_title('Staggered DiD Event Study: Effect of Major Patches on Player Counts\n' +
                'Jan-Apr 2025 Treatment Groups (N=100 per group, 100 control)',
                fontsize=15, fontweight='bold', pad=20)
    
    # Customize legend
    ax.legend(loc='upper left', fontsize=11, framealpha=0.95, edgecolor='black')
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    # Set axis limits and ticks
    ax.set_xlim(0.5, 7.5)
    ax.set_xticks(coefs_df['period'])
    ax.set_xticklabels([f"M{p}\n{m}" for p, m in zip(coefs_df['period'], coefs_df['month'])])
    
    plt.tight_layout()
    
    # Save
    filename = 'staggered_did_event_study.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Event study plot saved to: {filename}")
    plt.show()
    
    return fig, coefs_df


def main():
    """Main analysis workflow."""
    print("\n" + "="*80)
    print("STAGGERED DIFFERENCE-IN-DIFFERENCES ANALYSIS")
    print("Steam Major Patches - January to April 2025")
    print("="*80)
    
    # Step 1: Create panel dataset
    df = create_staggered_panel_google_style()
    
    # Step 2: Run DiD regressions
    model1, model2, model3 = run_did_regression(df)
    
    # Step 3: Create event study plot
    fig, coefs_df = plot_event_study(df)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nFiles created:")
    print("  1. staggered_panel_2025.csv - Panel dataset (google.csv style)")
    print("  2. staggered_did_results.json - Regression results summary")
    print("  3. staggered_did_event_study.png - Event study visualization")
    print("="*80)


if __name__ == "__main__":
    main()
