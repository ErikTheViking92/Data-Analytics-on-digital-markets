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
    
    # Define analysis months (Dec 2024 - Apr 2025)
    months = pd.date_range('2024-12-01', '2025-04-01', freq='MS')
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
                
                # Create time dummies (timedum_1 to timedum_5)
                time_dummies = {f'timedum_{i+1}': 1 if period_idx == i else 0 
                               for i in range(n_periods)}
                
                # Create DiD dummies (diddum_1 to diddum_5)
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
    
    # Model 1: Basic DiD with time fixed effects (pooled OLS)
    print("\nModel 1: Basic Staggered DiD (Pooled OLS)")
    print("-" * 60)
    print("Dependent Variable: ln_players (natural log of player counts)")
    print("Reference Period: January 2025 (timedum_2)")
    
    # Build formula with time dummies (exclude timedum_2/January as reference)
    time_vars = ['timedum_1'] + [f'timedum_{i}' for i in range(3, 6)]
    formula1 = f"ln_players ~ treated + post + did + {' + '.join(time_vars)}"
    
    model1 = ols(formula1, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Display only key coefficients
    print("\nKey Coefficients:")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    
    coef_names = ['Intercept', 'treated', 'post', 'did'] + time_vars
    for var in coef_names:
        if var in model1.params:
            coef = model1.params[var]
            se = model1.bse[var]
            pval = model1.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\nModel Statistics:")
    print(f"  N observations: {model1.nobs:.0f}")
    print(f"  R-squared: {model1.rsquared:.4f}")
    print(f"  Cluster-robust standard errors (clustered by game)")
    
    # Model 2: With game fixed effects (absorbs time-invariant 'treated')
    print("\n\nModel 2: Staggered DiD with Game Fixed Effects (Preferred Model)")
    print("-" * 60)
    print("Dependent Variable: ln_players (natural log of player counts)")
    print("Reference Period: January 2025 (timedum_2)")
    print("Note: 'treated' is absorbed by game FE since treatment doesn't vary within games")
    print("      Game fixed effects control for time-invariant game characteristics")
    
    # With game FE, we drop 'treated' (absorbed) and keep 'did' which varies within games over time
    formula2 = f"ln_players ~ did + C(appid) + {' + '.join(time_vars)}"
    model2 = ols(formula2, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Display only key coefficients (not individual game FE)
    print("\nKey Coefficients:")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    
    coef_names = ['Intercept', 'did'] + time_vars
    for var in coef_names:
        if var in model2.params:
            coef = model2.params[var]
            se = model2.bse[var]
            pval = model2.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\n  [Game Fixed Effects: {df['appid'].nunique()} games included but not displayed]")
    print(f"\nModel Statistics:")
    print(f"  N observations: {model2.nobs:.0f}")
    print(f"  R-squared: {model2.rsquared:.4f}")
    print(f"  Cluster-robust standard errors (clustered by game)")
    
    # Model 3: Event study with cohort-specific treatment effects
    print("\n\nModel 3: Event Study with Cohort-Specific Treatment Effects")
    print("-" * 60)
    print("Dependent Variable: ln_players (natural log of player counts)")
    print("Reference Period: January 2025 (timedum_2)")
    print("Treatment Cohorts: Jan (treated M2), Feb (treated M3), Mar (treated M4), Apr (treated M5)")
    
    # Create cohort-specific DiD dummy variables (diddum)
    # Each diddum is the interaction of being in that treatment cohort AND post-treatment
    df_model3 = df.copy()
    
    # Define treatment start periods for each cohort
    treatment_starts = {'jan': 2, 'feb': 3, 'mar': 4, 'apr': 5}
    
    # Create diddum variables: treated_cohort × post_cohort
    cohort_diddum_vars = []
    for cohort in ['jan', 'feb', 'mar', 'apr']:
        # diddum_cohort = 1 if game is in this cohort AND it's post-treatment for this cohort
        is_in_cohort = df_model3['treatment_group'] == cohort
        is_post = df_model3['period'] >= treatment_starts[cohort]
        df_model3[f'diddum_{cohort}'] = (is_in_cohort & is_post).astype(int)
        cohort_diddum_vars.append(f'diddum_{cohort}')
    
    # Build formula with cohort-specific DiD terms
    formula3 = f"ln_players ~ {' + '.join(cohort_diddum_vars)} + C(appid) + {' + '.join(time_vars)}"
    model3 = ols(formula3, data=df_model3).fit(cov_type='cluster', cov_kwds={'groups': df_model3['appid']})
    
    # Display cohort-specific DiD coefficients
    print("\nCohort-Specific DiD Coefficients (diddum variables):")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    
    # Show cohort-specific treatment effects
    for var in cohort_diddum_vars:
        if var in model3.params:
            coef = model3.params[var]
            se = model3.bse[var]
            pval = model3.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print("\nTime Fixed Effects:")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    for var in ['Intercept'] + time_vars:
        if var in model3.params:
            coef = model3.params[var]
            se = model3.bse[var]
            pval = model3.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\n  [Game Fixed Effects: {df['appid'].nunique()} games included but not displayed]")
    print(f"\nModel Statistics:")
    print(f"  N observations: {model3.nobs:.0f}")
    print(f"  R-squared: {model3.rsquared:.4f}")
    print(f"  Cluster-robust standard errors (clustered by game)")
    
    # Extract and display key results
    print("\n" + "="*80)
    print("KEY RESULTS SUMMARY")
    print("="*80)
    
    # Extract from both Model 1 (pooled) and Model 2 (with FE)
    did_coef_pooled = model1.params.get('did', np.nan)
    did_se_pooled = model1.bse.get('did', np.nan)
    did_pval_pooled = model1.pvalues.get('did', np.nan)
    did_ci_pooled = model1.conf_int().loc['did'] if 'did' in model1.params else [np.nan, np.nan]
    
    did_coef_fe = model2.params.get('did', np.nan)
    did_se_fe = model2.bse.get('did', np.nan)
    did_pval_fe = model2.pvalues.get('did', np.nan)
    did_ci_fe = model2.conf_int().loc['did'] if 'did' in model2.params else [np.nan, np.nan]
    
    print(f"\nModel 1 (Pooled OLS) - Average Treatment Effect:")
    print(f"  Coefficient: {did_coef_pooled:.4f}")
    print(f"  Std. Error:  {did_se_pooled:.4f}")
    print(f"  P-value:     {did_pval_pooled:.4f}")
    print(f"  95% CI:      [{did_ci_pooled[0]:.4f}, {did_ci_pooled[1]:.4f}]")
    print(f"  Significant: {'Yes ***' if did_pval_pooled < 0.01 else 'Yes **' if did_pval_pooled < 0.05 else 'Yes *' if did_pval_pooled < 0.1 else 'No'}")
    percent_change_pooled = (np.exp(did_coef_pooled) - 1) * 100
    print(f"  Interpretation: {percent_change_pooled:.2f}% change in player counts")
    
    print(f"\nModel 2 (With Game FE) - Average Treatment Effect:")
    print(f"  Coefficient: {did_coef_fe:.4f}")
    print(f"  Std. Error:  {did_se_fe:.4f}")
    print(f"  P-value:     {did_pval_fe:.4f}")
    print(f"  95% CI:      [{did_ci_fe[0]:.4f}, {did_ci_fe[1]:.4f}]")
    print(f"  Significant: {'Yes ***' if did_pval_fe < 0.01 else 'Yes **' if did_pval_fe < 0.05 else 'Yes *' if did_pval_fe < 0.1 else 'No'}")
    percent_change_fe = (np.exp(did_coef_fe) - 1) * 100
    print(f"  Interpretation: {percent_change_fe:.2f}% change in player counts")
    
    print(f"\n** PREFERRED MODEL: Model 2 (With Game FE) controls for time-invariant game characteristics **")
    
    # Save results
    results = {
        "model_pooled": {
            "did_coefficient": float(did_coef_pooled),
            "std_error": float(did_se_pooled),
            "p_value": float(did_pval_pooled),
            "ci_lower": float(did_ci_pooled[0]),
            "ci_upper": float(did_ci_pooled[1]),
            "percent_change": float(percent_change_pooled),
            "r_squared": float(model1.rsquared)
        },
        "model_with_game_fe": {
            "did_coefficient": float(did_coef_fe),
            "std_error": float(did_se_fe),
            "p_value": float(did_pval_fe),
            "ci_lower": float(did_ci_fe[0]),
            "ci_upper": float(did_ci_fe[1]),
            "percent_change": float(percent_change_fe),
            "r_squared": float(model2.rsquared)
        },
        "n_observations": int(model1.nobs),
        "n_games": int(df['appid'].nunique()),
        "n_time_periods": 5,
        "treatment_groups": ["jan", "feb", "mar", "apr"],
        "control_group_size": 100
    }
    
    with open("staggered_did_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n✓ Results saved to: staggered_did_results.json")
    
    print("="*80)
    
    return model1, model2, model3


def plot_event_study(df, model3):
    """Create event study plot showing cohort-specific treatment effects over time."""
    print("\n" + "="*80)
    print("CREATING EVENT STUDY PLOT")
    print("="*80)
    
    # Extract cohort-specific coefficients from Model 3
    month_labels = ['2024-12', '2025-01', '2025-02', '2025-03', '2025-04']
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_names = {'jan': 'January', 'feb': 'February', 'mar': 'March', 'apr': 'April'}
    treatment_starts = {'jan': 2, 'feb': 3, 'mar': 4, 'apr': 5}
    
    # Prepare data for plotting
    plot_data = []
    
    for cohort in cohorts:
        for period in range(1, 6):
            var_name = f'{cohort}_t{period}'
            
            if period == 1 or period < treatment_starts[cohort]:
                # Pre-treatment: coefficient is 0 (reference)
                plot_data.append({
                    'cohort': cohort,
                    'cohort_name': cohort_names[cohort],
                    'period': period,
                    'month': month_labels[period-1],
                    'coef': 0.0,
                    'ci_low': 0.0,
                    'ci_high': 0.0,
                    'is_post': False
                })
            elif var_name in model3.params:
                # Post-treatment: extract coefficient
                coef = model3.params[var_name]
                ci = model3.conf_int().loc[var_name]
                
                plot_data.append({
                    'cohort': cohort,
                    'cohort_name': cohort_names[cohort],
                    'period': period,
                    'month': month_labels[period-1],
                    'coef': coef,
                    'ci_low': ci[0],
                    'ci_high': ci[1],
                    'is_post': True
                })
            else:
                # Variable not in model (shouldn't happen)
                plot_data.append({
                    'cohort': cohort,
                    'cohort_name': cohort_names[cohort],
                    'period': period,
                    'month': month_labels[period-1],
                    'coef': 0.0,
                    'ci_low': 0.0,
                    'ci_high': 0.0,
                    'is_post': False
                })
    
    coefs_df = pd.DataFrame(plot_data)
    
    # Create plot with cohort-specific lines
    fig, ax = plt.subplots(figsize=(16, 9))
    
    # Define colors and markers for each cohort
    cohort_colors = {'jan': '#e74c3c', 'feb': '#3498db', 'mar': '#2ecc71', 'apr': '#f39c12'}
    cohort_markers = {'jan': 'o', 'feb': 's', 'mar': '^', 'apr': 'D'}
    
    # Plot each cohort
    for cohort in cohorts:
        cohort_data = coefs_df[coefs_df['cohort'] == cohort].sort_values('period')
        
        # Plot line connecting points
        ax.plot(cohort_data['period'], cohort_data['coef'],
               color=cohort_colors[cohort], linewidth=2.5, alpha=0.8,
               label=f"{cohort_names[cohort]} Group (treated M{treatment_starts[cohort]})")
        
        # Plot points with error bars
        for idx, row in cohort_data.iterrows():
            if row['is_post']:
                # Post-treatment: show with error bars
                ax.errorbar(row['period'], row['coef'],
                           yerr=[[row['coef'] - row['ci_low']], [row['ci_high'] - row['coef']]],
                           fmt=cohort_markers[cohort], markersize=12, capsize=5, capthick=2,
                           color=cohort_colors[cohort], ecolor='gray', linewidth=2, alpha=0.9)
            else:
                # Pre-treatment: just marker (no error bars for zero)
                ax.plot(row['period'], row['coef'],
                       marker=cohort_markers[cohort], markersize=12,
                       color=cohort_colors[cohort], alpha=0.6)
    
    # Add reference line at zero
    ax.axhline(y=0, color='black', linestyle='-', linewidth=2, alpha=0.8, zorder=1)
    
    # Add vertical lines for treatment timing for each cohort
    for cohort, start_period in treatment_starts.items():
        ax.axvline(x=start_period - 0.5, color=cohort_colors[cohort], 
                  linestyle='--', linewidth=1.5, alpha=0.4, zorder=1)
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=15, fontweight='bold')
    ax.set_ylabel('Treatment Effect on Log(Player Count)', fontsize=15, fontweight='bold')
    ax.set_title('Staggered DiD Event Study: Cohort-Specific Treatment Effects\n' +
                'Effect of Major Patches on Player Counts (Dec 2024 - Apr 2025)\n' +
                '100 games per treatment cohort + 100 control games',
                fontsize=16, fontweight='bold', pad=20)
    
    # Customize legend
    ax.legend(loc='best', fontsize=12, framealpha=0.95, edgecolor='black', fancybox=True)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    # Set axis limits and ticks
    ax.set_xlim(0.7, 5.3)
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels([f"M{i}\n{month_labels[i-1]}" for i in range(1, 6)], fontsize=11)
    
    # Add text annotation
    ax.text(0.02, 0.98, 'Note: Treatment timing varies by cohort (staggered design)',
           transform=ax.transAxes, fontsize=10, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    # Save
    filename = 'staggered_did_event_study.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Event study plot saved to: {filename}")
    plt.close()
    
    return fig, coefs_df


def plot_did_effect(model2):
    """
    Create a simple visualization of the DiD treatment effect from Model 2.
    Shows the coefficient with 95% confidence interval.
    """
    print("\n" + "="*80)
    print("CREATING DiD EFFECT PLOT")
    print("="*80)
    
    # Extract DiD coefficient and confidence interval
    did_coef = model2.params['did']
    did_se = model2.bse['did']
    did_pval = model2.pvalues['did']
    
    # Calculate 95% CI
    ci_low = model2.conf_int().loc['did', 0]
    ci_high = model2.conf_int().loc['did', 1]
    
    # Determine significance
    is_significant = did_pval < 0.05
    sig_marker = '***' if did_pval < 0.01 else ('**' if did_pval < 0.05 else ('*' if did_pval < 0.10 else 'ns'))
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 8))
    
    # Plot coefficient with error bars
    color = '#e74c3c' if is_significant else '#95a5a6'
    ax.errorbar([1], [did_coef], 
                yerr=[[did_coef - ci_low], [ci_high - did_coef]],
                fmt='o', markersize=20, capsize=15, capthick=3,
                color=color, ecolor='black', linewidth=3, alpha=0.9,
                label=f'DiD Coefficient = {did_coef:.6f}\n95% CI: [{ci_low:.6f}, {ci_high:.6f}]\np-value = {did_pval:.4f} {sig_marker}')
    
    # Add reference line at zero
    ax.axhline(y=0, color='black', linestyle='-', linewidth=2, alpha=0.8, zorder=1)
    
    # Add shaded region for confidence interval
    ax.fill_between([0.7, 1.3], ci_low, ci_high, alpha=0.2, color=color)
    
    # Formatting
    ax.set_xlim(0.5, 1.5)
    ax.set_xticks([1])
    ax.set_xticklabels(['Average Treatment Effect\n(Model 2: With Game FE)'], fontsize=13, fontweight='bold')
    ax.set_ylabel('Effect on Log(Player Count)', fontsize=15, fontweight='bold')
    ax.set_title('Staggered DiD: Average Treatment Effect of Major Patches\n' +
                f'Effect on Player Counts (Dec 2024 - Apr 2025)\n' +
                f'500 treated games (4 cohorts) + 100 control games',
                fontsize=16, fontweight='bold', pad=20)
    
    # Add legend
    ax.legend(loc='upper right', fontsize=12, framealpha=0.95, edgecolor='black', fancybox=True)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1, axis='y')
    
    # Add interpretation text
    if is_significant:
        interpretation = f"Significant effect: {(np.exp(did_coef) - 1) * 100:.2f}% change in player counts"
        text_color = '#e74c3c'
    else:
        interpretation = f"No significant effect: {(np.exp(did_coef) - 1) * 100:.2f}% change (p={did_pval:.4f})"
        text_color = '#95a5a6'
    
    ax.text(0.5, 0.02, interpretation,
           transform=ax.transAxes, fontsize=11, fontweight='bold',
           ha='center', color=text_color,
           bbox=dict(boxstyle='round', facecolor='white', edgecolor=text_color, linewidth=2, alpha=0.9))
    
    # Add statistical note
    ax.text(0.02, 0.98, 
           'Note: Model 2 includes game fixed effects to control for time-invariant game characteristics.\n' +
           'Estimates use cluster-robust standard errors (clustered by game).',
           transform=ax.transAxes, fontsize=9, verticalalignment='top',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.3))
    
    plt.tight_layout()
    
    # Save
    filename = 'staggered_did_effect_plot.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ DiD effect plot saved to: {filename}")
    plt.close()
    
    return fig


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
    
    # Step 3: Create DiD effect plot
    did_fig = plot_did_effect(model2)
    
    # Step 4: Create event study plot
    event_fig, coefs_df = plot_event_study(df, model3)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nFiles created:")
    print("  1. staggered_panel_2025.csv - Panel dataset (google.csv style)")
    print("  2. staggered_did_results.json - Regression results summary")
    print("  3. staggered_did_effect_plot.png - DiD treatment effect visualization")
    print("  4. staggered_did_event_study.png - Event study visualization")
    print("="*80)


if __name__ == "__main__":
    main()
