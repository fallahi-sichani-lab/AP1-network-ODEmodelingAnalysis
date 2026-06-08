# =============================================================================
# propeller_jund_functions.R
#
# Functions for proportion analysis when one condition has no biological
# replicates. Built on speckle::propeller (Phipson et al. 2022, Bioinformatics).
#
# Design:
#   - Propeller on REAL samples is the single, principled test.
#   - An effect-size reconciliation layer reports the per-cluster percentage
#     shift (KD - mean NTC) and flags whether it exceeds the observed
#     difference between the two NTC replicates. This is interpretive support,
#     not a second statistical test.
#
# USAGE:
#   source("R/propeller_jund_functions.R")
#   result <- run_propeller_analysis(
#     seurat_obj      = merged,
#     rna_cluster_col = "seurat_clusters",
#     sample_col      = "orig.ident",
#     kd_sample       = "JUND_KD",
#     ntc_samples     = c("NTC_rep1", "NTC_rep2")
#   )
#   result$master       # primary table for reporting
#   result$propeller    # propeller on real samples
#   result$stripchart   # ggplot object for visual sanity check
# =============================================================================

suppressPackageStartupMessages({
  library(speckle)
  library(tidyverse)
  library(tibble)
  library(ggplot2)
})

# -----------------------------------------------------------------------------
# Internal: build meta_df with sample, cluster, condition columns propeller
# expects.
# -----------------------------------------------------------------------------
.build_meta <- function(
    seurat_obj,
    rna_cluster_col,
    sample_col,
    ntc_samples,
    kd_sample
) {
  sample_order <- c(ntc_samples, kd_sample)
  stopifnot(rna_cluster_col %in% colnames(seurat_obj@meta.data))
  stopifnot(sample_col %in% colnames(seurat_obj@meta.data))
  
  seurat_obj@meta.data %>%
    as.data.frame() %>%
    dplyr::filter(.data[[sample_col]] %in% sample_order) %>%
    mutate(
      cluster = as.character(.data[[rna_cluster_col]]),
      sample = factor(.data[[sample_col]], levels = sample_order),
      condition = factor(
        ifelse(.data[[sample_col]] == kd_sample, "KD", "NTC"),
        levels = c("NTC", "KD")
      )
    )
}

# -----------------------------------------------------------------------------
# Internal: input sanity tests
# -----------------------------------------------------------------------------
.run_input_tests <- function(meta_df, ntc_samples, kd_sample, verbose = TRUE) {
  if (verbose) {
    cat("\n=== TEST 1: design table ===\n")
  }
  design_tbl <- meta_df %>% distinct(sample, condition) %>% arrange(sample)
  if (verbose) {
    print(design_tbl)
  }
  stopifnot(nrow(design_tbl) == length(ntc_samples) + 1)
  stopifnot(sum(design_tbl$condition == "NTC") == length(ntc_samples))
  stopifnot(sum(design_tbl$condition == "KD") == 1)
  if (verbose) {
    cat("PASS\n")
  }
  
  if (verbose) {
    cat("\n=== TEST 2: cells per sample ===\n")
  }
  cells_per_sample <- table(meta_df$sample)
  if (verbose) {
    print(cells_per_sample)
  }
  stopifnot(all(cells_per_sample > 100))
  if (verbose) {
    cat("PASS\n")
  }
  
  if (verbose) {
    cat("\n=== TEST 3: cluster x sample coverage ===\n")
  }
  cs_tbl <- table(meta_df$cluster, meta_df$sample)
  if (verbose) {
    print(cs_tbl)
  }
  missing <- rownames(cs_tbl)[rowSums(cs_tbl > 0) != ncol(cs_tbl)]
  if (length(missing) > 0) {
    warning(sprintf(
      "Clusters absent from at least one sample: %s",
      paste(missing, collapse = ", ")
    ))
  } else if (verbose) {
    cat("PASS\n")
  }
  
  invisible(TRUE)
}

# -----------------------------------------------------------------------------
# Internal: per-cluster stripchart sanity plot
# -----------------------------------------------------------------------------
.make_stripchart <- function(meta_df, sample_colors = NULL) {
  prop_long <- meta_df %>%
    dplyr::count(sample, cluster, name = "n") %>%
    group_by(sample) %>%
    mutate(prop = n / sum(n)) %>%
    ungroup() %>%
    mutate(condition = ifelse(grepl("KD", as.character(sample)), "KD", "NTC"))
  
  p <- ggplot(prop_long, aes(x = condition, y = prop, color = sample)) +
    geom_jitter(width = 0.15, size = 3) +
    facet_wrap(~cluster, scales = "free_y") +
    labs(
      x = NULL,
      y = "Proportion of sample",
      title = "Cell proportions per cluster (sanity check)"
    ) +
    theme_classic(base_size = 12) +
    theme(legend.position = "bottom")
  
  if (!is.null(sample_colors)) {
    p <- p + scale_color_manual(values = sample_colors)
  }
  p
}

# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------
run_propeller_analysis <- function(
    seurat_obj,
    rna_cluster_col,
    sample_col = "orig.ident",
    kd_sample = "JUND_KD",
    ntc_samples = c("NTC_rep1", "NTC_rep2"),
    sample_colors = NULL,
    verbose = TRUE
) {
  # ---- 1. Build inputs and run sanity tests ----
  meta_df <- .build_meta(
    seurat_obj,
    rna_cluster_col,
    sample_col,
    ntc_samples,
    kd_sample
  )
  .run_input_tests(meta_df, ntc_samples, kd_sample, verbose = verbose)
  
  # ---- 2. PRIMARY ANALYSIS: propeller on real samples ----
  if (verbose) {
    cat("\n=== PRIMARY: propeller on real samples ===\n")
  }
  prop_result <- propeller(
    clusters = meta_df$cluster,
    sample = as.character(meta_df$sample),
    group = as.character(meta_df$condition),
    transform = "logit",
    robust = TRUE
  ) %>%
    as.data.frame() %>%
    rownames_to_column("cluster") %>%
    arrange(cluster)
  
  stopifnot("P.Value" %in% colnames(prop_result))
  stopifnot(all(prop_result$P.Value >= 0 & prop_result$P.Value <= 1))
  if (verbose) {
    print(prop_result)
  }
  
  # ---- 3. Effect-size reconciliation (interpretive support, not a test) ----
  cluster_counts <- meta_df %>%
    dplyr::count(sample, cluster, name = "n_cells") %>%
    group_by(sample) %>%
    mutate(pct = 100 * n_cells / sum(n_cells)) %>%
    ungroup()
  
  pct_wide <- cluster_counts %>%
    select(sample, cluster, pct) %>%
    pivot_wider(names_from = sample, values_from = pct, values_fill = 0)
  
  ntc_cols <- ntc_samples
  effect_sizes <- pct_wide %>%
    mutate(
      mean_NTC_pct = rowMeans(across(all_of(ntc_cols))),
      delta_pct = .data[[kd_sample]] - mean_NTC_pct,
      ntc_diff = abs(.data[[ntc_cols[1]]] - .data[[ntc_cols[2]]]),
      consistent_direction = sign(.data[[kd_sample]] - .data[[ntc_cols[1]]]) ==
        sign(.data[[kd_sample]] - .data[[ntc_cols[2]]]),
      exceeds_ntc_noise = abs(delta_pct) > ntc_diff,
      effect_size_call = consistent_direction &
        exceeds_ntc_noise &
        abs(delta_pct) > 1
    ) %>%
    select(
      cluster,
      all_of(ntc_cols),
      all_of(kd_sample),
      delta_pct,
      ntc_diff,
      effect_size_call
    )
  
  # ---- 4. Master table: propeller is primary, effect size is supporting ----
  master <- effect_sizes %>%
    left_join(prop_result %>% select(cluster, P.Value, FDR), by = "cluster") %>%
    rename(propeller_p = P.Value, propeller_fdr = FDR) %>%
    mutate(
      # Primary call: propeller FDR (the principled test)
      primary_hit = propeller_fdr < 0.05,
      # Supporting evidence: effect-size sanity check
      effect_size_supports = effect_size_call
    ) %>%
    arrange(propeller_fdr)
  
  if (verbose) {
    cat("\n=== Master table ===\n")
    print(master)
  }
  
  # ---- 5. Visual sanity check ----
  stripchart_plot <- .make_stripchart(meta_df, sample_colors)
  
  list(
    propeller = prop_result,
    master = master,
    stripchart = stripchart_plot,
    meta_df = meta_df
  )
}