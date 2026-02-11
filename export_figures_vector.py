"""
Export event study figures as PDF and SVG for better scalability in documents.

Author: DiD Analysis Pipeline
Date: February 11, 2026
"""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import json
import numpy as np
import seaborn as sns

# Set style
sns.set_style("whitegrid")
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['legend.fontsize'] = 10

def export_symmetric_by_cohort():
    """Export symmetric event study by cohort as PDF and SVG"""
    
    print("Creating symmetric event study by cohort (vector formats)...")
    
    # Load results
    with open('cohort_symmetric_results.json', 'r') as f:
        cohort_results = json.load(f)
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_labels = ['January 2025', 'February 2025', 'March 2025', 'April 2025']
    cohort_sizes = [88, 79, 78, 74]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    
    for idx, (cohort, label, n_games) in enumerate(zip(cohorts, cohort_labels, cohort_sizes)):
        ax = axes[idx]
        
        cohort_data = cohort_results[cohort]
        
        rel_times = [d['rel_time'] for d in cohort_data]
        coefs = [d['coef'] for d in cohort_data]
        ci_lows = [d['ci_low'] for d in cohort_data]
        ci_highs = [d['ci_high'] for d in cohort_data]
        
        # Plot coefficients with error bars
        ax.errorbar(rel_times, coefs, 
                   yerr=[np.array(coefs) - np.array(ci_lows), 
                         np.array(ci_highs) - np.array(coefs)],
                   fmt='o-', capsize=5, capthick=2, markersize=8,
                   color='steelblue', ecolor='gray', linewidth=2)
        
        # Zero line
        ax.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
        
        # Treatment time vertical line
        ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=1.5, alpha=0.7, label='Treatment')
        
        # Formatting
        ax.set_xlabel('Relative Time to Treatment', fontweight='bold')
        ax.set_ylabel('Coefficient (log points)', fontweight='bold')
        ax.set_title(f'{label} Cohort (N={n_games})', fontweight='bold', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best')
        
        # Set x-ticks
        ax.set_xticks(range(-3, 4))
        ax.set_xticklabels(['t-3', 't-2', 't-1', 't', 't+1', 't+2', 't+3'])
    
    plt.tight_layout()
    
    # Save as PDF and SVG
    plt.savefig('Actual_final_results/symmetric_event_study_by_cohort.pdf', 
                format='pdf', dpi=300, bbox_inches='tight')
    plt.savefig('Actual_final_results/symmetric_event_study_by_cohort.svg', 
                format='svg', bbox_inches='tight')
    plt.close()
    
    print("  ✓ Saved: symmetric_event_study_by_cohort.pdf")
    print("  ✓ Saved: symmetric_event_study_by_cohort.svg")

def export_symmetric_combined():
    """Export symmetric event study combined as PDF and SVG"""
    
    print("Creating symmetric event study combined (vector formats)...")
    
    # Load results
    with open('cohort_symmetric_results.json', 'r') as f:
        cohort_results = json.load(f)
    
    cohorts = ['jan', 'feb', 'mar', 'apr']
    cohort_labels = ['January 2025', 'February 2025', 'March 2025', 'April 2025']
    colors = ['blue', 'coral', 'green', 'purple']
    
    fig, ax = plt.subplots(figsize=(12, 7))
    
    for cohort, label, color in zip(cohorts, cohort_labels, colors):
        cohort_data = cohort_results[cohort]
        
        rel_times = [d['rel_time'] for d in cohort_data]
        coefs = [d['coef'] for d in cohort_data]
        ci_lows = [d['ci_low'] for d in cohort_data]
        ci_highs = [d['ci_high'] for d in cohort_data]
        
        # Offset x-positions slightly for visibility
        offset = {'jan': -0.15, 'feb': -0.05, 'mar': 0.05, 'apr': 0.15}[cohort]
        rel_times_offset = [t + offset for t in rel_times]
        
        # Plot with error bars
        ax.errorbar(rel_times_offset, coefs,
                   yerr=[np.array(coefs) - np.array(ci_lows),
                         np.array(ci_highs) - np.array(coefs)],
                   fmt='o-', capsize=4, capthick=1.5, markersize=6,
                   color=color, ecolor=color, alpha=0.7, linewidth=1.5,
                   label=label)
    
    # Zero line
    ax.axhline(y=0, color='black', linestyle='--', linewidth=1.5, alpha=0.6)
    
    # Treatment marker
    ax.axvline(x=-0.5, color='red', linestyle='--', linewidth=2, alpha=0.5, label='Treatment Time')
    
    # Formatting
    ax.set_xlabel('Relative Time to Treatment', fontweight='bold', fontsize=13)
    ax.set_ylabel('Coefficient (log points)', fontweight='bold', fontsize=13)
    ax.set_title('Symmetric Event Study: All Cohorts with 95% Confidence Intervals\n(Balanced Windows t-3 to t+3)', 
                fontweight='bold', fontsize=14)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='best', frameon=True, shadow=True)
    
    # Set x-ticks
    ax.set_xticks(range(-3, 4))
    ax.set_xticklabels(['t-3', 't-2', 't-1', 't', 't+1', 't+2', 't+3'])
    
    plt.tight_layout()
    
    # Save as PDF and SVG
    plt.savefig('Actual_final_results/symmetric_event_study_combined.pdf',
                format='pdf', dpi=300, bbox_inches='tight')
    plt.savefig('Actual_final_results/symmetric_event_study_combined.svg',
                format='svg', bbox_inches='tight')
    plt.close()
    
    print("  ✓ Saved: symmetric_event_study_combined.pdf")
    print("  ✓ Saved: symmetric_event_study_combined.svg")

def main():
    """Main execution"""
    print("\n" + "="*80)
    print("EXPORTING SYMMETRIC EVENT STUDY FIGURES AS VECTOR FORMATS")
    print("="*80 + "\n")
    
    export_symmetric_by_cohort()
    print()
    export_symmetric_combined()
    
    print("\n" + "="*80)
    print("EXPORT COMPLETE")
    print("="*80 + "\n")
    
    print("Vector formats (PDF and SVG) provide:")
    print("  - Infinite scalability without quality loss")
    print("  - Smaller file sizes for simple graphics")
    print("  - Better rendering in LaTeX documents")
    print("  - Professional publication quality")

if __name__ == '__main__':
    main()
