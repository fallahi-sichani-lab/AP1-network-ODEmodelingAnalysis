# AP1-network-ODEmodelingAnalysis

A mechanistic ODE model of the AP-1 network capturing dimerization-controlled,
co-regulated, competitive interactions in single melanoma cells, followed by
model calibration to single-cell data, in silico perturbation, and experimental
validation by single-nucleus multiome (RNA + ATAC).

**Looking for the script behind a specific figure? See [FIGURES.md](FIGURES.md).**

Note: **Figures.md is in progress and will be updated**

## Repository structure

```
.
├── analysis/                        # Notebooks and R scripts, grouped by pipeline stage
│   ├── 01_experimental_data/        # 4i single-cell measurements
│   ├── 02_model_simulation/         # LHS sweep processing, uncalibrated model
│   ├── 03_calibration/              # Calibration to experimental data
│   ├── 04_calibrated_model_analysis/# PLSDA, UMAP, heterogeneity
│   └── 05_jund_kd_perturbation/     # JUND KD: in silico + multiome validation
├── src/                             # Python modules, R helpers, COPASI model, cluster scripts
├── data/                            # Small reference files committed to the repo
├── FIGURES.md                       # Figure → script index
└── environment.yml                  # Conda environment
```

Folders follow **run order**, not figure number. A single script often feeds
several figures (`07` feeds Figures 3, 4, and 6), and figure numbers change
during revision — so the figure mapping lives in [FIGURES.md](FIGURES.md) rather
than in directory names.

## This repository is code only

**No datasets are distributed here.** The repo documents and preserves the
analysis itself — what was computed, in what order, to produce which figure.
The 4i single-cell measurements, the simulation output, and the multiome data
are not included.

Input paths in the scripts point at the environment the analysis was originally
run in, so reusing any of this means supplying the data and adjusting those
paths. What the code provides is the method, the parameter choices, and the
exact sequence of steps.

Importing this repo's own Python and R helpers works from any directory — see
below.

### Importing `src/` modules

Notebooks that use `plsda_module`, `param_scan`, or `COLO858_pertrubation_analysis`
begin with a bootstrap cell that locates the repo root and adds `src/` to
`sys.path`. It walks up from the current working directory looking for a folder
containing both `src/` and `analysis/`.

If you run a notebook from outside this checkout — e.g. from wherever your data
lives — the walk-up won't find the repo. Point it there explicitly **before**
running the bootstrap cell:

```python
import os
os.environ["AP1_REPO_ROOT"] = "/path/to/AP1-network-ODEmodelingAnalysis"
```

`12_multiome_JUND_KD_analysis.Rmd` uses the same convention in R
(`Sys.setenv(AP1_REPO_ROOT = "...")`) to `source()` its propeller helpers.

## Analysis pipeline

Run in numerical order. Numbers are global across folders, so `06b` sits in the
perturbation stage even though it sorts near `06`.

### Stage 1 — Experimental data (`analysis/01_experimental_data/`)

`01_process_singlecell_experimental_data.ipynb`

- Processes single-cell AP-1 protein measurements from 4i imaging
- UMAP, PCA, violin plots, AP-1 state assignment
- Outputs processed experimental data used for calibration

`01b_threshold_sensitivity_analysis.ipynb`

- Tests how robust AP-1 state calls are to the protein-positivity thresholds
- Sweeps GMM-derived and anchor-based thresholds across all 19 cell lines,
scoring state stability
- Has a `SMOKE_TEST` flag: `True` runs a fast 3-value grid, `False` the full sweep

`plot_clustermap.R` (standalone — reads raw data directly)

- Hierarchical clustering of 5 AP-1 proteins + 2 differentiation markers across
cell lines



### Stage 2 — Model simulation (`analysis/02_model_simulation/`)

`02_process_LHS_simulations.ipynb`

- Processes the Latin Hypercube sweep (20,000 parameter sets × 200 initial
conditions), removing failed simulations
- Produces no figure; feeds every downstream stage

`03_analyze_uncalibrated_model.ipynb`

- Characterizes AP-1 model dynamics across parameter space before calibration



### Stage 3 — Calibration (`analysis/03_calibration/`)

`04_calibrate_model_to_experiments.ipynb`

- Calibrates ODE parameters to experimental single-cell data
- Inputs: outputs of `01` and `02`; outputs calibrated parameter sets

`04b_plot_upset_calibration.R`

- Upset plot of shared/unique calibrated parameter sets across the 19 cell lines



### Stage 4 — Calibrated model analysis (`analysis/04_calibrated_model_analysis/`)

`05_UMAP_calibrated_cells.ipynb`

- UMAP comparing calibrated simulations against experimental data

`06_PLSDA_cellline_discrimination.ipynb`

- Molecular parameters discriminating cell lines by AP-1 transcriptional state
- Uses `src/plsda_module.py`

`07_MAPK_AP1_comparison_analysis.ipynb`

- MAPK vs AP-1 protein comparisons (between and within cells)
- Violin plots of AP-1 parameters from the calibrated model
- AP-1 expression under ERK inhibition

`08_PLSDA_heterogeneity_analysis.ipynb`

- PLSDA of molecular parameters separating AP-1 states within and across cell lines
- Uses `src/plsda_module.py`



### Stage 5 — JUND knockdown (`analysis/05_jund_kd_perturbation/`)

`06b_COLO858_insilico_perturbations.ipynb`

- Generates in silico JUND knockdown and combination perturbations from the
calibrated COLO858 parameter sets
- Uses `src/COLO858_pertrubation_analysis.py`
- Produces no figure; its output feeds `09`, `10`, and `11`

`09_COLO858_JUND_KD_analysis.ipynb`

- Pre/post perturbation analysis, dimer tracking, dose response
- Uses `src/param_scan.py`

`10_COLO858_FRA2_PLSDA_analysis.ipynb`

- Molecular parameters driving elevated FRA2 after JUND knockdown
- Inputs: output of `09`; uses `src/plsda_module.py`

`11_COLO858_plot_JUND_KD_perturbations.ipynb`

- Plots JUND knockdown and combined perturbation effects

`12_multiome_JUND_KD_analysis.Rmd`

- Experimental validation: 10x single-nucleus Multiome (RNA + ATAC) on
NTC_rep1, NTC_rep2, and JUND_KD
- QC and doublet filtering, WNN joint RNA+ATAC clustering, Tsoi signature
scoring, differential markers, and cluster-proportion testing
- Uses `src/propeller_JUND_v2.R` and `data/Tsoi_et_al_gene_list.csv`
- Independent of the ODE model — reads the multiome data directly and reuses
per-sample checkpoints from the earlier 4-sample pipeline



## Source code



### Analysis modules


| File                                   | Purpose                                                                                                                    | Used by          |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| `src/plsda_module.py`                  | PLSDA implementation: cross-validation, class balancing, ROC                                                               | `06`, `08`, `10` |
| `src/COLO858_pertrubation_analysis.py` | Perturbation simulation pipeline incl. dimer tracking                                                                      | `06b`            |
| `src/param_scan.py`                    | Steady-state simulation and 1-D parameter sweeps via basico/COPASI                                                         | `09`             |
| `src/propeller_JUND_v2.R`              | Cluster-proportion testing built on `speckle::propeller`, for the case where the KD condition has no biological replicates | `12`             |




### ODE model and simulation infrastructure


| File                           | Purpose                                                            |
| ------------------------------ | ------------------------------------------------------------------ |
| `src/ap1_model_2_mod.cps`      | COPASI model of the AP-1 network                                   |
| `src/LHS_params_init_conds.py` | Generates 20,000 parameter sets and 210 initial conditions         |
| `src/run_simulation.py`        | Runs the COPASI sweep across parameter sets and initial conditions |
| `src/ap1.slurm`                | Slurm batch script for the HPC run                                 |




## Data

`data/Tsoi_et_al_gene_list.csv` — melanoma differentiation-state signatures
(Tsoi et al.), used by `12_multiome_JUND_KD_analysis.Rmd` for cell-state scoring.

## Dependencies

Conda environment:

```bash
conda env create -f environment.yml   # or environment-minimal.yml
conda activate ap1_proj
```

`environment.yml` pins exact builds from the working environment;
`environment-minimal.yml` lists unpinned core packages for lighter installs.
Both create an environment named `ap1_proj`.

**Python** — numpy, pandas, matplotlib, seaborn, scikit-learn, umap-learn,
basico (COPASI API), tqdm

**R** — tidyverse, UpSetR, ComplexHeatmap, Seurat, Signac, UCell,
EnsDb.Hsapiens.v86, GenomicRanges, GenomeInfoDb, Rsamtools,
SingleCellExperiment, speckle, patchwork