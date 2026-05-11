"""
VIIRS Satellite Fire Detection Processing
Combines VIIRS/MODIS data, grids to 1km² cells, engineers temporal/spatial features.
Output: satellite_fire_data.csv, satellite_fire_data.geojson
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import box
from scipy.spatial import cKDTree
import os

def load_victoria_boundary(boundary_geojson_path):
    """Load Victoria boundary from exported GEE GeoJSON.
    
    Parameters:
        boundary_geojson_path (str): Path to victoria_boundary_fao_gaul_2015.geojson
    
    Returns:
        victoria_gdf (GeoDataFrame): Victoria boundary polygon in EPSG:4326
    """
    victoria_gdf = gpd.read_file(boundary_geojson_path)
    
    if victoria_gdf.crs != 'EPSG:4326':
        victoria_gdf = victoria_gdf.to_crs('EPSG:4326')
    
    print(f"Loaded Victoria boundary from {boundary_geojson_path}")
    
    return victoria_gdf


def load_and_combine_data(n20_path, n_path, modis_path):
    """Load raw satellite CSV exports and combine into single dataframe with unified confidence values.
    
    Parameters:
        n20_path (str): Path to NOAA-20 (J1) VIIRS detections CSV
        n_path (str): Path to NOAA (S-NPP) VIIRS detections CSV
        modis_path (str): Path to MODIS detections CSV
    
    Returns:
        df (DataFrame): Combined detections from all three sources with columns [acq_date, acq_time, brightness, bright_t31, frp, confidence, latitude, longitude, daynight, satellite]; 
            confidence mapped to "l"(low), "n"(medium), "h"(high); sorted by acq_date, acq_time
    """
    n20_df = pd.read_csv(n20_path)
    n_df = pd.read_csv(n_path)
    m_df = pd.read_csv(modis_path)
    
    # Map MODIS confidence to match VIIRS
    def map_confidence(val):
        if pd.isna(val):
            return None
        elif val <= 30:
            return "l"
        elif val >= 70:
            return "h"
        else:
            return "n"
    
    m_df["confidence"] = m_df["confidence"].apply(map_confidence)
    
    df = pd.concat([n20_df, n_df, m_df], ignore_index=True)
    
    return df


def filter_to_victoria(df, victoria_boundary_gdf):
    """Apply Victoria boundary filter to isolate Victorian detections.
    
    Parameters:
        df (DataFrame): Raw satellite detections with latitude, longitude columns
        victoria_boundary_gdf (GeoDataFrame): Victoria boundary polygon
    
    Returns:
        vic_df (DataFrame): Filtered detections within Victoria boundary polygon; sorted by acq_date, acq_time
    """
    # Create GeoDataFrame from detections
    gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )
    
    # Clip to Victoria boundary
    vic_gdf = gpd.clip(gdf, victoria_boundary_gdf)
    
    # Convert back to DataFrame
    vic_df = pd.DataFrame(vic_gdf.drop(columns='geometry'))
    
    return vic_df.sort_values(["acq_date", "acq_time"], ascending=True)

def grid_cells_gee_aligned(vic_df, victoria_boundary_gdf, grid_scale=5000):
    """Project to local CRS, snap to 5km² cells, clip with Victoria geometry, aggregate per cell per satellite pass.
    
    Parameters:
        vic_df (DataFrame): Victorian detections with latitude, longitude, confidence, brightness, bright_t31, frp, acq_date, acq_time, daynight, satellite
        victoria_boundary_gdf: GeoDataFrame containing the boundaries for Victoria
    
    Returns:
        grid_gdf (GeoDataFrame): Gridded aggregates with columns [cell_x, cell_y, acq_date, daynight, satellite, brightness (max), bright_t31 (max), frp_peak (max), frp_cumulative (sum), confidence (max), 
            acq_time (max), geometry (1km² cell as Polygon), longitude, latitude]; CRS EPSG:4326; sorted by acq_date, daynight, satellite; one row per unique (cell_x, cell_y, acq_date, daynight, satellite) group
    """
    
    # Build Vic GeoDataFrame
    gdf = gpd.GeoDataFrame(
        vic_df,
        geometry=gpd.points_from_xy(vic_df.longitude, vic_df.latitude),
        crs="EPSG:4326"
    )
    gdf = gdf.to_crs(epsg=3857)
    
    victoria_3857 = victoria_boundary_gdf.to_crs(epsg=3857)
    xmin, ymin, xmax, ymax = victoria_3857.total_bounds
    
    # Snap to grid intervals
    xmin_grid = (xmin // grid_scale) * grid_scale
    ymin_grid = (ymin // grid_scale) * grid_scale
    xmax_grid = ((xmax // grid_scale) + 1) * grid_scale
    ymax_grid = ((ymax // grid_scale) + 1) * grid_scale
    
    gdf['cell_x'] = ((gdf.geometry.x - xmin_grid) // grid_scale).astype(int)
    gdf['cell_y'] = ((gdf.geometry.y - ymin_grid) // grid_scale).astype(int)
    
    # Build grid_id
    gdf['grid_id'] = gdf.apply(
        lambda row: int(row.cell_y * 1000000 + row.cell_x),
        axis=1
    )
    
    # Map confidence
    conf_map = {"l": 1, "n": 2, "h": 3}
    gdf["confidence"] = gdf["confidence"].map(conf_map)
    
    # Aggregate within grid cells
    grid_df = gdf.groupby(
        ["grid_id", "cell_x", "cell_y", "acq_date", "daynight", "satellite"]
    ).agg(
        brightness=('brightness', 'max'),
        bright_t31=("bright_t31", "max"),
        frp_peak=('frp', 'max'),
        frp_cumulative=('frp', 'sum'),
        confidence=('confidence', 'max'),
        acq_time=('acq_time', 'max')
    ).reset_index()
    
    # Build cell geometry
    grid_df['geometry'] = grid_df.apply(
        lambda row: box(
            xmin_grid + row.cell_x * grid_scale,
            ymin_grid + row.cell_y * grid_scale,
            xmin_grid + (row.cell_x + 1) * grid_scale,
            ymin_grid + (row.cell_y + 1) * grid_scale
        ),
        
        axis=1
    )
    
    grid_gdf = gpd.GeoDataFrame(grid_df, geometry='geometry', crs=3857)
    
    # Clip to Victoria boundary, only keep cells in Victoria
    print(f"Clipping grid to Victoria boundary... -- expensive operation, may take several minute")
    
    grid_gdf = gpd.clip(grid_gdf, victoria_3857)
    
    print(f"Clipped to Victoria boundary")
    
    grid_gdf = grid_gdf.to_crs(epsg=4326)
    
    # Build centroid longitudes/latitudes
    grid_gdf['longitude'] = grid_gdf.geometry.centroid.x
    grid_gdf['latitude'] = grid_gdf.geometry.centroid.y
    
    grid_gdf = grid_gdf.sort_values(
        by=['acq_date', 'daynight', 'satellite']
    ).reset_index(drop=True)
    
    return grid_gdf


def engineer_temporal_features(grid_gdf):
    """Build datetime, pass-level timestamps, and time-since-prev-pass.
    
    Parameters:
        grid_gdf (GeoDataFrame): Gridded detections with acq_date (YYYY-MM-DD), acq_time (HHMM), satellite, daynight columns
    
    Returns:
        grid_gdf (GeoDataFrame): Same dataset with new columns: datetime (merged acq_date + acq_time, timezone-naive), pass_datetime (min datetime per satellite/acq_date/daynight group), 
            time_since_prev_pass (seconds since previous pass for same satellite, 0 for first pass); sorted by pass_datetime
    """
    grid_gdf["datetime"] = pd.to_datetime(
        grid_gdf["acq_date"].astype(str) + " " + grid_gdf["acq_time"].astype(str).str.zfill(4),
        format="%Y-%m-%d %H%M"
    )
    
    # Group by satellite pass
    grid_gdf["pass_datetime"] = (
        grid_gdf.groupby(["satellite", "acq_date", "daynight"])["datetime"]
        .transform("min")
    )
    
    # Compute time since previous pass
    timestep_order = (
        grid_gdf[["pass_datetime", "satellite"]]
        .drop_duplicates()
        .sort_values("pass_datetime")
        .reset_index(drop=True)
    )
    timestep_order["prev_pass_datetime"] = timestep_order["pass_datetime"].shift(1)
    
    grid_gdf = grid_gdf.merge(
        timestep_order[["pass_datetime", "satellite", "prev_pass_datetime"]],
        on=["pass_datetime", "satellite"],
        how="left"
    )
    grid_gdf["time_since_prev_pass"] = (
        grid_gdf["pass_datetime"] - grid_gdf["prev_pass_datetime"]
    ).dt.total_seconds().fillna(0)
    
    return grid_gdf.sort_values("pass_datetime").reset_index(drop=True)


def compute_burning_neighbors(df, radius=2):
    """Count burning neighbors at given radius for current timestep.
    
     Parameters:
        df (DataFrame): Gridded detections with cell_x, cell_y, pass_datetime, is_burning columns
        radius (int): Search radius in cells (default 2); uses Chebyshev distance approximation (radius * sqrt(2))
    
    Returns:
        neighbors (ndarray): Integer count of burning neighbors per row; same length as input
    """
    neighbors = np.zeros(len(df), dtype=int)
    
    for pass_dt, group in df.groupby("pass_datetime"):
        coords = np.vstack([group["cell_x"], group["cell_y"]]).T
        burning = group["is_burning"].values
        
        tree = cKDTree(coords)
        idxs = tree.query_ball_tree(tree, r=radius * np.sqrt(2))
        
        for i, neigh in enumerate(idxs):
            neighbors[group.index[i]] = burning[neigh].sum() - burning[i]
    
    return neighbors


def compute_prev_burning_neighbors(df, radius=2):
    """Count burning neighbors in previous timestep.
    
     Parameters:
        df (DataFrame): Gridded detections with cell_x, cell_y, pass_datetime, is_burning columns
        radius (int): Search radius in cells (default 2); uses Chebyshev distance approximation (radius * sqrt(2))
    
    Returns:
        neighbors (ndarray): Float count of burning neighbors in previous pass per row; same length as input; 0 for first pass or if no previous data exists
    """
    neighbors = np.zeros(len(df), dtype=float)
    pass_times = df["pass_datetime"].drop_duplicates().sort_values().values
    
    for i, curr_pass in enumerate(pass_times):
        curr = df[df["pass_datetime"] == curr_pass]
        
        if i == 0:
            neighbors[curr.index] = 0
            continue
        
        prev_pass = pass_times[i - 1]
        prev = df[df["pass_datetime"] == prev_pass]
        
        if prev.empty:
            neighbors[curr.index] = 0
            continue
        
        prev_coords = np.vstack([prev["cell_x"], prev["cell_y"]]).T
        curr_coords = np.vstack([curr["cell_x"], curr["cell_y"]]).T
        
        tree = cKDTree(prev_coords)
        idxs = tree.query_ball_point(curr_coords, r=radius * np.sqrt(2))
        
        for j, neigh in zip(curr.index, idxs):
            neighbors[j] = len(neigh)
    
    return neighbors


def engineer_spatial_features(grid_gdf):
    """Compute burning neighbors at r=1 and r=2 for current and previous timesteps.
    
    Parameters:
        grid_gdf (GeoDataFrame): Gridded detections with cell_x, cell_y, pass_datetime columns
    
    Returns:
        grid_gdf (GeoDataFrame): Same dataset with new columns: is_burning (constant 1 for all rows, indicator of detection), burning_neighbors_r1 (neighbors at radius 1 now), burning_neighbors_r2 (neighbors at radius 2 now), 
            burning_neighbors_prev_r1 (neighbors at radius 1 in previous pass), burning_neighbors_prev_r2 (neighbors at radius 2 in previous pass)
    """
    grid_gdf["is_burning"] = 1
    
    grid_gdf["burning_neighbors_r1"] = compute_burning_neighbors(grid_gdf, radius=1)
    grid_gdf["burning_neighbors_r2"] = compute_burning_neighbors(grid_gdf, radius=2)
    grid_gdf["burning_neighbors_prev_r1"] = compute_prev_burning_neighbors(grid_gdf, radius=1)
    grid_gdf["burning_neighbors_prev_r2"] = compute_prev_burning_neighbors(grid_gdf, radius=2)
    
    return grid_gdf


def engineer_temporal_targets(grid_gdf):
    """Create lagged (previous) and lead (next) burn state and FRP values for supervised learning.
    
    Parameters:
        grid_gdf (GeoDataFrame): Gridded detections with cell_x, cell_y, pass_datetime, is_burning, frp_peak columns
    
    Returns:
        grid_gdf (GeoDataFrame): Same dataset with new columns: is_burning_prev (previous burn state, 0 for first pass per cell), frp_prev (previous FRP, 0 for first pass per cell), 
            is_burning_next (next burn state, 0 for last pass per cell), frp_next (next FRP, 0 for last pass per cell); all new columns are numeric (int or float)
    """
    grid_gdf = grid_gdf.sort_values(["cell_x", "cell_y", "pass_datetime"])
    
    # Previous state
    grid_gdf["is_burning_prev"] = grid_gdf.groupby(["cell_x", "cell_y"])["is_burning"].shift(1).fillna(0).astype(int)
    grid_gdf["frp_prev"] = grid_gdf.groupby(["cell_x", "cell_y"])["frp_peak"].shift(1).fillna(0)
    
    # Next state (targets)
    grid_gdf["is_burning_next"] = grid_gdf.groupby(["cell_x", "cell_y"])["is_burning"].shift(-1).fillna(0).astype(int)
    grid_gdf["frp_next"] = grid_gdf.groupby(["cell_x", "cell_y"])["frp_peak"].shift(-1).fillna(0)
    
    return grid_gdf


def finalize_and_export(grid_gdf, output_csv, output_geojson):
    """Encode categorical features, reorder columns, and export to CSV and GeoJSON formats.
    
    Parameters:
        grid_gdf (GeoDataFrame): Complete satellite data with all engineered features; daynight column contains "D" or "N" values
        output_csv (str): Output file path for CSV (e.g., "satellite_fire_data.csv")
        output_geojson (str): Output file path for GeoJSON (e.g., "satellite_fire_data.geojson")
    
    Returns:
        grid_gdf (GeoDataFrame): Same dataset with daynight encoded as numeric (0=Day, 1=Night), columns reordered to fixed sequence [cell_x, cell_y, datetime, daynight, satellite, time_since_prev_pass, confidence, is_burning, brightness, bright_t31, 
            frp_peak, frp_cumulative, burning_neighbors_r1, burning_neighbors_r2, is_burning_prev, frp_prev, burning_neighbors_prev_r1, burning_neighbors_prev_r2, is_burning_next, frp_next, longitude, latitude, geometry], sorted by pass_datetime; 
        writes CSV and GeoJSON files to disk, prints record count and file paths
    """
    # Encode daynight
    grid_gdf["daynight"] = grid_gdf["daynight"].map({"D": 0, "N": 1})
    
    grid_gdf = grid_gdf.sort_values("pass_datetime").reset_index(drop=True)
    
    # Column ordering
    new_order = [
        "cell_x", "cell_y", "datetime", "daynight", "satellite", "time_since_prev_pass",
        "confidence", "is_burning", "brightness", "bright_t31", "frp_peak", "frp_cumulative",
        "burning_neighbors_r1", "burning_neighbors_r2",
        "is_burning_prev", "frp_prev", "burning_neighbors_prev_r1", "burning_neighbors_prev_r2",
        "is_burning_next", "frp_next",
        "longitude", "latitude", "geometry"
    ]
    
    grid_gdf = grid_gdf[new_order]
    
    # Export
    grid_gdf.to_csv(output_csv, index=False)
    grid_gdf.to_file(output_geojson, driver="GeoJSON")
    
    print(f"Exported {len(grid_gdf)} records to {output_csv}")
    print(f"Exported GeoJSON to {output_geojson}")
    return grid_gdf

def main(output_csv="satellite_fire_data.csv", output_geojson="satellite_fire_data.geojson"):
    """Main processing pipeline.
    
    Parameters:
        output_csv (str): Output filename for CSV (default "satellite_fire_data.csv")
        output_geojson (str): Output filename for GeoJSON (default "satellite_fire_data.geojson")
    
    Returns:
        grid_gdf (GeoDataFrame): Complete processed satellite dataset with temporal/spatial features and ML targets
        writes CSV and GeoJSON files to script directory, prints progress messages at each pipeline stage
    """
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    
    boundary_geojson_path = os.path.join(data_dir, "victoria_boundary_fao_gaul_2015.geojson")
    
    n20_path = os.path.join(data_dir, "fire_archive_J1V-C2_734127.csv")
    n_path = os.path.join(data_dir, "fire_archive_SV-C2_734128.csv")
    modis_path = os.path.join(data_dir, "fire_archive_M-C61_734126.csv")
    
    output_csv = os.path.join(script_dir, output_csv)
    output_geojson = os.path.join(script_dir, output_geojson)
    
    print("Loading Victoria boundary from GEE...")
    victoria_boundary = load_victoria_boundary(boundary_geojson_path)
    
    print("Loading satellite data...")
    df = load_and_combine_data(n20_path, n_path, modis_path)
    print(f"Loaded {len(df)} raw detections")
    
    print("Filtering to Victoria...")
    vic_df = filter_to_victoria(df, victoria_boundary)
    print(f"Filtered to {len(vic_df)} Victorian detections")
    
    print("Gridding to 5km² cells...")
    grid_gdf = grid_cells_gee_aligned(vic_df, victoria_boundary, 5000)
    print(f"Created {len(grid_gdf)} gridded records")
    
    print("Engineering temporal features...")
    grid_gdf = engineer_temporal_features(grid_gdf)
    
    print("Engineering spatial features (neighbors)...")
    grid_gdf = engineer_spatial_features(grid_gdf)
    
    print("Engineering temporal targets...")
    grid_gdf = engineer_temporal_targets(grid_gdf)
    
    print("Finalizing and exporting...")
    grid_gdf = finalize_and_export(grid_gdf, output_csv, output_geojson)
    
    return grid_gdf


if __name__ == "__main__":
    # Run pipeline
    result = main()
    print("\nProcessing complete!")
    print(result.head())
