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


def load_and_combine_data(n20_path, n_path, modis_path):
    """Load raw satellite CSV exports and combine into single dataframe."""
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
    return df.sort_values(["acq_date", "acq_time"])


def filter_to_victoria(df):
    """Apply bounding box filter to isolate Victorian detections."""
    vic_df = df[(df["latitude"] >= -39.2) &
                (df["latitude"] <= -34.0) &
                (df["longitude"] >= 140.9) &
                (df["longitude"] <= 150.0)
            ].copy()
    return vic_df.sort_values(["acq_date", "acq_time"], ascending=True)


def grid_cells(vic_df):
    """Project to local CRS, snap to 1km² cells, aggregate per pass."""
    gdf = gpd.GeoDataFrame(
        vic_df,
        geometry=gpd.points_from_xy(vic_df.longitude, vic_df.latitude),
        crs="EPSG:4326"
    )
    
    # Project to meters
    gdf = gdf.to_crs(epsg=7855)
    
    # Grid setup
    cell_size = 1000
    xmin, ymin, xmax, ymax = gdf.total_bounds
    xmin = (xmin // cell_size) * cell_size
    ymin = (ymin // cell_size) * cell_size
    
    # Assign cells
    gdf['cell_x'] = ((gdf.geometry.x - xmin) // cell_size).astype(int)
    gdf['cell_y'] = ((gdf.geometry.y - ymin) // cell_size).astype(int)
    
    # Map confidence to numeric
    conf_map = {"l": 1, "n": 2, "h": 3}
    gdf["confidence"] = gdf["confidence"].map(conf_map)
    
    # Aggregate per cell per pass
    grid_df = gdf.groupby(["cell_x", "cell_y", "acq_date", "daynight", "satellite"]).agg(
        brightness=('brightness', 'max'),
        bright_t31=("bright_t31", "max"),
        frp_peak=('frp', 'max'),
        frp_cumulative=('frp', 'sum'),
        geometry=('geometry', 'first'),
        confidence=('confidence', 'max'),
        acq_time=('acq_time', 'max')
    ).reset_index()
    
    # Build cell geometry
    grid_df['geometry'] = grid_df.apply(
        lambda row: box(
            xmin + row.cell_x * cell_size,
            ymin + row.cell_y * cell_size,
            xmin + (row.cell_x + 1) * cell_size,
            ymin + (row.cell_y + 1) * cell_size
        ),
        axis=1
    )
    
    grid_gdf = gpd.GeoDataFrame(grid_df, geometry='geometry', crs=gdf.crs)
    grid_gdf = grid_gdf.to_crs(epsg=4326)
    
    # Rebuild centroids
    grid_gdf['centroid'] = grid_gdf.geometry.centroid
    centroids_latlon = grid_gdf.set_geometry('centroid').to_crs(epsg=4326)
    grid_gdf['longitude'] = centroids_latlon.geometry.x
    grid_gdf['latitude'] = centroids_latlon.geometry.y
    grid_gdf = grid_gdf.drop(columns='centroid')
    
    return grid_gdf.sort_values(by=['acq_date', 'daynight', 'satellite']).reset_index(drop=True)


def engineer_temporal_features(grid_gdf):
    """Build datetime, pass-level timestamps, and time-since-prev-pass."""
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
    """Count burning neighbors at given radius for current timestep."""
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
    """Count burning neighbors in previous timestep."""
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
    """Compute burning neighbors at r=1 and r=2 for current and previous timesteps."""
    grid_gdf["is_burning"] = 1
    
    grid_gdf["burning_neighbors_r1"] = compute_burning_neighbors(grid_gdf, radius=1)
    grid_gdf["burning_neighbors_r2"] = compute_burning_neighbors(grid_gdf, radius=2)
    grid_gdf["burning_neighbors_prev_r1"] = compute_prev_burning_neighbors(grid_gdf, radius=1)
    grid_gdf["burning_neighbors_prev_r2"] = compute_prev_burning_neighbors(grid_gdf, radius=2)
    
    return grid_gdf


def engineer_temporal_targets(grid_gdf):
    """Create previous/next burn state and FRP targets for supervised learning."""
    grid_gdf = grid_gdf.sort_values(["cell_x", "cell_y", "pass_datetime"])
    
    # Previous state
    grid_gdf["is_burning_prev"] = grid_gdf.groupby(["cell_x", "cell_y"])["is_burning"].shift(1).fillna(0).astype(int)
    grid_gdf["frp_prev"] = grid_gdf.groupby(["cell_x", "cell_y"])["frp_peak"].shift(1).fillna(0)
    
    # Next state (targets)
    grid_gdf["is_burning_next"] = grid_gdf.groupby(["cell_x", "cell_y"])["is_burning"].shift(-1).fillna(0).astype(int)
    grid_gdf["frp_next"] = grid_gdf.groupby(["cell_x", "cell_y"])["frp_peak"].shift(-1).fillna(0)
    
    return grid_gdf


def finalize_and_export(grid_gdf, output_csv, output_geojson):
    """Reorder columns, encode categorical features, export to CSV and GeoJSON."""
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
    """Main processing pipeline."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    
    n20_path = os.path.join(data_dir, "fire_archive_J1V-C2_734127.csv")
    n_path = os.path.join(data_dir, "fire_archive_SV-C2_734128.csv")
    modis_path = os.path.join(data_dir, "fire_archive_M-C61_734126.csv")
    
    output_csv = os.path.join(script_dir, output_csv)
    output_geojson = os.path.join(script_dir, output_geojson)
    
    print("Loading satellite data...")
    df = load_and_combine_data(n20_path, n_path, modis_path)
    print(f"  Loaded {len(df)} raw detections")
    
    print("Filtering to Victoria...")
    vic_df = filter_to_victoria(df)
    print(f"  Filtered to {len(vic_df)} Victorian detections")
    
    print("Gridding to 1km² cells...")
    grid_gdf = grid_cells(vic_df)
    print(f"  Created {len(grid_gdf)} gridded records")
    
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
