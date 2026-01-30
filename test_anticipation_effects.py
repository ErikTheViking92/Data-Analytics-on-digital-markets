"""
Test for Anticipation Effects in February 2025 DiD Analysis

Research Question:
Do players re-engage with games BEFORE a major patch is released due to 
announcements/hype? If so, this would violate the parallel trends assumption.

Methodology:
1. Load February 2025 panel data (2 weeks before and after patches)
2. Test parallel trends in pre-treatment period (weeks 1-2)
3. Examine if treatment group shows increasing trend before treatment
4. Visual inspection of pre-treatment trends
5. Statistical test for pre-treatment trend differences
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import ols
from scipy import stats

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

def load_february_data():
    """Load the February 2025 DiD panel data."""
    print("="*80)
    print("LOADING FEBRUARY 2025 DiD DATA")
    print("="*80)
    
    df = pd.read_csv("february_2025_panel_data.csv")
    
    print(f"Total observations: {len(df)}")
    print(f"Unique games: {df['appid'].nunique()}")
    print(f"Time periods: {df['week'].nunique()} weeks")
    print(f"Treatment games: {df[df['treated']==1]['appid'].nunique()}")
    print(f"Control games: {df[df['treated']==0]['appid'].nunique()}")
    
    return df


def test_parallel_trends_pretreatment(df):
    """
    Test if treatment and control groups had parallel trends in the 
    pre-treatment period (weeks 1-2).
    """
    print("\n" + "="*80)
    print("PARALLEL TRENDS TEST - PRE-TREATMENT PERIOD")
    print("="*80)
    
    # Filter to pre-treatment period only
    df_pre = df[df['post'] == 0].copy()
    
    print(f"\nAnalyzing pre-treatment period (weeks 1-2):")
    print(f"  Observations: {len(df_pre)}")
    print(f"  Week 1: {len(df_pre[df_pre['week']==1])} obs")
    print(f"  Week 2: {len(df_pre[df_pre['week']==2])} obs")
    
    # Test 1: Interaction of treatment with week in pre-period
    # If coefficient is significant, trends differ between groups
    formula = "ln_players ~ treated + week + treated:week"
    model = ols(formula, data=df_pre).fit(cov_type='cluster', 
                                          cov_kwds={'groups': df_pre['appid']})
    
    print("\n" + "-"*80)
    print("Regression: ln_players ~ treated + week + treated:week")
    print("(Pre-treatment period only)")
    print("-"*80)
    
    print(f"\n{'Variable':<20} {'Coefficient':>12} {'Std Error':>12} {'P-value':>10} {'Sig':>5}")
    print("-"*60)
    
    for var in ['Intercept', 'treated', 'week', 'treated:week']:
        if var in model.params:
            coef = model.params[var]
            se = model.bse[var]
            pval = model.pvalues[var]
            sig = '***' if pval < 0.01 else '**' if pval < 0.05 else '*' if pval < 0.1 else ''
            print(f"{var:<20} {coef:>12.4f} {se:>12.4f} {pval:>10.4f} {sig:>5}")
    
    print(f"\nR-squared: {model.rsquared:.4f}")
    print(f"N observations: {model.nobs:.0f}")
    
    # Interpret the interaction term
    interaction_coef = model.params.get('treated:week', np.nan)
    interaction_pval = model.pvalues.get('treated:week', 1)
    
    print("\n" + "="*80)
    print("INTERPRETATION - ANTICIPATION EFFECT TEST")
    print("="*80)
    
    print(f"\nKey coefficient: treated:week = {interaction_coef:.4f} (p={interaction_pval:.4f})")
    print("\nThis coefficient measures the DIFFERENCE in pre-treatment trends:")
    print("  - If positive & significant: Treatment group trending UP faster before patch")
    print("    → Suggests ANTICIPATION EFFECT (players re-engaging before patch)")
    print("  - If zero/not significant: Both groups trending similarly")
    print("    → Parallel trends assumption holds")
    print("  - If negative & significant: Treatment group trending DOWN before patch")
    print("    → No anticipation effect")
    
    if interaction_pval < 0.05:
        if interaction_coef > 0:
            print(f"\n⚠ WARNING: Significant POSITIVE pre-treatment trend difference!")
            print(f"  Treatment group player counts increasing {interaction_coef:.4f} log points")
            print(f"  faster per week BEFORE the patch (p={interaction_pval:.4f})")
            print(f"\n  → ANTICIPATION EFFECT DETECTED")
            print(f"  → PARALLEL TRENDS ASSUMPTION VIOLATED")
            print(f"\n  Possible explanations:")
            print(f"    1. Patch announcements caused early re-engagement")
            print(f"    2. Pre-patch hype and marketing")
            print(f"    3. Players returning to prepare for new content")
        else:
            print(f"\n✓ Significant NEGATIVE pre-treatment trend difference")
            print(f"  Treatment group declining faster before patch")
            print(f"  → No evidence of anticipation effect")
    else:
        print(f"\n✓ PARALLEL TRENDS ASSUMPTION HOLDS")
        print(f"  Pre-treatment trends not significantly different (p={interaction_pval:.4f})")
        print(f"  → No evidence of anticipation effects")
        print(f"  → DiD identification strategy is valid")
    
    return model, interaction_coef, interaction_pval


def calculate_week_over_week_changes(df):
    """Calculate week-over-week growth rates for each group."""
    print("\n" + "="*80)
    print("WEEK-OVER-WEEK GROWTH RATES (PRE-TREATMENT)")
    print("="*80)
    
    # Calculate means by week and group
    means = df.groupby(['week', 'treated'])['ln_players'].mean().reset_index()
    
    # Week 1 to Week 2 change for each group
    control_w1 = means[(means['week']==1) & (means['treated']==0)]['ln_players'].values[0]
    control_w2 = means[(means['week']==2) & (means['treated']==0)]['ln_players'].values[0]
    treatment_w1 = means[(means['week']==1) & (means['treated']==1)]['ln_players'].values[0]
    treatment_w2 = means[(means['week']==2) & (means['treated']==1)]['ln_players'].values[0]
    
    control_change = control_w2 - control_w1
    treatment_change = treatment_w2 - treatment_w1
    diff_in_changes = treatment_change - control_change
    
    print(f"\nControl Group:")
    print(f"  Week 1 avg: {control_w1:.4f}")
    print(f"  Week 2 avg: {control_w2:.4f}")
    print(f"  Change:     {control_change:.4f} ({(np.exp(control_change)-1)*100:.2f}%)")
    
    print(f"\nTreatment Group:")
    print(f"  Week 1 avg: {treatment_w1:.4f}")
    print(f"  Week 2 avg: {treatment_w2:.4f}")
    print(f"  Change:     {treatment_change:.4f} ({(np.exp(treatment_change)-1)*100:.2f}%)")
    
    print(f"\nDifference in Changes:")
    print(f"  (Treatment - Control): {diff_in_changes:.4f}")
    
    if diff_in_changes > 0:
        print(f"\n  → Treatment group grew FASTER in pre-period")
        print(f"  → Suggests possible anticipation effect")
    elif diff_in_changes < 0:
        print(f"\n  → Treatment group grew SLOWER in pre-period")
        print(f"  → No evidence of anticipation")
    else:
        print(f"\n  → Both groups changed equally in pre-period")
    
    return {
        'control_w1': control_w1,
        'control_w2': control_w2,
        'treatment_w1': treatment_w1,
        'treatment_w2': treatment_w2,
        'control_change': control_change,
        'treatment_change': treatment_change,
        'diff_in_changes': diff_in_changes
    }


def plot_anticipation_test(df, save_path="anticipation_test.png"):
    """Create detailed visualization of pre-treatment trends."""
    
    # Calculate means and SEs
    means = df.groupby(['week', 'treated'])['ln_players'].mean().reset_index()
    se = df.groupby(['week', 'treated'])['ln_players'].sem().reset_index()
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
    
    # ===== PLOT 1: Full period with focus on pre-treatment =====
    means_pivot = means.pivot(index='week', columns='treated', values='ln_players')
    se_pivot = se.pivot(index='week', columns='treated', values='ln_players')
    
    # Plot treatment group
    ax1.plot(means_pivot.index, means_pivot[1], 'o-', 
            color='steelblue', linewidth=3, markersize=12,
            label='Treatment Group')
    ax1.fill_between(means_pivot.index,
                     means_pivot[1] - 1.96 * se_pivot[1],
                     means_pivot[1] + 1.96 * se_pivot[1],
                     alpha=0.2, color='steelblue')
    
    # Plot control group
    ax1.plot(means_pivot.index, means_pivot[0], 's-',
            color='coral', linewidth=3, markersize=12,
            label='Control Group')
    ax1.fill_between(means_pivot.index,
                     means_pivot[0] - 1.96 * se_pivot[0],
                     means_pivot[0] + 1.96 * se_pivot[0],
                     alpha=0.2, color='coral')
    
    # Treatment time
    ax1.axvline(x=2.5, linestyle='--', color='red', linewidth=2.5, 
              alpha=0.8, label='Treatment (Feb 15)')
    
    # Shade pre/post periods
    ax1.axvspan(0.5, 2.5, alpha=0.15, color='gray')
    ax1.text(1.5, ax1.get_ylim()[1]*0.98, 'PRE-TREATMENT\n(Test for anticipation)', 
            ha='center', va='top', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    ax1.axvspan(2.5, 4.5, alpha=0.15, color='yellow')
    ax1.text(3.5, ax1.get_ylim()[1]*0.98, 'POST-TREATMENT', 
            ha='center', va='top', fontsize=11, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))
    
    ax1.set_xlabel('Week (February 2025)', fontsize=13, fontweight='bold')
    ax1.set_ylabel('Log(Player Count)', fontsize=13, fontweight='bold')
    ax1.set_title('Parallel Trends Test: Full Period', 
                 fontsize=14, fontweight='bold')
    ax1.set_xticks([1, 2, 3, 4])
    ax1.set_xticklabels(['Week 1\n(Feb 1-7)', 'Week 2\n(Feb 8-14)', 
                        'Week 3\n(Feb 15-21)', 'Week 4\n(Feb 22-28)'])
    ax1.legend(loc='best', fontsize=11)
    ax1.grid(True, alpha=0.4)
    
    # ===== PLOT 2: Pre-treatment period ZOOMED IN =====
    df_pre = df[df['post'] == 0]
    means_pre = df_pre.groupby(['week', 'treated'])['ln_players'].mean().reset_index()
    se_pre = df_pre.groupby(['week', 'treated'])['ln_players'].sem().reset_index()
    
    means_pre_pivot = means_pre.pivot(index='week', columns='treated', values='ln_players')
    se_pre_pivot = se_pre.pivot(index='week', columns='treated', values='ln_players')
    
    # Plot with trend lines
    for treated_val, color, marker, label in [(1, 'steelblue', 'o', 'Treatment'),
                                                (0, 'coral', 's', 'Control')]:
        weeks = means_pre_pivot.index
        values = means_pre_pivot[treated_val]
        
        # Plot points with error bars
        ax2.errorbar(weeks, values, 
                    yerr=1.96 * se_pre_pivot[treated_val],
                    fmt=marker+'-', color=color, linewidth=3, 
                    markersize=14, capsize=8, capthick=2,
                    label=f'{label} Group')
        
        # Add linear trend line
        z = np.polyfit(weeks, values, 1)
        p = np.poly1d(z)
        ax2.plot(weeks, p(weeks), '--', color=color, alpha=0.5, linewidth=2)
        
        # Add slope annotation
        slope_pct = (np.exp(z[0]) - 1) * 100
        ax2.text(2.1, p(2), f'Trend: {slope_pct:+.2f}%/week', 
                color=color, fontsize=10, fontweight='bold',
                ha='left', va='bottom' if treated_val==1 else 'top')
    
    ax2.set_xlabel('Week (PRE-TREATMENT only)', fontsize=13, fontweight='bold')
    ax2.set_ylabel('Log(Player Count)', fontsize=13, fontweight='bold')
    ax2.set_title('Pre-Treatment Trends: Anticipation Effect Test',
                 fontsize=14, fontweight='bold')
    ax2.set_xticks([1, 2])
    ax2.set_xticklabels(['Week 1\n(Feb 1-7)', 'Week 2\n(Feb 8-14)'])
    ax2.legend(loc='best', fontsize=11)
    ax2.grid(True, alpha=0.4)
    
    # Add text box with interpretation
    textstr = 'Parallel Trends Assumption:\n'
    textstr += 'If trend lines are PARALLEL → Assumption holds\n'
    textstr += 'If treatment trending UP faster → ANTICIPATION EFFECT'
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.7)
    ax2.text(0.02, 0.98, textstr, transform=ax2.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"\n✓ Anticipation test plot saved to: {save_path}")
    
    return fig


def main():
    """Run the anticipation effects analysis."""
    
    print("\n" + "="*80)
    print("ANTICIPATION EFFECTS ANALYSIS - FEBRUARY 2025 DiD")
    print("Testing if players re-engage BEFORE major patches are released")
    print("="*80)
    
    # Load data
    df = load_february_data()
    
    # Test parallel trends in pre-treatment period
    model, interaction_coef, interaction_pval = test_parallel_trends_pretreatment(df)
    
    # Calculate week-over-week changes
    changes = calculate_week_over_week_changes(df)
    
    # Create visualizations
    fig = plot_anticipation_test(df)
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY - COMMON TRENDS ASSUMPTION")
    print("="*80)
    
    print("\nThe common trends (parallel trends) assumption requires that:")
    print("  In the ABSENCE of treatment, treatment and control groups would")
    print("  have followed parallel trends.")
    
    print(f"\nEvidence from this analysis:")
    print(f"  1. Pre-treatment interaction coefficient: {interaction_coef:.4f} (p={interaction_pval:.4f})")
    print(f"  2. Treatment group W1→W2 change: {changes['treatment_change']:.4f}")
    print(f"  3. Control group W1→W2 change: {changes['control_change']:.4f}")
    print(f"  4. Difference: {changes['diff_in_changes']:.4f}")
    
    if interaction_pval < 0.05 and interaction_coef > 0:
        print("\n⚠ CONCLUSION: PARALLEL TRENDS ASSUMPTION VIOLATED")
        print("\n  → Treatment group shows ANTICIPATION EFFECT")
        print("  → Player counts increasing BEFORE patch release")
        print("  → Likely due to patch announcements/hype")
        print("\n  Implications for DiD:")
        print("    - DiD estimate may be BIASED")
        print("    - Effect includes both:")
        print("      (a) Pre-patch anticipation")
        print("      (b) Post-patch actual effect")
        print("    - True causal effect is CONFOUNDED")
        print("\n  Recommendations:")
        print("    1. Use earlier pre-treatment period (before announcements)")
        print("    2. Control for announcement timing")
        print("    3. Consider event study with multiple pre-periods")
        print("    4. Interpret results with caution")
    else:
        print("\n✓ CONCLUSION: PARALLEL TRENDS ASSUMPTION HOLDS")
        print("\n  → No evidence of anticipation effects")
        print("  → Pre-treatment trends are parallel")
        print("  → DiD identification strategy is valid")
        print("  → Causal interpretation is justified")
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    
    # Save results
    results = {
        'analysis_type': 'anticipation_effects_test',
        'date': pd.Timestamp.now().isoformat(),
        'pre_treatment_interaction_coef': float(interaction_coef),
        'pre_treatment_interaction_pval': float(interaction_pval),
        'treatment_w1_to_w2_change': float(changes['treatment_change']),
        'control_w1_to_w2_change': float(changes['control_change']),
        'difference_in_pretrend_changes': float(changes['diff_in_changes']),
        'anticipation_detected': bool(interaction_pval < 0.05 and interaction_coef > 0),
        'parallel_trends_holds': bool(interaction_pval >= 0.05)
    }
    
    import json
    with open('anticipation_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✓ Results saved to: anticipation_test_results.json")


if __name__ == "__main__":
    main()
