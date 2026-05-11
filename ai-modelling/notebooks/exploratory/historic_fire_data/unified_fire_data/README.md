# Unified Historical Bushfire Events and Satellite Detection Dataset

A Python workflow to match VIIRS satellite detections to ground-truth historic bushfire polygons and extract estimated extinguish dates, burn durations, and FRP measures (Severity).
The outputted dataset provides a baseline for historical fire training data.

## Overview

This notebook processes VIIRS thermal detections and historic bushfire extent polygons to:
- Spatially join detections to known fire boundaries
- Filter detections within a temporal window (ignition date ± 120 days)
- Estimate extinguish dates from detection gaps (4+ days)
- Calculate peak and cumulative FRP severity metrics
- Flag detection coverage and handle undetected fires

The final dataset covers Victoria, Australia, with a buffer to ensure detection of fire events on the border.

## Inputs

- `viirs_historic_fires.csv` – Gridded, time-series satellite (VIIRS, MODIS) thermal detections with lat/lon, datetime, confidence, FRP, and spread information - output from: `..\satellite_fire_data\satellite_data_processing.py`
- `historic_fire_extents.csv` – Ground-Truth Bushfire polygon boundaries with ignition dates, final burn size, fire meta data, and final fire shape - output from: `..\historic_fire_events_data\historic_fire_data_processing.py`

To use this script, ensure that the above outputs exist in there working folder.

## Outputs

- `unified_historic_fire_dataset.geojson` – Final fire dataset with all computed metrics
- `unified_historic_fire_dataset.csv` – Final fire dataset with all computed metrics
- `satellite_detections_within_fires.geojson` - Final satellite detections dataset filtered by confirmed detections within fire events
- `satellite_detections_within_fires.csv` - Final satellite detections dataset filtered by confirmed detections within fire events

## Output Features
### Unified Dataset
| Feature | Type | Description |
|---------|------|-------------|
| **fire_id** | str | Unique fire identifier; negative values are synthetic IDs for fires with no official ids Unique fire identifier; negative values are synthetic IDs for fires with no official idsUnique fire identifier; negative values are synthetic IDs for fires with no official idsUnique fire identifier; negative values are synthetic IDs for fires with no official idsUnique fire identifier; negative values are synthetic IDs for fires with no official idsUnique fire identifier; negative values are synthetic IDs for fires with no official ids |
| **fire_name** | str | Given name of the bushfire event |
| **ignition_date** | datetime | Recorded fire start date |
| **extinguish_date** | datetime | Estimated extinguish date |
| **duration_days** | float | Days between ignition and extinguish dates; total fire duration|
| **detection_status** | str | One of: `detected`, `imputed_same_day`, `coverage_gap` |
| **peak_frp** | float | Maximum Fire Radiative Power across all detections (MW) |
| **cumulative_frp** | float | Sum of FRP across all detections (MW); total detected MW output |
| **season** | str | Season that the fire occured in |
| **fire_type** | str | Fire classification (Bushfire, Prescribed Burn) |
| **size_class** | str | Fire size category: `small`, `medium`, `large`, `mega` |
| **area_ha** | float | Total fire burn area in hectares |
| **perim_km** | float | Length of Fire perimeter in kilometers |
| **compactness** | float | Shape metric (perimeter² / area); low compactness indicates irregular spread |
| **log_area** | float | Log-transformed area (log₁ₚ(area_ha)); reduces skew for analysis |
| **geometry** | geometry | Polygon boundary (WKT) |

### Filtered Satellite Detections
| Feature | Type | Description |
|---------|------|-------------|
| **cell_x** | int | Grid cell x-coordinate |
| **cell_y** | int | Grid cell y-coordinate |
| **datetime** | datetime | Acquisition date of detection |
| **daynight** | int | 0 = AM, 1 = PM |
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

## Detection Status Logic

- **`detected`** – Fire had ≥1 VIIRS detection within time window
- **`imputed_same_day`** – Undetected small/medium fire; assumed burned out same day between satellite passes (duration = 6 hours)
- **`coverage_gap`** – Undetected large/mega fire; likely due to satellite coverage gap

## Size Class 

- **`small`** – total area in hectres < 10
- **`medium`** – total area in hectres >= 10 & < 100
- **`large`** – total area in hectres >= 100 & < 1000
- **`mega`** – total area in hectres >= 1000

## Processing Steps

### 1. Load Data
- Reads gridded satellite thermal detections from `satellite_fire_data.csv` (output from satellite_data_processing.ipynb)
- Reads ground-truth bushfire extent polygons from `historic_fire_extents_data.csv` (output from historic_fire_data_processing.ipynb)
- Converts both to GeoDataFrames with WKT geometry parsing

### 2. Assign Synthetic IDs for Unmatched Fires
- Identifies bushfire records with null `fire_id` values
- Assigns synthetic negative IDs (starting from -1, -2, -3...) for processing
- Allows fires without official IDs to be tracked through spatial join

### 3. Spatial Join: Match VIIRS Detections to Bushfires
- Performs spatial intersection join between satellite detection points and bushfire polygons
- Attaches `fire_id` and `ignition_date` to each matched detection
- Standardizes datetime formats (UTC → naive local time)

### 4. Filter Satellite Detections by Time Window
- Keeps only detections within [-1 day, +120 days] relative to ignition date
- Identifies first detection per fire
- Removes fires with first detection >4 days after ignition (prevents unrelated detections from being assigned)
- Ensures temporal alignment between ignition record and satellite observations

### 5. Estimate Extinguish Dates from Detection Gaps
- Sorts detections by fire and datetime
- Calculates gap (in days) between consecutive detections for each fire
- Identifies first significant gap (4+ days with no detections)
- Sets extinguish date to the datetime of the last detection before the gap
- Uses end-of-detections as extinguish if no gap is found

### 6. Merge Extinguish Dates onto Bushfire Dataset
- Joins estimated extinguish dates back to the main bushfire geodataframe
- Standardizes date formats and handles timezone conversions

### 7. Calculate Fire Duration
- Computes duration as: `(extinguish_date - ignition_date)` in days
- Handles edge case where extinguish is before ignition (late-recorded ignitions)
- Imputes 6-hour duration for short-burning fires ocurring between satellite passes
- Rounds to 2 decimal places

### 8. Extract Peak and Cumulative FRP
- **Peak FRP**: Maximum FRP value across all detections for each fire (single highest value)
- **Cumulative FRP**: Sum of all FRP values across all detections for each fire (total energy output)
- Merges severity metrics onto bushfire dataset

### 9. Classify Detection Status
- Counts VIIRS detections per fire
- Classifies as either:
    - `detected` – ≥1 detection within time window
    - `never_detected` – 0 detections (to be handled in next step)

### 10. Handle Undetected Fires
- **Small/medium undetected fires**: Imputed as 6-hour burns (assumed to burn out between satellite passes)
    - Sets status to `imputed_same_day`, duration to 0.25 days
- **Large/mega undetected fires**: Flagged with status `coverage_gap` (likely satellite coverage gap, not short duration)
    - No duration imputation applied
    - Likely fast-moving grass fires, handling should be explored further

### 11. Unified Final Output
- Enforces column ordering for consistency
- Sorts by ignition_date and fire_id (groups same-date fires together)
- Ensures WGS84 lat/lon (EPSG:4326) for compatibility with basemaps and Earth Engine
- Exports to CSV

### 12. Filtered Satellite Detections Output
- Filters original satellite dataset to only contain detections confirmed as bushfires by the historic fire events

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Detection window | -1 day before ignition, +120 days after | Captures fires that may have a late recorded ignition date |
| First detection threshold | ≤4 days after ignition | If no detections occur within 4 days from the ignition date, disregard any later detections. Prevents late detections from being assigned to the wrong fire event |
| Gap threshold | 4 days | If there is gap of detections past the threshold, infer extinguish date |

## Use Case
This notebook's output provides clean historic bushfire events data with the engineered extinguish dates, burn durations, severity (FRP) measures derived from satellite data. 
As a dataset, this provides the following information: 
- When the fire ignited
- When the fire was considered extinguished
- How long the fire burnt for
- The exact dimensions of the final burnt area
- The severity (FRP) of the fire event

These features provide essential information for mapping historical bushfire events and behaviour in Victoria. As a geodataframe, it is also ready for mapping with Google Earth Engine datasets through multipolygon geometry.

## Notes
### Limitations
- Satellite data contains multiple-hour gaps in passes. Short-burning fires are common, and may have no detections.
- Small fires deemed unimpactful are not included in the Government's official historic bushfire dataset, and as such aren't included here.
- Undetected small and medium fires have no detected FRP values.

### Assumptions
- Small and medium undetected fires are considered to be short-burning and are imputed as 6-hour burns (conservative estimate)
- Large undetected fires are flagged but not imputed (likely data gap, not actual short duration)
- Cumulative FRP sums all detections, peak FRP reports the single highest value
- Dates are timezone-localized to UTC then converted to naive (local) for analysis