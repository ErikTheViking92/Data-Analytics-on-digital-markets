"""
Extended Staggered DiD Analysis with November 2024 Data

Extends the analysis period to include November 2024, providing:
- 2 pre-treatment periods (Nov & Dec 2024) instead of 1
- Better parallel trends testing capability
- Event study plots with relative time for each cohort
- DiD effects with 95% CIs for each treatment cohort
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import ols
import json
import os
from datetime import datetime
from scraper.steamcharts_scraper import fetch_monthly_series
from scraper.store_scraper import SteamStoreScraper
from scraper.reviews_scraper import fetch_app_reviews
import time

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)


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


def load_cached_metadata():
    """Load metadata from existing panel dataset if available."""
    cache = {}
    try:
        if os.path.exists("staggered_panel_2025.csv"):
            df_old = pd.read_csv("staggered_panel_2025.csv")
            for appid in df_old['appid'].unique():
                game_data = df_old[df_old['appid'] == appid].iloc[0]
                cache[appid] = {
                    'genre_category': game_data.get('genre_category', 'Other'),
                    'age_years': game_data.get('age_years', 2.0),
                    'price_usd': game_data.get('price_usd', 20.0),
                    'is_free': game_data.get('is_free', 0),
                    'review_score': game_data.get('review_score', 5.0)
                }
            print(f"  Loaded cached metadata for {len(cache)} games")
    except Exception as e:
        print(f"  Note: Could not load cache: {e}")
    return cache


def fetch_game_metadata(appid: int, store_scraper: SteamStoreScraper, metadata_cache: dict):
    """Fetch game metadata for control variables, using cache when possible."""
    # Check cache first
    if appid in metadata_cache:
        return metadata_cache[appid].copy()
    
    # Default values
    metadata = {
        'genre_category': 'Other',
        'age_years': 2.0,
        'price_usd': 20.0,
        'is_free': 0,
        'review_score': 5.0
    }
    
    # Add small delay to avoid rate limiting (200ms)
    time.sleep(0.2)
    
    try:
        game_data = store_scraper.fetch_app(appid)
        
        if game_data:
            # Genre
            genres = game_data.get('genres', [])
            if genres:
                main_genre = genres[0].get('description', 'Other')
                genre_map = {
                    'Action': 'Action',
                    'Adventure': 'Adventure',
                    'RPG': 'RPG',
                    'Strategy': 'Strategy',
                    'Simulation': 'Simulation',
                    'Sports': 'Sports'
                }
                metadata['genre_category'] = genre_map.get(main_genre, 'Other')
            
            # Age
            release_date_str = game_data.get('release_date', {}).get('date')
            if release_date_str:
                try:
                    release_date = datetime.strptime(release_date_str, '%d %b, %Y')
                    age_years = (datetime.now() - release_date).days / 365.25
                    metadata['age_years'] = age_years
                except:
                    pass
            
            # Price
            price_data = game_data.get('price_overview', {})
            if price_data:
                price_cents = price_data.get('final', 0)
                metadata['price_usd'] = price_cents / 100.0
                metadata['is_free'] = 0
            else:
                is_free = game_data.get('is_free', False)
                if is_free:
                    metadata['price_usd'] = 0.0
                    metadata['is_free'] = 1
        
        # Review score from reviews API
        try:
            review_data = fetch_app_reviews(appid)
            if review_data and 'percent_positive' in review_data:
                metadata['review_score'] = review_data['percent_positive'] / 10.0
        except:
            pass
    
    except Exception as e:
        # Silent failure - use defaults
        pass
    
    return metadata


def create_extended_panel():
    """
    Create panel dataset with November 2024 - April 2025 (6 months).
    
    Time periods:
    - Period 1: November 2024 (pre-treatment for all)
    - Period 2: December 2024 (pre-treatment for all)
    - Period 3: January 2025 (Jan cohort treated)
    - Period 4: February 2025 (Feb cohort treated)
    - Period 5: March 2025 (Mar cohort treated)
    - Period 6: April 2025 (Apr cohort treated)
    """
    print("\n" + "="*80)
    print("CREATING EXTENDED STAGGERED DiD PANEL (NOV 2024 - APR 2025)")
    print("="*80)
    
    jan_games, feb_games, mar_games, apr_games, control_games = load_staggered_groups()
    
    # Define analysis months (Nov 2024 - Apr 2025)
    months = pd.date_range('2024-11-01', '2025-04-01', freq='MS')
    month_labels = [m.strftime('%Y-%m') for m in months]
    n_periods = len(months)
    
    print(f"\nTime periods: {n_periods} months from {month_labels[0]} to {month_labels[-1]}")
    print(f"Treatment timing:")
    print(f"  - January cohort: Period 3 ({month_labels[2]})")
    print(f"  - February cohort: Period 4 ({month_labels[3]})")
    print(f"  - March cohort: Period 5 ({month_labels[4]})")
    print(f"  - April cohort: Period 6 ({month_labels[5]})")
    
    # Load metadata cache from existing dataset
    metadata_cache = load_cached_metadata()
    
    rows = []
    store_scraper = SteamStoreScraper()
    
    def process_group(games, group_name, treatment_period_idx):
        """
        Process a group of games and create panel observations.
        
        treatment_period_idx: Period when treatment occurs (None for control)
        """
        nonlocal rows
        
        print(f"\n  Processing {group_name} group ({len(games)} games)...")
        
        games_included = 0
        games_skipped = 0
        
        for i, game in enumerate(games, 1):
            appid = game['appid']
            name = game['name']
            
            if i % 20 == 0:
                print(f"    Processed {i}/{len(games)} games...")
            
            # Fetch monthly player data
            try:
                monthly_data = fetch_monthly_series(appid)
            except Exception as e:
                print(f"    Warning: Could not fetch data for {appid} ({name}): {e}")
                games_skipped += 1
                continue
            
            if not monthly_data:
                games_skipped += 1
                continue
            
            # Create lookup dictionary keyed by year-month
            monthly_lookup = {}
            for entry in monthly_data:
                try:
                    date_obj = pd.to_datetime(entry['date'])
                    ym = date_obj.strftime('%Y-%m')
                    monthly_lookup[ym] = entry
                except:
                    continue
            
            # Check if we have data for all required months
            missing_months = []
            for month_label in month_labels:
                if month_label not in monthly_lookup:
                    missing_months.append(month_label)
            
            if missing_months:
                games_skipped += 1
                continue
            
            # Fetch metadata once per game (using cache when available)
            metadata = fetch_game_metadata(appid, store_scraper, metadata_cache)
            
            # Create observations for each time period
            has_variation = False
            player_values = []
            
            for period_idx, month_label in enumerate(month_labels, start=1):
                month_data = monthly_lookup[month_label]
                
                # Use 'avg' field for average concurrent players
                avg_players = month_data.get('avg')
                if avg_players is None or avg_players <= 0:
                    avg_players = month_data.get('value', 1)  # Fallback
                
                if avg_players <= 0:
                    avg_players = 1  # Minimum to avoid log(0)
                
                player_values.append(avg_players)
                
                # Determine treatment status
                treated = 1 if group_name != 'control' else 0
                
                # Post indicator (cohort-specific)
                if treatment_period_idx is None:
                    post = 0  # Control never treated
                    rel_time = None
                else:
                    post = 1 if period_idx >= treatment_period_idx else 0
                    # Relative time to treatment
                    rel_time = period_idx - treatment_period_idx
                
                # DiD interaction
                did = treated * post
                
                # Create observation
                obs = {
                    'appid': appid,
                    'name': name,
                    'period': period_idx,
                    'month': month_label,
                    'treatment_group': group_name,
                    'treated': treated,
                    'post': post,
                    'did': did,
                    'rel_time': rel_time if rel_time is not None else 999,  # 999 for control
                    'players': avg_players,
                    'ln_players': np.log(avg_players),
                    **metadata
                }
                
                rows.append(obs)
            
            # Check for temporal variation
            if len(player_values) > 1:
                std_dev = np.std(player_values)
                if std_dev > 0:
                    has_variation = True
            
            if has_variation:
                games_included += 1
            else:
                # Remove observations for this game (no variation)
                rows = [r for r in rows if r['appid'] != appid]
                games_skipped += 1
        
        print(f"    ✓ {group_name}: {games_included} games included, {games_skipped} skipped")
    
    # Process all groups
    # Treatment period indices (1-indexed):
    # Nov=1, Dec=2, Jan=3, Feb=4, Mar=5, Apr=6
    process_group(jan_games, 'jan', treatment_period_idx=3)
    process_group(feb_games, 'feb', treatment_period_idx=4)
    process_group(mar_games, 'mar', treatment_period_idx=5)
    process_group(apr_games, 'apr', treatment_period_idx=6)
    process_group(control_games, 'control', treatment_period_idx=None)
    
    df = pd.DataFrame(rows)
    
    print(f"\n{'='*80}")
    print(f"Extended panel dataset created:")
    print(f"  Total observations: {len(df)}")
    print(f"  Unique games: {df['appid'].nunique()}")
    print(f"  Time periods: {df['period'].nunique()}")
    print(f"  Treatment groups: {df['treatment_group'].value_counts().to_dict()}")
    print(f"{'='*80}")
    
    # Save to CSV
    output_file = "staggered_panel_extended_2025.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved extended panel data to: {output_file}")
    
    return df


def run_extended_did_analysis(df):
    """Run DiD regression on extended panel."""
    print("\n" + "="*80)
    print("EXTENDED STAGGERED DiD REGRESSION ANALYSIS")
    print("="*80)
    
    # Model 2: Two-Way Fixed Effects (PREFERRED)
    print("\nModel 2: Two-Way Fixed Effects")
    print("-" * 60)
    
    formula2 = 'ln_players ~ did + C(appid) + C(period) - 1'
    
    model2 = ols(formula2, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    print(model2.summary())
    
    # Extract DiD coefficient
    did_coef = model2.params.get('did', np.nan)
    did_se = model2.bse.get('did', np.nan)
    did_pval = model2.pvalues.get('did', np.nan)
    
    ci_low = did_coef - 1.96 * did_se
    ci_high = did_coef + 1.96 * did_se
    
    percent_change = (np.exp(did_coef) - 1) * 100
    
    print("\n" + "="*80)
    print("EXTENDED STAGGERED DiD RESULTS (Model 2 - Two-Way FE)")
    print("="*80)
    print(f"Coefficient: {did_coef:.4f}")
    print(f"Std. Error:  {did_se:.4f}")
    print(f"P-value:     {did_pval:.4f}")
    print(f"95% CI:      [{ci_low:.4f}, {ci_high:.4f}]")
    print(f"Significant: {'Yes' if did_pval < 0.05 else 'No'} (α = 0.05)")
    print(f"\nEffect Size: {percent_change:+.2f}%")
    print("="*80)
    
    # Save results
    results = {
        'model': 'Two-Way Fixed Effects',
        'coefficient': float(did_coef),
        'std_error': float(did_se),
        'p_value': float(did_pval),
        'ci_low': float(ci_low),
        'ci_high': float(ci_high),
        'effect_size_pct': float(percent_change),
        'n_obs': len(df),
        'n_games': df['appid'].nunique(),
        'n_periods': df['period'].nunique()
    }
    
    with open('staggered_extended_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return model2, results


def run_cohort_specific_analysis(df):
    """
    Run event study with cohort-specific effects in relative time.
    
    Model: ln(Players_it) = Σ_{c,τ} β_{c,τ} · 1[cohort=c] · 1[rel_time=τ] + α_i + λ_t + ε_it
    """
    print("\n" + "="*80)
    print("COHORT-SPECIFIC EVENT STUDY (RELATIVE TIME)")
    print("="*80)
    
    # Create cohort × relative time dummies
    # Relative time ranges: -2, -1, 0, +1, +2, +3
    # (Nov & Dec are pre-treatment for all cohorts)
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    
    # For each cohort, create dummies for each relative time period
    # Omit t=-1 as reference period
    for cohort in cohorts:
        cohort_df = df[df['treatment_group'] == cohort]
        for idx in cohort_df.index:
            rel_time = df.loc[idx, 'rel_time']
            for tau in [-2, 0, 1, 2, 3]:
                var_name = f'{cohort}_tau{tau}' if tau >= 0 else f'{cohort}_taum{abs(tau)}'
                df.loc[idx, var_name] = 1 if rel_time == tau else 0
    
    # Fill NaN with 0 for all cohort-time dummies
    cohort_time_vars = []
    for cohort in cohorts:
        for tau in [-2, 0, 1, 2, 3]:
            var_name = f'{cohort}_tau{tau}' if tau >= 0 else f'{cohort}_taum{abs(tau)}'
            cohort_time_vars.append(var_name)
            if var_name not in df.columns:
                df[var_name] = 0
            df[var_name] = df[var_name].fillna(0)
    
    # Build formula
    formula = 'ln_players ~ ' + ' + '.join(cohort_time_vars) + ' + C(appid) + C(period) - 1'
    
    print(f"\nEstimating event study model with {len(cohort_time_vars)} cohort-time interactions...")
    print(f"Reference: t=-1 (one period before treatment) for each cohort")
    
    model_event = ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Extract coefficients for each cohort
    cohort_results = {}
    
    for cohort in cohorts:
        cohort_results[cohort] = []
        
        # Add reference point (t=-1, coefficient=0)
        cohort_results[cohort].append({
            'rel_time': -1,
            'coef': 0.0,
            'se': 0.0,
            'ci_low': 0.0,
            'ci_high': 0.0,
            'pval': 1.0
        })
        
        for tau in [-2, 0, 1, 2, 3]:
            var_name = f'{cohort}_tau{tau}' if tau >= 0 else f'{cohort}_taum{abs(tau)}'
            
            if var_name in model_event.params:
                coef = model_event.params[var_name]
                se = model_event.bse[var_name]
                pval = model_event.pvalues[var_name]
                ci_low = coef - 1.96 * se
                ci_high = coef + 1.96 * se
                
                cohort_results[cohort].append({
                    'rel_time': tau,
                    'coef': coef,
                    'se': se,
                    'ci_low': ci_low,
                    'ci_high': ci_high,
                    'pval': pval
                })
        
        # Sort by relative time
        cohort_results[cohort] = sorted(cohort_results[cohort], key=lambda x: x['rel_time'])
    
    # Print results
    print("\n" + "="*80)
    print("COHORT-SPECIFIC TREATMENT EFFECTS (RELATIVE TIME)")
    print("="*80)
    
    for cohort in cohorts:
        print(f"\n{cohort.upper()} COHORT:")
        print("-" * 60)
        print(f"{'Rel Time':<10} {'Coefficient':>12} {'Std Err':>10} {'P-value':>10} {'95% CI':>25}")
        print("-" * 60)
        
        for result in cohort_results[cohort]:
            tau = result['rel_time']
            coef = result['coef']
            se = result['se']
            pval = result['pval']
            ci = f"[{result['ci_low']:>6.4f}, {result['ci_high']:>6.4f}]"
            
            tau_str = f"t={tau:+d}" if tau != -1 else "t=-1 (ref)"
            pval_str = f"{pval:.4f}" if pval < 1.0 else "---"
            se_str = f"{se:.4f}" if se > 0 else "---"
            
            print(f"{tau_str:<10} {coef:>12.4f} {se_str:>10} {pval_str:>10} {ci:>25}")
    
    print("="*80)
    
    return model_event, cohort_results


def plot_event_study_by_cohort(cohort_results):
    """
    Create event study plots showing treatment effects in relative time for each cohort.
    Separate plot for each cohort with 95% CIs.
    """
    print("\n--- Creating event study plots by cohort ---")
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_labels = {
        'jan': 'January 2025 Cohort',
        'feb': 'February 2025 Cohort',
        'mar': 'March 2025 Cohort',
        'apr': 'April 2025 Cohort'
    }
    
    # Create 2×2 subplot
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, cohort in enumerate(cohorts):
        ax = axes[idx]
        
        results_df = pd.DataFrame(cohort_results[cohort])
        
        # Plot coefficients
        ax.plot(results_df['rel_time'], results_df['coef'],
               marker='o', markersize=10, linewidth=2.5,
               color='steelblue', label='DiD Estimate', zorder=3)
        
        # Plot 95% CI
        ax.fill_between(results_df['rel_time'],
                        results_df['ci_low'],
                        results_df['ci_high'],
                        alpha=0.25, color='steelblue', label='95% CI')
        
        # Reference lines
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7, zorder=1)
        ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5,
                  alpha=0.7, label='Treatment Time', zorder=2)
        
        # Shade pre/post regions
        ax.axvspan(-2.5, -0.5, alpha=0.1, color='orange', zorder=0)
        ax.axvspan(-0.5, 3.5, alpha=0.1, color='lightblue', zorder=0)
        
        # Formatting
        ax.set_xlabel('Relative Time to Treatment', fontsize=12, fontweight='bold')
        ax.set_ylabel('Treatment Effect (Log Points)', fontsize=12, fontweight='bold')
        ax.set_title(f'{cohort_labels[cohort]}\nEvent Study in Relative Time',
                    fontsize=13, fontweight='bold')
        
        ax.set_xticks([-2, -1, 0, 1, 2, 3])
        ax.set_xticklabels(['t-2', 't-1\n(ref)', 't', 't+1', 't+2', 't+3'])
        
        ax.legend(loc='best', fontsize=10, framealpha=0.95)
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/extended_event_study_by_cohort.png'
    os.makedirs('Actual_final_results', exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {save_path}")
    plt.close()
    
    return save_path


def plot_combined_event_study(cohort_results):
    """
    Create single plot showing all cohorts together in relative time.
    """
    print("\n--- Creating combined event study plot ---")
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_labels = {
        'jan': 'January Cohort',
        'feb': 'February Cohort',
        'mar': 'March Cohort',
        'apr': 'April Cohort'
    }
    colors = {
        'jan': 'steelblue',
        'feb': 'coral',
        'mar': 'seagreen',
        'apr': 'mediumpurple'
    }
    
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for cohort in cohorts:
        results_df = pd.DataFrame(cohort_results[cohort])
        
        # Plot with offset for visibility
        offset = {'jan': -0.1, 'feb': -0.033, 'mar': 0.033, 'apr': 0.1}[cohort]
        x_positions = results_df['rel_time'] + offset
        
        ax.errorbar(x_positions, results_df['coef'],
                   yerr=[results_df['coef'] - results_df['ci_low'],
                         results_df['ci_high'] - results_df['coef']],
                   fmt='o', markersize=8, capsize=5, capthick=2,
                   color=colors[cohort], ecolor=colors[cohort],
                   label=cohort_labels[cohort], alpha=0.8, zorder=3)
    
    # Reference lines
    ax.axhline(y=0, color='black', linestyle='-', linewidth=2, alpha=0.7, zorder=1)
    ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5,
              alpha=0.6, label='Treatment Time', zorder=2)
    
    # Shade regions
    ax.axvspan(-2.5, -0.5, alpha=0.1, color='orange', zorder=0)
    ax.axvspan(-0.5, 3.5, alpha=0.1, color='lightblue', zorder=0)
    
    # Formatting
    ax.set_xlabel('Relative Time to Treatment', fontsize=13, fontweight='bold')
    ax.set_ylabel('Treatment Effect (Log Points)', fontsize=13, fontweight='bold')
    ax.set_title('Staggered DiD Event Study - All Cohorts\n' +
                'Treatment Effects in Relative Time with 95% Confidence Intervals',
                fontsize=15, fontweight='bold', pad=20)
    
    ax.set_xticks([-2, -1, 0, 1, 2, 3])
    ax.set_xticklabels(['t-2', 't-1\n(reference)', 't\n(treatment)', 't+1', 't+2', 't+3'])
    ax.set_xlim(-2.5, 3.5)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95,  ncol=2)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/extended_event_study_combined.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {save_path}")
    plt.close()
    
    return save_path


def main():
    """Run extended staggered DiD analysis."""
    print("\n" + "="*80)
    print("EXTENDED STAGGERED DiD ANALYSIS")
    print("November 2024 - April 2025 (6 months)")
    print("="*80)
    
    # Create extended panel
    df = create_extended_panel()
    
    # Run main DiD regression
    model_main, results_main = run_extended_did_analysis(df)
    
    # Run cohort-specific event study
    model_event, cohort_results = run_cohort_specific_analysis(df)
    
    # Save cohort results
    with open('cohort_specific_results.json', 'w') as f:
        json.dump(cohort_results, f, indent=2)
    
    # Create visualizations
    plot_event_study_by_cohort(cohort_results)
    plot_combined_event_study(cohort_results)
    
    print("\n" + "="*80)
    print("EXTENDED ANALYSIS COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print("  1. staggered_panel_extended_2025.csv - Extended panel data")
    print("  2. staggered_extended_results.json - Main DiD results")
    print("  3. cohort_specific_results.json - Event study coefficients")
    print("  4. Actual_final_results/extended_event_study_by_cohort.png")
    print("  5. Actual_final_results/extended_event_study_combined.png")
    print("="*80)


if __name__ == "__main__":
    main()
