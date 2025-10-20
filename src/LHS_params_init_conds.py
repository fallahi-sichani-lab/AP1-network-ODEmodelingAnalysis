#%% Importing libraries
from itertools import product
import time
import numpy as np
import pandas as pd
import itertools
import logging
import time
from tqdm import tqdm
from pyDOE2 import lhs
import matplotlib.pyplot as plt
from datetime import datetime


#%% Defining functions


# def InitConds(values, num_vars):
#     """ This function creates a dataframe of initial conditions for the model
#     values: list of values for each variable
#     (currently fixed for the 4 values I want 0,1 10, 100, 1000 )
#     num_vars: int: number of variables in the model
#     """
#     var_ranges = [values for _ in range(num_vars)]
#     initial_conditions = list(itertools.product(*var_ranges))
#     return np.array(initial_conditions)

# start_time = time.time()
# #%% Generate Initial conditions
# # right now these four values are set and the grid will be 1024 points
# print("Generating initial conditions...")
# arr_values = np.array([0.1, 1, 10, 100, 1000])
# mid_values = np.sqrt(arr_values[:-1] * arr_values[1:])
# values_init = mid_values.round(3).tolist()
# init_cond_array = InitConds(values_init, 5)  # start, stop, density, num_vars
# init_cond_df = pd.DataFrame(init_cond_array, columns=[
#                             'fos', 'jun', 'fra1', 'fra2', 'jund'])
# print("Done generating initial conditions.")


#%% Generate LHS for parameters and initial conditions
start_time = time.time()
param_values = [
    ('(basal_fos).v', (0.08, 0.8, 80)), # increased range for FOS from 8 to 80
    ('(basal_jun).v', (0.08, 0.8, 8)),
    ('(basal_fra1).v', (0.08, 0.8, 8)),
    ('(basal_fra2).v', (0.08, 0.8, 8)),
    ('(basal_jund).v', (0.08, 0.8, 8)),
    ('(jun_by_junjun).beta', (2, 20, 200)),
    ('(jun_by_junfos).beta', (2, 20, 200)),
    ('(fra1_by_junfra1).beta', (2, 20, 200)),
    ('(fra1_by_jundfos).beta', (2, 20, 200)),
    ('(fra2_by_junfra2).beta', (2, 20, 200)),
    ('(degradation_fos).k1', (0.426, 0.852, 1.704)),
    ('(degradation_jun).k1', (0.417, 0.834, 1.668)),
    ('(degradation_fra1).k1', (0.174, 0.347, 0.694)),
    ('(degradation_fra2).k1', (0.08, 0.16, 0.32)),
    ('(degradation_jund).k1', (0.058, 0.116, 0.232))
]

init_cond_values = [ 
    ('fos', (0.316, 10,316.228)), # mid value is 10 taking the geometric mean of 0.316 and 316.228
    ('jun', (0.316, 10,316.228)),
    ('fra1', (0.316,10, 316.228)),
    ('fra2', (0.316,10, 316.228)),
    ('jund', (0.316,10, 316.228))
]

# use lhs to sample the parameter space
# sampling 10000 points for each parameter
print("Generating LHS...")
param_samples  = 20000
lhs_params = lhs(len(param_values), samples = param_samples, random_state=0)

init_cond_samples = 200
lhs_initconds = lhs(len(init_cond_values), samples = init_cond_samples, random_state=0)
#each row in lhs_samples is a sample and the columns are the parameters
# values are in the range of [0,1] for lhs so we need to scale them to the parameter range

# adjust the formula for the parameters
param_samples = []

for i, ((param_name, param_range), sample_vals) in enumerate(zip(param_values, lhs_params.T)):
    min_val, mid_val, max_val = param_range

    # check the scaling type
    if np.isclose(max_val/mid_val, 10, atol=1e-1) or max_val/min_val > 10:
        
        # If it's 100-fold logarithmic scaling:
        log_min = np.log10(min_val)
        log_max = np.log10(max_val)
        log_vals = log_min + sample_vals * (log_max-log_min)
        scaled_vals = np.power(10, log_vals)
    else:
        # If it's 2-fold difference:
        log_min = np.log2(min_val)
        log_max = np.log2(max_val)
        log_vals = log_min + sample_vals * (log_max-log_min)
        scaled_vals = np.power(2, log_vals)


    param_samples.append((param_name, scaled_vals))

# adjust the formula for the initial conditions
init_cond_samples = []

for i, ((init_cond_name, init_cond_range), sample_vals) in enumerate(zip(init_cond_values, lhs_initconds.T)):
    min_val, mid_val, max_val = init_cond_range

    # check the scaling type
    if np.isclose(max_val/mid_val, mid_val/min_val, atol=1e-1) and np.isclose(max_val/mid_val, 10, atol=1e-1):
        # If it's 100-fold logarithmic scaling:
        log_min = np.log10(min_val)
        log_max = np.log10(max_val)
        log_vals = log_min + sample_vals * (log_max-log_min)
        scaled_vals = np.power(10, log_vals)
    else:
        # If it's 2-fold difference:
        log_min = np.log2(min_val)
        log_max = np.log2(max_val)
        log_vals = log_min + sample_vals * (log_max-log_min)
        scaled_vals = np.power(2, log_vals)


    init_cond_samples.append((init_cond_name, scaled_vals))




# we can transform this to a dataframe
paramset_df = pd.DataFrame(dict(param_samples))
init_cond_df = pd.DataFrame(dict(init_cond_samples))

print("Done generating LHS.")
#%% 
#PLOTTING THE DISTRIBUTIONS FOR THE PARAMETER AND INITIAL CONDITION SAMPLES
plt.rcParams['xtick.labelsize'] = 14  # or whatever size you want
plt.rcParams['ytick.labelsize'] = 14  # or whatever size you want

# Set global font size for labels, titles and legends
plt.rcParams['axes.labelsize'] = 16  # or whatever size you want
plt.rcParams['axes.titlesize'] = 16  # or whatever size you want
plt.rcParams['legend.fontsize'] = 14  # or whatever size you want
fig, axes = plt.subplots(nrows=2, ncols=3, figsize=(15, 20))
axes = axes.ravel()
# change for init_conds or params (use the names)
# for i, (init_cond_name,samples) in enumerate(init_cond_samples):
#     ax = axes[i]
#     bins = np.logspace(np.log10(min(samples)), np.log10(max(samples)), 50)
#     #samples = 10**log_samples  # Convert back to original scale
#     ax.hist(samples, bins=bins, color='lightcoral', edgecolor='black', alpha=0.7)
#     ax.set_xscale('log')
#     ax.set_title(init_cond_name)
#     ax.set_xticks(init_cond_values[i][1])  # Setting xticks to the three points you provided
#     ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())  # Format xticks properly in log scale

# plt.tight_layout()
# # save figures as png into the figs folder
# plt.savefig('/scratch/njr7jk/ap1_hpc/figs/LHS_sampled_init_conds_distributions.png')
# #plt.show()


def plot_log_histograms(samples, titles, xticks, output_path, figsize=(15, 20), nrows=3, ncols=5):
    """
    Plot histograms on a logarithmic scale.
    
    :param samples: List of sample arrays to plot.
    :param titles: List of titles for each subplot.
    :param xticks: List of xticks for each subplot.
    :param output_path: Path to save the figure.
    :param figsize: Tuple defining figure size.
    :param nrows: Number of rows in the subplot grid.
    :param ncols: Number of columns in the subplot grid.
    """
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=figsize)
    axes = axes.ravel()

    for i, (sample, title, xtick) in enumerate(zip(samples, titles, xticks)):
        ax = axes[i]
        bins = np.logspace(np.log10(min(sample)), np.log10(max(sample)), 50)
        ax.hist(sample, bins=bins, color='lightcoral',
                edgecolor='black', alpha=0.7)
        ax.set_xscale('log')
        ax.set_title(title)
        ax.set_xticks(xtick)
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

    plt.tight_layout()
    plt.savefig(output_path)
    # plt.show()


# Generate the current date string in MMDDYY format
date_str = datetime.now().strftime("%m%d%y")

# Example usage for initial conditions
plot_log_histograms(
    samples=[samples for _, samples in init_cond_samples],
    titles=[name for name, _ in init_cond_samples],
    xticks=[init_cond_values[i][1] for i in range(len(init_cond_samples))],
    output_path=f'/scratch/njr7jk/ap1_hpc/figs/{date_str}_LHS_sampled_init_conds_distributions.png',
    nrows=1, ncols=5  # Grid for 5 initial conditions
)

# Example usage for parameters
plot_log_histograms(
    samples=[samples for _, samples in param_samples],
    titles=[name for name, _ in param_samples],
    xticks=[param_values[i][1] for i in range(len(param_samples))],
    output_path=f'/scratch/njr7jk/ap1_hpc/figs/{date_str}_LHS_sampled_params_distributions.png',
    nrows=3, ncols=5  # Grid for 15 parameters
)


#%% Merge the two dataframes
# now we can merge the two dataframesparamset_df.reset_index(inplace=True)

paramset_df.reset_index(inplace=True)
paramset_df.rename(columns={'index': 'param_index'}, inplace=True)

init_cond_df.reset_index(inplace=True)
init_cond_df.rename(columns={'index': 'init_cond_index'}, inplace=True)

paramset_df['param_index'] = paramset_df['param_index'].astype('int64')
init_cond_df['init_cond_index'] = init_cond_df['init_cond_index'].astype('int64')

# Create a DataFrame for all combinations of parameter sets and initial conditions

def process_chunk(start_row, end_row):
    # Generate the parameter combinations for the current chunk
    param_rows = paramset_df.reset_index().astype('int64')['index'][start_row:end_row]
    init_rows = init_cond_df.reset_index().astype('int64')['index']
    

    print(f"Number of valid param rows in range: {len(param_rows)}")
    print(f"Number of init_cond rows: {len(init_rows)}")
    
    chunk_combinations = product(param_rows, init_rows)

    num_combinations = sum(1 for _ in chunk_combinations)
    print(f"Number of combinations: {num_combinations}")
    
    chunk_combinations = product(param_rows, init_rows)  # Re-create the iterator

    num_combinations = sum(1 for _ in chunk_combinations)
    print(f"Number of combinations: {num_combinations}")
    
    chunk_combinations = product(param_rows, init_rows)  # Re-create the iterator

    # Create a DataFrame for the current chunk
    param_init_cond_df = pd.DataFrame(chunk_combinations, columns=['param_index', 'init_cond_index'])
    param_init_cond_df = param_init_cond_df.join(paramset_df, on='param_index', rsuffix='_param')
    param_init_cond_df = param_init_cond_df.join(init_cond_df, on='init_cond_index', rsuffix='_init')

    # Drop unnecessary columns
    if 'param_index_param' in param_init_cond_df.columns and 'init_cond_index_init' in param_init_cond_df.columns:
        param_init_cond_df = param_init_cond_df.drop(['param_index_param', 'init_cond_index_init'], axis=1)
    
    return param_init_cond_df
    #%% 


# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Set up your chunk size
# Total number of rows
number_samples = 10000
total_rows = 2000000

# Number of chunks
num_chunks = 100

# Chunk size (number of rows per chunk)
chunk_size = total_rows // num_chunks

if total_rows % chunk_size:
    num_chunks += 1

param_rows_per_chunk = len(paramset_df) // num_chunks

#print("Dividing data into chunks...")
# Iterate over the number of chunks

logging.info(f"Dividing data into {num_chunks} chunks...")
for chunk_idx in tqdm(range(num_chunks), desc="Processing chunks"):
# Calculate the range of rows for the current chunk
    start_row = chunk_idx * param_rows_per_chunk
    end_row = min((chunk_idx+1) * param_rows_per_chunk, len(paramset_df))
    
    print(f"Processing chunk {chunk_idx}: start_row={start_row}, end_row={end_row}")


    param_init_cond_df = process_chunk(start_row, end_row)
    
    filename = f'/scratch/njr7jk/ap1_hpc/input/chunk_{chunk_idx}_LHS_samples_{number_samples}.csv'
    print(f"Saving to {filename}")

    param_init_cond_df.to_csv(filename, index=False)

print("Done dividing data into chunks.")

print("All chunks have been created and saved.")


print("Time elapsed: " + str(time.time() - start_time) + " seconds")