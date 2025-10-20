#%%
import os
import io
import sys
from itertools import product
import time
import numpy as np
import pandas as pd
import datetime
# import traceback
# import itertools
#from collections import namedtuple
#import argparse
from multiprocessing import Pool
# from functools import partial
from memory_profiler import profile
from numpy.random import rand
import csv
from basico import *
#Initialize logging
import logging
#%%
# logging.basicConfig(filename="sim_err.log", level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# logging.basicConfig(filename="sim_err.log", level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)

# ERROR_LOG_FILE = '/scratch/njr7jk/ap1_hpc/error_log.txt'
# error_log_handler = logging.FileHandler(ERROR_LOG_FILE)
# error_log_handler.setLevel(logging.ERROR)  # Only log errors
# formatter = logging.Formatter('%(message)s')
# error_log_handler.setFormatter(formatter)
# logging.getLogger().addHandler(error_log_handler)

# logger.debug("Starting Script...")
def setup_logging(base_dir):
    # Main log file
    log_file_path = os.path.join(base_dir, "sim_err.log")
    logging.basicConfig(
        filename=log_file_path,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    logger = logging.getLogger(__name__)

    # Additional error log file
    error_log_file_path = os.path.join(base_dir, 'error_log.txt')
    error_handler = logging.FileHandler(error_log_file_path)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(error_handler)
    
    return logger

#import pdb; pdb.set_trace()
print("Loading model...")
model = load_model('ap1_model_081025_mod.cps')
print("Model loaded successfully.")
# set task setting for Newton-Raphson false
set_task_settings(T.STEADY_STATE, settings={'method': {
                  'Use Newton': False, 'Use Integration': True}})
#%%
# functions for changing parameters or defining range of initial conditions
# set initial values for dimers

#%%
def fixed_initial_variables(species_name, species_value):
    """This function sets the initial value of the species to the value in species_value
    this will be used for setting the initial values of dimers once you load the model
    Enter the species name and the value in a list
    species_name: list of species names
    species_value: list of species values 
    """
    for i in range(len(species_name)):
        set_species(
            name=species_name[i], initial_concentration=species_value[i], exact=True)

#change local or global parameters


def change_model_parameters(par_name, par_value, par_type):
    """ This function changes the model parameters to the values in par_value
    Enter the parameter name and the value in a list
    par_name: list of parameter names
    par_value: list of parameter values
    par_type: string: 'local' or 'global' 
    """

    if par_type == 'local':
       for i in range(len(par_name)):
            set_reaction_parameters(name=par_name[i], value=par_value[i])
    elif par_type == 'global':
        (set_parameters(name=par_name[i], initial_value=par_value[i]) for i in range(len(par_name)))

def run_steadystate_wrapper(*args, **kwargs):
    # Redirect stdout
    old_stdout = sys.stdout
    new_stdout = io.StringIO()
    sys.stdout = new_stdout

    # Call the actual function
    error_occurred = False
    try:
       status = basico.task_steadystate.run_steadystate(*args, **kwargs)
    except:
        error_occurred = True
    finally:
        # Get the stdout content and revert redirection
        output = new_stdout.getvalue()
        sys.stdout = old_stdout

    # Check if the output has the error message
    if "DLSODA" in output or error_occurred:  
        raise Exception("Steady state calculation failed due to DLSODA error.")
    
    return status
#%%
# Steady State functions
#modifying this to take on row of initial conditions at a time
def get_steadystate(init_cond_rows):
    """ This function runs the steady state for the model
    init_cond_df: DataFrame: DataFrame of initial conditions
    """
    # create empty dataframe to store the steady state values
    #logging.debug("Entering get_steadystate...")
    num_init_col = len(init_cond_rows)
    steady_state_arr = np.zeros((num_init_col))  #  same as num species
    #steady_state_df = pd.DataFrame(steady_state_arr, columns= init_cond_df.columns.tolist())

    # set all dimer initial values to 0
    # need to make the names more flexible here for the AP1 dimer names
    spec_names = ['junfos', 'junfra1', 'junfra2','junjund','junjun','jundfos','jundfra1','jundfra2','jundjund']
    spec_vals = np.zeros(len(spec_names)).tolist() #
    fixed_initial_variables(spec_names, spec_vals)

    # loop through all the initial conditions and run the steady state
    # extract name of species (**YOU ONLY NEED TO CHANGE THE NUMBER OF SPECIES**)
    #my_species = get_species().reset_index()
    
    #species_name = get_species().index.tolist()[:num_init_col]
    species_name = ['fos', 'jun', 'fra1', 'fra2', 'jund']
    #logging.debug(f"Set species with names: {species_name}")
    #species_name = ['fos', 'jun', 'fra1', 'fra2', 'jund']
    # for i in range(0, len(init_cond_df)):
    #     init_cond_rows = init_cond_df.iloc[i].values
        
        # set the initial conditions for the species based on the initial condition dataframe
    for j, name in enumerate(species_name):
        set_species(
            name=name, initial_concentration=init_cond_rows[j], exact=True)

    # run the steady state
    #run_steadystate(use_initial_values = True, update_model = False)
    status = run_steadystate_wrapper(use_initial_values=True, update_model=False)

    # Check the status here and raise exception if necessary
    if status == 0:
        raise Exception("Steady state not found.")
    elif status == 3:
        raise Exception("Steady state with negative concentrations found.")
    elif status not in [1, 2]:
        raise Exception(f"Unexpected return code: {status}")
    
    ss_v = get_species()[['concentration']].reset_index()
    ss_vtotal = ss_v[ss_v['name'].str.contains("total")]
    steady_state_arr[:len(species_name)] = np.round(ss_vtotal['concentration'].values,1)
    #logging.debug("Ran steady state...")

        
    return steady_state_arr
#%%
steady_state_species_names = ['fos', 'jun', 'fra1', 'fra2', 'jund']
headers = ['param_index', 'init_cond_index'] + steady_state_species_names

def process_chunk_rows(rows, output_file, chunk_file_name, BASE_DIR):
    steady_state_species_names = ['fos', 'jun', 'fra1', 'fra2', 'jund']
    headers = ['param_index', 'init_cond_index'] + steady_state_species_names
    results_to_write = []
    
    for row in rows:
        init_cond_index = row['init_cond_index']
        param_index = row['param_index']
        param_values = pd.Series(row).iloc[2:17].round(3).tolist()
        init_cond_values = pd.Series(row).iloc[17:].tolist()
        par_names = pd.Series(row).iloc[2:17].index.tolist()

        #logging.info(f"Processing row with param_index {param_index} and init_cond_index {init_cond_index}...")

        try:
            change_model_parameters(par_names, param_values, 'local')
            steady_state_result = get_steadystate(init_cond_values)
            
            result = {
                'param_index': param_index,
                'init_cond_index': init_cond_index,
                **dict(zip(steady_state_species_names, steady_state_result))
            }
            results_to_write.append(result)
        except Exception as e:
            #print(f"Error at param_index {param_index}, init_cond_index {init_cond_index}: {str(e)}")
            logger.error(
                f"Error at param_index {param_index}, init_cond_index {init_cond_index}: {str(e)}")

            try:
                with open(os.path.join(BASE_DIR, 'failed_indices.txt'), 'a') as f:
                    f.write(f"Failed for param_index {param_index}, init_cond_index {init_cond_index}: {str(e)}\n")
            except Exception as file_error:
                print(f"Error writing to file: {file_error}")

            error_msg = f"Error processing row with param_index {param_index} and init_cond_index {init_cond_index}: {str(e)}"
            logger.debug(error_msg)

            result = {
                'param_index': param_index,
                'init_cond_index': init_cond_index,
            }
            for species_name in steady_state_species_names:
                result[species_name] = 'NA'
            results_to_write.append(result)
    
    # Write results immediately to file
    with open(output_file, 'a') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writerows(results_to_write)
    
    logger.info(f"Processed {len(rows)} rows, wrote to {output_file}.")

def process_chunk(chunk_file, OUTPUT_DIR, BASE_DIR):
    steady_state_species_names = ['fos', 'jun', 'fra1', 'fra2', 'jund']
    headers = ['param_index', 'init_cond_index'] + steady_state_species_names
    
    chunk_file_name = os.path.basename(chunk_file)
    output_file = os.path.join(OUTPUT_DIR, f'results_{chunk_file_name}')
    
    # Write header if file doesn't exist
    if not os.path.exists(output_file):
        with open(output_file, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
    
    logger.info(f"Started processing file {chunk_file}...")
    chunk_size = 500
    for batch_data in pd.read_csv(chunk_file, chunksize=chunk_size):
        logger.info(f"Processing {len(batch_data)} records from {chunk_file}...")
        process_chunk_rows(batch_data.to_dict('records'), output_file, chunk_file_name, BASE_DIR)
    
    logger.info(f"Completed processing file {chunk_file}.")

if __name__ == '__main__':

    #INPUT_DIR = '/scratch/njr7jk/ap1_hpc/input'
    #OUTPUT_DIR = '/scratch/njr7jk/ap1_hpc/output'
    BASE_DIR = sys.argv[1]
    # Set up logging
    logger = setup_logging(BASE_DIR)

    INPUT_DIR = os.path.join(BASE_DIR, 'input')
    OUTPUT_DIR = os.path.join(BASE_DIR, 'output')

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    chunk_files = [os.path.join(INPUT_DIR, f) for f in os.listdir(INPUT_DIR) if f.startswith('chunk_')]
    #chunk_files = chunk_files[:2] # For testing purposes
    nprox = int(os.getenv('SLURM_NPROCS'))

    # Create a multiprocessing Pool
    with Pool(processes=nprox) as pool:
        pool.starmap(process_chunk, [(chunk, OUTPUT_DIR, BASE_DIR) for chunk in chunk_files])
    
    logger.info("Script completed.")
