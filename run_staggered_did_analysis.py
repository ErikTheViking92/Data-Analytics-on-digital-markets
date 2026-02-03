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
from dateutil import parser as date_parser
from scraper.steamcharts_scraper import fetch_monthly_series
from scraper.store_scraper import SteamStoreScraper
from scraper.reviews_scraper import fetch_app_reviews

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


def fetch_game_metadata(appid: int, store_scraper: SteamStoreScraper):
    """Fetch game metadata for control variables."""
    metadata = {
        'genre_category': 'Other',  # Default
        'age_years': 2.0,  # Default
        'price_usd': 20.0,  # Default
        'is_free': 0,
        'review_score': 5.0  # Default (neutral)
    }
    
    try:
        # Fetch store data
        store_data = store_scraper.fetch_app(appid)
        
        if store_data:
            # Genre categorization (more specific)
            genres = store_data.get('genres', [])
            genre_str = ' '.join(genres).lower() if genres else ''
            
            if any(g in genre_str for g in ['action']):
                metadata['genre_category'] = 'Action'
            elif any(g in genre_str for g in ['adventure']):
                metadata['genre_category'] = 'Adventure'
            elif any(g in genre_str for g in ['rpg', 'role-playing']):
                metadata['genre_category'] = 'RPG'
            elif any(g in genre_str for g in ['strategy']):
                metadata['genre_category'] = 'Strategy'
            elif any(g in genre_str for g in ['simulation']):
                metadata['genre_category'] = 'Simulation'
            elif any(g in genre_str for g in ['sports', 'racing']):
                metadata['genre_category'] = 'Sports'
            else:
                metadata['genre_category'] = 'Other'
            
            # Release date (calculate age in years)
            release_date_str = store_data.get('release_date')
            if release_date_str:
                try:
                    release_date = date_parser.parse(release_date_str)
                    age_days = (datetime.now() - release_date).days
                    metadata['age_years'] = max(0, age_days / 365.25)
                except:
                    pass
            
            # Price
            price_overview = store_data.get('price_overview')
            if price_overview:
                # Price is in cents
                metadata['price_usd'] = price_overview.get('final', 0) / 100.0
                metadata['is_free'] = 0
            elif store_data.get('is_free', False):
                metadata['price_usd'] = 0.0
                metadata['is_free'] = 1
        
        # Fetch review score
        try:
            review_data = fetch_app_reviews(appid)
            if review_data and 'percent_positive' in review_data:
                pct = review_data['percent_positive']
                if pct is not None and 0 <= pct <= 100:
                    metadata['review_score'] = pct / 10.0  # Convert to 0-10 scale
        except Exception as e:
            pass  # Use default
    
    except Exception as e:
        # Use defaults on error
        pass
    
    return metadata


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
    
    # Initialize store scraper for metadata
    store_scraper = SteamStoreScraper()
    
    def process_group(games, group_name, treatment_month_idx):
        """Process a treatment or control group."""
        nonlocal game_id
        
        for game_entry in games:
            appid = game_entry["appid"]
            name = game_entry["name"]
            
            # Fetch metadata for control variables (do once per game)
            metadata = fetch_game_metadata(appid, store_scraper)
            
            # Fetch historical monthly data
            monthly_data = fetch_monthly_series(appid)
            
            # Create lookup dict by month using 'avg' player count
            monthly_lookup = {}
            for entry in monthly_data:
                try:
                    date_str = entry.get("date", "")
                    if date_str:
                        # Handle both YYYY-MM-DD and YYYY-MM formats
                        if len(date_str) >= 7:  # At least YYYY-MM
                            month_key = date_str[:7]  # Get YYYY-MM part
                            avg_players = entry.get("avg", entry.get("peak", 0))
                            if avg_players and avg_players > 0:
                                monthly_lookup[month_key] = int(avg_players)
                except Exception as e:
                    continue
            
            # Check if we have complete data for all 5 periods
            has_complete_data = all(monthly_lookup.get(month.strftime('%Y-%m'), 0) > 0 
                                   for month in months)
            
            if not has_complete_data:
                # Skip this game - we need complete time-varying data for valid DiD
                continue
            
            # Create row for each time period
            for period_idx, month in enumerate(months):
                month_key = month.strftime('%Y-%m')
                
                # Get player count from monthly data (guaranteed to exist by earlier check)
                players = monthly_lookup.get(month_key, 1000)
                
                if players == 0:
                    players = 1000  # Minimum fallback to avoid log(0)
                
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
                    'ln_players': np.log(max(players, 1)),  # Avoid log(0)
                    # Control variables (game-level, constant across time)
                    'genre_category': metadata['genre_category'],
                    'age_years': metadata['age_years'],
                    'price_usd': metadata['price_usd'],
                    'is_free': metadata['is_free'],
                    'review_score': metadata['review_score']
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
    print(f"\n[OK] Saved panel data to: {output_file}")
    
    return df


def run_did_regression(df):
    """Run DiD regression models."""
    print("\n" + "="*80)
    print("STAGGERED DIFFERENCE-IN-DIFFERENCES REGRESSION ANALYSIS")
    print("="*80)
    
    # Model 1: Basic DiD with time fixed effects and control variables (pooled OLS)
    print("\nModel 1: Basic Staggered DiD with Control Variables (Pooled OLS)")
    print("-" * 60)
    print("Dependent Variable: ln_players (natural log of player counts)")
    print("Reference Period: January 2025 (timedum_2)")
    print("Reference Genre: Other (genre_category encoded)")
    
    # Handle missing values in control variables
    print(f"\nHandling missing values in control variables...")
    print(f"  Missing age_years: {df['age_years'].isna().sum()}")
    print(f"  Missing price_usd: {df['price_usd'].isna().sum()}")
    print(f"  Missing review_score: {df['review_score'].isna().sum()}")
    
    # Fill missing values with medians (use 0 if all missing)
    if df['age_years'].notna().any():
        df['age_years'] = df['age_years'].fillna(df['age_years'].median())
    else:
        df['age_years'] = df['age_years'].fillna(5.0)  # Default 5 years
    
    if df['price_usd'].notna().any():
        df['price_usd'] = df['price_usd'].fillna(df['price_usd'].median())
    else:
        df['price_usd'] = df['price_usd'].fillna(0.0)
    
    if df['review_score'].notna().any():
        df['review_score'] = df['review_score'].fillna(df['review_score'].median())
    else:
        df['review_score'] = df['review_score'].fillna(7.0)  # Default 70% positive (typical median)
    
    # Build formula with time dummies (exclude timedum_2/January as reference)
    time_vars = ['timedum_1'] + [f'timedum_{i}' for i in range(3, 6)]
    
    # Add control variables
    control_vars = [
        'C(genre_category)',  # Genre (categorical: mmo, multiplayer, singleplayer, other)
        'age_years',          # Game age in years
        'price_usd',          # Current price in USD
        'is_free',            # Free-to-play indicator
        'review_score'        # Steam review score (0-10)
    ]
    
    formula1 = f"ln_players ~ treated + post + did + {' + '.join(time_vars)} + {' + '.join(control_vars)}"
    
    model1 = ols(formula1, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Display only key coefficients
    print("\nKey DiD Coefficients:")
    print(f"{'Variable':<30} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 70)
    
    coef_names = ['Intercept', 'treated', 'post', 'did'] + time_vars
    for var in coef_names:
        if var in model1.params:
            coef = model1.params[var]
            se = model1.bse[var]
            pval = model1.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<30} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print("\nControl Variables:")
    print(f"{'Variable':<30} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 70)
    
    # Display control variable coefficients
    control_coef_names = [
        'C(genre_category)[T.mmo]',
        'C(genre_category)[T.multiplayer]', 
        'C(genre_category)[T.singleplayer]',
        'age_years',
        'price_usd',
        'is_free',
        'review_score'
    ]
    
    for var in control_coef_names:
        if var in model1.params:
            coef = model1.params[var]
            se = model1.bse[var]
            pval = model1.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<30} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\nModel Statistics:")
    print(f"  N observations: {model1.nobs:.0f}")
    print(f"  R-squared: {model1.rsquared:.4f}")
    print(f"  Cluster-robust standard errors (clustered by game)")
    
    # Model 2: With game fixed effects AND time fixed effects (absorbs time-invariant 'treated')
    print("\n\nModel 2: Staggered DiD with Game & Time Fixed Effects (Preferred Model)")
    print("-" * 60)
    print("Dependent Variable: ln_players (natural log of player counts)")
    print("Reference Period: January 2025 (timedum_2)")
    print("Note: 'treated' is absorbed by game FE since treatment doesn't vary within games")
    print("      Game fixed effects control for time-invariant game characteristics")
    print("      Time fixed effects control for global shocks (e.g., Steam sales, holidays)")
    
    # With game FE, we drop 'treated' (absorbed) and keep 'did' which varies within games over time
    # Time dummies (timedum_1, timedum_3-5) are the time fixed effects
    formula2 = f"ln_players ~ did + C(appid) + {' + '.join(time_vars)}"
    model2 = ols(formula2, data=df).fit(cov_type='cluster', cov_kwds={'groups': df['appid']})
    
    # Display only key coefficients (not individual game FE)
    print("\nKey DiD Coefficient:")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    
    if 'did' in model2.params:
        coef = model2.params['did']
        se = model2.bse['did']
        pval = model2.pvalues['did']
        sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
        print(f"{'did':<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print("\nTime Fixed Effects (control for period-specific shocks):")
    print(f"{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-" * 60)
    
    coef_names = ['Intercept'] + time_vars
    for var in coef_names:
        if var in model2.params:
            coef = model2.params[var]
            se = model2.bse[var]
            pval = model2.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\n  [Game Fixed Effects: {df['appid'].nunique()} games included but not displayed]")
    print(f"  [Time Fixed Effects: {len(time_vars)+1} periods included (Dec, Jan, Feb, Mar, Apr)]")
    print(f"\nModel Statistics:")
    print(f"  N observations: {model2.nobs:.0f}")
    print(f"  R-squared: {model2.rsquared:.4f}")
    print(f"  Cluster-robust standard errors (clustered by game)")
    print(f"\nInterpretation of Time Fixed Effects:")
    print(f"  - Control for aggregate time-varying shocks affecting ALL games")
    print(f"  - Examples: Steam sales, holidays, platform-wide events")
    print(f"  - Ensures DiD estimate isolates treatment effect from global trends")
    
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
    print(f"\n[OK] Results saved to: staggered_did_results.json")
    
    print("="*80)
    
    return model1, model2, model3


def plot_event_study_relative_time(df, model_name='staggered'):
    """
    Create event study plot showing treatment effects relative to treatment time.
    Similar to the February 2025 analysis style.
    """
    print("\n" + "="*80)
    print(f"CREATING EVENT STUDY PLOT (RELATIVE TIME) - {model_name.upper()}")
    print("="*80)
    
    # For staggered DiD, we'll create relative time for each treated game
    df_relative = []
    
    for idx, row in df.iterrows():
        if row['treated'] == 1:
            # Find when this game was treated based on treatment_group
            treatment_month = row['treatment_group']
            if treatment_month == 'jan':
                treatment_period = 2
            elif treatment_month == 'feb':
                treatment_period = 3
            elif treatment_month == 'mar':
                treatment_period = 4
            elif treatment_month == 'apr':
                treatment_period = 5
            else:
                continue
            
            relative_time = row['period'] - treatment_period
            df_relative.append({
                'relative_time': relative_time,
                'ln_players': row['ln_players'],
                'appid': row['appid'],
                'treated': 1,
                'post': 1 if relative_time >= 0 else 0
            })
    
    df_rel = pd.DataFrame(df_relative)
    
    if len(df_rel) == 0:
        print("No relative time data available")
        return None
    
    # Run regression with relative time dummies
    # Create time dummies for relative periods
    rel_times = sorted(df_rel['relative_time'].unique())
    
    # Exclude one period as reference (use -1 as reference)
    ref_time = -1
    time_dummies = []
    for t in rel_times:
        if t != ref_time:
            df_rel[f'rel_time_{int(t)}'] = (df_rel['relative_time'] == t).astype(int)
            time_dummies.append(f'rel_time_{int(t)}')
    
    # Run regression
    formula = f"ln_players ~ {' + '.join(time_dummies)} + C(appid)"
    
    try:
        model = ols(formula, data=df_rel).fit(cov_type='cluster', cov_kwds={'groups': df_rel['appid']})
        
        # Extract coefficients
        coefs = []
        for t in rel_times:
            if t == ref_time:
                coefs.append({
                    'relative_time': t,
                    'coef': 0,
                    'ci_low': 0,
                    'ci_high': 0,
                    'is_post': t >= 0
                })
            else:
                var = f'rel_time_{int(t)}'
                if var in model.params:
                    ci = model.conf_int().loc[var]
                    coefs.append({
                        'relative_time': t,
                        'coef': model.params[var],
                        'ci_low': ci[0],
                        'ci_high': ci[1],
                        'is_post': t >= 0
                    })
        
        coefs_df = pd.DataFrame(coefs).sort_values('relative_time')
        
        # Create plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Separate pre and post
        pre = coefs_df[coefs_df['is_post'] == False]
        post = coefs_df[coefs_df['is_post'] == True]
        
        # Plot pre-treatment with coral markers
        ax.errorbar(pre['relative_time'], pre['coef'],
                    yerr=[pre['coef'] - pre['ci_low'], pre['ci_high'] - pre['coef']],
                    fmt='o', markersize=10, capsize=6, capthick=2,
                    color='coral', ecolor='gray', linewidth=2,
                    label='Pre-Treatment', zorder=3)
        
        # Plot post-treatment with blue markers
        ax.errorbar(post['relative_time'], post['coef'],
                    yerr=[post['coef'] - post['ci_low'], post['ci_high'] - post['coef']],
                    fmt='s', markersize=10, capsize=6, capthick=2,
                    color='steelblue', ecolor='gray', linewidth=2,
                    label='Post-Treatment', zorder=3)
        
        # Add zero line
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.8, zorder=1)
        
        # Add treatment time line
        ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5, alpha=0.7,
                  label='Treatment (Feb 15, 2025)', zorder=2)
        
        # Shade pre and post regions
        ax.axvspan(coefs_df['relative_time'].min() - 0.5, -0.5, alpha=0.1, color='yellow',
                  label='Pre-Treatment Period', zorder=0)
        ax.axvspan(-0.5, coefs_df['relative_time'].max() + 0.5, alpha=0.1, color='lightblue',
                  label='Post-Treatment Period', zorder=0)
        
        # Formatting
        ax.set_xlabel('Months Relative to Major Patch Release', fontsize=14, fontweight='bold')
        ax.set_ylabel('Treatment Effect on Log(Player Count)', fontsize=14, fontweight='bold')
        ax.set_title(f'Event Study: Effect of Major Patches on Player Counts\n'
                    f'{model_name.upper()} (Jan-Apr 2025 Treatment Groups)',
                    fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='best', fontsize=11, framealpha=0.95, edgecolor='black')
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
        
        # Set x-axis
        ax.set_xticks(coefs_df['relative_time'])
        
        plt.tight_layout()
        
        # Save
        filename = f'staggered_event_study_relative_{model_name}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"[OK] Event study (relative time) plot saved to: {filename}")
        plt.close()
        
        return fig, coefs_df
        
    except Exception as e:
        print(f"Error creating relative time event study: {e}")
        return None, None


def plot_event_study_relative_time(df, model_name='staggered'):
    """
    Create event study plot showing treatment effects relative to treatment time.
    Similar to the February 2025 analysis style.
    """
    print("\n" + "="*80)
    print(f"CREATING EVENT STUDY PLOT (RELATIVE TIME) - {model_name.upper()}")
    print("="*80)
    
    # For staggered DiD, we'll create relative time for each treated game
    df_relative = []
    
    for idx, row in df.iterrows():
        if row['treated'] == 1:
            # Find when this game was treated based on treatment_group
            treatment_month = row['treatment_group']
            if treatment_month == 'jan':
                treatment_period = 2
            elif treatment_month == 'feb':
                treatment_period = 3
            elif treatment_month == 'mar':
                treatment_period = 4
            elif treatment_month == 'apr':
                treatment_period = 5
            else:
                continue
            
            relative_time = row['period'] - treatment_period
            df_relative.append({
                'relative_time': relative_time,
                'ln_players': row['ln_players'],
                'appid': row['appid'],
                'treated': 1,
                'post': 1 if relative_time >= 0 else 0
            })
    
    df_rel = pd.DataFrame(df_relative)
    
    if len(df_rel) == 0:
        print("No relative time data available")
        return None, None
    
    # Run regression with relative time dummies
    # Create time dummies for relative periods
    rel_times = sorted(df_rel['relative_time'].unique())
    
    # Exclude one period as reference (use -1 as reference)
    ref_time = -1
    time_dummies = []
    var_mapping = {}  # Map from relative time to variable name
    for t in rel_times:
        if t != ref_time:
            # Use 't' prefix for time variables to avoid negative sign issues
            var_name = f'rel_time_t{int(t)}' if t >= 0 else f'rel_time_neg{abs(int(t))}'
            df_rel[var_name] = (df_rel['relative_time'] == t).astype(int)
            time_dummies.append(var_name)
            var_mapping[t] = var_name
    
    # Run regression
    formula = f"ln_players ~ {' + '.join(time_dummies)} + C(appid)"
    
    try:
        model = ols(formula, data=df_rel).fit(cov_type='cluster', cov_kwds={'groups': df_rel['appid']})
        
        # Extract coefficients
        coefs = []
        for t in rel_times:
            if t == ref_time:
                coefs.append({
                    'relative_time': t,
                    'coef': 0,
                    'ci_low': 0,
                    'ci_high': 0,
                    'is_post': t >= 0
                })
            else:
                var = var_mapping[t]
                if var in model.params:
                    ci = model.conf_int().loc[var]
                    coefs.append({
                        'relative_time': t,
                        'coef': model.params[var],
                        'ci_low': ci[0],
                        'ci_high': ci[1],
                        'is_post': t >= 0
                    })
        
        coefs_df = pd.DataFrame(coefs).sort_values('relative_time')
        
        # Create plot
        fig, ax = plt.subplots(figsize=(14, 8))
        
        # Separate pre and post
        pre = coefs_df[coefs_df['is_post'] == False]
        post = coefs_df[coefs_df['is_post'] == True]
        
        # Plot pre-treatment with coral markers
        ax.errorbar(pre['relative_time'], pre['coef'],
                    yerr=[pre['coef'] - pre['ci_low'], pre['ci_high'] - pre['coef']],
                    fmt='o', markersize=10, capsize=6, capthick=2,
                    color='coral', ecolor='gray', linewidth=2,
                    label='Pre-Treatment', zorder=3)
        
        # Plot post-treatment with blue markers
        ax.errorbar(post['relative_time'], post['coef'],
                    yerr=[post['coef'] - post['ci_low'], post['ci_high'] - post['coef']],
                    fmt='s', markersize=10, capsize=6, capthick=2,
                    color='steelblue', ecolor='gray', linewidth=2,
                    label='Post-Treatment', zorder=3)
        
        # Add zero line
        ax.axhline(y=0, color='black', linestyle='-', linewidth=1.5, alpha=0.8, zorder=1)
        
        # Add treatment time line
        ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2.5, alpha=0.7,
                  label='Treatment Time', zorder=2)
        
        # Shade pre and post regions
        ax.axvspan(coefs_df['relative_time'].min() - 0.5, -0.5, alpha=0.1, color='yellow',
                  label='Pre-Treatment Period', zorder=0)
        ax.axvspan(-0.5, coefs_df['relative_time'].max() + 0.5, alpha=0.1, color='lightblue',
                  label='Post-Treatment Period', zorder=0)
        
        # Formatting
        ax.set_xlabel('Months Relative to Major Patch Release', fontsize=14, fontweight='bold')
        ax.set_ylabel('Treatment Effect on Log(Player Count)', fontsize=14, fontweight='bold')
        ax.set_title(f'Event Study: Effect of Major Patches on Player Counts\\n'
                    f'{model_name.upper()} (Jan-Apr 2025 Treatment Groups)',
                    fontsize=16, fontweight='bold', pad=20)
        ax.legend(loc='best', fontsize=11, framealpha=0.95, edgecolor='black')
        ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
        
        # Set x-axis
        ax.set_xticks(coefs_df['relative_time'])
        
        plt.tight_layout()
        
        # Save
        filename = f'staggered_event_study_relative_{model_name}.png'
        plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
        print(f"[OK] Event study (relative time) plot saved to: {filename}")
        plt.close()
        
        return fig, coefs_df
        
    except Exception as e:
        print(f"Error creating relative time event study: {e}")
        return None, None


def plot_event_study(df, model3, model_name='model2'):
    """Create event study plot showing cohort-specific treatment effects over time."""
    print("\n" + "="*80)
    print(f"CREATING EVENT STUDY PLOT - {model_name.upper()}")
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
    filename = f'staggered_did_event_study_{model_name}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] Event study plot saved to: {filename}")
    plt.close()
    
    return fig, coefs_df


def plot_parallel_trends(df, model, model_name='model2'):
    """
    Plot parallel trends visualization showing treatment vs control groups over time.
    Similar to February 2025 analysis style with 95% confidence intervals.
    """
    print("\n" + "="*80)
    print(f"CREATING PARALLEL TRENDS PLOT (WITH 95% CI) - {model_name.upper()}")
    print("="*80)
    
    # Calculate means and standard errors by period and treatment group
    stats = df.groupby(['period', 'treated']).agg({
        'ln_players': ['mean', 'std', 'count']
    }).reset_index()
    stats.columns = ['period', 'treated', 'mean', 'std', 'count']
    stats['se'] = stats['std'] / np.sqrt(stats['count'])
    stats['ci_low'] = stats['mean'] - 1.96 * stats['se']
    stats['ci_high'] = stats['mean'] + 1.96 * stats['se']
    
    # Separate treatment and control
    control = stats[stats['treated'] == 0].sort_values('period')
    treatment = stats[stats['treated'] == 1].sort_values('period')
    
    # Month labels
    month_labels = ['Dec 2024', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025']
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot treatment group with confidence interval
    ax.plot(treatment['period'], treatment['mean'], 
           'o-', color='steelblue', linewidth=3, markersize=10,
           label='Treatment Group (500 games)', zorder=3)
    ax.fill_between(treatment['period'], treatment['ci_low'], treatment['ci_high'],
                    alpha=0.3, color='steelblue', label='95% CI (Treatment)')
    
    # Plot control group with confidence interval
    ax.plot(control['period'], control['mean'],
           's-', color='coral', linewidth=3, markersize=10,
           label='Control Group (100 games)', zorder=3)
    ax.fill_between(control['period'], control['ci_low'], control['ci_high'],
                    alpha=0.3, color='coral', label='95% CI (Control)')
    
    # Add vertical line indicating average treatment timing
    # For staggered design, treatment starts vary (Jan-Apr), so show approximate middle
    ax.axvline(x=2.5, color='red', linestyle='--', linewidth=2.5, alpha=0.7,
              label='Avg Treatment Time', zorder=2)
    
    # Shade pre-treatment and post-treatment regions
    ax.axvspan(0.5, 2.5, alpha=0.1, color='gray', label='Pre-Treatment')
    ax.axvspan(2.5, 5.5, alpha=0.1, color='yellow', label='Post-Treatment')
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=14, fontweight='bold')
    ax.set_ylabel('Log(Player Count)', fontsize=14, fontweight='bold')
    ax.set_title('Parallel Trends: Treatment vs Control Groups\n' +
                'Staggered DiD Analysis (Dec 2024 - Apr 2025)',
                fontsize=16, fontweight='bold', pad=20)
    ax.legend(loc='best', fontsize=11, framealpha=0.95, edgecolor='black', ncol=2)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    # Set x-axis
    ax.set_xlim(0.7, 5.3)
    ax.set_xticks(range(1, 6))
    ax.set_xticklabels(month_labels, fontsize=11)
    
    # Add interpretation note
    ax.text(0.5, 0.02,
           'Parallel trends assumption: Pre-treatment trends should be similar\n' +
           'DiD effect: Difference between groups after treatment',
           transform=ax.transAxes, fontsize=10, ha='center',
           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.7))
    
    plt.tight_layout()
    
    # Save
    filename = f'staggered_parallel_trends_{model_name}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] Parallel trends plot saved to: {filename}")
    plt.close()
    
    return fig


def plot_did_effect_lines(df, model, model_name='model2'):
    """
    Create DiD effect visualization showing treatment vs control with counterfactual.
    
    Simplified approach:
    - Control Group: Average ln_players for control games over time
    - Treatment Group: Average ln_players for treated games over time
    - Counterfactual: What treatment group would look like without treatment
                     (= pre-treatment level + control group's change over time)
    """
    print("\n" + "="*80)
    print(f"CREATING DiD EFFECT PLOT (WITH COUNTERFACTUAL LINES) - {model_name.upper()}")
    print("="*80)
    
    # Calculate means for each period and group
    period_means = df.groupby(['period', 'treated'])['ln_players'].mean().reset_index()
    
    # Separate treatment and control
    control_means = period_means[period_means['treated'] == 0].sort_values('period').reset_index(drop=True)
    treatment_means = period_means[period_means['treated'] == 1].sort_values('period').reset_index(drop=True)
    
    # Get DiD effect from model
    did_coef_model = model.params.get('did', 0.0)
    percent_change_model = (np.exp(did_coef_model) - 1) * 100
    did_pval = model.pvalues.get('did', 1.0)
    
    # Calculate counterfactual:
    # Pre-treatment (period 1): Same as actual treatment group
    # Post-treatment (periods 2-5): Treatment group's period 1 level + control group's change from period 1
    
    treatment_period1 = treatment_means[treatment_means['period'] == 1]['ln_players'].values[0]
    control_period1 = control_means[control_means['period'] == 1]['ln_players'].values[0]
    
    # Counterfactual for each period = treatment_period1 + (control_period_t - control_period1)
    counterfactual = []
    for period in range(1, 6):
        control_period_t = control_means[control_means['period'] == period]['ln_players'].values[0]
        cf_value = treatment_period1 + (control_period_t - control_period1)
        counterfactual.append({'period': period, 'ln_players_cf': cf_value})
    
    counterfactual_df = pd.DataFrame(counterfactual)
    
    # Time labels
    month_labels = ['Dec 2024', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025']
    periods = range(1, 6)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot control group
    ax.plot(control_means['period'], control_means['ln_players'], 'o-',
            color='coral', linewidth=3, markersize=12,
            label='Control Group', zorder=3)
    
    # Plot treatment group (actual)
    ax.plot(treatment_means['period'], treatment_means['ln_players'], 's-',
            color='steelblue', linewidth=3, markersize=12,
            label='Treatment Group (Actual)', zorder=3)
    
    # Plot counterfactual (parallel to control, shifted to treatment's pre-treatment level)
    ax.plot(counterfactual_df['period'], counterfactual_df['ln_players_cf'], 's--',
            color='steelblue', linewidth=2.5, markersize=10, alpha=0.5,
            label='Counterfactual (No Patch)', zorder=2)
    
    # Add shaded region showing DiD effect for post-treatment periods (period 2+)
    if abs(did_coef_model) > 0.001:
        post_periods = counterfactual_df[counterfactual_df['period'] >= 2]['period']
        actual_post = treatment_means[treatment_means['period'] >= 2]['ln_players']
        counterfactual_post = counterfactual_df[counterfactual_df['period'] >= 2]['ln_players_cf']
        
        ax.fill_between(post_periods, actual_post, counterfactual_post,
                        alpha=0.2, color='green', label='DiD Effect Region')
    
    # Add arrow showing DiD effect at the last period
    last_period = 5
    treatment_last = treatment_means[treatment_means['period'] == last_period]['ln_players'].values[0]
    counterfactual_last = counterfactual_df[counterfactual_df['period'] == last_period]['ln_players_cf'].values[0]
    
    if abs(treatment_last - counterfactual_last) > 0.01:  # Only show arrow if effect is visible
        ax.annotate('', xy=(last_period, treatment_last), xytext=(last_period, counterfactual_last),
                    arrowprops=dict(arrowstyle='<->', color='green', lw=3))
        # Position text to the right of arrow
        mid_point = (treatment_last + counterfactual_last) / 2
        ax.text(last_period + 0.15, mid_point,
                f'DiD Effect:\n{percent_change_model:+.2f}%',
                fontsize=11, fontweight='bold', color='green',
                verticalalignment='center')
    
    # Add vertical lines for each cohort's treatment timing
    # Jan cohort: treated at period 2 (Jan 2025)
    ax.axvline(x=1.5, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Jan Cohort Treatment', zorder=1)
    # Feb cohort: treated at period 3 (Feb 2025)
    ax.axvline(x=2.5, color='#3498db', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Feb Cohort Treatment', zorder=1)
    # Mar cohort: treated at period 4 (Mar 2025)
    ax.axvline(x=3.5, color='#2ecc71', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Mar Cohort Treatment', zorder=1)
    # Apr cohort: treated at period 5 (Apr 2025)
    ax.axvline(x=4.5, color='#f39c12', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Apr Cohort Treatment', zorder=1)
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=14, fontweight='bold')
    ax.set_ylabel('Log(Player Count)', fontsize=14, fontweight='bold')
    ax.set_title('Difference-in-Differences: Effect of Major Patches on Player Counts\n' +
                f'Staggered DiD Analysis - {model_name.upper()}',
                fontsize=16, fontweight='bold', pad=20)
    
    # Set x-axis to show all 5 time periods
    ax.set_xlim(0.7, 5.3)
    ax.set_xticks(periods)
    ax.set_xticklabels(month_labels, fontsize=11)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, edgecolor='black')
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    # Add interpretation note using MODEL estimate
    if did_pval < 0.05:
        interpretation = f"DiD Estimate: {percent_change_model:+.2f}% (p={did_pval:.4f}, significant)"
        note_color = 'lightgreen'
    else:
        interpretation = f"DiD Estimate: {percent_change_model:+.2f}% (p={did_pval:.4f}, not significant)"
        note_color = 'lightyellow'
    
    ax.text(0.5, 0.02, interpretation,
           transform=ax.transAxes, fontsize=11, fontweight='bold',
           ha='center', bbox=dict(boxstyle='round', facecolor=note_color, alpha=0.8))
    
    plt.tight_layout()
    
    # Save
    filename = f'staggered_did_effect_lines_{model_name}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] DiD effect (lines) plot saved to: {filename}")
    plt.close()
    
    return fig


def plot_did_effect_actual_players(df, model, model_name='model2'):
    """
    Create DiD effect visualization with ACTUAL player counts (not log).
    This makes the effect more visible and interpretable.
    """
    print("\n" + "="*80)
    print(f"CREATING DiD EFFECT PLOT - ACTUAL PLAYER COUNTS - {model_name.upper()}")
    print("="*80)
    
    # Calculate means for each period and group
    period_means = df.groupby(['period', 'treated'])['players'].mean().reset_index()
    
    # Separate treatment and control
    control_means = period_means[period_means['treated'] == 0].sort_values('period').reset_index(drop=True)
    treatment_means = period_means[period_means['treated'] == 1].sort_values('period').reset_index(drop=True)
    
    # Get DiD effect from model (still in log terms)
    did_coef_model = model.params.get('did', 0.0)
    percent_change_model = (np.exp(did_coef_model) - 1) * 100
    did_pval = model.pvalues.get('did', 1.0)
    
    # Calculate counterfactual in actual player counts
    # Pre-treatment (period 1): Same as actual treatment group
    # Post-treatment: Treatment group's period 1 level + control group's change from period 1
    treatment_period1 = treatment_means[treatment_means['period'] == 1]['players'].values[0]
    control_period1 = control_means[control_means['period'] == 1]['players'].values[0]
    
    counterfactual = []
    for period in range(1, 6):
        control_period_t = control_means[control_means['period'] == period]['players'].values[0]
        cf_value = treatment_period1 + (control_period_t - control_period1)
        counterfactual.append({'period': period, 'players_cf': cf_value})
    
    counterfactual_df = pd.DataFrame(counterfactual)
    
    # Time labels
    month_labels = ['Dec 2024', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025']
    periods = range(1, 6)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot control group
    ax.plot(control_means['period'], control_means['players'], 'o-',
            color='coral', linewidth=3, markersize=12,
            label='Control Group', zorder=3)
    
    # Plot treatment group (actual)
    ax.plot(treatment_means['period'], treatment_means['players'], 's-',
            color='steelblue', linewidth=3, markersize=12,
            label='Treatment Group (Actual)', zorder=3)
    
    # Plot counterfactual
    ax.plot(counterfactual_df['period'], counterfactual_df['players_cf'], 's--',
            color='steelblue', linewidth=2.5, markersize=10, alpha=0.5,
            label='Counterfactual (No Patch)', zorder=2)
    
    # Add shaded region showing DiD effect
    post_periods = counterfactual_df[counterfactual_df['period'] >= 2]['period']
    actual_post = treatment_means[treatment_means['period'] >= 2]['players']
    counterfactual_post = counterfactual_df[counterfactual_df['period'] >= 2]['players_cf']
    
    ax.fill_between(post_periods, actual_post, counterfactual_post,
                    alpha=0.2, color='green', label='DiD Effect Region')
    
    # Add arrow showing DiD effect at the last period
    last_period = 5
    treatment_last = treatment_means[treatment_means['period'] == last_period]['players'].values[0]
    counterfactual_last = counterfactual_df[counterfactual_df['period'] == last_period]['players_cf'].values[0]
    
    if abs(treatment_last - counterfactual_last) > 10:  # Only show if visible
        ax.annotate('', xy=(last_period, treatment_last), xytext=(last_period, counterfactual_last),
                    arrowprops=dict(arrowstyle='<->', color='green', lw=3))
        mid_point = (treatment_last + counterfactual_last) / 2
        ax.text(last_period + 0.15, mid_point,
                f'DiD Effect:\n{percent_change_model:+.2f}%',
                fontsize=11, fontweight='bold', color='green',
                verticalalignment='center')
    
    # Add vertical lines for cohort treatment timing
    ax.axvline(x=1.5, color='#e74c3c', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Jan Cohort Treatment', zorder=1)
    ax.axvline(x=2.5, color='#3498db', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Feb Cohort Treatment', zorder=1)
    ax.axvline(x=3.5, color='#2ecc71', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Mar Cohort Treatment', zorder=1)
    ax.axvline(x=4.5, color='#f39c12', linestyle='--', linewidth=1.5, alpha=0.6,
              label='Apr Cohort Treatment', zorder=1)
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=14, fontweight='bold')
    ax.set_ylabel('Average Concurrent Players', fontsize=14, fontweight='bold')
    ax.set_title('Difference-in-Differences: Effect of Major Patches on Player Counts\n' +
                f'Staggered DiD Analysis - {model_name.upper()} (Actual Player Counts)',
                fontsize=16, fontweight='bold', pad=20)
    
    ax.set_xlim(0.7, 5.3)
    ax.set_xticks(periods)
    ax.set_xticklabels(month_labels, fontsize=11)
    
    # Format y-axis with commas
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{int(x):,}'))
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95, edgecolor='black')
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    # Add interpretation note
    if did_pval < 0.05:
        interpretation = f"DiD Estimate: {percent_change_model:+.2f}% (p={did_pval:.4f}, significant)"
        note_color = 'lightgreen'
    else:
        interpretation = f"DiD Estimate: {percent_change_model:+.2f}% (p={did_pval:.4f}, not significant)"
        note_color = 'lightyellow'
    
    ax.text(0.5, 0.02, interpretation,
           transform=ax.transAxes, fontsize=11, fontweight='bold',
           ha='center', bbox=dict(boxstyle='round', facecolor=note_color, alpha=0.8))
    
    plt.tight_layout()
    
    # Save
    filename = f'staggered_did_effect_actual_players_{model_name}.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] DiD effect (actual players) plot saved to: {filename}")
    plt.close()
    
    return fig


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
    print(f"[OK] DiD effect plot saved to: {filename}")
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
    
    # Step 3: Create visualizations
    print("\n" + "="*80)
    print("CREATING VISUALIZATIONS")
    print("="*80)
    
    # February-style visualizations for Model 1 (Pooled OLS)
    print("\n" + "-"*80)
    print("MODEL 1 VISUALIZATIONS (Pooled OLS)")
    print("-"*80)
    parallel_fig_m1 = plot_parallel_trends(df, model1, model_name='model1')
    did_lines_fig_m1 = plot_did_effect_lines(df, model1, model_name='model1')
    did_actual_fig_m1 = plot_did_effect_actual_players(df, model1, model_name='model1')
    
    # February-style visualizations for Model 2 (With Game FE)
    print("\n" + "-"*80)
    print("MODEL 2 VISUALIZATIONS (With Game FE)")
    print("-"*80)
    parallel_fig_m2 = plot_parallel_trends(df, model2, model_name='model2')
    did_lines_fig_m2 = plot_did_effect_lines(df, model2, model_name='model2')
    did_actual_fig_m2 = plot_did_effect_actual_players(df, model2, model_name='model2')
    
    # Simple coefficient plot
    did_fig = plot_did_effect(model2)
    
    # Event study plots (cohort-specific) for both models
    print("\n" + "-"*80)
    print("EVENT STUDY PLOTS (COHORT-SPECIFIC EFFECTS)")
    print("-"*80)
    event_fig_m1, coefs_df_m1 = plot_event_study(df, model3, model_name='model1')
    event_fig_m2, coefs_df_m2 = plot_event_study(df, model3, model_name='model2')
    
    # Event study plot (relative time)
    event_rel_fig, event_rel_coefs = plot_event_study_relative_time(df, model_name='staggered')
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nFiles created:")
    print("  1. staggered_panel_2025.csv - Panel dataset (google.csv style)")
    print("  2. staggered_did_results.json - Regression results summary")
    print("\n  Model 1 Visualizations (Pooled OLS):")
    print("  3. staggered_parallel_trends_model1.png - Parallel trends with 95% CI")
    print("  4. staggered_did_effect_lines_model1.png - DiD effect with counterfactual (log scale)")
    print("  5. staggered_did_effect_actual_players_model1.png - DiD effect (actual player counts)")
    print("  6. staggered_event_study_relative_model1.png - Event study (relative time)")
    print("\n  Model 2 Visualizations (With Game FE):")
    print("  7. staggered_parallel_trends_model2.png - Parallel trends with 95% CI")
    print("  8. staggered_did_effect_lines_model2.png - DiD effect with counterfactual (log scale)")
    print("  9. staggered_did_effect_actual_players_model2.png - DiD effect (actual player counts)")
    print("  10. staggered_did_effect_plot.png - Simple DiD coefficient plot")
    print("  11. staggered_did_event_study.png - Cohort-specific event study")
    print("  12. staggered_event_study_relative_staggered.png - Event study (relative time)")
    print("="*80)


if __name__ == "__main__":
    main()
