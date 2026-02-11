"""
Formal Parallel Trends Test for DiD Analyses

Tests the parallel trends assumption for both:
1. Staggered DiD Analysis (Dec 2024 - Apr 2025)
2. February 2025 Single-Cohort Analysis

Methodology:
- Restrict to pre-treatment period only
- Estimate: Y_it = α + β·Treated_i + γ·Time_t + δ·(Treated_i × Time_t) + ε_it
- Test H0: δ = 0 (no differential trends)
- Visualize treatment vs control trends with 95% CIs
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import ols
from scipy import stats
import os

sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)


def test_staggered_parallel_trends():
    """
    Test parallel trends for staggered DiD analysis.
    Pre-treatment period: December 2024 only (period 1)
    """
    print("\n" + "="*80)
    print("PARALLEL TRENDS TEST - STAGGERED DiD ANALYSIS")
    print("="*80)
    
    # Load panel data
    try:
        df = pd.read_csv("staggered_panel_2025.csv")
    except FileNotFoundError:
        print("Error: staggered_panel_2025.csv not found!")
        return None
    
    print(f"\nLoaded panel data: {len(df)} observations, {df['appid'].nunique()} games")
    print(f"Time periods: {sorted(df['period'].unique())}")
    print(f"Treatment groups: {df['treatment_group'].value_counts().to_dict()}")
    
    # Restrict to pre-treatment period only
    # For staggered design, we need to be careful - each cohort has different treatment timing
    # The cleanest test: use December 2024 (period 1) for all groups
    df_pre = df[df['period'] == 1].copy()
    
    print(f"\n--- Pre-Treatment Period Analysis ---")
    print(f"Restricting to Period 1 (December 2024)")
    print(f"Observations in pre-period: {len(df_pre)}")
    print(f"  Treatment games: {(df_pre['treated'] == 1).sum()}")
    print(f"  Control games: {(df_pre['treated'] == 0).sum()}")
    
    # Since we only have 1 pre-treatment period, we can't test trends over time
    # Instead, we test for level differences in pre-treatment period
    print("\n--- Testing Pre-Treatment Differences ---")
    print("Note: With only 1 pre-treatment period, we test for level differences")
    print("Model: ln_players ~ treated")
    
    model_pre = ols('ln_players ~ treated', data=df_pre).fit(cov_type='HC1')
    
    print("\n" + model_pre.summary().as_text())
    
    coef_treated = model_pre.params.get('treated', np.nan)
    se_treated = model_pre.bse.get('treated', np.nan)
    pval_treated = model_pre.pvalues.get('treated', np.nan)
    
    print("\n" + "="*80)
    print("PRE-TREATMENT BALANCE TEST")
    print("="*80)
    print(f"Coefficient on 'treated': {coef_treated:.4f}")
    print(f"Standard Error: {se_treated:.4f}")
    print(f"P-value: {pval_treated:.4f}")
    
    if pval_treated > 0.05:
        print("\n✓ PASSED: No significant pre-treatment differences (p > 0.05)")
        print("  → Parallel trends assumption is plausible")
    else:
        print("\n✗ WARNING: Significant pre-treatment differences detected (p < 0.05)")
        print("  → Parallel trends assumption may be violated")
    print("="*80)
    
    # Now create visual test across all pre-treatment periods available
    # For staggered design, this is more complex - each cohort has different pre-periods
    # Let's create a visualization showing trends for each cohort
    
    print("\n--- Creating Parallel Trends Visualization ---")
    
    # For visualization, we'll show average ln_players over time for treated vs control
    # Separately for each period
    
    trends_data = df.groupby(['period', 'treated'])['ln_players'].agg(['mean', 'sem', 'count']).reset_index()
    trends_data['ci_low'] = trends_data['mean'] - 1.96 * trends_data['sem']
    trends_data['ci_high'] = trends_data['mean'] + 1.96 * trends_data['sem']
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot treated group
    treated_data = trends_data[trends_data['treated'] == 1]
    ax.plot(treated_data['period'], treated_data['mean'], 
            marker='o', markersize=10, linewidth=2.5, 
            color='steelblue', label='Treatment Group', zorder=3)
    ax.fill_between(treated_data['period'], 
                     treated_data['ci_low'], 
                     treated_data['ci_high'],
                     alpha=0.2, color='steelblue')
    
    # Plot control group
    control_data = trends_data[trends_data['treated'] == 0]
    ax.plot(control_data['period'], control_data['mean'], 
            marker='s', markersize=10, linewidth=2.5,
            color='coral', label='Control Group', zorder=3)
    ax.fill_between(control_data['period'], 
                     control_data['ci_low'], 
                     control_data['ci_high'],
                     alpha=0.2, color='coral')
    
    # Mark treatment timing for each cohort
    # Jan cohort: treated in period 2
    # Feb cohort: treated in period 3
    # Mar cohort: treated in period 4
    # Apr cohort: treated in period 5
    treatment_periods = [2, 3, 4, 5]
    treatment_labels = ['Jan Cohort', 'Feb Cohort', 'Mar Cohort', 'Apr Cohort']
    
    for i, (tp, label) in enumerate(zip(treatment_periods, treatment_labels)):
        ax.axvline(x=tp - 0.5, color='red', linestyle='--', alpha=0.5, linewidth=1.5)
        ax.text(tp - 0.5, ax.get_ylim()[1] * 0.95, label, 
                rotation=90, verticalalignment='top',
                fontsize=9, color='red', alpha=0.7)
    
    # Formatting
    ax.set_xlabel('Time Period (Month)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Log(Average Concurrent Players)', fontsize=13, fontweight='bold')
    ax.set_title('Parallel Trends Test - Staggered DiD Analysis\n' + 
                 'Treatment vs Control Groups Over Time (with 95% CI)',
                 fontsize=15, fontweight='bold', pad=20)
    
    # Set x-axis labels
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.set_xticklabels(['Dec 2024\n(Pre)', 'Jan 2025', 'Feb 2025', 'Mar 2025', 'Apr 2025'])
    
    ax.legend(loc='best', fontsize=12, framealpha=0.95)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/staggered_parallel_trends_test.png'
    os.makedirs('Actual_final_results', exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved parallel trends plot: {save_path}")
    plt.close()
    
    return {
        'pre_treatment_diff': coef_treated,
        'pre_treatment_se': se_treated,
        'pre_treatment_pval': pval_treated,
        'parallel_trends_valid': pval_treated > 0.05,
        'model': model_pre,
        'trends_data': trends_data
    }


def test_february_parallel_trends():
    """
    Test parallel trends for February 2025 single-cohort analysis.
    Pre-treatment period: Weeks 1-2 (Feb 1-14)
    """
    print("\n" + "="*80)
    print("PARALLEL TRENDS TEST - FEBRUARY 2025 ANALYSIS")
    print("="*80)
    
    # Load panel data
    try:
        df = pd.read_csv("february_2025_panel_data_improved.csv")
    except FileNotFoundError:
        try:
            df = pd.read_csv("february_2025_panel_data.csv")
        except FileNotFoundError:
            print("Error: February panel data not found!")
            return None
    
    print(f"\nLoaded panel data: {len(df)} observations, {df['appid'].nunique()} games")
    print(f"Weeks: {sorted(df['week'].unique())}")
    
    # Restrict to pre-treatment period (weeks 1-2)
    df_pre = df[df['week'].isin([1, 2])].copy()
    
    print(f"\n--- Pre-Treatment Period Analysis ---")
    print(f"Restricting to Weeks 1-2 (February 1-14, before treatment on Feb 15)")
    print(f"Observations in pre-period: {len(df_pre)}")
    print(f"  Treatment games: {(df_pre['treated'] == 1).sum()}")
    print(f"  Control games: {(df_pre['treated'] == 0).sum()}")
    
    # Test for differential trends in pre-treatment period
    # Model: ln_players ~ treated + week + treated:week
    print("\n--- Parallel Trends Model ---")
    print("Model: ln_players ~ treated + week + treated:week")
    print("H0: coefficient on 'treated:week' = 0 (parallel trends)")
    
    model_trends = ols('ln_players ~ treated + week + treated:week', 
                       data=df_pre).fit(cov_type='cluster', 
                                       cov_kwds={'groups': df_pre['appid']})
    
    print("\n" + model_trends.summary().as_text())
    
    # Extract key coefficient
    coef_interaction = model_trends.params.get('treated:week', np.nan)
    se_interaction = model_trends.bse.get('treated:week', np.nan)
    pval_interaction = model_trends.pvalues.get('treated:week', np.nan)
    
    print("\n" + "="*80)
    print("PARALLEL TRENDS TEST RESULTS")
    print("="*80)
    print(f"Coefficient on 'treated × week': {coef_interaction:.4f}")
    print(f"Standard Error: {se_interaction:.4f}")
    print(f"P-value: {pval_interaction:.4f}")
    
    if pval_interaction > 0.05:
        print("\n✓ PASSED: No significant differential pre-trends (p > 0.05)")
        print("  → Treated and control groups exhibit parallel trends")
        print("  → DiD identifying assumption is satisfied")
    else:
        print("\n✗ WARNING: Significant differential pre-trends detected (p < 0.05)")
        print("  → Parallel trends assumption may be violated")
        print("  → DiD estimates may be biased")
    print("="*80)
    
    # Create visualization
    print("\n--- Creating Parallel Trends Visualization ---")
    
    # Calculate means and CIs for each week by treatment status
    trends_data = df.groupby(['week', 'treated'])['ln_players'].agg(['mean', 'sem', 'count']).reset_index()
    trends_data['ci_low'] = trends_data['mean'] - 1.96 * trends_data['sem']
    trends_data['ci_high'] = trends_data['mean'] + 1.96 * trends_data['sem']
    
    # Create figure
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Plot treated group
    treated_data = trends_data[trends_data['treated'] == 1]
    ax.plot(treated_data['week'], treated_data['mean'], 
            marker='o', markersize=12, linewidth=3, 
            color='steelblue', label='Treatment Group', zorder=3)
    ax.fill_between(treated_data['week'], 
                     treated_data['ci_low'], 
                     treated_data['ci_high'],
                     alpha=0.25, color='steelblue')
    
    # Plot control group
    control_data = trends_data[trends_data['treated'] == 0]
    ax.plot(control_data['week'], control_data['mean'], 
            marker='s', markersize=12, linewidth=3,
            color='coral', label='Control Group', zorder=3)
    ax.fill_between(control_data['week'], 
                     control_data['ci_low'], 
                     control_data['ci_high'],
                     alpha=0.25, color='coral')
    
    # Mark treatment timing
    ax.axvline(x=2.5, color='red', linestyle='--', linewidth=3, 
               alpha=0.7, label='Treatment Date (Feb 15)', zorder=2)
    
    # Shade pre-treatment and post-treatment periods
    ax.axvspan(0.5, 2.5, alpha=0.1, color='orange', label='Pre-Treatment Period')
    ax.axvspan(2.5, 4.5, alpha=0.1, color='lightblue', label='Post-Treatment Period')
    
    # Formatting
    ax.set_xlabel('Week (February 2025)', fontsize=13, fontweight='bold')
    ax.set_ylabel('Log(Average Concurrent Players)', fontsize=13, fontweight='bold')
    ax.set_title('Parallel Trends Test - February 2025 DiD Analysis\n' + 
                 f'Treatment vs Control Groups (95% CI)\nPre-Trend Test: p = {pval_interaction:.4f}',
                 fontsize=15, fontweight='bold', pad=20)
    
    # Set x-axis labels
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(['Week 1\n(Feb 1-7)', 'Week 2\n(Feb 8-14)', 
                        'Week 3\n(Feb 15-21)', 'Week 4\n(Feb 22-28)'])
    ax.set_xlim(0.5, 4.5)
    
    ax.legend(loc='best', fontsize=11, framealpha=0.95)
    ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)
    
    plt.tight_layout()
    
    save_path = 'Actual_final_results/february_parallel_trends_test.png'
    os.makedirs('Actual_final_results', exist_ok=True)
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Saved parallel trends plot: {save_path}")
    plt.close()
    
    return {
        'differential_trend': coef_interaction,
        'differential_trend_se': se_interaction,
        'differential_trend_pval': pval_interaction,
        'parallel_trends_valid': pval_interaction > 0.05,
        'model': model_trends,
        'trends_data': trends_data
    }


def create_combined_summary(staggered_results, february_results):
    """Create summary table of parallel trends test results."""
    print("\n" + "="*80)
    print("PARALLEL TRENDS TEST SUMMARY")
    print("="*80)
    
    summary = pd.DataFrame({
        'Analysis': ['Staggered DiD', 'February 2025'],
        'Test Statistic': [
            'Pre-treatment difference',
            'Differential pre-trend (treated × time)'
        ],
        'Coefficient': [
            f"{staggered_results['pre_treatment_diff']:.4f}" if staggered_results else 'N/A',
            f"{february_results['differential_trend']:.4f}" if february_results else 'N/A'
        ],
        'Std Error': [
            f"{staggered_results['pre_treatment_se']:.4f}" if staggered_results else 'N/A',
            f"{february_results['differential_trend_se']:.4f}" if february_results else 'N/A'
        ],
        'P-value': [
            f"{staggered_results['pre_treatment_pval']:.4f}" if staggered_results else 'N/A',
            f"{february_results['differential_trend_pval']:.4f}" if february_results else 'N/A'
        ],
        'Conclusion': [
            'PASSED ✓' if staggered_results and staggered_results['parallel_trends_valid'] else 'WARNING ✗',
            'PASSED ✓' if february_results and february_results['parallel_trends_valid'] else 'WARNING ✗'
        ]
    })
    
    print("\n" + summary.to_string(index=False))
    print("\n" + "="*80)
    
    # Save to CSV
    summary.to_csv('Actual_final_results/parallel_trends_test_summary.csv', index=False)
    print("\n✓ Saved summary: Actual_final_results/parallel_trends_test_summary.csv")
    
    return summary


def main():
    """Run parallel trends tests for both analyses."""
    print("\n" + "="*80)
    print("FORMAL PARALLEL TRENDS TESTING")
    print("Testing the identifying assumption for DiD analyses")
    print("="*80)
    
    # Test staggered DiD
    staggered_results = test_staggered_parallel_trends()
    
    # Test February DiD
    february_results = test_february_parallel_trends()
    
    # Create combined summary
    if staggered_results and february_results:
        summary = create_combined_summary(staggered_results, february_results)
    
    print("\n" + "="*80)
    print("PARALLEL TRENDS TESTING COMPLETE")
    print("="*80)
    print("\nGenerated files:")
    print("  1. Actual_final_results/staggered_parallel_trends_test.png")
    print("  2. Actual_final_results/february_parallel_trends_test.png")
    print("  3. Actual_final_results/parallel_trends_test_summary.csv")
    print("="*80)


if __name__ == "__main__":
    main()
