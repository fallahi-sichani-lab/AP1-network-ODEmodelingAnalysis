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