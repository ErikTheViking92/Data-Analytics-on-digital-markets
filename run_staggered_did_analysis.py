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
        'genre_category': 'other',  # Default
        'age_years': None,
        'price_usd': None,
        'is_free': 0,
        'review_score': None
    }
    
    try:
        # Fetch store data
        store_data = store_scraper.fetch_app(appid)
        
        if store_data:
            # Genre categorization
            genres = store_data.get('genres', [])
            genre_str = ' '.join(genres).lower() if genres else ''
            
            if any(g in genre_str for g in ['mmo', 'massively multiplayer']):
                metadata['genre_category'] = 'mmo'
            elif any(g in genre_str for g in ['multiplayer', 'competitive', 'pvp', 'online']):
                metadata['genre_category'] = 'multiplayer'
            elif any(g in genre_str for g in ['single-player', 'singleplayer', 'story']):
                metadata['genre_category'] = 'singleplayer'
            else:
                metadata['genre_category'] = 'other'
            
            # Release date (calculate age in years)
            release_date_str = store_data.get('release_date')
            if release_date_str:
                try:
                    release_date = date_parser.parse(release_date_str)
                    age_days = (datetime.now() - release_date).days
                    metadata['age_years'] = age_days / 365.25
                except:
                    metadata['age_years'] = None
            
            # Price
            price_overview = store_data.get('price_overview')
            if price_overview:
                # Price is in cents
                metadata['price_usd'] = price_overview.get('final', 0) / 100.0
                metadata['is_free'] = 0
            else:
                # Check if game is free
                metadata['price_usd'] = 0.0
                metadata['is_free'] = 1
        
        # Fetch review score
        try:
            review_data = fetch_app_reviews(appid)
            if review_data:
                # Use review score (0-10 scale based on percentage)
                pct = review_data.get('percent_positive')
                if pct is not None:
                    metadata['review_score'] = pct / 10.0  # Convert to 0-10 scale
        except:
            metadata['review_score'] = None
    
    except Exception as e:
        print(f"  [metadata] Error fetching metadata for {appid}: {e}")
    
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
                    # Control variables (game-level, constant across time)
                    'genre_category': metadata['genre_category'],
                    'age_years': metadata['age_years'] if metadata['age_years'] is not None else np.nan,
                    'price_usd': metadata['price_usd'] if metadata['price_usd'] is not None else np.nan,
                    'is_free': metadata['is_free'],
                    'review_score': metadata['review_score'] if metadata['review_score'] is not None else np.nan
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
    print(f"[OK] Event study plot saved to: {filename}")
    plt.close()
    
    return fig, coefs_df


def plot_parallel_trends(df, model2):
    """
    Plot parallel trends visualization showing treatment vs control groups over time.
    Similar to February 2025 analysis style with 95% confidence intervals.
    """
    print("\n" + "="*80)
    print("CREATING PARALLEL TRENDS PLOT (WITH 95% CI)")
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
    filename = 'staggered_parallel_trends.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] Parallel trends plot saved to: {filename}")
    plt.close()
    
    return fig


def plot_did_effect_lines(df, model2):
    """
    Create DiD effect visualization with parallel lines showing counterfactual.
    Shows the DiD effect with a green arrow, similar to February 2025 analysis.
    """
    print("\n" + "="*80)
    print("CREATING DiD EFFECT PLOT (WITH COUNTERFACTUAL LINES)")
    print("="*80)
    
    # Calculate group means for pre/post periods
    means = df.groupby(['post', 'treated'])['ln_players'].mean().reset_index()
    
    # Extract values
    control_pre = means[(means['treated'] == 0) & (means['post'] == 0)]['ln_players'].values[0]
    control_post = means[(means['treated'] == 0) & (means['post'] == 1)]['ln_players'].values[0]
    treatment_pre = means[(means['treated'] == 1) & (means['post'] == 0)]['ln_players'].values[0]
    treatment_post = means[(means['treated'] == 1) & (means['post'] == 1)]['ln_players'].values[0]
    
    # Calculate DiD effect
    did_effect = (treatment_post - treatment_pre) - (control_post - control_pre)
    percent_change = (np.exp(did_effect) - 1) * 100
    
    # Get p-value from model
    did_pval = model2.pvalues.get('did', 1.0)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot control group
    ax.plot([0, 1], [control_pre, control_post], 'o-',
            color='coral', linewidth=4, markersize=14,
            label='Control Group', zorder=3)
    
    # Plot treatment group
    ax.plot([0, 1], [treatment_pre, treatment_post], 's-',
            color='steelblue', linewidth=4, markersize=14,
            label='Treatment Group', zorder=3)
    
    # Plot counterfactual (what treatment would have been without patches)
    counterfactual_post = treatment_pre + (control_post - control_pre)
    ax.plot([0, 1], [treatment_pre, counterfactual_post], 's--',
            color='steelblue', linewidth=2.5, markersize=10, alpha=0.5,
            label='Counterfactual (No Patch)', zorder=2)
    
    # Highlight DiD effect with arrow
    if abs(did_effect) > 0.01:  # Only show arrow if effect is visible
        ax.annotate('', xy=(1, treatment_post), xytext=(1, counterfactual_post),
                    arrowprops=dict(arrowstyle='<->', color='green', lw=3))
        ax.text(1.08, (treatment_post + counterfactual_post) / 2,
                f'DiD Effect:\n{percent_change:+.2f}%',
                fontsize=12, fontweight='bold', color='green',
                verticalalignment='center')
    else:
        # If effect is very small, just show text annotation
        mid_y = (max(treatment_post, control_post) + min(treatment_pre, control_pre)) / 2
        ax.text(0.5, mid_y,
                f'DiD Effect: {percent_change:+.2f}%\n(Not statistically significant)',
                fontsize=13, fontweight='bold', color='gray',
                ha='center', va='center',
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8, edgecolor='black'))
    
    # Formatting
    ax.set_xlabel('Period', fontsize=14, fontweight='bold')
    ax.set_ylabel('Log(Player Count)', fontsize=14, fontweight='bold')
    ax.set_title('Difference-in-Differences: Effect of Major Patches on Player Counts\n' +
                'Staggered DiD Analysis (Dec 2024 - Apr 2025)',
                fontsize=16, fontweight='bold', pad=20)
    ax.set_xticks([0, 1])
    ax.set_xticklabels(['Pre-Treatment\n(Before Patches)', 
                        'Post-Treatment\n(After Patches)'],
                       fontsize=12)
    ax.legend(loc='best', fontsize=12, framealpha=0.95, edgecolor='black')
    ax.grid(True, alpha=0.3, linestyle=':')
    
    # Add interpretation note
    if did_pval < 0.05:
        interpretation = f"DiD Estimate: {percent_change:+.2f}% (p={did_pval:.4f}, significant)"
        note_color = 'lightgreen'
    else:
        interpretation = f"DiD Estimate: {percent_change:+.2f}% (p={did_pval:.4f}, not significant)"
        note_color = 'lightyellow'
    
    ax.text(0.5, 0.02, interpretation,
           transform=ax.transAxes, fontsize=11, fontweight='bold',
           ha='center', bbox=dict(boxstyle='round', facecolor=note_color, alpha=0.8))
    
    plt.tight_layout()
    
    # Save
    filename = 'staggered_did_effect_lines.png'
    plt.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"[OK] DiD effect (lines) plot saved to: {filename}")
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
    
    # February-style visualizations (parallel trends + DiD effect with counterfactual)
    parallel_fig = plot_parallel_trends(df, model2)
    did_lines_fig = plot_did_effect_lines(df, model2)
    
    # Simple coefficient plot
    did_fig = plot_did_effect(model2)
    
    # Event study plot
    event_fig, coefs_df = plot_event_study(df, model3)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print("\nFiles created:")
    print("  1. staggered_panel_2025.csv - Panel dataset (google.csv style)")
    print("  2. staggered_did_results.json - Regression results summary")
    print("  3. staggered_parallel_trends.png - Parallel trends with 95% CI")
    print("  4. staggered_did_effect_lines.png - DiD effect with counterfactual lines")
    print("  5. staggered_did_effect_plot.png - Simple DiD coefficient plot")
    print("  6. staggered_did_event_study.png - Event study visualization")
    print("="*80)


if __name__ == "__main__":
    main()
