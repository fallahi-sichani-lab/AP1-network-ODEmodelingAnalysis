# Figure Index

Maps each manuscript figure to the script that generates it. This file is the
place to look when you need "which script made Figure 5?" — the `analysis/`
folders are organized by **pipeline stage** (run order), not by figure, because
several scripts feed more than one figure and figure numbers move during
revision.

**When figure numbers change, update this file only.** Nothing else in the repo
should encode a figure number.

Paths below are relative to `analysis/`.

---

## Main figures

| Figure | Script | Stage folder |
|--------|--------|--------------|
| 1A | `plot_clustermap.R` | `01_experimental_data/` |
| 1 (other panels) | `01_process_singlecell_experimental_data.ipynb` | `01_experimental_data/` |
| 2 | `03_analyze_uncalibrated_model.ipynb` | `02_model_simulation/` |
| 3A | `04_calibrate_model_to_experiments.ipynb` | `03_calibration/` |
| 3B | `04b_plot_upset_calibration.R` | `03_calibration/` |
| 3C | `05_UMAP_calibrated_cells.ipynb` | `04_calibrated_model_analysis/` |
| 3 (other panels) | `06_PLSDA_cellline_discrimination.ipynb`, `07_MAPK_AP1_comparison_analysis.ipynb` | `04_calibrated_model_analysis/` |
| 4 | `07_MAPK_AP1_comparison_analysis.ipynb`, `08_PLSDA_heterogeneity_analysis.ipynb` | `04_calibrated_model_analysis/` |
| 5 | `08_PLSDA_heterogeneity_analysis.ipynb` | `04_calibrated_model_analysis/` |
| 6 | `07_MAPK_AP1_comparison_analysis.ipynb` | `04_calibrated_model_analysis/` |
| 7 | `09_COLO858_JUND_KD_analysis.ipynb`, `10_COLO858_FRA2_PLSDA_analysis.ipynb`, `11_COLO858_plot_JUND_KD_perturbations.ipynb`, `12_multiome_JUND_KD_analysis.Rmd` | `05_jund_kd_perturbation/` |

## Supplementary figures

| Figure | Script | Stage folder |
|--------|--------|--------------|
| S1 | `01_process_singlecell_experimental_data.ipynb` | `01_experimental_data/` |
| S1C | `01b_threshold_sensitivity_analysis.ipynb` | `01_experimental_data/` |
| Multiome QC (number TBD) | `12_multiome_JUND_KD_analysis.Rmd` | `05_jund_kd_perturbation/` |

> **Check S1C for a collision.** `01_process_singlecell_experimental_data.ipynb`
> previously wrote a file named `Figure1SC_umap_protein_subplot.pdf`, which also
> reads as "Figure S1C". If `01b` is S1C, then that panel from `01` belongs to a
> different supplementary number. Worth resolving during the figure-number review
> below.

## Scripts that produce no figure

| Script | Role |
|--------|------|
| `02_process_LHS_simulations.ipynb` | Cleans raw LHS simulation output; feeds stages 3–5 |
| `06b_COLO858_insilico_perturbations.ipynb` | Generates the perturbation simulations consumed by `09`, `10`, `11` |
| `src/LHS_params_init_conds.py`, `src/run_simulation.py`, `src/ap1.slurm` | Generate and run the 20,000 × 200 LHS sweep on the cluster |

---

## PENDING: figure-number review

Output filenames used to carry figure numbers from **earlier versions of the
manuscript** that no longer matched the current numbering. Those numbers have
been **stripped from the filenames** so nothing in the code asserts a number that
may be wrong. The full record is below — every removal is listed so the original
association is recoverable.

**To do:** open each script, confirm which figure the panel actually belongs to,
and record it in the tables above. Do **not** put the number back into the
filename — this file is where numbers live now.

### Figure numbers removed from output filenames

| Script | Old filename | New filename |
|--------|--------------|--------------|
| `01_process_singlecell_experimental_data.ipynb` | `1B_network_heatmap.pdf` | `network_heatmap.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `1C_ap1_state_umap.pdf` | `ap1_state_umap.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `2A_protein_violin_plot.pdf` | `protein_violin_plot.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `S1B_heatmap_protein_expression.pdf` | `heatmap_protein_expression.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `Figure1SC_umap_protein_subplot.pdf` | `umap_protein_subplot.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `Fig1Supp_violin_ap1_states_all_proteins.pdf` | `violin_ap1_states_all_proteins.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `Fig2Supp_ap1_protein_density_fixed_scale.pdf` | `ap1_protein_density_fixed_scale.pdf` |
| `01_process_singlecell_experimental_data.ipynb` | `Fig2Supp_PCA_on_pop_avg_clustermap_PC1_PC2.pdf` | `PCA_on_pop_avg_clustermap_PC1_PC2.pdf` |
| `03_analyze_uncalibrated_model.ipynb` | `1F_unique_states_percentage.pdf` | `unique_states_percentage.pdf` |
| `03_analyze_uncalibrated_model.ipynb` | `Fig1Supp_time_course_simulations_FRA2_high_low.pdf` | `time_course_simulations_FRA2_high_low.pdf` |
| `05_UMAP_calibrated_cells.ipynb` | `Fig3A_Updated_calibrated_UMAP_combined_model_experimental_WM115_more_samples.pdf` | `calibrated_UMAP_combined_model_experimental_WM115_more_samples.pdf` |
| `07_MAPK_AP1_comparison_analysis.ipynb` | `3L_model_comparison_violin_plots_WM115_LOXIMVI.pdf` | `model_comparison_violin_plots_WM115_LOXIMVI.pdf` |
| `07_MAPK_AP1_comparison_analysis.ipynb` | `3T_pJNK_pP38_pJNKxpP38_comparison.pdf` | `pJNK_pP38_pJNKxpP38_comparison.pdf` |
| `07_MAPK_AP1_comparison_analysis.ipynb` | `4H_FRA1_pERK_comparison_WM902B.pdf` | `FRA1_pERK_comparison_WM902B.pdf` |
| `07_MAPK_AP1_comparison_analysis.ipynb` | `Fig6D_violin_JUND_drug_treatments.pdf` | `violin_JUND_drug_treatments.pdf` |
| `08_PLSDA_heterogeneity_analysis.ipynb` | `Fig5E_multistable_LOXIMVI_analysis_alpha_beta_fra2.pdf` | `multistable_LOXIMVI_analysis_alpha_beta_fra2.pdf` |
| `08_PLSDA_heterogeneity_analysis.ipynb` | `Fig5Supp_bistable_25_parmas_vip_scores_violin.pdf` | `bistable_25_parmas_vip_scores_violin.pdf` |
| `11_COLO858_plot_JUND_KD_perturbations.ipynb` | `6Q_FRA2_distribution_across_peturbations.pdf` | `FRA2_distribution_across_peturbations.pdf` |

Some of these may well have been correct (`Fig5E_` sits in a script that does
feed Figure 5). They were stripped anyway, because a filename that is right
today silently becomes wrong at the next renumbering.

### Figure numbers still present in comments and section headings

These are **prose inside the scripts**, not filenames, so they were left alone.
They also predate the current numbering and need the same review.

| Script | Reference |
|--------|-----------|
| `01_process_singlecell_experimental_data.ipynb` | `#### Fig 1B (UMAP)`, `#### Figure S1A Violin plot with thresholds`, `#### Figure S1B` |
| `03_analyze_uncalibrated_model.ipynb` | `#### Figure S2`, `#### Figure 2F`, `#### Figure 2G`, `#### Figure 2H` |
| `05_UMAP_calibrated_cells.ipynb` | `## Figure 3 A: UMAP on calibrated parameters and experimental data` |
| `07_MAPK_AP1_comparison_analysis.ipynb` | `### Figure 3,4 Experimental data`, `### Figure 6 Analysis of Vemurafenib and Trametinib data` |
| `08_PLSDA_heterogeneity_analysis.ipynb` | `### Figure 5 (B-C)`, `#### Figure 5C`, `### Figure 4 Heterogeneity analysis` |
| `11_COLO858_plot_JUND_KD_perturbations.ipynb` | `#### Figure 7 E Model perturbation`, `# Figure 2: Density plot of log-transformed FRA2` |
| `12_multiome_JUND_KD_analysis.Rmd` | `### Figure 7 plots`, `## Figure W1/W3/W4` (see note below) |

The `Figure W1 / W3 / W4` labels in the multiome Rmd — and the matching
`FigW1a_`, `FigW1b_`, `FigW3_` filenames — were **left unchanged**. They are
internal working labels for that analysis, not claims about manuscript numbering,
so they are not stale in the same way. Say the word if you'd rather they go too.

---

## Output files by script

Figure files are written to whatever output directory you configure — see the
README. Nothing is written into this repo.

### `01_experimental_data/`

**`01_process_singlecell_experimental_data.ipynb`**
- `network_heatmap.pdf`
- `protein_violin_plot.pdf`
- `AP1_proteins_clustermap.pdf`
- `Differentiation_markers_heatmap.pdf`
- `Figure_umap_3pc.pdf`
- `umap_protein_subplot.pdf`, `umap_protein_subplot_{cell_line}.pdf`
- `ap1_state_umap.pdf`
- `heatmap_protein_expression.pdf`
- `violin_ap1_states_all_proteins.pdf`
- `ap1_protein_density_fixed_scale.pdf`
- `PCA_on_pop_avg_clustermap_PC1_PC2.pdf`

**`01b_threshold_sensitivity_analysis.ipynb`**
- `per_cell_line_distributions_examples.pdf`
- `balanced_gmm_derivation_all_celllines.pdf`
- `protein_specific_subset_gmm_derivation_with_current_thresholds.pdf`
- `protein_specific_anchor_gmm_thresholds_with_sweep_windows.pdf`
- `state_stability_*_ranked_balanced_gmm_all19cellines.pdf`
- `state_stability_*_ranked_heatmap.pdf`

**`plot_clustermap.R`**
- `AP1_split_heatmap.pdf`, `AP1_split_heatmap_v2.pdf`

### `02_model_simulation/`

**`03_analyze_uncalibrated_model.ipynb`**
- `time_course_simulations_FRA2_high_low.pdf`
- `unique_states_percentage.pdf`
- `{par_name}_steadystate_distribution.pdf`

### `03_calibration/`

**`04_calibrate_model_to_experiments.ipynb`**
- `overlap_model_exp.pdf`
- `AP1_protein_distribution_gridthresholds.pdf`

**`04b_plot_upset_calibration.R`**
- `test_upset_plot_with_calibrated_parameters.pdf`

### `04_calibrated_model_analysis/`

**`05_UMAP_calibrated_cells.ipynb`**
- `calibrated_UMAP_combined_model_experimental_WM115_more_samples.pdf`

**`06_PLSDA_cellline_discrimination.ipynb`**
- `{cell_1}_{cell_2}_boxplot.png` (one per cell-line pair)

**`07_MAPK_AP1_comparison_analysis.ipynb`**
- `model_comparison_violin_plots_WM115_LOXIMVI.pdf`
- `pJNK_pP38_pJNKxpP38_comparison.pdf`
- `FRA1_pERK_comparison_WM902B.pdf`
- `violin_JUND_drug_treatments.pdf`
- `fra2_cjun_high_fraction_vs_mitf_shift_au_percent_mean_first.pdf`
- `replicate_consistency_JUND.png`
- `{safe_cellline}_{x_column}_vs_{y_column}.pdf`

**`08_PLSDA_heterogeneity_analysis.ipynb`**
- `multistable_LOXIMVI_analysis_alpha_beta_fra2.pdf`
- `bistable_25_parmas_vip_scores_violin.pdf`
- `monostable_{cell}_distribution.pdf`, `monostable_{cell}_3d_scatter_FRA2.pdf`
- `multistable_{cell}_2d_scatter_fra2.pdf`, `multistable_{cell}_3d_scatter_fra2.pdf`
- `multistable_{cell}_distribution_with_fra2_ratio.pdf`
- `multistable_{cell}_fra2_ratio_distribution.pdf`

### `05_jund_kd_perturbation/`

**`09_COLO858_JUND_KD_analysis.ipynb`**
- `protein_comparison_{perturb_type}.pdf`
- `COLO858_pre_post_JUND_KD_protein_comparisons_stratified_60_efficiency.png`
- `COLO858_JUNDKD_FRA2_dimer_scan_{scan_param}_param_index_{param_idx}_correct.pdf`
- `COLO858_JUNDKD_thresh_10_histograms.pdf`

**`11_COLO858_plot_JUND_KD_perturbations.ipynb`**
- `FRA2_distribution_across_peturbations.pdf`
- `high_fra2_percentage_barplot_COLO858_JUNDKD_model.pdf`
- `high_fra2_percentage_denisty_log10_COLO858_JUNDKD_model.pdf`

**`12_multiome_JUND_KD_analysis.Rmd`** — manuscript panels:
- `WNN_cluster_tsoi4_heatmap_filtered_final.pdf`
- `tsoi_marker_genes_complexheatmap.pdf`
- `JUND_WNN_cluster_frequency_with_propeller_fdr.pdf`
- `FigW1b_WNN_UMAP_trio_percell_labels.pdf`
- `WNN_UMAP_tsoi4_UCell_continuous.pdf`
- `WNN_UMAP_MITF_SOX10_expression.pdf`
- `FigW3_cluster_composition.pdf`
- `top_RNA_markers_dotplot_specificity.pdf`

**`12_multiome_JUND_KD_analysis.Rmd`** — QC / diagnostics:
- `QC_pre_filter_violins.pdf`, `QC_post_filter_violins.pdf`, `QC_atac_pre_filter_violins.pdf`
- `QC_doublet_scatter.pdf`, `QC_fragment_histogram.pdf`, `QC_gene_detection.pdf`
- `QC_density_TSS_vs_nCount_ATAC.pdf`
- `PCA_LSI_elbow_plots.pdf`, `WNN_resolution_sweep.pdf`
