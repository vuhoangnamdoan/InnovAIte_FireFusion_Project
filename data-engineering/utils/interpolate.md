# interpolate.py

Grid interpolation util for the FireFusion data pipeline.

---

## Overview

This module provides two functions for loading the FireFusion location registry grid from Supabase and interpolating any sparse spatial dataset onto every point in that grid.

The grid is the universal 1km spatial reference shared across all observation tables. It is loaded once and reused across all interpolation calls.

---

## How It Fits the Architecture

The FireFusion database uses a Hub and Spoke model. All observation tables (Weather, Vegetation, Fire) store sparse source points with original coordinates. This module takes those sparse points and produces a value at every grid location, making the data ready for the ML model.

| Stage | What Happens |
|---|---|
| Ingestion | Sparse observations stored in Supabase with `original_latitude` / `original_longitude` |
| `fetch_grid()` | Full `location_registry` loaded into memory once |
| `interpolate_to_grid()` | Sparse points expanded to all 400k grid locations via scipy griddata |
| ML Input | Every grid point has a complete feature vector |

---

## Functions

### `fetch_grid()`

Loads the full `location_registry` table from Supabase into a private `_df_grid` variable. Returns the DataFrame but also stores it internally so `interpolate_to_grid` can reference it without being passed it explicitly.

**Call this once at the start of your session.** The grid is static and never changes between runs, so there is no reason to reload it every time.

```python
from interpolate import fetch_grid, interpolate_to_grid

fetch_grid()  # run once
```

> If you forget to call `fetch_grid()`, `interpolate_to_grid()` will detect that `_df_grid` is empty and call it automatically as a failsafe. A warning will be printed to console when this happens.

---

### `interpolate_to_grid(df_source, lat_col, lon_col, method="cubic")`

Interpolates a sparse observation DataFrame onto every point in the location registry grid using scipy griddata. Returns a **copy** of `_df_grid` with the interpolated columns added. The internal `_df_grid` is never modified.

| Argument | Type | Description |
|---|---|---|
| `df_source` | DataFrame | Sparse observations to interpolate. See requirements below. |
| `lat_col` | str | Name of the latitude column in `df_source`. |
| `lon_col` | str | Name of the longitude column in `df_source`. |
| `method` | str | `"cubic"` (default) or `"nearest"`. See method guide below. |

---

## Requirements for df_source

### 1. Single timestamp only

Filter your data to one point in time before passing it in. Mixing multiple timestamps will produce meaningless spatial interpolation.

```python
# correct
df_now = df_weather[df_weather["time"] == "2026-05-10T14:00"]
interpolate_to_grid(df_now, lat_col="lat", lon_col="lon")

# wrong -- multiple timestamps mixed together
interpolate_to_grid(df_weather, lat_col="lat", lon_col="lon")
```

### 2. Source points should extend beyond Victoria's boundary

Cubic interpolation only works within the convex hull of the source points. If your observation points stop exactly at Victoria's border, grid points near the edges will have no coverage and fall back to nearest-neighbour, which can produce hard edges in the output surface.

| Direction | Victoria Boundary | Recommended Source Coverage |
|---|---|---|
| Latitude | -33.5 to -40.0 | -32.0 to -42.0 |
| Longitude | 140.0 to 151.0 | 138.0 to 153.0 |

> For Open-Meteo this is free -- just extend the sample grid a few degrees past the state border. For satellite data (SMAP, FIRMS) the raw continental source already covers this range automatically.

---

## Method Guide

| Method | Use For | Tables |
|---|---|---|
| `cubic` | Smooth continuous fields | `weather_observation`, `vegetation_condition`, `topography_profile` |
| `nearest` | Discrete or point events | `fire_incident_record`, `infrastructure_asset` |

> NaN values that appear at edge grid points after cubic interpolation (outside the convex hull) are automatically filled with nearest-neighbour as a fallback. The output will never contain gaps.

---

## Full Example

```python
from interpolate import fetch_grid, interpolate_to_grid

# load grid once at session start
fetch_grid()

ts = "2026-05-10T14:00"

# filter each source to a single timestamp
df_weather_now    = df_weather[df_weather["time"] == ts]
df_vegetation_now = df_vegetation[df_vegetation["time"] == ts]
df_fire_now       = df_fire[df_fire["time"] == ts]

# interpolate each source onto the grid
df_weather_grid    = interpolate_to_grid(df_weather_now,    lat_col="lat", lon_col="lon")
df_vegetation_grid = interpolate_to_grid(df_vegetation_now, lat_col="lat", lon_col="lon")
df_fire_grid       = interpolate_to_grid(df_fire_now,       lat_col="lat", lon_col="lon", method="nearest")
df_topo_grid       = interpolate_to_grid(df_topo,           lat_col="original_latitude",  lon_col="original_longitude")

# merge all into one grid
df_final = df_weather_grid.merge(
    df_vegetation_grid.drop(columns=["grid_latitude", "grid_longitude"]), on="location_id"
).merge(
    df_fire_grid.drop(columns=["grid_latitude", "grid_longitude"]), on="location_id"
)
```

---

## Extra

- All numeric columns in `df_source` (except lat/lon) are interpolated automatically. No need to specify which variables -- the function detects them.
- String and datetime columns are ignored and will not appear in the output.
- Each call to `interpolate_to_grid` returns a fresh copy of `_df_grid`. The base grid is never modified, so you can call the function multiple times safely.
- `fetch_grid()` only needs to be called once per session. Calling it again will reload all 400k rows unnecessarily.