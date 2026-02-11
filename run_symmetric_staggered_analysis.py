"""
Extended Staggered DiD Analysis with Symmetric Event Windows
October 2024 - July 2025 (10 months total)

Each cohort gets exactly 7 months: t-3, t-2, t-1, t, t+1, t+2, t+3
This enables:
- 3 pre-treatment periods for strong parallel trends testing
- Consistent post-treatment observation across all cohorts
- Balanced event study design
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
        if os.path.exists("staggered_panel_extended_2025.csv"):
            df_old = pd.read_csv("staggered_panel_extended_2025.csv")
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
    if appid in metadata_cache:
        return metadata_cache[appid].copy()
    
    metadata = {
        'genre_category': 'Other',
        'age_years': 2.0,
        'price_usd': 20.0,
        'is_free': 0,
        'review_score': 5.0
    }
    
    time.sleep(0.2)
    
    try:
        game_data = store_scraper.fetch_app(appid)
        
        if game_data:
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
            
            release_date_str = game_data.get('release_date', {}).get('date')
            if release_date_str:
                try:
                    release_date = datetime.strptime(release_date_str, '%d %b, %Y')
                    age_years = (datetime.now() - release_date).days / 365.25
                    metadata['age_years'] = age_years
                except:
                    pass
            
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
        
        try:
            review_data = fetch_app_reviews(appid)
            if review_data and 'percent_positive' in review_data:
                metadata['review_score'] = review_data['percent_positive'] / 10.0
        except:
            pass
    
    except Exception as e:
        pass
    
    return metadata


def create_symmetric_panel():
    """
    Create balanced panel with symmetric event windows (t-3 to t+3) for each cohort.
    
    Full time span: October 2024 - July 2025 (10 months)
    
    Cohort-specific windows:
    - January cohort: Oct, Nov, Dec, Jan, Feb, Mar, Apr (7 months)
    - February cohort: Nov, Dec, Jan, Feb, Mar, Apr, May (7 months)
    - March cohort: Dec, Jan, Feb, Mar, Apr, May, Jun (7 months)
    - April cohort: Jan, Feb, Mar, Apr, May, Jun, Jul (7 months)
    - Control: All 10 months (for comparability)
    """
    print("\n" + "="*80)
    print("CREATING SYMMETRIC STAGGERED DiD PANEL (OCT 2024 - JUL 2025)")
    print("Each cohort: 7 months (t-3 to t+3)")
    print("="*80)
    
    jan_games, feb_games, mar_games, apr_games, control_games = load_staggered_groups()
    
    # Define all months (Oct 2024 - Jul 2025)
    all_months = pd.date_range('2024-10-01', '2025-07-01', freq='MS')
    month_labels = [m.strftime('%Y-%m') for m in all_months]
    
    print(f"\nFull time span: {len(all_months)} months from {month_labels[0]} to {month_labels[-1]}")
    print(f"\nCohort-specific windows (each 7 months, t-3 to t+3):")
    print(f"  - January cohort: {month_labels[0]} to {month_labels[6]}")
    print(f"  - February cohort: {month_labels[1]} to {month_labels[7]}")
    print(f"  - March cohort: {month_labels[2]} to {month_labels[8]}")
    print(f"  - April cohort: {month_labels[3]} to {month_labels[9]}")
    print(f"  - Control group: All {len(month_labels)} months")
    
    # Load metadata cache
    metadata_cache = load_cached_metadata()
    
    rows = []
    store_scraper = SteamStoreScraper()
    
    def process_cohort(games, cohort_name, treatment_month_idx, window_start_idx, window_end_idx):
        """
        Process a treatment cohort with symmetric event window.
        
        Args:
            games: List of games in cohort
            cohort_name: 'jan', 'feb', 'mar', or 'apr'
            treatment_month_idx: Index of treatment month in all_months
            window_start_idx: Start of 7-month window (treatment - 3)
            window_end_idx: End of 7-month window (treatment + 3, inclusive)
        """
        nonlocal rows
        
        print(f"\n  Processing {cohort_name.upper()} cohort ({len(games)} games)...")
        print(f"    Window: {month_labels[window_start_idx]} to {month_labels[window_end_idx]}")
        print(f"    Treatment: {month_labels[treatment_month_idx]} (position {treatment_month_idx - window_start_idx})")
        
        games_included = 0
        games_skipped = 0
        
        # Get relevant months for this cohort
        cohort_months = month_labels[window_start_idx:window_end_idx + 1]
        
        for i, game in enumerate(games, 1):
            appid = game['appid']
            name = game['name']
            
            if i % 20 == 0:
                print(f"    Processed {i}/{len(games)} games...")
            
            # Fetch monthly player data
            try:
                monthly_data = fetch_monthly_series(appid)
            except Exception as e:
                games_skipped += 1
                continue
            
            if not monthly_data:
                games_skipped += 1
                continue
            
            # Create lookup dictionary
            monthly_lookup = {}
            for entry in monthly_data:
                try:
                    date_obj = pd.to_datetime(entry['date'])
                    ym = date_obj.strftime('%Y-%m')
                    monthly_lookup[ym] = entry
                except:
                    continue
            
            # Check if we have data for all required months in this cohort's window
            missing_months = [m for m in cohort_months if m not in monthly_lookup]
            
            if missing_months:
                games_skipped += 1
                continue
            
            # Fetch metadata once per game
            metadata = fetch_game_metadata(appid, store_scraper, metadata_cache)
            
            # Create observations for cohort's 7-month window
            player_values = []
            
            for month_label in cohort_months:
                month_data = monthly_lookup[month_label]
                
                # Get average players
                avg_players = month_data.get('avg')
                if avg_players is None or avg_players <= 0:
                    avg_players = month_data.get('value', 1)
                
                if avg_players <= 0:
                    avg_players = 1
                
                player_values.append(avg_players)
                
                # Calculate relative time
                month_idx_in_all = month_labels.index(month_label)
                rel_time = month_idx_in_all - treatment_month_idx
                
                # Post indicator
                post = 1 if month_idx_in_all >= treatment_month_idx else 0
                
                # DiD interaction
                did = 1 * post
                
                # Create observation
                obs = {
                    'appid': appid,
                    'name': name,
                    'month': month_label,
                    'treatment_group': cohort_name,
                    'treated': 1,
                    'post': post,
                    'did': did,
                    'rel_time': rel_time,
                    'players': avg_players,
                    'ln_players': np.log(avg_players),
                    **metadata
                }
                
                rows.append(obs)
            
            # Check for temporal variation
            if len(player_values) > 1 and np.std(player_values) > 0:
                games_included += 1
            else:
                rows = [r for r in rows if r['appid'] != appid]
                games_skipped += 1
        
        print(f"    ✓ {cohort_name}: {games_included} games included, {games_skipped} skipped")
        return games_included
    
    def process_control(games):
        """Process control group (uses all 10 months)."""
        nonlocal rows
        
        print(f"\n  Processing CONTROL group ({len(games)} games)...")
        print(f"    Window: {month_labels[0]} to {month_labels[-1]} (all months)")
        
        games_included = 0
        games_skipped = 0
        
        for i, game in enumerate(games, 1):
            appid = game['appid']
            name = game['name']
            
            if i % 20 == 0:
                print(f"    Processed {i}/{len(games)} games...")
            
            try:
                monthly_data = fetch_monthly_series(appid)
            except Exception as e:
                games_skipped += 1
                continue
            
            if not monthly_data:
                games_skipped += 1
                continue
            
            monthly_lookup = {}
            for entry in monthly_data:
                try:
                    date_obj = pd.to_datetime(entry['date'])
                    ym = date_obj.strftime('%Y-%m')
                    monthly_lookup[ym] = entry
                except:
                    continue
            
            # Control needs all months
            missing_months = [m for m in month_labels if m not in monthly_lookup]
            
            if missing_months:
                games_skipped += 1
                continue
            
            metadata = fetch_game_metadata(appid, store_scraper, metadata_cache)
            
            player_values = []
            
            for month_label in month_labels:
                month_data = monthly_lookup[month_label]
                
                avg_players = month_data.get('avg')
                if avg_players is None or avg_players <= 0:
                    avg_players = month_data.get('value', 1)
                
                if avg_players <= 0:
                    avg_players = 1
                
                player_values.append(avg_players)
                
                obs = {
                    'appid': appid,
                    'name': name,
                    'month': month_label,
                    'treatment_group': 'control',
                    'treated': 0,
                    'post': 0,
                    'did': 0,
                    'rel_time': 999,  # Control has no relative time
                    'players': avg_players,
                    'ln_players': np.log(avg_players),
                    **metadata
                }
                
                rows.append(obs)
            
            if len(player_values) > 1 and np.std(player_values) > 0:
                games_included += 1
            else:
                rows = [r for r in rows if r['appid'] != appid]
                games_skipped += 1
        
        print(f"    ✓ control: {games_included} games included, {games_skipped} skipped")
        return games_included
    
    # Process all cohorts with symmetric windows
    # January: Oct(t-3), Nov(t-2), Dec(t-1), Jan(t), Feb(t+1), Mar(t+2), Apr(t+3)
    jan_count = process_cohort(jan_games, 'jan', treatment_month_idx=3, window_start_idx=0, window_end_idx=6)
    
    # February: Nov(t-3), Dec(t-2), Jan(t-1), Feb(t), Mar(t+1), Apr(t+2), May(t+3)
    feb_count = process_cohort(feb_games, 'feb', treatment_month_idx=4, window_start_idx=1, window_end_idx=7)
    
    # March: Dec(t-3), Jan(t-2), Feb(t-1), Mar(t), Apr(t+1), May(t+2), Jun(t+3)
    mar_count = process_cohort(mar_games, 'mar', treatment_month_idx=5, window_start_idx=2, window_end_idx=8)
    
    # April: Jan(t-3), Feb(t-2), Mar(t-1), Apr(t), May(t+1), Jun(t+2), Jul(t+3)
    apr_count = process_cohort(apr_games, 'apr', treatment_month_idx=6, window_start_idx=3, window_end_idx=9)
    
    # Control: All months
    ctrl_count = process_control(control_games)
    
    df = pd.DataFrame(rows)
    
    # Calculate summary statistics
    total_games = df['appid'].nunique()
    treatment_obs = df[df['treated'] == 1].shape[0]
    control_obs = df[df['treated'] == 0].shape[0]
    
    print(f"\n{'='*80}")
    print(f"Symmetric panel dataset created:")
    print(f"  Total observations: {len(df)}")
    print(f"  Unique games: {total_games}")
    print(f"  Treatment observations: {treatment_obs} ({jan_count + feb_count + mar_count + apr_count} games × 7 months)")
    print(f"  Control observations: {control_obs} ({ctrl_count} games × 10 months)")
    print(f"  Cohort distribution:")
    print(f"    - January: {jan_count} games (7 obs each)")
    print(f"    - February: {feb_count} games (7 obs each)")
    print(f"    - March: {mar_count} games (7 obs each)")
    print(f"    - April: {apr_count} games (7 obs each)")
    print(f"    - Control: {ctrl_count} games (10 obs each)")
    print(f"{'='*80}")
    
    # Save to CSV
    output_file = "staggered_panel_symmetric_2025.csv"
    df.to_csv(output_file, index=False)
    print(f"\n✓ Saved symmetric panel data to: {output_file}")
    
    return df


def run_symmetric_did_analysis(df):
    """Run DiD regression on symmetric panel."""
    print("\n" + "="*80)
    print("SYMMETRIC STAGGERED DiD REGRESSION ANALYSIS")
    print("="*80)
    
    print("\nModel: Two-Way Fixed Effects")
    print("-" * 60)
    
    formula = 'ln_players ~ did + C(appid) + C(month) - 1'
    
    model = ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    print(model.summary())
    
    # Extract DiD coefficient
    did_coef = model.params.get('did', np.nan)
    did_se = model.bse.get('did', np.nan)
    did_pval = model.pvalues.get('did', np.nan)
    
    ci_low = did_coef - 1.96 * did_se
    ci_high = did_coef + 1.96 * did_se
    
    percent_change = (np.exp(did_coef) - 1) * 100
    
    print("\n" + "="*80)
    print("SYMMETRIC STAGGERED DiD RESULTS (Two-Way FE)")
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
        'model': 'Two-Way Fixed Effects (Symmetric Windows)',
        'coefficient': float(did_coef),
        'std_error': float(did_se),
        'p_value': float(did_pval),
        'ci_low': float(ci_low),
        'ci_high': float(ci_high),
        'effect_size_pct': float(percent_change),
        'n_obs': len(df),
        'n_games': df['appid'].nunique(),
        'time_span': 'Oct 2024 - Jul 2025',
        'cohort_window': 't-3 to t+3 (7 months each)'
    }
    
    with open('staggered_symmetric_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    return model, results


def run_symmetric_event_study(df):
    """
    Run event study with symmetric relative time windows.
    Each cohort: t-3, t-2, t-1, t, t+1, t+2, t+3
    Reference: t=-1
    """
    print("\n" + "="*80)
    print("SYMMETRIC EVENT STUDY (RELATIVE TIME)")
    print("All cohorts: t-3 to t+3 (reference: t=-1)")
    print("="*80)
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    
    # Create cohort × relative time dummies
    for cohort in cohorts:
        cohort_df = df[df['treatment_group'] == cohort]
        for idx in cohort_df.index:
            rel_time = df.loc[idx, 'rel_time']
            for tau in [-3, -2, 0, 1, 2, 3]:  # Omit -1 as reference
                var_name = f'{cohort}_tau{tau}' if tau >= 0 else f'{cohort}_taum{abs(tau)}'
                df.loc[idx, var_name] = 1 if rel_time == tau else 0
    
    # Fill NaN with 0
    cohort_time_vars = []
    for cohort in cohorts:
        for tau in [-3, -2, 0, 1, 2, 3]:
            var_name = f'{cohort}_tau{tau}' if tau >= 0 else f'{cohort}_taum{abs(tau)}'
            cohort_time_vars.append(var_name)
            if var_name not in df.columns:
                df[var_name] = 0
            df[var_name] = df[var_name].fillna(0)
    
    # Build formula
    formula = 'ln_players ~ ' + ' + '.join(cohort_time_vars) + ' + C(appid) + C(month) - 1'
    
    print(f"\nEstimating event study with {len(cohort_time_vars)} cohort-time interactions...")
    print(f"Reference: t=-1 for each cohort")
    
    model_event = ols(formula, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Extract coefficients
    cohort_results = {}
    
    for cohort in cohorts:
        cohort_results[cohort] = []
        
        # Add reference point (t=-1)
        cohort_results[cohort].append({
            'rel_time': -1,
            'coef': 0.0,
            'se': 0.0,
            'ci_low': 0.0,
            'ci_high': 0.0,
            'pval': 1.0
        })
        
        for tau in [-3, -2, 0, 1, 2, 3]:
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
    print("SYMMETRIC EVENT STUDY RESULTS")
    print("="*80)
    
    for cohort in cohorts:
        print(f"\n{cohort.upper()} COHORT:")
        print("-" * 80)
        print(f"{'Rel Time':<12} {'Coefficient':>12} {'Std Err':>10} {'P-value':>10} {'95% CI':>28}")
        print("-" * 80)
        
        for result in cohort_results[cohort]:
            tau = result['rel_time']
            coef = result['coef']
            se = result['se']
            pval = result['pval']
            ci = f"[{result['ci_low']:>7.4f}, {result['ci_high']:>7.4f}]"
            
            tau_str = f"t={tau:+d}" if tau != -1 else "t=-1 (ref)"
            pval_str = f"{pval:.4f}" if pval < 1.0 else "---"
            se_str = f"{se:.4f}" if se > 0 else "---"
            
            sig_marker = " ***" if pval < 0.01 else (" **" if pval < 0.05 else (" *" if pval < 0.10 else ""))
            
            print(f"{tau_str:<12} {coef:>12.4f} {se_str:>10} {pval_str:>10} {ci:>28}{sig_marker}")
    
    print("=" * 80)
    print("*** p<0.01, ** p<0.05, * p<0.10")
    
    return model_event, cohort_results


def plot_symmetric_event_studies(cohort_results):
    """Create visualizations for symmetric event studies."""
    print("\n--- Creating symmetric event study plots ---")
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_labels = {
        'jan': 'January 2025 Cohort',
        'feb': 'February 2025 Cohort',
        'mar': 'March 2025 Cohort',
        'apr': 'April 2025 Cohort'
    }
    colors = {
        'jan': 'steelblue',
        'feb': 'coral',
        'mar': 'seagreen',
        'apr': 'mediumpurple'
    }
    
    # 1. By-cohort subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, cohort in enumerate(cohorts):
        ax = axes[idx]
        
        results_df = pd.DataFrame(cohort_results[cohort])
        
        ax.plot(results_df['rel_time'], results_df['coef'],
               marker='o', markersize=10, linewidth=2.5,
               color=colors[cohort], label='DiD Estimate', zorder=3)
        
        ax.fill_between(results_df['rel_time'],
                        results_df['ci_low'],
                        results_df['ci_high'],
                        alpha=0.25, color=colors[cohort], label='95% CI')
        
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.7, zorder=1)
        ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5,
                  alpha=0.7, label='Treatment Time', zorder=2)
        
        ax.axvspan(-3.5, -0.5, alpha=0.1, color='orange', zorder=0)
        ax.axvspan(-0.5, 3.5, alpha=0.1, color='lightblue', zorder=0)
        
        ax.set_xlabel('Relative Time to Treatment', fontsize=12, fontweight='bold')
        ax.set_ylabel('Treatment Effect (Log Points)', fontsize=12, fontweight='bold')
        ax.set_title(f'{cohort_labels[cohort]}\nSymmetric Event Window (t-3 to t+3)',
                    fontsize=13, fontweight='bold')
        
        ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
        ax.set_xticklabels(['t-3', 't-2', 't-1\n(ref)', 't', 't+1', 't+2', 't+3'])
        
        ax.legend(loc='best', fontsize=10, framealpha=0.95)
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/symmetric_event_study_by_cohort.png'
    os.makedirs('Actual_final_results', exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {save_path}")
    plt.close()
    
    # 2. Combined plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    for cohort in cohorts:
        results_df = pd.DataFrame(cohort_results[cohort])
        
        offset = {'jan': -0.15, 'feb': -0.05, 'mar': 0.05, 'apr': 0.15}[cohort]
        x_positions = results_df['rel_time'] + offset
        
        ax.errorbar(x_positions, results_df['coef'],
                   yerr=[results_df['coef'] - results_df['ci_low'],
                         results_df['ci_high'] - results_df['coef']],
                   fmt='o', markersize=8, capsize=5, capthick=2,
                   color=colors[cohort], ecolor=colors[cohort],
                   label=cohort_labels[cohort], alpha=0.8, zorder=3)
    
    ax.axhline(y=0, color='black', linestyle='-', linewidth=2, alpha=0.7, zorder=1)
    ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5,
              alpha=0.6, label='Treatment Time', zorder=2)
    
    ax.axvspan(-3.5, -0.5, alpha=0.1, color='orange', zorder=0)
    ax.axvspan(-0.5, 3.5, alpha=0.1, color='lightblue', zorder=0)
    
    ax.set_xlabel('Relative Time to Treatment', fontsize=13, fontweight='bold')
    ax.set_ylabel('Treatment Effect (Log Points)', fontsize=13, fontweight='bold')
    ax.set_title('Symmetric Staggered DiD Event Study - All Cohorts\n' +
                'Treatment Effects with 3 Pre-Periods and 3 Post-Periods (95% CI)',
                fontsize=15, fontweight='bold', pad=20)
    
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_xticklabels(['t-3', 't-2', 't-1\n(reference)', 't\n(treatment)', 't+1', 't+2', 't+3'])
    ax.set_xlim(-3.7, 3.7)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, ncol=2)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/symmetric_event_study_combined.png'
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {save_path}")
    plt.close()
    
    return True


def main():
    """Run symmetric staggered DiD analysis."""
    print("\n" + "="*80)
    print("SYMMETRIC STAGGERED DiD ANALYSIS")
    print("October 2024 - July 2025")
    print("Each cohort: 7 months (t-3, t-2, t-1, t, t+1, t+2, t+3)")
    print("="*80)
    
    # Create symmetric panel
    df = create_symmetric_panel()
    
    # Run main DiD regression
    model_main, results_main = run_symmetric_did_analysis(df)
    
    # Run symmetric event study
    model_event, cohort_results = run_symmetric_event_study(df)
    
    # Save cohort results
    with open('cohort_symmetric_results.json', 'w') as f:
        json.dump(cohort_results, f, indent=2)
    
    # Create visualizations
    plot_symmetric_event_studies(cohort_results)
    
    print("\n" + "="*80)
    print("SYMMETRIC ANALYSIS COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print("  1. staggered_panel_symmetric_2025.csv - Symmetric panel data")
    print("  2. staggered_symmetric_results.json - Main DiD results")
    print("  3. cohort_symmetric_results.json - Event study coefficients")
    print("  4. Actual_final_results/symmetric_event_study_by_cohort.png")
    print("  5. Actual_final_results/symmetric_event_study_combined.png")
    print("\nKey improvements:")
    print("  ✓ Each cohort has exactly 7 months (t-3 to t+3)")
    print("  ✓ 3 pre-treatment periods enable strong parallel trends testing")
    print("  ✓ 3 post-treatment periods for consistent effect measurement")
    print("  ✓ Balanced event study design across all cohorts")
    print("="*80)


if __name__ == "__main__":
    main()
