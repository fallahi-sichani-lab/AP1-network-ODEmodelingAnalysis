# AP1-network-ODEmodelingAnalysis

A mechanistic ODE model of the AP-1 network capturing dimerization-controlled, co-regulated, competitive interactions in single melanoma cells, followed by model calibration to single-cell data and follow-up single-cell analysis.

## Repository Structure

```
.
├── analysis/           # Jupyter notebooks for all analyses (run in order)
├── src/               # Python modules for analysis
└── README.md
```

## Analysis Pipeline

The notebooks should be run in numerical order. Each notebook corresponds to specific figures in the manuscript.

### Stage 1: Experimental Data Processing

**`01_process_singlecell_experimental_data.ipynb`**
- **Purpose**: Processes single-cell AP-1 protein measurements from 4i imaging
- **Analyses**: UMAP dimensionality reduction, PCA, violin plots
- **Outputs**: Processed experimental data for model calibration
- **Manuscript figures**: Figure 1, Supplementary Figure S1

### Stage 2: Model Simulations

**`02_process_LHS_simulations.ipynb`**
- **Purpose**: Processes large-scale parameter space exploration (20,000 parameter sets × 200 initial conditions)
- **Analyses**: Removes failed simulations, prepares data for downstream analysis
- **Outputs**: Cleaned simulation results
- **Manuscript figures**: None (data preparation)

**`03_analyze_uncalibrated_model.ipynb`**
- **Purpose**: Initial exploration of AP-1 ODE model dynamics before calibration
- **Analyses**: Characterizes model behavior across parameter space
- **Outputs**: Uncalibrated model analysis results
- **Manuscript figures**: Figure 2 (all panels)

### Stage 3: Model Calibration

**`04_calibrate_model_to_experiments.ipynb`**
- **Purpose**: Calibrates ODE model parameters to experimental single-cell data
- **Inputs**: Outputs from notebooks 01 and 02
- **Analyses**: Parameter calibration algorithm, validation
- **Outputs**: Calibrated parameter sets for downstream analysis
- **Manuscript figures**: Figure 3A (calibration logic)

### Stage 4: Calibrated Model Analysis

**`05_UMAP_calibrated_cells.ipynb`**
- **Purpose**: UMAP analysis comparing calibrated simulations to experimental data
- **Inputs**: Outputs from notebooks 04 and 01
- **Analyses**: Dimensionality reduction, validation of calibrated model
- **Manuscript figures**: Figure 3C

**`06_PLSDA_cellline_discrimination.ipynb`**
- **Purpose**: Identifies molecular parameters discriminating cell lines by AP-1 transcriptional state
- **Analyses**: Partial Least Squares Discriminant Analysis (PLSDA)
- **Dependencies**: `src/plsda_module.py`
- **Manuscript figures**: Figure 3 (most panels)

**`07_MAPK_AP1_comparison_analysis.ipynb`**
- **Purpose**: Compares MAPK and AP-1 protein levels between and within cells
- **Analyses**:
  - MAPK protein comparisons (between/within cells)
  - Violin plots for AP-1 protein parameters from calibrated ODE model
  - AP-1 expression under ERK inhibition
- **Manuscript figures**: Figures 3, 4, 6

**`08_PLSDA_heterogeneity_analysis.ipynb`**
- **Purpose**: PLSDA analysis of molecular parameters separating AP-1 states within and across cell lines
- **Analyses**: Heterogeneity analysis using PLSDA
- **Dependencies**: `src/plsda_module.py`
- **Manuscript figures**: Figures 4, 5

### Stage 5: Perturbation Analysis (JUND Knockdown)

**`09_COLO858_JUND_KD_analysis.ipynb`**
- **Purpose**: Analyzes effects of JUND knockdown in COLO858 melanoma cells
- **Analyses**: Pre/post perturbation analysis
- **Manuscript figures**: Figure 7 (partial)

**`10_COLO858_FRA2_PLSDA_analysis.ipynb`**
- **Purpose**: Identifies molecular parameters causing elevated FRA2 expression after JUND knockdown
- **Inputs**: Output from notebook 09
- **Analyses**: PLSDA to identify mechanistic drivers
- **Dependencies**: `src/plsda_module.py`
- **Manuscript figures**: Figure 7 (partial)

**`11_COLO858_plot_JUND_KD_perturbations.ipynb`**
- **Purpose**: Visualizes JUND knockdown and combined perturbation effects
- **Analyses**: Plotting analysis for perturbation experiments
- **Manuscript figures**: Figure 7 (one panel)

## Source Code Modules

**`src/plsda_module.py`**
- Custom implementation of Partial Least Squares Discriminant Analysis (PLSDA)
- Used by notebooks: 06, 08, 10
- Features: Cross-validation, class balancing, ROC analysis

## Manuscript Figure Mapping

| Figure | Notebook(s) | Description |
|--------|-------------|-------------|
| Figure 1 | `01_process_singlecell_experimental_data.ipynb` | Single-cell experimental data analysis |
| Figure 2 | `03_analyze_uncalibrated_model.ipynb` | Uncalibrated model dynamics |
| Figure 3A | `04_calibrate_model_to_experiments.ipynb` | Model calibration logic |
| Figure 3C | `05_UMAP_calibrated_cells.ipynb` | UMAP validation of calibration |
| Figure 3 (other) | `06_PLSDA_cellline_discrimination.ipynb`, `07_MAPK_AP1_comparison_analysis.ipynb` | Cell line discrimination, MAPK/AP-1 comparisons |
| Figure 4 | `07_MAPK_AP1_comparison_analysis.ipynb`, `08_PLSDA_heterogeneity_analysis.ipynb` | Protein comparisons, heterogeneity analysis |
| Figure 5 | `08_PLSDA_heterogeneity_analysis.ipynb` | AP-1 state heterogeneity |
| Figure 6 | `07_MAPK_AP1_comparison_analysis.ipynb` | ERK inhibition analysis |
| Figure 7 | `09_COLO858_JUND_KD_analysis.ipynb`, `10_COLO858_FRA2_PLSDA_analysis.ipynb`, `11_COLO858_plot_JUND_KD_perturbations.ipynb` | JUND knockdown perturbation analysis |
| Figure S1 | `01_process_singlecell_experimental_data.ipynb` | Supplementary experimental data |
