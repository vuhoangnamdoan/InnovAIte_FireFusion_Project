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
    """ 
    Loads satellite and bushfire datasets as GeoDataFrames with WKT Geometry.
    
    Parameters:
        satellite_path (str): Path to CSV with VIIRS/MODIS detections (datetime, geometry, frp_peak, frp_cumulative columns)
        bushfire_path (str): Path to CSV with bushfire polygons (fire_id, ignition_date, geometry columns)
    
    Returns:
        viirs_gdf (GeoDataFrame): Satellite detections with Point/Polygon geometry, CRS EPSG:4326
        bushfire_gdf (GeoDataFrame): Bushfire polygons with Polygon geometry, CRS EPSG:4326
    """

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
    """
    Assign synthetic IDs to fires without official IDs.
    
    Parameters:
        bushfire_gdf (GeoDataFrame): Bushfire records with fire_id column containign some NaN values
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with fire_id column filled; synthetic IDs start from -1
    """

    null_mask = bushfire_gdf["fire_id"].isna()
    synthetic_ids = range(-1, -null_mask.sum() - 1, -1)
    bushfire_gdf.loc[null_mask, "fire_id"] = list(synthetic_ids)
    return bushfire_gdf


def spatial_join(viirs_gdf, bushfire_gdf):
    """Perform spatial join between detections and fire polygons using geometry intersection.
    
    Parameters:
        viirs_gdf (GeoDataFrame): Satellite detections with datetime, geometry, frp_peak, frp_cumulative
        bushfire_gdf (GeoDataFrame): Bushfire polygons with filled fire_id, ignition_date, geometry columns
    
    Returns:
        joined (GeoDataFrame): Inner join of detections to fires (intersects predicate); contains all viirs columns plus fire_id, ignition_date; datetime and ignition_date formated as UTC timezone-naive
    """
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
    """Filter detections to temporal window around ignition and exlude fires with late detection.
    
    Parameters:
        joined (GeoDataFrame): Matched detections from spatial_join() with datetime, ignition_date, fire_id
        window_days (int): Max days after ignition to include detections (default 120); Safety net
    
    Returns:
        joined (GeoDataFrame): Filtered dataset with only detections in [ignition_date - 1 day, ignition_date + window_days] and fires where first detection <= ignition_date + 4 days
    """
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
    """Infer fire extinguish dates from detection gaps.
    
    Parameters:
        joined (GeoDataFrame): Filtered detections from filter_by_temporal_window() with fire_id, datetime
        gap_threshold_days (int): Minimum gap in days to infer fire is extinguished (default 4)
    
    Returns:
        extinguish_dates (DataFrame): Two columns [fire_id, extinguish_date]; extinguish_date is datetime of last detection before gap; one row per fire
    """
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
    """Add estimated extinguish dates onto bushfire dataset via left merge.
    
    Parameters:
        bushfire_gdf (GeoDataFrame): Original bushfire records with fire_id column
        extinguish_dates (DataFrame): Output from estimate_extinguish_dates() with [fire_id, extinguish_date]
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with new extinguish_date column (NaT for undetected fires);
    """
    bushfire_gdf = bushfire_gdf.merge(extinguish_dates, on="fire_id", how="left")
    bushfire_gdf["extinguish_date"] = pd.to_datetime(bushfire_gdf["extinguish_date"])
    bushfire_gdf["ignition_date"] = pd.to_datetime(bushfire_gdf["ignition_date"]).dt.tz_localize(None)
    
    return bushfire_gdf


def calculate_duration(bushfire_gdf):
    """Calculate fire duration and handle late recorded ignition data edge cases.
    
    Parameters:
        bushfire_gdf (GeoDataFrame): Bushfire records with ignition_date, extinguish_date (which may contain NaT)
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with new duration_days column (float, rounded to 2 decimals; NaT for fires without extinguish_date)
    """
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
    """Extract peak and cumulative FRP severity measures for each fire.
    
    Parameters:
        joined (GeoDataFrame): Satellite detections from filter_by_temporal_window() with fire_id, frp_peak, frp_cumulative
        bushfire_gdf (GeoDataFrame): Bushfire records with fire_id column
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with two new columns: peak_frp (max frp_peak per fire, NaN if undetected) and cumulative_frp (sum of frp_cumulative per fire, NaN if undetected)
    """
    peak_severity = joined.groupby("fire_id")["frp_peak"].max().rename("peak_frp")
    bushfire_gdf = bushfire_gdf.merge(peak_severity, on="fire_id", how="left")
    
    cumulative_severity = joined.groupby("fire_id")["frp_cumulative"].sum().rename("cumulative_frp")
    bushfire_gdf = bushfire_gdf.merge(cumulative_severity, on="fire_id", how="left")
    
    return bushfire_gdf


def classify_detection_status(joined, bushfire_gdf):
    """Count satellite detections per fire and classify as detected or never_detected.
    
    Parameters:
        joined (GeoDataFrame): Satellite detections from filter_by_temporal_window() with fire_id, datetime
        bushfire_gdf (GeoDataFrame): Bushfire records with fire_id column
    
    Returns:
        (GeoDataFrame): Same dataset with two new columns: viirs_detection_count (int, 0 for undetected) and detection_status (str: "never_detected" or "detected")
    """
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
    """Impute undetected small/medium fires; flag large/mega fires as coverage gaps.
    
    Parameters:
        bushfire_gdf (GeoDataFrame): Bushfire records with detection_status (detected/never_detected), size_class (small/medium/large/mega), ignition_date
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with modified columns for undetected fires: small/medium fires imputed with extinguish_date = ignition_date + 6 hours, detection_status = "imputed_same_day"; large/mega fires flagged with detection_status = "coverage_gap"
    """
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
    """Finalize dataset, reorder columns, and export.
    
    Parameters:
        bushfire_gdf (GeoDataFrame): Complete processed bushfire dataset with all computed columns
        output_csv (str): Output file path for CSV export (e.g., "unified_historic_fire_dataset.csv")
        output_geojson (str): Output file path for GeoJSON export (e.g., "unified_historic_fire_dataset.geojson")
    
    Returns:
        bushfire_gdf (GeoDataFrame): Same dataset with columns reordered to fixed sequence, sorted by ignition_date then fire_id, reprojected to EPSG:4326
        writes CSV and GeoJSON files to disk, prints confirmation messages
    """
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

def filter_detections_within_fires(viirs_gdf, bushfire_gdf, output_csv, output_geojson):
    """Filter satellite detections to those within fire extent polygons and aggregate by cell/date/daynight. Aggregates multiple detections per cell per timestep.
    
    Parameters:
        viirs_gdf (GeoDataFrame): Original satellite detections with all columns intact
        bushfire_gdf (GeoDataFrame): Bushfire polygons with fire_id and geometry
        output_csv (str): Output file path for CSV export
        output_geojson (str): Output file path for GeoJSON export
    
    Returns:
        aggregated_detections (GeoDataFrame): Aggregated detections within fire polygons
        writes CSV and GeoJSON files to disk
    """
    
    # Spatial join
    filtered_detections = gpd.sjoin(
        viirs_gdf,
        bushfire_gdf[["fire_id", "geometry"]],
        how="inner",
        predicate="intersects"
    )
    
    filtered_detections = filtered_detections.drop(columns=["index_right"], errors="ignore")
    filtered_detections = filtered_detections.drop_duplicates(subset=viirs_gdf.columns, keep="first")
    
    filtered_detections["date"] = pd.to_datetime(filtered_detections["datetime"]).dt.date
    
    # Define binary and contiuous columns
    binary_cols = [
        "confidence", "is_burning", "burning_neighbors_r1", "burning_neighbors_r2",
        "is_burning_prev", "is_burning_next"
    ]
    
    frp_cols = [
        "brightness", "bright_t31", "frp_peak", "frp_cumulative",
        "frp_prev", "frp_next"
    ]
    
    first_value_cols = ["satellite", "time_since_prev_pass", "longitude", "latitude"]
    
    agg_dict = {}
    
    # Aggregate across features
    for col in binary_cols:
        if col in filtered_detections.columns:
            agg_dict[col] = "max"
    
    for col in frp_cols:
        if col in filtered_detections.columns:
            agg_dict[col] = "max"
    
    for col in first_value_cols:
        if col in filtered_detections.columns:
            agg_dict[col] = "first"
    
    if "geometry" in filtered_detections.columns:
        agg_dict["geometry"] = "first"
    
    # Aggregate by cell_x, cell_y, date, daynight
    aggregated_detections = filtered_detections.groupby(
        ["cell_x", "cell_y", "date", "daynight"],
        as_index=False
    ).agg(agg_dict)
    
    aggregated_detections["datetime"] = aggregated_detections["date"]
    
    # Drop the intermediate date column
    aggregated_detections = aggregated_detections.drop(columns=["date"])
    
    # Reorder columns to match original format
    original_cols = list(viirs_gdf.columns)
    new_cols = [col for col in original_cols if col in aggregated_detections.columns]
    
    # Add any remaining columns
    remaining_cols = [col for col in aggregated_detections.columns if col not in new_cols]
    final_col_order = new_cols + remaining_cols
    
    aggregated_detections = aggregated_detections[final_col_order]
    
    # Convert to GeoDataFrame
    aggregated_detections = gpd.GeoDataFrame(
        aggregated_detections,
        geometry="geometry",
        crs="EPSG:4326"
    )
    
    # Sort by datetime
    aggregated_detections = aggregated_detections.sort_values("datetime", ascending=True)
    
    aggregated_detections = aggregated_detections.drop(columns=['satellite', 'time_since_prev_pass'])
    
    # Export CSV and GeoJSON
    aggregated_csv = aggregated_detections.copy()
    aggregated_csv["geometry"] = aggregated_csv["geometry"].astype(str)
    aggregated_csv.to_csv(output_csv, index=False)

    aggregated_detections.to_file(output_geojson, driver="GeoJSON")
    
    print(f"Exported csv to {output_csv}")
    print(f"Exported GeoJSON to {output_geojson}")
    
    return aggregated_detections

def main(output_csv="unified_historic_fire_dataset.csv", output_geojson="unified_historic_fire_dataset.geojson", detections_csv="satellite_detections_within_fires.csv", detections_geojson="satellite_detections_within_fires.geojson"):
    """Execute complete pipeline: load data → spatial join → temporal filter → estimate extinguish → calculate duration → extract FRP → classify detections → handle undetected → export.
    
    Parameters:
        output_csv (str): Output filename for CSV export (default "unified_historic_fire_dataset.csv")
        output_geojson (str): Output filename for GeoJSON export (default "unified_historic_fire_dataset.geojson")
    
    Returns:
        bushfire_gdf (GeoDataFrame): Complete processed dataset
        writes CSV and GeoJSON files to script directory
    """
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    
    # Paths to input datasets
    satellite_path = os.path.join(parent_dir, "satellite_fire_data", "satellite_fire_data.csv")
    bushfire_path = os.path.join(parent_dir, "historic_fire_events_data", "historic_fire_extents_data.csv")
    
    # Output paths
    output_csv = os.path.join(script_dir, output_csv)
    output_geojson = os.path.join(script_dir, output_geojson)
    detections_csv = os.path.join(script_dir, detections_csv)
    detections_geojson = os.path.join(script_dir, detections_geojson)
    
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
    
    print("Finalizing and exporting ...")
    bushfire_gdf = finalize_and_export(bushfire_gdf, output_csv, output_geojson)
    
    print("Detection-level dataset")
    detections_gdf = filter_detections_within_fires(viirs_gdf, bushfire_gdf, detections_csv, detections_geojson)
    
    return bushfire_gdf, detections_gdf


if __name__ == "__main__":
    result = main()
    print("\nProcessing complete!")
    print(result.head())