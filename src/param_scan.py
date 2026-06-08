"""
param_scan.py
-------------
Reusable utilities for steady-state simulation and parameter scanning of the
AP1 mechanistic model using basico/COPASI.

Typical usage in a notebook
----------------------------
    from param_scan import setup_model, run_simulations, run_param_scan
    import numpy as np

    setup_model('ap1_model_2.cps')

    # --- grid scan: many param sets × initial conditions ---
    results_df, _, failed = run_simulations(data, param_indices=[885, 886])

    # --- 1-D parameter sweep within one param set ---
    scan_df = run_param_scan(
        df=data,
        param_index=885,
        scan_param_name='(fra2_by_junfra2).beta',
        scan_values=np.logspace(1.0, 2.8, 120),
        track_monomer_dimer=True,
    )
"""

import sys
import io
import logging

import numpy as np
import pandas as pd
from tqdm import tqdm
import basico
from basico import *


# ── Constants ─────────────────────────────────────────────────────────────────

MONOMER_NAMES = ['fos', 'jun', 'fra1', 'fra2', 'jund']
DIMER_NAMES   = ['junfos', 'junfra1', 'junfra2', 'junjund', 'junjun',
                 'jundfos', 'jundfra1', 'jundfra2', 'jundjund']


# ── Model initialisation ───────────────────────────────────────────────────────

def setup_model(model_path='ap1_model_2.cps', use_newton=False, use_integration=True):
    """Load the COPASI model and configure the steady-state solver.

    Call this once at the top of your notebook before using any other function.

    Parameters
    ----------
    model_path : str
        Path to the .cps model file.
    use_newton : bool
        Whether to use Newton's method in the steady-state solver.
    use_integration : bool
        Whether to use integration in the steady-state solver.

    Returns
    -------
    model
        The loaded basico model object.
    """
    model = load_model(model_path)
    set_task_settings(
        T.STEADY_STATE,
        settings={'method': {'Use Newton': use_newton, 'Use Integration': use_integration}},
    )
    logging.info(f"Model loaded from '{model_path}' | Newton={use_newton}, Integration={use_integration}")
    return model


# ── Low-level model utilities ──────────────────────────────────────────────────

def fixed_initial_variables(species_name, species_value):
    """Set the initial concentration of a list of species.

    Primarily used to zero out dimer initial conditions before each steady-state
    run so they don't carry over from a previous call.

    Parameters
    ----------
    species_name : list[str]
    species_value : list[float]
    """
    for name, value in zip(species_name, species_value):
        set_species(name=name, initial_concentration=value, exact=True)


def change_model_parameters(par_name, par_value, par_type):
    """Set a list of model parameters to new values.

    Parameters
    ----------
    par_name : list[str]
    par_value : list[float]
    par_type : {'local', 'global'}
    """
    if par_type == 'local':
        for name, value in zip(par_name, par_value):
            set_reaction_parameters(name=name, value=value)
    elif par_type == 'global':
        for name, value in zip(par_name, par_value):
            set_parameters(name=name, initial_value=value)
    else:
        raise ValueError(f"par_type must be 'local' or 'global', got '{par_type}'")


# ── Steady-state engine ────────────────────────────────────────────────────────

def run_steadystate_wrapper(*args, **kwargs):
    """Call basico's run_steadystate while suppressing and inspecting COPASI stdout.

    Raises an exception if a DLSODA integration error is detected or if the
    underlying call itself raises.

    Returns
    -------
    int
        COPASI steady-state status code.
    """
    old_stdout = sys.stdout
    sys.stdout = new_stdout = io.StringIO()

    error_occurred = False
    try:
        status = basico.task_steadystate.run_steadystate(*args, **kwargs)
    except Exception:
        error_occurred = True
        status = None
    finally:
        output = new_stdout.getvalue()
        sys.stdout = old_stdout

    if "DLSODA" in output or error_occurred:
        raise RuntimeError("Steady-state calculation failed (DLSODA error).")

    return status


def get_steadystate(init_cond_rows, track_monomer_dimer=False):
    """Set initial conditions and compute the steady state.

    Dimer initial concentrations are always zeroed before the run so results
    are not contaminated by a previous call.

    Parameters
    ----------
    init_cond_rows : list[float]
        Initial concentrations for [fos, jun, fra1, fra2, jund].
    track_monomer_dimer : bool
        If True, also return monomer and dimer steady-state concentrations.

    Returns
    -------
    totals : np.ndarray, shape (5,)
        Steady-state total concentrations [cFOS, cJUN, FRA1, FRA2, JUND].
    monomers : np.ndarray, shape (5,)   (only if track_monomer_dimer=True)
    dimers : np.ndarray, shape (9,)     (only if track_monomer_dimer=True)
    """
    # Zero out all dimer ICs to avoid carry-over
    fixed_initial_variables(DIMER_NAMES, [0.0] * len(DIMER_NAMES))

    for name, value in zip(MONOMER_NAMES, init_cond_rows):
        set_species(name=name, initial_concentration=value, exact=True)

    status = run_steadystate_wrapper(use_initial_values=True, update_model=False)

    if status == 0:
        raise RuntimeError("Steady state not found.")
    if status == 3:
        raise RuntimeError("Steady state with negative concentrations found.")
    if status not in (1, 2):
        raise RuntimeError(f"Unexpected steady-state return code: {status}")

    ss_v = get_species()[['concentration']].reset_index()

    totals_df = ss_v[ss_v['name'].str.contains('total')]
    totals = np.round(totals_df['concentration'].values, 3)

    if not track_monomer_dimer:
        return totals

    monomers_df = (ss_v[ss_v['name'].isin(MONOMER_NAMES)]
                   .set_index('name').loc[MONOMER_NAMES].reset_index())
    monomers = np.round(monomers_df['concentration'].values, 3)

    dimers_df = (ss_v[ss_v['name'].isin(DIMER_NAMES)]
                 .set_index('name').loc[DIMER_NAMES].reset_index())
    dimers = np.round(dimers_df['concentration'].values, 3)

    return totals, monomers, dimers


# ── Grid scan: many param sets × initial conditions ───────────────────────────

def run_simulations(df, param_indices, track_monomer_dimer=False,
                    param_cols=slice(2, 17), init_cond_cols=slice(17, 22)):
    """Run steady-state simulations for a list of parameter sets.

    Each param_index in the DataFrame defines one complete set of model
    parameters.  For every param_index all associated initial conditions are
    evaluated.

    Parameters
    ----------
    df : pd.DataFrame
        Combined parameter + initial-condition DataFrame (the standard output
        of the parameter-sweep pipeline).
    param_indices : list[int]
        Which param_index values to process.
    track_monomer_dimer : bool
        If True, a second DataFrame with monomer/dimer concentrations is also
        returned.
    param_cols : slice
        Column slice that selects the model parameters inside df.
        Default slice(2, 17) matches the standard 15-parameter layout.
    init_cond_cols : slice
        Column slice that selects the initial conditions inside df.
        Default slice(17, 22) matches [fos, jun, fra1, fra2, jund].

    Returns
    -------
    results_totals_df : pd.DataFrame
    results_monomers_dimers_df : pd.DataFrame or None
    failed_param_indices : list[int]
    """
    results_totals = []
    results_monomers_dimers = [] if track_monomer_dimer else None
    failed_param_indices = []

    for param_index in tqdm(param_indices, desc="Simulating param sets"):
        param_df = df[df['param_index'] == param_index].copy()

        if param_df.empty:
            logging.warning(f"param_index {param_index} not found — skipping.")
            continue

        param_names  = param_df.columns[param_cols].tolist()
        param_values = param_df.iloc[0, param_cols].values.tolist()

        try:
            change_model_parameters(param_names, param_values, 'local')
        except Exception as exc:
            logging.error(f"param_index {param_index}: failed to set parameters — {exc}")
            failed_param_indices.append(param_index)
            continue

        for _, row in param_df.iterrows():
            init_cond_index = row['init_cond_index']
            init_cond_row   = row.iloc[init_cond_cols].values.tolist()

            try:
                if track_monomer_dimer:
                    totals, monomers, dimers = get_steadystate(init_cond_row, track_monomer_dimer=True)
                else:
                    totals = get_steadystate(init_cond_row, track_monomer_dimer=False)
                    monomers = dimers = None

            except Exception as exc:
                logging.error(f"param_index {param_index}, IC {init_cond_index}: {exc}")
                failed_param_indices.append(param_index)
                totals   = (np.nan,) * 5
                monomers = (np.nan,) * 5  if track_monomer_dimer else None
                dimers   = (np.nan,) * 9  if track_monomer_dimer else None

            results_totals.append({
                'param_index':    param_index,
                'init_cond_index': init_cond_index,
                'cFOS': totals[0], 'cJUN': totals[1],
                'FRA1': totals[2], 'FRA2': totals[3], 'JUND': totals[4],
            })

            if track_monomer_dimer and monomers is not None and dimers is not None:
                results_monomers_dimers.append({
                    'param_index':    param_index,
                    'init_cond_index': init_cond_index,
                    **{f'{n}_monomer': v for n, v in zip(MONOMER_NAMES, monomers)},
                    **{n: v for n, v in zip(DIMER_NAMES, dimers)},
                })

    totals_df = pd.DataFrame(results_totals)

    if track_monomer_dimer:
        md_df = pd.DataFrame(results_monomers_dimers)
        return totals_df, md_df, failed_param_indices

    return totals_df, None, failed_param_indices


# ── 1-D parameter sweep within a single param set ─────────────────────────────

def run_param_scan(df, param_index, scan_param_name, scan_values,
                   scan_param_type='local', track_monomer_dimer=False,
                   param_cols=slice(2, 17), init_cond_cols=slice(17, 22)):
    """Sweep one parameter over a range and collect steady states.

    For each value in scan_values the function:
      1. Restores the full base parameter set for param_index.
      2. Overrides scan_param_name with the current scan value.
      3. Runs steady state for every initial condition associated with
         param_index.

    Running across all initial conditions at every scan point makes it
    possible to detect bistability: two initial conditions that converge to
    different steady states at the same scan value indicate a bistable regime.

    Parameters
    ----------
    df : pd.DataFrame
        Combined parameter + initial-condition DataFrame.
    param_index : int
        Which base parameter set to use.
    scan_param_name : str
        Name of the parameter to sweep, e.g. '(fra2_by_junfra2).beta'.
        Can be any local reaction parameter or global parameter.
    scan_values : array-like
        Ordered values to sweep over (e.g. np.logspace(1, 2.8, 120)).
    scan_param_type : {'local', 'global'}
        Whether scan_param_name is a reaction ('local') or global parameter.
    track_monomer_dimer : bool
        If True, individual monomer and dimer columns are included in the
        output DataFrame.
    param_cols : slice
        Column slice for base parameters in df.
    init_cond_cols : slice
        Column slice for initial conditions in df.

    Returns
    -------
    pd.DataFrame
        One row per (scan_value × init_cond_index).  Always contains:
          scan_param_name, init_cond_index, cFOS, cJUN, FRA1, FRA2, JUND
        Plus monomer/dimer columns when track_monomer_dimer=True.
    """
    param_df = df[df['param_index'] == param_index].copy()

    if param_df.empty:
        raise ValueError(f"param_index {param_index} not found in df.")

    base_param_names  = param_df.columns[param_cols].tolist()
    base_param_values = param_df.iloc[0, param_cols].values.tolist()

    init_cond_df = param_df[['init_cond_index']].copy()
    init_cond_df[MONOMER_NAMES] = param_df.iloc[:, init_cond_cols].values

    records = []
    scan_values = list(scan_values)

    for i, scan_val in enumerate(scan_values):
        # Restore base parameters then override the scan parameter
        change_model_parameters(base_param_names, base_param_values, 'local')
        if scan_param_type == 'local':
            set_reaction_parameters(name=scan_param_name, value=scan_val)
        elif scan_param_type == 'global':
            set_parameters(name=scan_param_name, initial_value=scan_val)
        else:
            raise ValueError(f"scan_param_type must be 'local' or 'global', got '{scan_param_type}'")

        for _, row in init_cond_df.iterrows():
            init_vals = row[MONOMER_NAMES].values.tolist()

            try:
                if track_monomer_dimer:
                    totals, monomers, dimers = get_steadystate(init_vals, track_monomer_dimer=True)
                else:
                    totals   = get_steadystate(init_vals, track_monomer_dimer=False)
                    monomers = dimers = None
            except Exception as exc:
                logging.warning(f"  scan_val={scan_val:.4g}, IC {row['init_cond_index']}: {exc}")
                totals   = (np.nan,) * 5
                monomers = (np.nan,) * 5  if track_monomer_dimer else None
                dimers   = (np.nan,) * 9  if track_monomer_dimer else None

            record = {
                scan_param_name:   scan_val,
                'init_cond_index': row['init_cond_index'],
                'cFOS': totals[0], 'cJUN': totals[1],
                'FRA1': totals[2], 'FRA2': totals[3], 'JUND': totals[4],
            }

            if track_monomer_dimer and monomers is not None and dimers is not None:
                record.update({f'{n}_monomer': v for n, v in zip(MONOMER_NAMES, monomers)})
                record.update({n: v for n, v in zip(DIMER_NAMES, dimers)})

            records.append(record)

        print(f"  [{i+1}/{len(scan_values)}]  {scan_param_name} = {scan_val:.4g}")

    return pd.DataFrame(records)
