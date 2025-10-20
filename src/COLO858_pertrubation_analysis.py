import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import io
import seaborn as sns
from tqdm import tqdm 
import logging
from scipy import stats
from scipy.stats import beta
from scipy.stats import truncnorm
import simulate_ap1 as sim  # Your simulation module

import warnings
warnings.filterwarnings('ignore')
import logging
logging.getLogger().setLevel(logging.INFO)


# Your initial data loading and preparation
def prepare_initial_data(cell, version, folder_path):
    """Prepare initial dataset with your existing preprocessing steps"""
    data_file = f"{cell}_cell_specific_parameter_initialcondition_and_steadystates_{version}.csv"
    data = pd.read_csv(os.path.join(folder_path, data_file))
    data['state'] = data['state'].str.replace(', ', ',', regex=False)
    
    # create processed dataset
    data2 = data.copy()
    data2.drop(['fos', 'jun', 'fra1', 'fra2', 'jund'], axis=1, inplace=True)
    data2.drop('unique_steady_states', axis=1, inplace=True)
    data2 = data2.drop_duplicates(subset=['param_index', 'fos_ss', 'jun_ss', 'fra1_ss', 'fra2_ss', 'jund_ss'])
    
    data2['FOS_category'] = data2['fos_ss'].apply(lambda x: 'high' if x >= 10 else 'low')
    data2.rename(columns={'fos_ss': 'fos', 'jun_ss': 'jun', 'fra1_ss': 'fra1', 
                         'fra2_ss': 'fra2', 'jund_ss': 'jund'}, inplace=True)
    
    data2.drop('state', axis=1, inplace=True)
    
    # Sample from categories
    #data2_low = data2[data2['FOS_category'] == 'low'].sample(n=500, random_state=42)
    #data2_high = data2[data2['FOS_category'] == 'high'].sample(n=500, random_state=42)
    #data2 = data2.sample(n=7000, random_state=42)
    #data2 = pd.concat([data2_low, data2_high])
    
    return data2

def run_simulations_with_duplicates(fos_data, param_indices):
    """Your original simulation function"""
    import simulate_ap1 as sim
    from functools import partial
    
    all_results = []
    all_failed_indices = []
    
    total_simulations = sum(len(fos_data[fos_data['param_index'] == param_idx]['init_cond_index'].unique()) 
                          for param_idx in param_indices)
    
    with tqdm(total=total_simulations, desc="Running all simulations") as pbar:
        def run_single_simulation(param_idx, init_idx, data):
            temp_df = data[
                (data['param_index'] == param_idx) & 
                (data['init_cond_index'] == init_idx)
            ].copy()
            
            orig_tqdm = sim.tqdm
            sim.tqdm = lambda x, **kwargs: x
            
            try:
                temp_results, failed_indices = sim.run_simulations(temp_df, [param_idx])
            finally:
                sim.tqdm = orig_tqdm
            
            return temp_results, failed_indices
        
        for param_idx in param_indices:
            param_subset = fos_data[fos_data['param_index'] == param_idx]
            init_cond_indices = param_subset['init_cond_index'].unique()
            
            for init_idx in init_cond_indices:
                try:
                    temp_results, failed_indices = run_single_simulation(param_idx, init_idx, fos_data)
                    
                    if not temp_results.empty:
                        all_results.append(temp_results)
                    if failed_indices:
                        all_failed_indices.extend(failed_indices)
                except Exception as e:
                    logging.error(f"Error in simulation {param_idx}, {init_idx}: {str(e)}")
                    all_failed_indices.append(param_idx)
                
                pbar.update(1)
    
    final_results = pd.concat(all_results, ignore_index=True) if all_results else pd.DataFrame()
    return final_results, list(set(all_failed_indices))

def reorder_for_simulation(df):
    """
    Force df to have columns in the exact order that run_simulations() expects:
      0: param_index
      1: init_cond_index
      2..16: (basal_fos).v, (basal_jun).v, etc. (all parameter columns)
      17..21: fos, jun, fra1, fra2, jund
    Adjust as necessary to match your real param columns.
    """
    param_cols = [
        '(basal_fos).v', '(basal_jun).v',
       '(basal_fra1).v', '(basal_fra2).v', '(basal_jund).v',
       '(jun_by_junjun).beta', '(jun_by_junfos).beta',
       '(fra1_by_junfra1).beta', '(fra1_by_jundfos).beta',
       '(fra2_by_junfra2).beta', '(degradation_fos).k1',
       '(degradation_jun).k1', '(degradation_fra1).k1',
       '(degradation_fra2).k1', '(degradation_jund).k1'
    ]
    species_cols = ['fos','jun','fra1','fra2','jund']

    # Build final order
    final_order = ['param_index','init_cond_index'] + param_cols + species_cols
    # Filter out any missing columns just in case
    final_order = [col for col in final_order if col in df.columns]
    
    return df[final_order].copy()

class PerturbationPipeline:
    def __init__(self, initial_data):
        """
        Initialize the perturbation pipeline with initial data
        
        Parameters:
        -----------
        initial_data : pd.DataFrame
            Initial dataset with parameters and states
        """
        self.initial_data = initial_data.copy()
        self.current_data = initial_data.copy()
        self.failed_indices = set()
        
        # Define standard column mappings
        self.STATE_MAPPINGS = {
            'input': ['fos', 'jun', 'fra1', 'fra2', 'jund'],
            'output': ['cFOS', 'cJUN', 'FRA1', 'FRA2', 'JUND']
        }
        self.PROTEIN_PARAMETERS = {
            'FOS': {
                'basal': ['(basal_fos).v']
               # add the fos_jun dimer here if necessary
            },
            'JUN': {
                'basal': ['(basal_jun).v'],
                'induced': ['(jun_by_junjun).beta','(jun_by_junfos).beta'],
            },
            'FRA1': {
                'basal': ['(basal_fra1).v'],
                'induced': ['(fra1_by_junfra1).beta','(fra1_by_jundfos).beta'],  #
            },
            'FRA2': {
                'basal': ['(basal_fra2).v'],
                'induced': ['(fra2_by_junfra2).beta'],
            },
            'JUND': {
                'basal': ['(basal_jund).v'],

            }
        }
        # Track perturbation history
        self.perturbation_history = []
    
    def get_protein_parameters(self, protein, parameter_types = None):

        if protein not in self.PROTEIN_PARAMETERS:
            raise ValueError(f"Protein {protein} not found in PROTEIN_PARAMETERS")
        
        protein_params = self.PROTEIN_PARAMETERS[protein]

        if parameter_types is None:
            all_params = []
            for param_list in protein_params.values():
                all_params.extend(param_list)
            return all_params
        else:
            #get specific parameter type
            selected_params = []
            for param_type in parameter_types:
                if param_type not in protein_params:
                    raise ValueError(f"Unknown parameter type: {param_type}. Available types: {list(protein_params.keys())}")
                selected_params.extend(protein_params[param_type])
            return selected_params
                    
    def perturb_params(self, parameters_to_perturb, perturbation_type='kd', beta_a=2, beta_b=6.8,kd_approach = 'beta',
                    ko_value=0.0001, seed=42, ko_method='set', ko_multiplier=0.5, param_multipliers=None, spread_factor = 0.6,
                    kd_mean_eff=0.41, max_kd_pct=0.9):
        """
        Perturb parameters based on biological knockdown or knockout mechanism.
        
        Parameters:
        -----------
        parameters_to_perturb : list
            List of parameter names to perturb
        perturbation_type : str, optional
            Type of perturbation, either 'kd' (knockdown) or 'ko' (knockout)
        beta_a, beta_b : float, optional
            Shape parameters for beta distribution for knockdown
        ko_value : float, optional
            The value to set for knocked out parameter when ko_method='set'
        seed : int, optional
            Random seed for reproducibility
        ko_method : str, optional
            Method for knockout: 'set' or 'multiply'
        ko_multiplier : float, optional
            Default multiplier to use when ko_method='multiply'
        param_multipliers : dict, optional
            Dictionary mapping parameter names to specific multipliers
        """
        print("\n----- PERTURB_PARAMS FUNCTION -----")
        print(f"Method: {ko_method}, Parameters: {parameters_to_perturb}")
        print(f"Param multipliers: {param_multipliers}")
        
        np.random.seed(seed)
        perturbed_data = self.current_data.copy()
        
        # Validate parameters
        missing_params = [param for param in parameters_to_perturb if param not in perturbed_data.columns]
        if missing_params:
            raise ValueError(f"Parameters not found in data: {missing_params}")
        
        # Debug: print original values
        print("Original parameter values:")
        for param in parameters_to_perturb:
            print(f"  {param}: {perturbed_data[param].iloc[0]}")
        
        if perturbation_type == 'kd':
            if kd_approach == 'beta':
                raw_multipliers = stats.beta.rvs(a=beta_a, b=beta_b, size=len(perturbed_data))
                # Scale multipliers to be between 0.1 and 1 instead of 0 and 1
                multipliers = 0.01 + (raw_multipliers * 0.99)
                # convert to log10
                #multipliers = np.log10(multipliers)
                #multipliers = 0.2 + (raw_multipliers * 0.8)
                perturbed_data['knockdown_multiplier'] = multipliers # now its log10
                for param in parameters_to_perturb:
                        perturbed_data[param] = perturbed_data[param] * multipliers
            elif kd_approach == 'truncnorm':
                target_log_shift = np.log10(1-kd_mean_eff)
                log_shift_std = 0.8
                
                # set bounds 
                upper_bound = -0.01
                min_multiplier = 1- max_kd_pct
                lower_bound = np.log10(min_multiplier)

                a, b = (lower_bound - target_log_shift) / log_shift_std, (upper_bound - target_log_shift) / log_shift_std
                log_shifts = truncnorm.rvs(a, b, loc=target_log_shift, scale=log_shift_std, size=len(perturbed_data))

                log_shifts = np.minimum(log_shifts, -0.004) 
             # Calculate equivalent multipliers
                multipliers = 10**log_shifts
                
                perturbed_data['knockdown_multiplier'] = multipliers
                #
                # apply multipliers to parameters
                for param in parameters_to_perturb:
                    perturbed_data[param] = 10**(np.log10(perturbed_data[param]) + log_shifts)

            elif kd_approach == 'direct':
                multipliers = self.create_controlled_knockdown_multipliers(
                    len(perturbed_data),
                    target_mean=1-kd_mean_eff,  # e.g., 0.59 for 41% knockdown
                    min_val=1-max_kd_pct,       # e.g., 0.1 for 90% max knockdown
                    max_val=0.99,               # Ensure at least 1% knockdown
                    spread_factor=spread_factor, # Control distribution overlap
                    seed=seed
                )
                perturbed_data['knockdown_multiplier'] = multipliers
                for param in parameters_to_perturb:
                    perturbed_data[param] = perturbed_data[param] * multipliers

                
                # Report achieved knockdown efficiency
                achieved_efficiency = 1 - np.mean(multipliers)
                print(f"Target efficiency: {kd_mean_eff:.2f}, Achieved: {achieved_efficiency:.2f}")
            else:
                raise ValueError(f"Unknown knockdown approach: {kd_approach}. Use 'beta' or 'truncnorm'.")

          
                    
        else:  # knockout case
            if ko_method == 'set':
                # set to a fixed value
                print(f"Setting all parameters to fixed value: {ko_value}")
                perturbed_data['knockout_value'] = ko_value
                for param in parameters_to_perturb:
                    perturbed_data[param] = ko_value
                    print(f"  {param} set to {ko_value}")
                multipliers = np.array([ko_value / perturbed_data[param].iloc[0] 
                                    for param in parameters_to_perturb])
            elif ko_method == 'multiply':
                print("Applying multiply method with custom multipliers")
                # Record all parameter multipliers used
                param_mults = []
                
                for param in parameters_to_perturb:
                    mult = param_multipliers.get(param, ko_multiplier) if param_multipliers else ko_multiplier
                    print(f"  Applying multiplier {mult} to {param}")
                    
                    # Store original for checking
                    orig_val = perturbed_data[param].iloc[0]
                    
                    # Apply multiplier
                    perturbed_data[param] = perturbed_data[param] * mult
                    
                    # Verify the change
                    new_val = perturbed_data[param].iloc[0]
                    print(f"  {param}: {orig_val} × {mult} = {new_val}")
                    
                    param_mults.append(mult)
                    
                # Store the default multiplier or create a summary field
                if param_multipliers:
                    perturbed_data['knockout_custom_multipliers'] = True
                    # Also store individual multipliers for reference
                    for param, mult in param_multipliers.items():
                        if param in parameters_to_perturb:
                            col_name = f"knockout_mult_{param.split('.')[-1]}"
                            perturbed_data[col_name] = mult
                else:
                    perturbed_data['knockout_multiplier'] = ko_multiplier
                    
                multipliers = np.array(param_mults)
            else:
                raise ValueError(f"Unknown knockout method: {ko_method}. Use 'set' or 'multiply'.")
        
        # Debug: print final values
        print("Final parameter values after perturbation:")
        for param in parameters_to_perturb:
            print(f"  {param}: {perturbed_data[param].iloc[0]}")
        
        print("----- PERTURB_PARAMS COMPLETE -----\n")
        
        return perturbed_data, multipliers
    def create_controlled_knockdown_multipliers(self, n_samples, target_mean=0.59, min_val=0.1, max_val=0.99, spread_factor=0.6, seed=None):
        """
        Create knockdown multipliers with precise control over mean and distribution shape.
        
        Parameters:
        -----------
        n_samples : int
            Number of samples to generate
        target_mean : float
            Target mean for multipliers (e.g., 0.59 for 41% knockdown)
        min_val : float
            Minimum allowed value (e.g., 0.1 for max 90% knockdown)
        max_val : float
            Maximum allowed value (e.g., 0.99 for min 1% knockdown)
        spread_factor : float
            Controls distribution spread (higher = more spread, less overlap)
            Values around 0.2-0.4 give reasonable spread
            Higher values (0.5-0.7) give more separation between distributions
        seed : int, optional
            Random seed for reproducibility
            
        Returns:
        --------
        np.array
            Array of multipliers with target mean
        """
        if seed is not None:
            np.random.seed(seed)
        
        # Generate beta distribution with parameters that control shape
        # Higher spread_factor = more variance = less overlap with control
        if spread_factor <= 0.3:
            # More concentrated distribution (~80% overlap)
            alpha, beta = 4, 3
        elif spread_factor <= 0.5:
            # Medium spread (~60% overlap)
            alpha, beta = 2, 2
        else:
            # Wide spread (~45% overlap)
            alpha, beta = 2, 6.8
        
        # Generate raw beta values
        raw_values = np.random.beta(alpha, beta, n_samples)
        
        # Scale to our desired range
        scaled_values = min_val + raw_values * (max_val - min_val)
        
        # Calculate current mean
        current_mean = np.mean(scaled_values)
        
        # Apply adjustment to hit target mean exactly
        adjustment_factor = target_mean / current_mean
        adjusted_values = scaled_values * adjustment_factor
        
        # Re-clip to ensure bounds after adjustment
        adjusted_values = np.clip(adjusted_values, min_val, max_val)
        
        # Fine-tune to hit target mean after clipping
        for _ in range(3):
            current_mean = np.mean(adjusted_values)
            if abs(current_mean - target_mean) < 0.001:
                break
            
            adjustment_factor = target_mean / current_mean
            adjusted_values = adjusted_values * adjustment_factor
            adjusted_values = np.clip(adjusted_values, min_val, max_val)
        
        return adjusted_values

    def _handle_failed_simulations(self, failed_indices):
        """
        Update failed indices and remove failed simulations from current data
        """
        self.failed_indices.update(failed_indices)
        self.current_data = self.current_data[~self.current_data['param_index'].isin(self.failed_indices)]
        # removed failed simulations from initial data
        self.initial_data = self.initial_data[~self.initial_data['param_index'].isin(self.failed_indices)]
        
    def _update_state_names(self, data, perturbation_info):
        """
        Update column names based on perturbation sequence
        """
        rename_dict = {}
        perturbation_type = perturbation_info['type']
        target_gene = perturbation_info['gene']
        
        for old_name, new_name in zip(self.STATE_MAPPINGS['output'], 
                                    self.STATE_MAPPINGS['output']):
            # Check if this is a subsequent perturbation after a knockout
            if self.perturbation_history and self.perturbation_history[-1]['type'] == 'ko' and perturbation_type in ['kd', 'oe']:
                # Get previous perturbation details
                prev_pert = self.perturbation_history[-1]
                
                # Create appropriate suffix based on perturbation type
                if perturbation_type == 'kd':
                    suffix = f"post {prev_pert['gene']}KO {target_gene}KD"
                elif perturbation_type == 'oe':
                    suffix = f"post {prev_pert['gene']}KO {target_gene}OE"
            else:
                # First perturbation or not following a knockout
                if perturbation_type == 'ko':
                    suffix = f"post {target_gene}KO"
                elif perturbation_type == 'kd':
                    suffix = f"post {target_gene}KD"
                elif perturbation_type == 'oe':
                    suffix = f"post {target_gene}OE"
                    
            rename_dict[old_name] = f"{new_name} {suffix}"
            
        return data.rename(columns=rename_dict)

    def perform_knockout(self, target_gene=None, ko_value=0.0001, ko_method='set', 
                    ko_multiplier=0.5, custom_params=None,param_multipliers=None):
        """
        Perform knockout perturbation with support for parameter-specific multipliers
        
        Parameters:
        -----------
        target_gene : str, optional
            The gene to knockout (e.g., 'FOS', 'JUN')
        ko_value : float, optional
            The value to set for knocked out parameter when ko_method='set'
        ko_method : str, optional
            Method for knockout: 'set' or 'multiply'
        ko_multiplier : float, optional
            Default multiplier to use when ko_method='multiply'
        custom_params : list, optional
            Custom list of parameters to perturb (overrides target_gene if provided)
        param_multipliers : dict, optional
            Dictionary mapping parameter names to specific multipliers
            Example: {'(basal_fos).v': 0.5, '(jun_by_junfos).beta': 0.1}
        """
        # Debug: Print input parameters
        print("\n----- STARTING KNOCKOUT -----")
        print(f"Target gene: {target_gene}")
        print(f"Custom params: {custom_params}")
        print(f"Method: {ko_method}")
        print(f"Param multipliers: {param_multipliers}")
        
        # Determine parameters to perturb based on input
        if custom_params is not None:
            ko_params = custom_params
            target_name = target_gene if target_gene is not None else "CustomParams"
        elif target_gene is not None:
            ko_params = self.get_protein_parameters(target_gene)
            target_name = target_gene
        else:
            raise ValueError("Either target_gene or custom_params must be provided")
        
        print(f"Parameters to perturb (ko_params): {ko_params}")
        
        # Check if parameters exist in current data
        for param in ko_params:
            if param in self.current_data.columns:
                print(f"{param} exists in current_data, sample value: {self.current_data[param].iloc[0]}")
            else:
                print(f"WARNING: {param} does not exist in current_data columns!")
        
        # Log the start of knockout simulation
        if ko_method == 'set':
            logging.info(f"Starting {target_name} knockout simulation with ko_value={ko_value}")
        elif ko_method == 'multiply':
            if param_multipliers:
                logging.info(f"Starting {target_name} knockout simulation with custom multipliers")
                for param, mult in param_multipliers.items():
                    if param in ko_params:
                        logging.info(f"  - {param}: {mult}")
            else:
                logging.info(f"Starting {target_name} knockout simulation with ko_multiplier={ko_multiplier}")
        else:
            raise ValueError(f"Unknown knockout method: {ko_method}. Use 'set' or 'multiply'.")
        
        # Perform knockout perturbation
        perturbed_data, _ = self.perturb_params(
            ko_params, 
            perturbation_type='ko',
            ko_value=ko_value,
            ko_method=ko_method,
            ko_multiplier=ko_multiplier,
            param_multipliers=param_multipliers
        )
        
        # Debug: Check perturbed values before simulation
        print("\n----- AFTER PERTURBATION, BEFORE SIMULATION -----")
        for param in ko_params:
            print(f"{param} value after perturbation: {perturbed_data[param].iloc[0]}")
        
        # Run simulations
        print("\n----- RUNNING SIMULATION -----")
        results_df, failed_indices = run_simulations_with_duplicates(
            perturbed_data, 
            perturbed_data['param_index'].unique()
        )
        
        # Debug: Check values after simulation
        print("\n----- AFTER SIMULATION -----")
        for param in ko_params:
            if param in results_df.columns:
                print(f"{param} exists in results_df, sample value: {results_df[param].iloc[0] if not results_df.empty else 'N/A'}")
            else:
                print(f"{param} does not exist in results_df columns!")
        
        # Handle failed simulations and log the number of failures
        initial_size = len(results_df)
        self._handle_failed_simulations(failed_indices)
        
        # Remove failed simulations from results_df
        results_df = results_df[~results_df['param_index'].isin(self.failed_indices)]
        logging.info(f"Removed {initial_size - len(results_df)} failed simulations")
        
        # Update current data with new steady states
        results_df = self._update_state_names(
            results_df, 
            {'type': 'ko', 'gene': target_name}
        )
        
        # Debug: Check columns before merge
        print("\n----- COLUMNS BEFORE MERGE -----")
        print(f"Results columns: {results_df.columns.tolist()}")
        print(f"Initial data columns: {self.initial_data.columns.tolist()}")
        
        # Merge with full parameter set from initial data
        param_columns = [c for c in self.initial_data.columns
                        if c not in self.STATE_MAPPINGS['input'] + ['FOS_category']]
        print(f"Param columns for merge: {param_columns}")
        
        results_df = results_df.merge(
            self.initial_data[param_columns],
            on=['param_index','init_cond_index'],
            how='left', suffixes=("", "_old")
        )
        
        # Debug: Check values after merge
        print("\n----- AFTER MERGE -----")
        for param in ko_params:
            if param in results_df.columns:
                print(f"{param} exists after merge, sample value: {results_df[param].iloc[0] if not results_df.empty else 'N/A'}")
            else:
                print(f"{param} does not exist after merge!")
        
        # Overwrite old param with new KO param values - THIS IS CRITICAL
        print("\n----- APPLYING FINAL PARAMETER VALUES -----")
        for p in ko_params:
            if ko_method == 'set':
                # e.g. results_df["(basal_fos).v"] = 0.0001
                print(f"Setting {p} to fixed value {ko_value}")
                results_df[p] = ko_value
            else:  # ko_method == 'multiply'
                # Get the multiplier for this parameter
                mult = param_multipliers.get(p, ko_multiplier) if param_multipliers else ko_multiplier
                print(f"Applying multiplier {mult} to {p}")
                
                # Get original value from initial_data and multiply
                orig_values = self.initial_data.set_index(['param_index', 'init_cond_index'])[p].to_dict()
                
                # Direct assignment using at for guaranteed precision
                for idx, row in results_df.iterrows():
                    key = (row['param_index'], row['init_cond_index'])
                    orig_val = orig_values.get(key, 0)
                    new_val = orig_val * mult
                    results_df.at[idx, p] = new_val
                    
                    # Only print first row for debugging
                    if idx == 0:
                        print(f"  {p}: {orig_val} × {mult} = {new_val}")
                
            old_col = p + "_old"
            if old_col in results_df.columns:
                results_df.drop(columns=[old_col], inplace=True)
        
        # Debug: Check final values
        print("\n----- FINAL PARAMETER VALUES -----")
        for param in ko_params:
            if param in results_df.columns:
                print(f"{param} final value: {results_df[param].iloc[0] if not results_df.empty else 'N/A'}")
            else:
                print(f"{param} missing from final results!")
        
        # Verify results are not empty
        if len(results_df) == 0:
            raise ValueError("No valid results after merging in KO step.")
        
        # Save to history with enhanced information
        self.perturbation_history.append({
            'type': 'ko',
            'gene': target_name,
            'results': results_df,
            'ko_params': ko_params,
            'ko_method': ko_method,
            'ko_value': ko_value if ko_method == 'set' else None,
            'ko_multiplier': ko_multiplier if ko_method == 'multiply' else None,
            'param_multipliers': param_multipliers.copy() if param_multipliers else None
        })
        
        # Set self.current_data to results_df,
        # BUT also rename back to fos,jun,fra1,fra2,jund so next step sees them:
        self.current_data = self._rename_back_to_input(results_df, target_name, is_ko=True)
        
        # Reorder so columns 17..21 are fos,jun,fra1,fra2,jund
        self.current_data = reorder_for_simulation(self.current_data)
        
        # Debug: Check if parameters carried over to current_data
        print("\n----- PARAMETERS IN CURRENT_DATA AFTER KNOCKOUT -----")
        for param in ko_params:
            if param in self.current_data.columns:
                print(f"{param} in current_data: {self.current_data[param].iloc[0]}")
            else:
                print(f"{param} missing from current_data!")
        
        print("----- KNOCKOUT COMPLETE -----\n")
        
        return results_df
        
    

    def perform_knockdown(self, target_gene, beta_a=2.5, beta_b=7.4, kd_mean_eff=0.41, max_kd_pct=0.9, kd_approach='direct', spread_factor = 0.8):
        """
        Perform knockdown perturbation
        """
        # Determine parameters to perturb based on target gene
        kd_params = [f'(basal_{target_gene.lower()}).v']
        
        # Validation check for state columns
        current_columns = set(self.current_data.columns)
        required_states = set(self.STATE_MAPPINGS['input'])
        missing_states = required_states - current_columns
        
        if missing_states:
            # If coming from a knockout, need to rename the state columns back to lowercase
            if self.perturbation_history and self.perturbation_history[-1]['type'] == 'ko':
                # Get the previous knockout gene
                prev_gene = self.perturbation_history[-1]['gene']
                
                # Create reverse mapping from uppercase to lowercase
                reverse_rename = {}
                for old_name, new_name in zip(self.STATE_MAPPINGS['output'], 
                                            self.STATE_MAPPINGS['input']):
                    column_name = f"{old_name} post {prev_gene}KO"
                    reverse_rename[column_name] = new_name
                
                # Rename columns back to lowercase
                self.current_data = self.current_data.rename(columns=reverse_rename)
                
                # Verify the renaming worked
                if not all(state in self.current_data.columns for state in self.STATE_MAPPINGS['input']):
                    raise ValueError(f"Failed to properly rename state columns for knockdown. "
                                f"Expected states: {self.STATE_MAPPINGS['input']}, "
                                f"Got: {[col for col in self.current_data.columns if col in reverse_rename.values()]}")
                                
                logging.info(f"Successfully renamed post-KO columns back to lowercase for KD simulation")
        
        # Perform knockdown perturbation
        if kd_approach == 'beta':
            # Original beta approach
            print("Beta approach")
            perturbed_data, multipliers = self.perturb_params(
                kd_params,
                perturbation_type='kd',
                beta_a=beta_a,
                beta_b=beta_b,
                kd_approach='beta'
            )
        elif kd_approach == 'truncnorm':
            print("Truncated normal approach")
            # Truncated normal approach
            perturbed_data, multipliers = self.perturb_params(
                kd_params,
                perturbation_type='kd',
                kd_approach='truncnorm',
                kd_mean_eff=kd_mean_eff,
                max_kd_pct=max_kd_pct
            )
        elif kd_approach == 'direct':
            print("Direct approach")
            # Direct approach
            perturbed_data, multipliers = self.perturb_params(
                kd_params,
                perturbation_type='kd',
                kd_approach='direct',
                kd_mean_eff=kd_mean_eff,
                max_kd_pct=max_kd_pct,
                spread_factor=spread_factor
            )
        else:
            raise ValueError(f"Unknown knockdown approach: {kd_approach}. Use 'beta', 'truncnorm', or 'direct'.")
        # Run simulations
        results_df, failed_indices = run_simulations_with_duplicates(
            perturbed_data,
            perturbed_data['param_index'].unique()
        )
        
        # Handle failed simulations
        self._handle_failed_simulations(failed_indices)
        
        # Remove failed simulations from results_df
        results_df = results_df[~results_df['param_index'].isin(self.failed_indices)]
        
        # Add the knockdown multiplier to results
        results_df = results_df.merge(
            perturbed_data[['param_index', 'init_cond_index', 'knockdown_multiplier']],
            on=['param_index', 'init_cond_index'],
            how='left'
        )
        
        # Update current data with new steady states
        if self.perturbation_history and self.perturbation_history[-1]['type'] == 'ko':
            # If there was a previous KO, include it in the state names
            prev_gene = self.perturbation_history[-1]['gene']
            results_df = self._update_state_names(
                results_df,
                {'type': 'kd', 'gene': target_gene, 'prev_ko': prev_gene}
            )
        else:
            results_df = self._update_state_names(
                results_df,
                {'type': 'kd', 'gene': target_gene}
            )
        
        # 5) Keep param columns from current_data but preserve updated KD param
        param_columns = [c for c in self.current_data.columns
                         if c not in self.STATE_MAPPINGS['input'] + ['FOS_category']]
        results_df = results_df.merge(
            self.current_data[param_columns],
            on=['param_index','init_cond_index'],
            how='left', suffixes=("", "_old")
        )
        for p in kd_params:
            # E.g. results_df["(basal_jund).v"] = results_df["(basal_jund).v"] from perturbed_data
            updated_vals = perturbed_data.set_index(['param_index','init_cond_index'])[p].to_dict()
            results_df[p] = results_df.apply(
                lambda row: updated_vals.get((row['param_index'], row['init_cond_index']), np.nan),
                axis=1
            )
            old_col = p + "_old"
            if old_col in results_df.columns:
                results_df.drop(columns=[old_col], inplace=True)
        
        # 6) Save to history
        self.perturbation_history.append({
            'type': 'kd',
            'gene': target_gene,
            'kd_approach': kd_approach,
            'results': results_df
        })
        
        # 7) Set self.current_data for next step,
        # rename back to fos,jun,fra1,fra2,jund,
        # reorder so run_simulations() can pick them
        self.current_data = self._rename_back_to_input(results_df, target_gene, is_ko=False)
        self.current_data = reorder_for_simulation(self.current_data)
        
        return results_df
    
    def perform_overexpression(self, target_gene, oe_method='beta', beta_a=8.0, beta_b=2.5, max_mult=2.0, set_mult=2.0, custom_params=None):
        """
        Perform overexpression perturbation
        
        Parameters:
        -----------
        target_gene : str
            The gene to overexpress (e.g., 'FRA1', 'JUN')
        oe_method : str, optional
            Method for overexpression: 'beta' or 'set'
        beta_a, beta_b : float, optional
            Shape parameters for beta distribution - used when oe_method='beta'
        max_mult : float, optional
            Maximum multiplier value to scale the overexpression when using beta distribution
        set_mult : float, optional
            Fixed multiplier to use when oe_method='set'
        custom_params : list, optional
            Custom list of parameters to perturb (overrides target_gene parameters if provided)
        """
        # Choose parameters to perturb based on target gene or custom parameters
        if custom_params is not None:
            oe_params = custom_params
            print(f"Overexpressing custom parameters: {oe_params}")
        else:
            oe_params = self.get_protein_parameters(target_gene)
            print(f"Overexpressing parameters for {target_gene}: {oe_params}")
        
        # Similar validation as knockdown for state columns
        current_columns = set(self.current_data.columns)
        required_states = set(self.STATE_MAPPINGS['input'])
        missing_states = required_states - current_columns
        
        if missing_states:
            # If coming from a knockout, need to rename the state columns back to lowercase
            if self.perturbation_history and self.perturbation_history[-1]['type'] == 'ko':
                # Get the previous knockout gene
                prev_gene = self.perturbation_history[-1]['gene']
                
                # Create reverse mapping from uppercase to lowercase
                reverse_rename = {}
                for old_name, new_name in zip(self.STATE_MAPPINGS['output'], 
                                            self.STATE_MAPPINGS['input']):
                    column_name = f"{old_name} post {prev_gene}KO"
                    reverse_rename[column_name] = new_name
                
                # Rename columns back to lowercase
                self.current_data = self.current_data.rename(columns=reverse_rename)
                
                # Verify the renaming worked
                if not all(state in self.current_data.columns for state in self.STATE_MAPPINGS['input']):
                    raise ValueError(f"Failed to properly rename state columns for overexpression. "
                                f"Expected states: {self.STATE_MAPPINGS['input']}, "
                                f"Got: {[col for col in self.current_data.columns if col in reverse_rename.values()]}")
                                
                logging.info(f"Successfully renamed post-KO columns back to lowercase for OE simulation")
        
        # Create a copy of the current data for perturbation
        perturbed_data = self.current_data.copy()
        
        # Apply overexpression based on method
        if oe_method == 'beta':
            # Generate beta-distributed values for multipliers
            np.random.seed(42)  # For reproducibility
            raw_multipliers = stats.beta.rvs(a=beta_a, b=beta_b, size=len(perturbed_data))
            
            # Scale raw values (between 0-1) to desired overexpression range (1 to max_mult)
            # This transformation maps the beta output [0,1] to [1,max_mult]
            multipliers = 1.0 + ((max_mult - 1.0) * raw_multipliers)
            
            # Store the multiplier values for reference
            perturbed_data['overexpression_multiplier'] = multipliers
            
            # Calculate and log mean overexpression
            mean_oe = np.mean(multipliers) - 1.0  # Subtract 1 to get percentage increase
            logging.info(f"Using beta distribution for overexpression. Mean increase: {mean_oe*100:.1f}%")
            
        elif oe_method == 'set':
            # Use a fixed multiplier for all simulations
            multipliers = np.full(len(perturbed_data), set_mult)
            perturbed_data['overexpression_multiplier'] = set_mult
            logging.info(f"Using fixed multiplier of {set_mult} for overexpression")
            
        else:
            raise ValueError(f"Unknown overexpression method: {oe_method}. Use 'beta' or 'set'.")
        
        # Apply multipliers to all parameters for this gene
        for param in oe_params:
            if param in perturbed_data.columns:
                perturbed_data[param] = perturbed_data[param] * multipliers
                print(f"Applied overexpression to {param}, sample before/after: "
                    f"{self.current_data[param].iloc[0]:.4f} -> {perturbed_data[param].iloc[0]:.4f}")
            else:
                print(f"Warning: Parameter {param} not found in current data, skipping")
        
        # Run simulations with the perturbed parameters
        results_df, failed_indices = run_simulations_with_duplicates(
            perturbed_data,
            perturbed_data['param_index'].unique()
        )
        
        # Handle failed simulations
        self._handle_failed_simulations(failed_indices)
        
        # Remove failed simulations from results
        results_df = results_df[~results_df['param_index'].isin(self.failed_indices)]
        
        # Add the overexpression multiplier to results
        results_df = results_df.merge(
            perturbed_data[['param_index', 'init_cond_index', 'overexpression_multiplier']],
            on=['param_index', 'init_cond_index'],
            how='left'
        )
        
        # Update state names to show OE instead of KD
        if self.perturbation_history and self.perturbation_history[-1]['type'] == 'ko':
            # If there was a previous KO, include it in the state names
            prev_gene = self.perturbation_history[-1]['gene']
            results_df = self._update_state_names(
                results_df,
                {'type': 'oe', 'gene': target_gene, 'prev_ko': prev_gene}
            )
        else:
            results_df = self._update_state_names(
                results_df,
                {'type': 'oe', 'gene': target_gene}
            )
        
        # Keep parameter columns from current_data but preserve updated OE params
        param_columns = [c for c in self.current_data.columns
                        if c not in self.STATE_MAPPINGS['input'] + ['FOS_category']]
        
        results_df = results_df.merge(
            self.current_data[param_columns],
            on=['param_index', 'init_cond_index'],
            how='left', suffixes=("", "_old")
        )
        
        # Update the OE parameter values in the results
        for p in oe_params:
            if p in perturbed_data.columns:
                updated_vals = perturbed_data.set_index(['param_index', 'init_cond_index'])[p].to_dict()
                results_df[p] = results_df.apply(
                    lambda row: updated_vals.get((row['param_index'], row['init_cond_index']), np.nan),
                    axis=1
                )
                old_col = p + "_old"
                if old_col in results_df.columns:
                    results_df.drop(columns=[old_col], inplace=True)
        
        # Save to history with appropriate method information
        history_entry = {
            'type': 'oe',
            'gene': target_gene,
            'results': results_df,
            'oe_params': oe_params,
            'oe_method': oe_method
        }
        
        if oe_method == 'beta':
            history_entry.update({
                'beta_a': beta_a,
                'beta_b': beta_b,
                'max_mult': max_mult
            })
        else:  # oe_method == 'set'
            history_entry.update({
                'set_mult': set_mult
            })
        
        self.perturbation_history.append(history_entry)
        
        # Set current_data for next step
        self.current_data = self._rename_back_to_input(results_df, target_gene, is_ko=False)
        self.current_data = reorder_for_simulation(self.current_data)
        
        # Calculate and report actual mean overexpression
        if oe_method == 'beta':
            mean_oe = np.mean(multipliers) - 1.0  # Subtract 1 to get percentage increase
        else:
            mean_oe = set_mult - 1.0
        
        logging.info(f"Overexpression of {target_gene} complete. Mean increase: {mean_oe*100:.1f}%")
        
        return results_df
    
    def _rename_back_to_input(self, df, gene, is_ko):
        """
        After we get new columns 'cFOS post FOSKO' etc., 
        we want to keep those columns for final results, 
        but also *duplicate* them as 'fos','jun','fra1','fra2','jund'
        so that the next run can treat them as the initial states.
        """
        # 1) Identify the 'output' columns in df
        #    e.g. cFOS post FOSKO, cJUN post FOSKO, ...
        #    or cFOS post FOSKO JUNDKD, etc.
        post_cols = []
        for c in self.STATE_MAPPINGS['output']:
            # c might be 'cFOS','cJUN' etc.
            # We find columns that *start* with that or contain 'post' 
            # so something like "cFOS post FOSKO" 
            # or "cFOS post FOSKO JUNDKD"
            for col in df.columns:
                if col.startswith(c) and 'post' in col:
                    post_cols.append(col)
        
        if len(post_cols) != 5:
            logging.warning(f"Expected 5 post columns, found {len(post_cols)}: {post_cols}")
        
        # 2) Map 'cFOS -> fos', 'cJUN -> jun', etc.
        #    We'll find each "cFOS post X" column and rename it to "fos"
        rename_to_input = {}
        for out_name, in_name in zip(self.STATE_MAPPINGS['output'], self.STATE_MAPPINGS['input']):
            # We look for the column in `post_cols` that starts with out_name
            matching = [col for col in post_cols if col.startswith(out_name)]
            if matching:
                # take the first match or all matches if there's multiple
                rename_to_input[matching[0]] = in_name
        
        # 3) Duplicate these columns so we keep both:
        #    "cFOS post FOSKO" AND a brand-new "fos" with the same values.
        df2 = df.copy()
        for old_col,new_col in rename_to_input.items():
            df2[new_col] = df2[old_col]
        
        return df2

    
    def save_state(self):
        """Saves current pipeline state"""
        state = {
            'current_data': self.current_data.copy(),
            'initial_data': self.initial_data.copy(),
            'failed_indices': self.failed_indices.copy(),
            'perturbation_history': self.perturbation_history.copy()
        }
        return state
    
    def load_state(self, state):
        """Loads a previously saved state"""
        self.current_data = state['current_data'].copy()
        self.initial_data = state['initial_data'].copy()
        self.failed_indices = state['failed_indices'].copy()
        self.perturbation_history = state['perturbation_history'].copy()

    def reset_to_last_knockout(self):
        """Resets to the last knockout state"""
        if not self.perturbation_history:
            logging.warning("No perturbations in history to reset to")
            return
            
        last_ko_idx = None
        for idx, pert in enumerate(self.perturbation_history):
            if pert['type'] == 'ko':
                last_ko_idx = idx
                
        if last_ko_idx is None:
            logging.warning("No knockouts found in perturbation history")
            return
            
        self.perturbation_history = self.perturbation_history[:last_ko_idx + 1]
        self.current_data = self.perturbation_history[last_ko_idx]['results'].copy()
    
    def get_final_results(self):
        """Generate final merged dataset with all states and parameters"""
        if not self.perturbation_history:
            return self.initial_data
                
        final_data = self.initial_data.copy()
        
        # Keep track of perturbed parameters
        perturbed_params = set()
        
        # Track original parameter columns for consistent ordering
        param_columns = [col for col in self.initial_data.columns 
                        if col not in self.STATE_MAPPINGS['input'] and 
                        col not in ['FOS_category'] and
                        col not in ['param_index', 'init_cond_index']]
        
        # Merge results from each perturbation
        for perturbation in self.perturbation_history:
            results_to_merge = perturbation['results'].copy()
            
            # Track perturbed parameter
            if perturbation['type'] == 'ko':
                if 'ko_params' in perturbation:
                    for param in perturbation['ko_params']:
                        perturbed_params.add(param)
            elif perturbation['type'] == 'oe':
                if 'oe_params' in perturbation:
                    for param in perturbation['oe_params']:
                        perturbed_params.add(param)
            
            # Add the state columns and any multipliers from this perturbation
            merge_columns = ['param_index', 'init_cond_index']
            state_cols = [col for col in results_to_merge.columns if 'post' in col]
            merge_columns.extend(state_cols)
            
            # Add multiplier columns
            for mult_col in ['knockdown_multiplier', 'overexpression_multiplier']:
                if mult_col in results_to_merge.columns:
                    merge_columns.append(mult_col)
            
            # Don't try to merge parameter columns to avoid duplicates
            merge_columns = [col for col in merge_columns 
                            if col not in param_columns or col in ['param_index', 'init_cond_index']]
            
            # Ensure merge columns exist in both dataframes
            merge_columns = [col for col in merge_columns if col in results_to_merge.columns]
            
            final_data = pd.merge(
                final_data,
                results_to_merge[merge_columns],
                on=['param_index', 'init_cond_index'],
                how='inner'
            )
            
            # CRITICAL: Update perturbed parameter values
            for param in perturbed_params:
                if param in results_to_merge.columns:
                    # Create a mapping from (param_index, init_cond_index) to parameter value
                    param_values = results_to_merge.set_index(['param_index', 'init_cond_index'])[param]
                    
                    # Update values in final_data
                    for idx, row in final_data.iterrows():
                        key = (row['param_index'], row['init_cond_index'])
                        if key in param_values:
                            final_data.at[idx, param] = param_values[key]
        
        # Maintain consistent column ordering and remove any duplicates
        ordered_columns = ['param_index', 'init_cond_index']
        ordered_columns.extend(param_columns)  # All parameter columns
        ordered_columns.extend(self.STATE_MAPPINGS['input'])  # Original state columns
        
        # Add state columns in order of perturbation
        for perturbation in self.perturbation_history:
            state_cols = [col for col in final_data.columns if f"post {perturbation['gene']}" in col]
            ordered_columns.extend(state_cols)
        
        # Add multiplier columns at the end if they exist
        for mult_col in ['knockdown_multiplier', 'overexpression_multiplier']:
            if mult_col in final_data.columns:
                ordered_columns.append(mult_col)
        
        # Remove duplicates while preserving order
        ordered_columns = list(dict.fromkeys(ordered_columns))
        
        # Only select columns that exist
        ordered_columns = [col for col in ordered_columns if col in final_data.columns]
        final_data = final_data[ordered_columns]
        
        return final_data

    def save_results(self, cell_line, version, beta_a=None, beta_b=None, output_dir='processed_simulations'):
        """
        Save results with detailed filename including perturbation information
        """
        from datetime import datetime
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate date string
        date_str = datetime.now().strftime('%Y%m%d')
        
        # Build perturbation string
        perturbation_parts = []
        for p in self.perturbation_history:
            if p['type'] == 'ko':
                if 'ko_method' in p and p.get('ko_method') == 'multiply':
                    # Check if we used custom param multipliers
                    if p.get('param_multipliers'):
                        # For custom multipliers, use a shorthand representation
                        # Format: FOS_KO_custom_v0.5_beta0.1 (for (basal_fos).v=0.5, (jun_by_junfos).beta=0.1)
                        mult_info = []
                        for param, mult in p.get('param_multipliers').items():
                            # Extract just the last part of the parameter name
                            param_short = param.split('.')[-2].split('_')[-1] if '_' in param else param.split('.')[-2]
                            mult_info.append(f"{param_short}{mult:.2f}")
                        mult_str = '_'.join(mult_info)
                        part = f"{p['gene']}_{p['type'].upper()}_custom_{mult_str}"
                    else:
                        # Default multiplier for all parameters
                        part = f"{p['gene']}_{p['type'].upper()}_mult{p.get('ko_multiplier', 0.5):.2f}"
                else:
                    # Set to constant value
                    part = f"{p['gene']}_{p['type'].upper()}_set{p.get('ko_value', 0.0001):.4f}"
            elif p['type'] == 'oe':
                # Handle overexpression case
                if p.get('oe_method') == 'set':
                    part = f"{p['gene']}_{p['type'].upper()}_set{p.get('set_mult', 1.0):.2f}"
                elif 'max_mult' in p:
                    # If we used a max_mult parameter
                    part = f"{p['gene']}_{p['type'].upper()}_max{p.get('max_mult', 2.0):.2f}"
                else:
                    # Simple case
                    part = f"{p['gene']}_{p['type'].upper()}"
            else:
                # Knockdown case
                part = f"{p['gene']}_{p['type'].upper()}" 
            perturbation_parts.append(part)
        
        perturbation_str = '_'.join(perturbation_parts)
        
        # Build parameter string for KD/OE (if applicable)
        param_str = ''
        if beta_a is not None and beta_b is not None:
            # This works for both KD and OE since both use beta distribution
            param_str = f'_a_{beta_a:.2f}_b_{beta_b:.2f}'
        
        # Construct filename
        filename = f'{date_str}_{cell_line}_{perturbation_str}_steady_states_results{param_str}_{version}.csv'
        
        # Get final results and save
        results = self.get_final_results()
        filepath = os.path.join(output_dir, filename)
        results.to_csv(filepath, index=False)
        
        logging.info(f'Results saved to: {filepath}')