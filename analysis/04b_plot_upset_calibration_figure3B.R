# ============================================================================
# UpSet Plot for AP-1 Calibrated Parameters Analysis
# ============================================================================

# Load required libraries
library(tidyverse)
library(UpSetR)
library(ComplexUpset)
library(scales)

# ============================================================================
# DATA LOADING AND PROCESSING
# ============================================================================

# Load and prepare data
dat <- read_csv("ap1_calibrated_matched_parameters_initialConditions_states.csv") %>% 
  select(-c(init_cond_index, input_state, model_steadystate))

# Get parameter indices for each cell line
WM902B <- dat %>% filter(cell_line == "WM902B") %>% select(param_index) %>% unique()
LOXIMVI <- dat %>% filter(cell_line == "LOXIMVI") %>% select(param_index) %>% unique()
COLO858 <- dat %>% filter(cell_line == "COLO858") %>% select(param_index) %>% unique()

# Find intersection of COLO858 and LOXIMVI parameters
intersect_params <- intersect(COLO858$param_index, LOXIMVI$param_index)

# Filter out intersecting parameters from COLO858 and LOXIMVI
dat_filtered <- dat %>% 
  filter(!(param_index %in% intersect_params & cell_line %in% c("COLO858", "LOXIMVI")))

# Prepare data for UpSet plot
unique_data <- distinct(dat_filtered)
binary_data <- unique_data %>%
  mutate(value = 1) %>%
  pivot_wider(names_from = cell_line, values_from = value, values_fill = 0)

# Get all cell line names
all_names <- unique(dat$cell_line)

# ============================================================================
# UPSET PLOT GENERATION
# ============================================================================
# Create final UpSet plot with percentage display
my_plot_final <- upset(
  binary_data,
  all_names,
  width_ratio = 0.4,
  height_ratio = 1.5,
  
  # Set sizes on right side (as percentages)
  set_sizes = (
    upset_set_size(
      geom = geom_bar(width = 0.5),
      mapping = aes(y = ..count../24677 * 100),
      position = "right"
    ) +
      ylab("% calibrated to full parameter sets") +
      scale_y_continuous(
        labels = function(x) paste0(x, ""),
        breaks = seq(0, 12, by = 1),  # Explicit breaks every 2%
        limits = c(0, 12),           # Set clear limits
        expand = c(0, 0),            # Remove padding
        minor_breaks = seq(0, 12, by = 1)  
      ) +
  
    theme(
        axis.text.x = element_text(size = 12, angle = 0),
        axis.text.y = element_text(size = 12),
        axis.title.x = element_text(size = 12),
        axis.title.y = element_text(size = 12),
        axis.ticks = element_line(size = 0.3),
        axis.ticks.length = unit(0.1, "cm"),
        panel.grid.major.y = element_line(color = "grey90", size = 0.3),
        panel.grid.minor.y = element_line(color = "grey95", size = 0.2)
      )
  ),
  
  # Main intersection plot with percentage ratios
  base_annotations = list(
    'Intersection ratio' = (
      intersection_ratio(
        text = list(alpha = 0),
        text_mapping = aes(label = !!upset_text_percentage())
      ) +
        theme(
          axis.text.y = element_text(size = 12),
          axis.text.x = element_text(size = 12),
          axis.title.y = element_text(size = 12),
          axis.title.x = element_text(size = 12)
        ) +
        labs(y = "% of Intersecting parameters")
    )
  ),
  
  # Matrix visualization
  matrix = intersection_matrix(
    geom = geom_point(
      shape = 'circle',
      size = 2
    )
  ),
  
  # Theme customization
  themes = upset_modify_themes(
    list(
      'intersections_matrix' = theme(
        text = element_text(size = 12),
        axis.title = element_text(size = 12)
      ),
      'intersection_size' = theme(
        axis.text = element_text(size = 12),
        axis.title = element_text(size = 12),
        axis.ticks = element_line(size = 0.5),
        axis.ticks.length = unit(0.2, "cm")
      ),
      'overall_sizes' = theme(
        axis.text.x = element_text(size = 12),
        axis.text.y = element_text(size = 12),
        axis.title.x = element_text(size = 12),
        axis.title.y = element_text(size = 12),
        axis.ticks = element_line(size = 0.5),
        axis.ticks.length = unit(0.2, "cm")
      )
    )
  )
)

# Display the plot
my_plot_final

# Save the final plot
ggsave(
  filename = "test_upset_plot_with_calibrated_parameters.pdf", 
  plot = my_plot_final, 
  width = 8,  
  height = 6,  
  dpi = 300
)
