# Import iNaturalist observations
# 1. library ----
if(!require("pacman")) {
  install.packages("pacman")
}

pacman::p_load(
  dplyr,
  rinat,
  ggplot2,
  stringr,
  sf,
  maptiles,
  ggspatial,
  patchwork
)

# Set relative paths assuming the script is run from the project root
out_dir <- "docs/assets"
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

# 2. import your dataset ----
inat_data = get_inat_obs_project("living-lab-campus-agripolis-unipd", type = c("observations", "info"), raw = FALSE)

# clean the observations
inat_data_clean <- inat_data %>%
  filter(
    quality_grade != "casual",                      # remove casual observations
    str_count(taxon.name, "\\w+") > 1              # delete observations at genus level
  )

# 3. data elaboration ----
# which taxa has more observations?
taxon_counts <- inat_data_clean %>%
  filter(!is.na(iconic_taxon_name) & iconic_taxon_name != "") %>%
  group_by(iconic_taxon_name) %>%
  summarise(count = n()) %>%
  arrange(desc(count)) %>%
  mutate(
    prop = count / sum(count),
    label = paste0(iconic_taxon_name, " (", count, ")")
  )

# create a pie chart
pie_plot = ggplot(taxon_counts, aes(x = "", y = count, fill = label)) +
  geom_col(width = 1, color = "white") +
  coord_polar(theta = "y") +
  theme_void() +
  labs(
    title = "iNaturalist Observations by Taxon within Agripolis Campus",
    fill = "Taxonomic Group"
  ) +
  scale_fill_brewer(palette = "Set3")

# Save pie plot
ggsave(file.path(out_dir, "pie_chart.png"), plot = pie_plot, width = 8, height = 6, bg = "white")

# 4. mapping the observations
# Create sf object
inat_sf <- st_as_sf(
  inat_data_clean,
  coords = c("longitude", "latitude"),
  crs = 4326,     # WGS84
  remove = FALSE  # keep original lat/long columns
)

# reproject data as required by maptiles
inat_sf_web <- st_transform(inat_sf, 3857)

# download the basemap (es: Esri.WorldImagery)
basemap <- get_tiles(inat_sf_web, provider = "Esri.WorldImagery")

# generate the map
map_plot = ggplot() +
  layer_spatial(basemap) +
  geom_sf(data = inat_sf_web, aes(color = iconic_taxon_name), size = 1.5, alpha = 0.8) +
  theme_minimal() +
  labs(title = "Spatial distribution of iNaturalist observations",
       subtitle = "Agripolis Campus",
       color = "Taxonomic groups") +
  ggspatial::annotation_scale(
    location = "bl",
    pad_x = unit(0.4, "in"), pad_y = unit(0.4, "in"),
    bar_cols = c("grey60", "white"),
  ) +
  ggspatial::annotation_north_arrow(
    location = "tr", which_north = "true",
    pad_x = unit(0.4, "in"), pad_y = unit(0.4, "in"),
    style = ggspatial::north_arrow_nautical(
      fill = c("grey40", "white"),
      line_col = "grey20"
    )
  )

# Save map plot
ggsave(file.path(out_dir, "spatial_map.png"), plot = map_plot, width = 10, height = 8, bg = "white")

# Density Heatmap
density_plot = ggplot() +
  layer_spatial(basemap) +
  stat_density_2d_filled(
    data = inat_sf_web,
    aes(x = sf::st_coordinates(inat_sf_web)[, 1],
        y = sf::st_coordinates(inat_sf_web)[, 2],
        fill = after_stat(level)),
    alpha = 0.7,
    contour_var = "density"
  ) +
  scale_fill_viridis_d(option = "magma", name = "Observation Density") +
  theme_minimal() +
  labs(title = "Heatmap of iNaturalist Observation Density (Agripolis Campus)",
       subtitle = "Darker areas indicate a higher concentration of observations")

# Save density plot
ggsave(file.path(out_dir, "density_map.png"), plot = density_plot, width = 10, height = 8, bg = "white")

print("R script executed successfully. Plots saved to docs/assets/")
