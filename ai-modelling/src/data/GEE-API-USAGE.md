# FireFusion GEE API Documentation

## Overview
The `gee_api.py` module is the core data ingestion engine for the FireFusion project. It leverages the Google Earth Engine (GEE) Python API to extract spatio-temporal environmental data, converting satellite and meteorological observations into structured formats (Pandas DataFrames or NumPy arrays) suitable for Deep Learning models like LSTMs.

### 1. Initialization

To use this module, you must have a Google Cloud Project registered with Earth Engine.

### 2. Authentication
Before running your scripts, authenticate your machine via the terminal:

```bash
earthengine authenticate
```

This will open a browser window where you can log in with your Google account and grant permissions to access Earth Engine data.

### 3. Python Setup

Ensure your `requirements.txt` is installed and the `src` directory is in your Python path.

```bash
from src.data.gee_api import EarthEngineAPI

# Initialize the API with your specific GCP Project ID
api = EarthEngineAPI(project_id='your-gcp-project-id')
```

### 4. Core Functionalities

#### a. Spatial Area Definition

The API uses a **Square Buffer** logic. This ensures pixel alignment and reduces computational overhead compared to circular buffers.

- Method: `create_area(lat, lon, area_km)`
- Logic: Calculates the side length needed to achieve the target square kilometers and returns an `ee.Geometry.2`.

#### b. Mean Time-Series Extraction (`collect_mean_data`)

This is the primary method for training Time-Series LSTMs. It collapses a spatial region into a single average value per time step.

- Output: A Pandas DataFrame with columns: `[time, datetime, latitude, longitude, band_1, ... band_n]`.
- Scale: Defaulted to 500m (ideal for MODIS).

#### c. Raw Spatial Extraction (`collect_raw_data`)

Used for Spatio-Temporal Tensors (CNN-LSTMs) or high-fidelity visualization.

- Output: A raw nested list containing every pixel coordinate and its associated value across the time range.
- Warning: High memory usage. Always use a scale of `500+` for areas $>10km^2$.

### 5. Usage Examples

#### Example 1: Extracting Weather Data (ERA5)

```bash
# Configuration
COORDS = {"lat": -31.2667, "lon": 149.2667} # Example: Warrumbungle National Park
DATES = {"start": "2023-01-01", "end": "2023-12-31"}
BANDS = ['temperature_2m', 'total_precipitation']

# Get spatially averaged weather data
weather_df = api.collect_mean_data(
    dataset='ECMWF/ERA5_LAND/HOURLY',
    bands=BANDS,
    lat=COORDS['lat'],
    lon=COORDS['lon'],
    area_km=25,
    start_date=DATES['start'],
    end_date=DATES['end']
)

print(weather_df.head())
```

#### Example 2: Extracting Satellite Land Temperature (MODIS)

```bash
lst_df = api.collect_mean_data(
    dataset='MODIS/061/MOD11A1',
    bands=['LST_Day_1km'],
    lat=COORDS['lat'],
    lon=COORDS['lon'],
    area_km=10,
    start_date='2024-01-01',
    end_date='2024-02-01'
)
```

### 6. Technical Notes

#### a.Data Reshaping

After using `collect_mean_data`, use the `reshape_to_3d` utility in `data_processing.py` to prepare the data for the LSTM:

- Input: (Total_Steps, Features)
- Output: (Samples, Window_Size, Features)

#### b. Coordinate Reference System (CRS)

All geometries are created in WGS84 (EPSG:4326). When extracting raw data, Earth Engine handles reprojection internally based on the scale parameter provided.

#### c. Memory Management

The `getInfo()` call is a synchronous request. If the request exceeds 10MB or 5,000 elements, GEE may return a "User Memory Limit Exceeded" error. To mitigate this:

- Increase the scale (e.g., from 500 to 1000).
- Shorten the `start_date` and `end_date` range.