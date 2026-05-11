# Satellite Thermal Fire Detection Data — Victoria
Processing pipeline for NASA VIIRS satellite fire detection data.
Produces a gridded, feature-engineered dataset for ML modelling or further engineering.

---

## Overview

This notebook processes raw VIIRS and MODIS satellite thermal detections to:
- Combine multi-satellite feeds (VIIRS N20, VIIRS SNPP, MODIS Aqua, MODIS Terra) into a unified dataset
- Filter detections to Victoria using latitude/longitude bounding box and spatial bounds
- Map detections to a grid with 5 km² cells and aggregate per satellite pass
- Clips grid to only include those with Victoria boundary
- Engineer temporal features (pass timing, time since previous pass)
- Compute spatial neighbours at two radii (r=1, r=2 cells)
- Generate targets for time-series prediction (next-timestep burn state and FRP)

The final dataset is a geospatial gridded, temporally ordered, and model-ready overview of thermal detections between 07/2018 and 07/2022.
The time period of the dataset can be easily expanded with larger raw NASA exports.

## Inputs

- `fire_archive_J1V-C2_734127.csv` – VIIRS N20 satellite detections (raw NASA export)
- `fire_archive_SV-C2_734128.csv` – VIIRS SNPP satellite detections (raw NASA export)
- `fire_archive_M-C61_734126.csv` – MODIS Aqua and MODIS Terra satellite detections (raw NASA export)
- `victoria_boundary_fao_gaul_2015.geojson` - Precise Victoria boundary recieved from GEE script

All satellite files can be downloaded from https://firms.modaps.eosdis.nasa.gov/download. This script can work with any provided time period that the above satellite detections exist for.

The victoria boundary geojson can be extracted for GEE using the provided  `victoria_boundary_GEE.js`. Copy the script into the GEE script interface, run the task, and download from the Google Drive.

To use the script, download the above raw NASA exports, place the downloaded data into the data folder inside `historic_fire_events_dataset`, and ensure the correct naming convention.

## Outputs

- `satellite_fire_data.csv` – Gridded, feature-engineered time-series dataset
- `satellite_fire_data.geojson` – Gridded, feature-engineered time-series dataset

## Output Features

| Feature | Type | Description |
|---------|------|-------------|
| **cell_x** | int | Grid cell x-coordinate |
| **cell_y** | int | Grid cell y-coordinate |
| **datetime** | datetime | Precise acquisition time of detection (HHmm format) UTC |
| **daynight** | int | 0 = day pass, 1 = night pass |
| **satellite** | str | Source satellite: `N20` (VIIRS), `N` (VIIRS), `Terra` (MODIS), or `Aqua` (MODIS) |
| **time_since_prev_pass** | float | Seconds elapsed since previous recorded satellite pass. Gives context to each timestep |
| **confidence** | int | Confidence that detection is a fire: `1` = low, `2` = nominal, `3` = high |
| **is_burning** | int | Binary flag; `1` = currently burning, `0` = not currently burning |
| **brightness** | float | Max detected brightness temperature (Kelvin) in cell |
| **bright_t31** | float | Max 11-micron brightness temperature (Kelvin) in cell |
| **frp_peak** | float | Maximum Fire Radiative Power (MW) in cell. FRP provides a measure of fire severity |
| **frp_cumulative** | float | Sum of FRP across all detections in cell (MW) |
| **burning_neighbors_r1** | int | Count of cells burning in radius 1-cell neighbourhood in the same timestep (0-8) |
| **burning_neighbors_r2** | int | Count of cells burning in radius 2-cell neighbourhood in the same timestep (0-24) |
| **is_burning_prev** | int | Binary flag; `1` if cell detected fire at the previous timestep |
| **frp_prev** | float | Peak FRP in this cell in the previous timestep |
| **burning_neighbors_prev_r1** | int | Count of cells burning in radius 1-cell neighbourhood in the previous timestep (0-8) |
| **burning_neighbors_prev_r2** | int | Count of cells burning in radius 2-cell neighbourhood in the previous timestep (0-24) |
| **is_burning_next** | int | Binary flag; `1` if cell detected fire at next pass (prediction target) |
| **frp_next** | float | Peak FRP at this cell in next timestep (prediction target) |
| **longitude** | float | Cell centroid longitude (EPSG:4326) |
| **latitude** | float | Cell centroid latitude (EPSG:4326) |
| **geometry** | geometry | Cell polygon boundary |

## Processing Steps

### 1. Load Data
Reads raw NASA CSV exports from four satellites and combines into a single dataframe.

### 2. Filter to Victoria
Applies bounding box filter (lat: -39.2 to -34.0, lon: 140.9 to 150.0) to isolate Victorian detections.
*Note: A Victoria shape mask should be considered for accuracy along state border. Need to balance accuracy with a buffer to ensure state border fires are captured.*

### 3. Grid Cells
- Projects to EPSG:7855 (GDA2020 / MGA zone 55) for meter-accurate geometry
- Snaps detections to 5 km² cells (5000m × 5000m)
- Clips cells to only those contained within the Victoria region
- Aggregates to the highest reading per cell per satellite pass
- Rebuilds cell centroids and geometry in lat/lon (EPSG:4326)

### 4. Visualize Coverage
Plots detected cells across the full date range to verify spatial coverage. Cell colors represent maximum brightness.

### 5. Timestep Engineering
- Creates consistent pass-level timestamps per satellite and day/night (2 passes per satellite)
- Calculates time elapsed since the previous recorded timestep
- Groups individual satellite passes into single timesteps to ensure timestep consistency

### 6. Feature Engineering
Derives temporal and spatial features:
- **Temporal**: Current burn state, previous/next states, FRP at previous/next timesteps
- **Spatial**: Burning neighbour counts at r=1 and r=2 cell radii
- **Targets**: `is_burning_next` and `frp_next` for supervised learning

### 7. Export
Drops intermediate columns, enforces column ordering, and writes final dataset to CSV.

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Grid cell size | 5000 m (5 km²) | Defines spatial resolution of the dataset |
| neighbour radius r1 | 1 cell | Immediate 8-cell neighbourhood |
| neighbour radius r2 | 2 cells | Extended neighbourhood (24 cells) |

## Use Case

Output provides a time-series dataset ready for machine learning applications:

### Fire Spread Prediction
- Predict next-timestep burn state (`is_burning_next`) using current FRP, neighbours, and temporal context
- Identify zones with high spread probability using neighbour features
- Train models on sequences of cell states across multiple passes

### Fire Intensity Forecasting
- Predict next-timestep FRP (`frp_next`) to forecast fire intensity changes
- Classify cells into intensity buckets (low/medium/high) based on neighbour burning patterns
- Detect intensity escalation/de-escalation trends

### Satellite Coverage Analysis
- Validate detection consistency across day/night passes
- Identify detection gaps or coverage blind spots

### Spatiotemporal Fire Behavior
- Analyze fire propagation patterns using neighbour counts and temporal sequences
- Study correlation between neighbour state and future burn likelihood

The output also provides clean satellite fire detections for incorporation with other datasets. By matching detections with ground-truth historic fire records, a more holistic overview of fire behaviour in Victoria can be established. See `../unified_fire_data/` for the processing notebook and documentation of this approach.

## Limitations

- **Temporal gaps**: Multiple-hour gaps exist between satellite passes; short-burning fires may be missed
- **Grid resolution**: 1 km² cells may be too coarse for small fires or too granular for large fire fronts
- **Confidence mapping**: MODIS confidence (0-100%) is binned to match VIIRS levels (low/nominal/high), losing precision

## Assumptions

- Cells detected at a given timestep represent active fire presence during that pass window
- neighbour relationships are computed independently for each timestep
- Previous timestep features are based on spatial alignment only (no time-distance weighting)
- Cell geometry is square and axis-aligned in projected space (EPSG:7855)

## Notes

### Spatial Reference
- Input data in lat/lon (EPSG:4326) is projected to EPSG:7855 (GDA2020 MGA zone 55) for consistent 1 km² cell sizing
- Output centroids and geometry are back-projected to EPSG:4326 for compatibility with basemaps and Google Earth Engine

### Time Aggregation
- Pass-level datetime is the minimum acquisition time across all detections in that satellite's pass. This grouping prevents a cell considering the same satellite pass as being a seperate timestep
- `time_since_prev_pass` captures revisit interval. Useful for providing temporal context to each timestep

### neighbour Computation
- neighbours are computed using Chebyshev distance (r × √2) to capture diagonal neighbours within radius
- Previous neighbours (`burning_neighbors_prev_*`) looks back one full timestep
