library(tidyverse)
library(ComplexHeatmap)
library(circlize)
library(stats)

# import data as csv file
folder_path = "/Volumes/FallahiLab/Maize-Data/Data/Yonatan_Degefu/COPASI_Modeling/Basico_python/Copasi_basico_cluster/AP1 single cell data/"

file_name = "19celllines_baseline_ap1_log10_coreAP1s_MITF_SOX10.csv"

data <- read.csv(
  file     = paste0(folder_path, file_name),
  header   = TRUE,
  stringsAsFactors = FALSE
)

# 2) define your proteins
proteins <- c("cFOS","cJUN","FRA1","FRA2","JUND","MITF","SOX10")

# 3) rename that bad cell_line entry, select & group-mean exactly like pandas
heatmap_data <- data %>%
  mutate(
    cell_line = case_when(
      cell_line %in% c(
        "A375 _x001A_NRAS(Q61K)",
        "A375_NRAS(Q61K)"
      ) ~ "A375\u0394NRAS",  # Δ in place of underscore
      TRUE ~ cell_line
    )
  ) %>%
  select(cell_line, all_of(proteins)) %>%
  group_by(cell_line) %>%
  summarise(across(all_of(proteins), mean, na.rm = TRUE)) %>%
  ungroup()
#4) z-score each column (protein) just as in Python
heatmap_z <- heatmap_data %>%
  mutate(across(
    all_of(proteins),
    ~ (. - mean(.)) / sd(.)
  ))

# 5) transpose so rows = proteins, columns = cell lines
mat <- heatmap_z %>%
  column_to_rownames("cell_line") %>%
  t()


# --- assume `mat` already exists: rows=cFOS,cJUN,FRA1,FRA2,JUND,MITF,SOX10; cols=cell lines

# 1) split into two matrices
ap1_proteins <- c("cFOS","cJUN","FRA1","FRA2","JUND")
diff_markers <- c("MITF","SOX10")

mat_ap1  <- mat[ap1_proteins, , drop = FALSE]
mat_diff <- mat[diff_markers, , drop = FALSE]

# 1) Compute Pearson‐based distances and average‐linkage hclust for rows (AP-1) and columns (all)
#    (a) rows of AP-1 block:
row_cor   <- cor(t(mat_ap1), method = "pearson")      # correlation between proteins
row_dist  <- as.dist(1 - row_cor)                     # convert to distance
row_hc    <- hclust(row_dist, method = "average")     # average linkage

#    (b) columns on the full matrix (so bottom panel columns match top):
full_cor  <- cor(mat, method = "pearson")             # corr between cell lines
col_dist  <- as.dist(1 - full_cor)
col_hc    <- hclust(col_dist, method = "average")

# 2) Define your color scale
col_fun3 <- colorRamp2(
  c(-3, 0, 3),
  c("#08519C", "#FFFFFF", "#A50F15")
)
cell_size_factor_w <- 0.3 # cm per column, adjust this
cell_size_factor_h <- 0.3 # cm per row, adjust this

# 3) Rebuild the two Heatmap objects, feeding in your hclusts
ht_ap1 <- Heatmap(
  mat_ap1,
  name               = "z-score",
  col                = col_fun3,
  cluster_rows       = row_hc,       # use your custom row clustering
  cluster_columns    = col_hc,       # use your custom column clustering
  show_row_dend      = TRUE,
  show_column_dend   = TRUE,
  show_column_names  = FALSE,
  rect_gp            = gpar(col = "black", lwd = 1),
  row_names_gp       = gpar(fontsize = 6),
  column_title       = " ",
  column_title_gp    = gpar(fontsize = 6, fontface = "bold",fontfamily = "Arial Unicode MS"),
  heatmap_legend_param = list(title = "Protein expression (z-score log a.u.)" ,
                              at = c(-3,-2,-1,0,1,2,3), 
                              labels = c("-3","-2","-1","0","1","2","3"),
                              direction = "horizontal",
                              title_position = "topcenter",
                              title_gp = gpar(fontsize = 6, fontface = "bold", fontfamily = "Arial Unicode MS"), # Font for legend
                              labels_gp = gpar(fontsize = 6, fontfamily = "Arial Unicode MS"),
                              legend_width = unit(4, "cm"), # Adjust the width of the color bar itself if needed
                              legend_height = unit(0.5, "cm"), # Adjust the thickness of the color bar itself if needed
                              grid_width = unit(1, "cm") ),
  width = unit(ncol(mat_ap1) * cell_size_factor_w, "cm"),
  height = unit(nrow(mat_ap1) * cell_size_factor_h, "cm")
)

ht_diff <- Heatmap(
  mat_diff,
  name               = "z-score",
  col                = col_fun3,
  cluster_rows       = FALSE,        # no row clustering
  cluster_columns    = col_hc,       # same column clustering as above
  show_row_dend      = FALSE,
  show_column_dend   = FALSE,
  rect_gp            = gpar(col = "black", lwd = 1),
  row_names_gp       = gpar(fontsize = 6,fontfamily = "Arial Unicode MS"),
  column_names_gp    = gpar(fontsize = 6, rot = 45, just = "right",fontfamily = "Arial Unicode MS"),
  column_title       = "Differentiation markers",
  column_title_gp    = gpar(fontsize = 6, fontface = "bold"),
  width = unit(ncol(mat_diff) * cell_size_factor_w, "cm"),
  height = unit(nrow(mat_diff) * cell_size_factor_h, "cm")
)

# 4) Stack and draw with a big gap
ht_list <- ht_ap1 %v% ht_diff
#CairoPDF("AP1_split_heatmap.pdf", width=14, height=10)

out_path <- "/Volumes/FallahiLab/Maize-Data/Data/Yonatan_Degefu/AP1_mechanistic_modelling/AP1_split_heatmap.pdf"
Cairo::CairoPDF("AP1_split_heatmap_v2.pdf", width=3.3, height=3.3, family="Arial Unicode MS")




# redraw your plot:
draw(
  ht_list,
  ht_gap = unit(0.5, "cm"),
  merge_legends       = TRUE,
  heatmap_legend_side = "bottom",
  padding = unit(c(8, 5, 5, 5), "mm")
)
#grid.text(
  #"AP-1 Protein Expression Across Cell Lines",
  #y  = unit(1, "npc") - unit(2, "cm"),
  #gp = gpar(fontsize = 24, fontface = "bold", fontfamily = "sans")
#)
dev.off()  # close device










































