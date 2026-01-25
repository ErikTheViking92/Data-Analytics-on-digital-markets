"""
Difference-in-Differences Analysis in Python
Replicates R DiD analysis functionality using pandas, statsmodels, and matplotlib
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.formula.api import ols
from statsmodels.iolib.summary2 import summary_col
import statsmodels.api as sm

# Set plotting style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (10, 6)


def load_data(filepath, file_format='csv'):
    """
    Load data from various formats
    
    Parameters:
    -----------
    filepath : str
        Path to the data file
    file_format : str
        Format of the file ('csv', 'dta', 'excel', etc.)
    
    Returns:
    --------
    pd.DataFrame
        Loaded data
    """
    if file_format == 'csv':
        data = pd.read_csv(filepath)
    elif file_format == 'dta':
        data = pd.read_stata(filepath)
    elif file_format == 'excel':
        data = pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {file_format}")
    
    return data


def summary_statistics(data, variables):
    """
    Display summary statistics for selected variables
    
    Parameters:
    -----------
    data : pd.DataFrame
        The dataset
    variables : list
        List of variable names to summarize
    """
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    
    summary = data[variables].describe().T
    summary['count'] = summary['count'].astype(int)
    
    print(summary.to_string())
    print("="*60 + "\n")
    
    return summary


def run_did_regression(data, formula, model_name="DiD Model"):
    """
    Run a DiD regression model
    
    Parameters:
    -----------
    data : pd.DataFrame
        The dataset
    formula : str
        R-style formula for the regression
    model_name : str
        Name of the model for display
    
    Returns:
    --------
    statsmodels regression results object
    """
    model = ols(formula, data=data).fit()
    
    print(f"\n{model_name}")
    print("-" * 60)
    print(model.summary())
    
    return model


def create_regression_table(models, model_names=None, **kwargs):
    """
    Create a formatted regression table comparing multiple models
    
    Parameters:
    -----------
    models : list
        List of fitted statsmodels regression objects
    model_names : list
        List of model names for column headers
    """
    if model_names is None:
        model_names = [f"Model {i+1}" for i in range(len(models))]
    
    print("\n" + "="*80)
    print("REGRESSION RESULTS COMPARISON")
    print("="*80)
    
    # Create comparison table
    results_table = summary_col(
        models,
        stars=True,
        float_format='%.4f',
        model_names=model_names,
        info_dict={
            'N': lambda x: f"{int(x.nobs)}",
            'R-squared': lambda x: f"{x.rsquared:.4f}",
            'Adj. R-squared': lambda x: f"{x.rsquared_adj:.4f}"
        }
    )
    
    print(results_table)
    print("="*80 + "\n")
    
    return results_table


def test_parallel_trends(data, treatment_var, time_dummies, outcome_var, 
                         treatment_period=None):
    """
    Test parallel trends assumption using pre-treatment time dummies
    
    Parameters:
    -----------
    data : pd.DataFrame
        The dataset
    treatment_var : str
        Name of the treatment group indicator variable
    time_dummies : list
        List of time dummy variable names
    outcome_var : str
        Name of the outcome variable
    treatment_period : int
        The period when treatment occurs (for reference)
    
    Returns:
    --------
    statsmodels regression results object
    """
    # Build formula with interaction terms
    interactions = [f"{treatment_var}:{td}" for td in time_dummies]
    formula = f"{outcome_var} ~ {' + '.join(interactions)}"
    
    model = ols(formula, data=data).fit()
    
    print("\n" + "="*60)
    print("PARALLEL TRENDS TEST - DiD COEFFICIENTS OVER TIME")
    print("="*60)
    print(model.summary())
    
    return model


def plot_did_coefficients(model, treatment_var, time_var_prefix="timedum_", 
                          treatment_period=None, save_path=None):
    """
    Plot DiD coefficients over time with confidence intervals
    
    Parameters:
    -----------
    model : statsmodels regression results
        Fitted model with interaction terms
    treatment_var : str
        Name of the treatment variable
    time_var_prefix : str
        Prefix for time dummy variables
    treatment_period : float
        X-axis position where treatment occurs (for vertical line)
    save_path : str
        If provided, save the plot to this path
    """
    # Extract coefficients and confidence intervals
    params = model.params
    conf_int = model.conf_int()
    
    # Filter interaction terms
    interaction_pattern = f"{treatment_var}:{time_var_prefix}"
    did_coefs = []
    
    for param_name in params.index:
        if interaction_pattern in param_name:
            time_label = param_name.replace(f"{treatment_var}:", "").replace(time_var_prefix, "t")
            did_coefs.append({
                'time': time_label,
                'estimate': params[param_name],
                'conf_low': conf_int.loc[param_name, 0],
                'conf_high': conf_int.loc[param_name, 1]
            })
    
    # Convert to DataFrame for easier plotting
    plot_data = pd.DataFrame(did_coefs)
    
    # Create plot
    fig, ax = plt.subplots(figsize=(12, 7))
    
    # Plot points and error bars
    x_positions = range(len(plot_data))
    ax.errorbar(x_positions, plot_data['estimate'], 
                yerr=[plot_data['estimate'] - plot_data['conf_low'],
                      plot_data['conf_high'] - plot_data['estimate']],
                fmt='o', markersize=8, capsize=5, capthick=2,
                color='steelblue', ecolor='steelblue', label='DiD Estimate')
    
    # Add horizontal line at zero
    ax.axhline(y=0, linestyle='--', color='gray', linewidth=1, alpha=0.7)
    
    # Add vertical line at treatment time
    if treatment_period is not None:
        ax.axvline(x=treatment_period, linestyle=':', color='red', 
                  linewidth=2, alpha=0.7, label='Treatment Time')
    
    # Formatting
    ax.set_xlabel('Time Period', fontsize=12, fontweight='bold')
    ax.set_ylabel('Coefficient Estimate', fontsize=12, fontweight='bold')
    ax.set_title('DiD Coefficients Over Time', fontsize=14, fontweight='bold')
    ax.set_xticks(x_positions)
    ax.set_xticklabels(plot_data['time'])
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')
        print(f"\nPlot saved to: {save_path}")
    
    plt.show()
    
    return fig, ax


def main():
    """
    Main function demonstrating the DiD analysis workflow
    """
    print("\n" + "="*60)
    print("DIFFERENCE-IN-DIFFERENCES ANALYSIS")
    print("="*60 + "\n")
    
    # Step 1: Load data
    # Example: Uncomment and modify the path below
    # data = load_data("path/to/your/data.csv", file_format='csv')
    # For .dta files (Stata format):
    data = load_data("C:/Users/DrMUAPOR/Documents/Uni/ws25/(SE) Data Analytics on Digital Markets/Difference-in-Differences Analysis/google.dta", file_format='dta')
    
    print("Step 1: Load your data using the load_data() function")
    print("Example: data = load_data('your_file.csv', file_format='csv')")
    
    # Step 2: Summary Statistics
    # Example variables - replace with your actual variable names
    variables = ['goog', 'dum', 'ln_count_all', 'rating', 'experience']
    summary_statistics(data, variables)


if __name__ == "__main__":
    # Run the main demonstration
    main()
    
    # Example with actual data (uncomment and modify as needed):
    
    # Load your data
    data = load_data("C:/Users/DrMUAPOR/Documents/Uni/ws25/(SE) Data Analytics on Digital Markets/Difference-in-Differences Analysis/google.dta", file_format='dta')
    # Save file as csv
    data.to_csv('google.csv')
    # Summary statistics
    summary_statistics(data, ['goog', 'dum', 'ln_count_all'])
    
    # Run DiD models
    model_a = run_did_regression(data, 'ln_count_all ~ goog + dum + goog:dum', 'Model A: No Controls')
    model_b = run_did_regression(data, 'ln_count_all ~ goog + dum + goog:dum + rating + experience', 'Model B: With Controls')
    
    # Compare models
    create_regression_table([model_a, model_b], model_names=['No Controls', 'With Controls'])
    
    # Test parallel trends
    time_dummies = ['timedum_1', 'timedum_2', 'timedum_3', 'timedum_5', 'timedum_6', 'timedum_7', 'timedum_8']
    model_trends = test_parallel_trends(data, 'goog', time_dummies, 'ln_count_all')
    
    # Plot coefficients
    plot_did_coefficients(model_trends, 'goog', treatment_period=3.5, save_path='did_plot.png')

