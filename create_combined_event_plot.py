"""
Create combined event study plot from cohort results
"""

import json
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_style("whitegrid")

# Load cohort results
with open('cohort_specific_results.json', 'r') as f:
    cohort_results = json.load(f)

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

ax.legend(loc='best', fontsize=11, framealpha=0.95, ncol=2)
ax.grid(True, alpha=0.3, linestyle=':', linewidth=1)

plt.tight_layout()

save_path = 'Actual_final_results/extended_event_study_combined.png'
plt.savefig(save_path, dpi=300, bbox_inches='tight')
print(f"✓ Saved: {save_path}")
plt.close()
