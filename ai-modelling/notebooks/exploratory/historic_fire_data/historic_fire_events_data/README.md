# Victorian Bushfire Events — Feature Engineering & EDA
Processing pipeline for the National Historical Bushfire Extents dataset, filtered to Victoria.

---

## Overview

This notebook processes the National Historical Bushfire Extents geodatabase to:
- Load and filter bushfire extent polygons to Victorian records
- Quality check and clean the dataset (remove null columns, zero-area fires)
- Isolate the 2018–2022 period (including Black Summer 2019–2020)
- Filter to bushfire events only (exclude prescribed burns)
- Engineer spatial and temporal features (season, area, perimeter, compactness, size class)
- Perform exploratory analysis (fire type breakdown, area distribution, seasonal patterns, morphology)

The final dataset provides ground-truth fire boundaries with shape characteristics ready for spatial analysis and modelling.

## Inputs

- `BushfireEvents.gdb/National_Historical_Bushfire_Extents_v4` – National database of historic bushfire extent polygons (Geospatial Database, GeoDatabase format)

Input data can be downloaded from: https://digital.atlas.gov.au/datasets/524e2962bd8b4968b8df9f9774345926/about

## Outputs

- `historic_fire_extents_data.csv` – Cleaned and feature-engineered Victorian bushfire dataset
- `historic_fire_extents_data.geojson` – Cleaned and feature-engineered Victorian bushfire dataset

## Output Features

| Feature | Type | Description |
|---------|------|-------------|
| **fire_id** | str | Unique fire identifier from national dataset |
| **fire_name** | str | Given name of the bushfire event |
| **ignition_date** | datetime | Recorded fire start date |
| **season** | str | Season of ignition: `Summer`, `Autumn`, `Winter`, `Spring` |
| **fire_type** | str | Fire classification: `Bushfire`, `Prescribed Burn` (filtered dataset contains only bushfires) |
| **size_class** | str | Fire size category based on final burnt area: `small` (<10 ha), `medium` (10–100 ha), `large` (100–1000 ha), `mega` (≥1000 ha) |
| **area_ha** | float | Total fire burn area in hectares |
| **perim_km** | float | Length of fire perimeter in kilometers |
| **compactness** | float | Shape metric (perimeter² / area); low compactness indicates irregular spread, high compactness indicates circular, regular spread |
| **log_area** | float | Log-transformed area (log₁ₚ(area_ha)); reduces skew for analysis |
| **SHAPE_Length** | float | Original GeoDatabase shape length attribute (meters) |
| **SHAPE_Area** | float | Original GeoDatabase shape area attribute (square meters) |
| **geometry** | geometry | Polygon boundary of burnt extent (WKT) |

## Processing Steps

### 1. Load Data
- Reads the National Historical Bushfire Extents GeoDatabase layer
- Applies bounding box filter (lat: -29 to -43, lon: 130 to 160) to isolate Victorian records with a buffer for state-border fires
- Filters on state feature to ensure `VIC (Victoria)` designation

### 2. Data Quality
- Checks for null values across all columns
- Identifies and drops columns with no usable data: `capture_date`, `extinguish_date`, `ignition_cause`, `capt_method`
- Notes: These columns are null for all records in the dataset for Victoria

### 3. Filter to 2018–2022
- Isolates the Black Summer period and surrounding years for analysis
- Date range: July 1, 2018 – July 31, 2022
- Removes zero-area polygon records (low-impact events)

### 4. Feature Engineering
Derives new features from geometry and ignition date:
- **Season**: Derived from month of ignition date (Dec-Feb: Summer, Mar-May: Autumn, Jun-Aug: Winter, Sep-Nov: Spring)
- **Area & Perimeter**: Calculated from polygon geometry in projected coordinate system (EPSG:7855)
- **Compactness**: Shape metric indicating regularity of fire spread (4π × area / perimeter²)
- **Log Area**: Log-transformed area to reduce right skew for statistical analysis
- **Size Class**: Categorical binning of area into four classes for summary statistics

### 5. Exploratory Analysis
Investigates fire characteristics and patterns:

**5.1 Fire Type Breakdown**
- Identifies that dataset contains large majority of prescribed burns with smaller bushfire population
- Filters to bushfire records only for analysis (n ≈ 1310)
- Notes that bushfires have significantly higher mean and std dev area than prescribed burns

**5.2 Area Distribution**
- Visualizes log-transformed area histogram
- Identifies massive right skew: large majority of bushfires are small, with very few being enormous

**5.3 Seasonal Patterns**
- Aggregates fires by season: count, total area, mean area
- Finds bushfires occur significantly more often in summer with much larger median area
- Caution: Dataset includes Black Summer 2019–2020, which may exaggerate seasonal effect

**5.4 Compactness vs Size**
- Scatter plot of log area (x-axis) against compactness (y-axis)
- Finds inverse relationship: larger fires tend to have lower compactness, suggesting more irregular spread in large events

### 6. Export
- Enforces column ordering for consistency
- Writes final dataset to CSV with geometry in WKT format

## Key Parameters

| Parameter | Value | Notes |
|-----------|-------|-------|
| Time period | July 1, 2018 – July 31, 2022 | Covers Black Summer 2019–2020 and surrounding years. Can be modified for larger time periods |
| Spatial filter | Bounding box (lat: -29 to -43, lon: 130 to 160) | Covers Victoria with buffer for border fires |
| Fire type filter | `Bushfire` only | Excludes prescribed burns |
| Area threshold | > 0 ha | Removes zero-area records |
| Size class bins | [0, 10, 100, 1000, ∞) | Small, medium, large, mega categories |

## Use Case

Output provides a clean, ground-truth dataset of historic Victorian bushfire events:

### Spatial Fire Risk Mapping
- Identify high-risk burn zones using size class and seasonal aggregation
- Correlate with terrain, vegetation, and proximity to infrastructure

### Time-Series Analysis
- Align with satellite detection data to validate coverage and timing
- Identify seasonal fire cycles and multi-year trends
- Study fire behavior changes across the Black Summer period

### Morphological Analysis
- Analyze relationship between fire size and compactness to understand spread patterns
- Classify fires by shape regularity (compact vs. sprawling)
- Train models to predict fire spread pattern from ignition conditions

### Ground Truth Validation
- Match with satellite detections to validate VIIRS/MODIS coverage and sensitivity
- Identify detection gaps (fires with no satellite detections)
- Establish baseline detection rates by fire size and season

While useful on its own, this dataset does not contain extinguish dates or severity measures. By matching fire events with satellite thermal detections, these critical features can be derived. See `../unified_fire_data/` for the processing notebook and documentation of this approach.

## Limitations

- **Ignition date accuracy**: Ignition dates are estimated based on official records; actual starts may differ by hours or days
- **Boundary precision**: Polygon extent may reflect final fire size estimates rather than real-time boundary evolution
- **Missing detections data**: No original extinguish dates recorded; must be inferred from satellite data or other sources
- **Prescribed burn exclusion**: Dataset focuses on uncontrolled bushfires; prescribed burns (controlled by fire management) are excluded
- **Incomplete coverage**: Small fires not deemed significant may not be included in the national database

The lack of extinguish dates in particular greatly limits the usefulness as a dataset for modelling fire risk, spread, and severity. 

## Assumptions

- Ignition dates are recorded at start of fire (within 1–2 days)
- Polygon geometries represent final burnt extent after fire extinguishment
- Fire names are consistently recorded where available
- Compactness metric (4π × area / perimeter²) is a valid measure of fire shape regularity

## Notes

### Multiple Entries per Fire
- Some fires have mulitple entires with the same fire id and name
- The seperate entries represent seperate perimeter polygons that have been designated as part of a single fire event

### Spatial Reference
- Source data in lat/lon (EPSG:4326)
- Projected to EPSG:7855 (GDA2020 / MGA zone 55) for accurate area/perimeter calculation in meters
- Output geometry back-projected to EPSG:4326 for compatibility with basemaps and spatial joins

### Size Class Rationale
- `small` (<10 ha): Minor fires, often contained quickly
- `medium` (10–100 ha): Moderate fires requiring intervention
- `large` (100–1000 ha): Major fires with significant impact
- `mega` (≥1000 ha): Catastrophic fires (includes largest Black Summer events)

### Compactness Interpretation
- Circle has compactness = 1 (most compact)
- Lower compactness indicates irregular, multi-front burns
- Large fires in this dataset typically have compactness < 0.5, reflecting complex propagation patterns
