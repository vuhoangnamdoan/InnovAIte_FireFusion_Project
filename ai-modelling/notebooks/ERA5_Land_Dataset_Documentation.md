# ERA5-Land Dataset Documentation
## Project
FireFusion - Bushfire Forecasting Model

## Purpose
This document explains the dataset selection, feature definition, processing workflow, and modelling relevance of the ERA5-Land dataset used for the FIreFusion bushfire forecasting project.  
The goal is to prepare a structured environmental dataset that supports bushfire occurence prediction and future fire spread modelling across Victoria, Australia. 

## Dataset Selection
### ERA5-Land Hourly Dataset
ERA5-Land was selected because it provides high-quality land and weather variables with hourly temporal resolution and strong historical coverage. 

It is widely used in wildfire research for:
- fire risk prediction
- drought analysis
- land surface temperature monitoring
- wind-driven fire spread modelling

**Dataset ID**: ECMWF/ERA5_LAND/HOURLY

**Source**: Google Earth Engine

**Provider**: European Centre for Medium-Range Weather Forecasts(ECMWF)

### Study Area
Victoria was selected because: 
- it is one of Australia's highest bushfire risk regions
- it includes major historical bushfire events
- it aligns with the FireFusion project scope
- it provides strong relevance for practical model testing

The administrative boundary is extracted using FAO/GAUL/2015/level1

### Time Range Selection
The period chosen is from 2018 to 2022, as this period includes:
- pre-Black Summer conditions
- Black Summer bushfires (2019-2020)
- post-fire recovery patterns

This improves model by covering both normal and extreme fire seasons. 

### Temporal Resolution
**Original Frequency**

ERA5-Land provides hourly environmental observations.

**Target Frequency**

The team modelling decision uses **12-hour prediction intervals**. 
Since ERA5-Land does not directly provide 12-hour data, hourly data is collected first and then aggregated into **12-hour mean intervals**. 

This creates cleaner input for: 
- bushfire risk prediction
- fire event matching
- baseline LSTM model training

### Spatial Design
Instead of using the exact coordinates, the project uses 5km x 5km grid cells.

Each row in the final dataset represents one grid cell during one 12-hour time interval.

This improves:
- model consistency
- fire event matching
- spatial prediction
- satellite fire event integration

This also matches the team's decision to use cell-based fire prediction rather than exact point prediction.

## Defined Features
| Feature | Purpose |
|---|---|
| 'temperature_2m' | Near-surface air temperature |
| 'skin_temperature' | Land surface heat |
| 'soil_temperature_level_1' | Ground heat and dryness |
| 'surface_solar_radiation_downwards' | Fuel drying and solar heating |
| 'surface_thermal_radiation_downwards' | Surface heat balance |
| 'u_component_of_wind_10m' | East-West wind movement |
| 'v_component_of_wind_10m' | North-South wind movement |

## Feature Logic
### Core Ignition Features 
The first five variables mainly support:
- ignition prediction
- dryness detection
- heat accumulation
- fuel condition monitoring

### Wind Features
The wind variables support:
- fire spread direction
- fire movement analysis
- future model extention for fire behaviour prediction

This helps the model move beyond only fire occurrence prediction. 

## Feature Engineering
### Temperature Conversion
ERA5-Land temperature values are originally stored in Kelvin.

They are converted into Celsius for: 
- easier model interpretation
- debugging
- reporting
- team understanding

Converted variables: 
- temperature_2m_c
- skin_temperature_c
- soil_temperature_level_1_c

## Future Integration
This ERA5-Land dataset will later be joined with:
- satellite fire events labels
- thermal hotspot observations
- climate datasets
- topographical variables

This supports the full FireFusion bushfire forecasting pipeline.

## References
ECMWF (2024) ERA5-Land hourly data from 1950 to present

Google Earth Engine (20224) ECMWF/ERA5_LAND/HOURLY dataset documentation

FAO (2015) GAUL Global Administrative Unit Layers

Jain, P. et al. (2020) A review of machine learning applications in wildfire science and management

Abatzoglou, J.T. and Williams, A.P. (2016) Impact of anthropogenic climate change on wildfire across western US forests
