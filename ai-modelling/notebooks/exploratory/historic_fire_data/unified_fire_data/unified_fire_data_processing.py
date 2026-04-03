"""
Unified Historical Bushfire Events and Satellite Detection Dataset
Match VIIRS/MODIS satellite detections to ground-truth bushfire polygons and extract 
estimated extinguish dates, burn durations, and FRP measures (severity).
Output: unified_historic_fire_dataset.csv, unified_historic_fire_dataset.geojson
"""

import pandas as pd
import geopandas as gpd
from shapely import wkt
import os


def load_data(satellite_path, bushfire_path):
    """Load satellite and bushfire datasets as GeoDataFrames."""
    viirs_df = pd.read_csv(satellite_path)
    bushfire_df = pd.read_csv(bushfire_path)
    
    viirs_gdf = gpd.GeoDataFrame(
        viirs_df,
        geometry=viirs_df["geometry"].apply(wkt.loads),
        crs="EPSG:4326"
    )
    
    bushfire_gdf = gpd.GeoDataFrame(
        bushfire_df,
        geometry=bushfire_df["geometry"].apply(wkt.loads),
        crs="EPSG:4326"
    )
    
    return viirs_gdf, bushfire_gdf


def assign_synthetic_ids(bushfire_gdf):
    """Assign synthetic IDs to fires without official IDs."""
    null_mask = bushfire_gdf["fire_id"].isna()
    synthetic_ids = range(-1, -null_mask.sum() - 1, -1)
    bushfire_gdf.loc[null_mask, "fire_id"] = list(synthetic_ids)
    return bushfire_gdf


def spatial_join(viirs_gdf, bushfire_gdf):
    """Perform spatial join between detections and fire polygons."""
    joined = gpd.sjoin(
        viirs_gdf,
        bushfire_gdf[["fire_id", "ignition_date", "geometry"]],
        how="inner",
        predicate="intersects"
    )
    
    # Standardize datetime formats
    joined["datetime"] = pd.to_datetime(joined["datetime"], utc=True).dt.tz_localize(None)
    joined["ignition_date"] = pd.to_datetime(joined["ignition_date"], utc=True).dt.tz_localize(None)
    
    return joined


def filter_by_temporal_window(joined, window_days=120):
    """Filter detections to temporal window around ignition."""
    joined = joined[
        (joined["datetime"] >= (joined["ignition_date"] - pd.Timedelta(days=1))) &
        (joined["datetime"] <= (joined["ignition_date"] + pd.Timedelta(days=window_days)))
    ]
    
    # Find first detection per fire
    first_detection = (
        joined.groupby("fire_id")["datetime"]
        .min()
        .rename("first_detection")
        .reset_index()
    )
    joined = joined.merge(first_detection, on="fire_id", how="left")
    
    # Keep only fires with first detection within 4 days of ignition
    joined = joined[
        joined["first_detection"] <= (joined["ignition_date"] + pd.Timedelta(days=4))
    ]
    
    joined = joined.drop(columns="first_detection")
    return joined


def estimate_extinguish_dates(joined, gap_threshold_days=4):
    """Estimate extinguish dates from detection gaps."""
    joined = joined.sort_values(["fire_id", "datetime"])
    
    # Calculate gaps between consecutive detections
    joined["next_datetime"] = joined.groupby("fire_id")["datetime"].shift(-1)
    joined["gap_to_next_days"] = (
        (joined["next_datetime"] - joined["datetime"])
        .dt.total_seconds() / 86400
    )
    
    # Identify first significant gap
    joined["is_gap"] = (
        (joined["gap_to_next_days"] > gap_threshold_days) |
        joined["next_datetime"].isna()
    )
    
    first_gap = (
        joined[joined["is_gap"]]
        .groupby("fire_id")
        .first()
        .reset_index()
    )
    
    extinguish_dates = first_gap[["fire_id", "datetime"]].rename(
        columns={"datetime": "extinguish_date"}
    )
    
    return extinguish_dates


def merge_extinguish_dates(bushfire_gdf, extinguish_dates):
    """Merge estimated extinguish dates onto bushfire dataset."""
    bushfire_gdf = bushfire_gdf.merge(extinguish_dates, on="fire_id", how="left")
    bushfire_gdf["extinguish_date"] = pd.to_datetime(bushfire_gdf["extinguish_date"])
    bushfire_gdf["ignition_date"] = pd.to_datetime(bushfire_gdf["ignition_date"]).dt.tz_localize(None)
    
    return bushfire_gdf


def calculate_duration(bushfire_gdf):
    """Calculate fire duration and handle edge cases."""
    # Handle late ignition dates
    lag_mask = bushfire_gdf["extinguish_date"] < bushfire_gdf["ignition_date"]
    bushfire_gdf.loc[lag_mask, "extinguish_date"] = (
        pd.to_datetime(bushfire_gdf.loc[lag_mask, "ignition_date"]) + pd.Timedelta(hours=6)
    )
    
    # Calculate duration in days
    bushfire_gdf["duration_days"] = (
        (bushfire_gdf["extinguish_date"] - bushfire_gdf["ignition_date"])
        .dt.total_seconds() / 86400
    ).round(2)
    
    return bushfire_gdf


def extract_frp_severity(joined, bushfire_gdf):
    """Extract peak and cumulative FRP severity measures."""
    peak_severity = joined.groupby("fire_id")["frp_peak"].max().rename("peak_frp")
    bushfire_gdf = bushfire_gdf.merge(peak_severity, on="fire_id", how="left")
    
    cumulative_severity = joined.groupby("fire_id")["frp_cumulative"].sum().rename("cumulative_frp")
    bushfire_gdf = bushfire_gdf.merge(cumulative_severity, on="fire_id", how="left")
    
    return bushfire_gdf


def classify_detection_status(joined, bushfire_gdf):
    """Classify detection status and count detections."""
    detection_counts = (
        joined.groupby("fire_id")["datetime"]
        .count()
        .rename("viirs_detection_count")
        .reset_index()
    )
    
    bushfire_gdf = bushfire_gdf.merge(detection_counts, on="fire_id", how="left")
    bushfire_gdf["viirs_detection_count"] = bushfire_gdf["viirs_detection_count"].fillna(0).astype(int)
    
    bushfire_gdf["detection_status"] = bushfire_gdf["viirs_detection_count"].apply(
        lambda x: "never_detected" if x == 0 else "detected"
    )
    
    return bushfire_gdf


def handle_undetected_fires(bushfire_gdf):
    """Impute undetected small/medium fires; flag large/mega fires."""
    # Small/medium undetected fires: impute as 6-hour burns
    small_mask = (
        (bushfire_gdf["detection_status"] == "never_detected") &
        (bushfire_gdf["size_class"].isin(["small", "medium"]))
    )
    
    bushfire_gdf.loc[small_mask, "extinguish_date"] = (
        pd.to_datetime(bushfire_gdf.loc[small_mask, "ignition_date"]) + pd.Timedelta(hours=6)
    )
    bushfire_gdf.loc[small_mask, "duration_days"] = 6 / 24
    bushfire_gdf.loc[small_mask, "detection_status"] = "imputed_same_day"
    
    # Large/mega undetected fires: flag as coverage gap
    coverage_gap_mask = (
        (bushfire_gdf["detection_status"] == "never_detected") &
        (bushfire_gdf["size_class"].isin(["large", "mega"]))
    )
    
    bushfire_gdf.loc[coverage_gap_mask, "detection_status"] = "coverage_gap"
    
    return bushfire_gdf


def finalize_and_export(bushfire_gdf, output_csv, output_geojson):
    """Finalize dataset, reorder columns, and export."""
    column_order = [
        "fire_id", "fire_name", "ignition_date", "extinguish_date", "duration_days",
        "detection_status", "season", "fire_type", "size_class", "area_ha", "perim_km",
        "compactness", "log_area", "peak_frp", "cumulative_frp",
        "SHAPE_Length", "SHAPE_Area", "geometry"
    ]
    
    bushfire_gdf = bushfire_gdf[column_order]
    bushfire_gdf = bushfire_gdf.sort_values(["ignition_date", "fire_id"], ascending=True)
    bushfire_gdf = bushfire_gdf.to_crs(epsg=4326)
    
    # Export
    bushfire_gdf.to_csv(output_csv, index=False)
    bushfire_gdf.to_file(output_geojson, driver="GeoJSON")
    
    print(f"Exported csv to {output_csv}")
    print(f"Exported GeoJSON to {output_geojson}")
    
    return bushfire_gdf


def main(output_csv="unified_historic_fire_dataset.csv", output_geojson="unified_historic_fire_dataset.geojson"):
    """Main processing pipeline."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    # Paths to input datasets
    satellite_path = os.path.join(parent_dir, "satellite_fire_data", "satellite_fire_data.csv")
    bushfire_path = os.path.join(parent_dir, "historic_fire_events_data", "historic_fire_extents_data.csv")
    
    # Output paths
    output_csv = os.path.join(script_dir, output_csv)
    output_geojson = os.path.join(script_dir, output_geojson)
    
    print("Loading satellite and bushfire datasets...")
    viirs_gdf, bushfire_gdf = load_data(satellite_path, bushfire_path)
    print(f"  Loaded {len(viirs_gdf)} satellite detections")
    print(f"  Loaded {len(bushfire_gdf)} bushfire records")
    
    print("Assigning synthetic IDs for fires lacking IDs...")
    bushfire_gdf = assign_synthetic_ids(bushfire_gdf)
    
    print("Performing spatial join...")
    joined = spatial_join(viirs_gdf, bushfire_gdf)

    print("Filtering by desired datetime...")
    joined = filter_by_temporal_window(joined)
  
    print("Estimating extinguish dates from detection gaps...")
    extinguish_dates = estimate_extinguish_dates(joined)
    
    print("Merging extinguish dates...")
    bushfire_gdf = merge_extinguish_dates(bushfire_gdf, extinguish_dates)
    
    print("Calculating fire duration...")
    bushfire_gdf = calculate_duration(bushfire_gdf)
    
    print("Building FRP severity measures...")
    bushfire_gdf = extract_frp_severity(joined, bushfire_gdf)
    
    print("Classifying detection status...")
    bushfire_gdf = classify_detection_status(joined, bushfire_gdf)
    
    print("Handling undetected fires...")
    bushfire_gdf = handle_undetected_fires(bushfire_gdf)
    
    print("Finalizing and exporting...")
    bushfire_gdf = finalize_and_export(bushfire_gdf, output_csv, output_geojson)
    
    return bushfire_gdf


if __name__ == "__main__":
    result = main()
    print("\nProcessing complete!")
    print(result.head())
