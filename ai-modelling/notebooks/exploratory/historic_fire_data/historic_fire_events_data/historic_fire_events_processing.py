"""
Victorian Bushfire Events Processing
Processing pipeline for the National Historical Bushfire Extents dataset.
Output: historic_fire_extents_data.csv, historic_fire_extents_data.geojson
"""

import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import box
import os


def load_data(gdb_path):
    """Load GeoDatabase file and filter to Victorian records."""
    vic_bbox = box(130, -29, 160, -43)
    gdf = gpd.read_file(gdb_path, layer="National_Historical_Bushfire_Extents_v4", bbox=vic_bbox)
    vic_gdf = gdf[gdf["state"] == "VIC (Victoria)"].reset_index()
    return vic_gdf


def data_quality_check(vic_gdf):
    """Check for nulls and drop columns with no usable data."""
    vic_gdf = vic_gdf.drop(columns=["capture_date", "extinguish_date", "ignition_cause", "capt_method"])
    return vic_gdf


def filter_to_period(vic_gdf, start_date="2018-07-01", end_date="2022-07-31"):
    """Filter to specified time period and remove zero-area records."""
    vic_gdf = vic_gdf[
        (vic_gdf["ignition_date"] >= start_date) &
        (vic_gdf["ignition_date"] <= end_date)
    ].reset_index(drop=True)
    
    vic_gdf = vic_gdf[vic_gdf["area_ha"] > 0].reset_index(drop=True)
    return vic_gdf


def engineer_features(vic_gdf):
    """Engineer season and geometry-based features."""
    def get_season(month):
        if month in [12, 1, 2]:
            return "Summer"
        elif month in [3, 4, 5]:
            return "Autumn"
        elif month in [6, 7, 8]:
            return "Winter"
        else:
            return "Spring"
    
    vic_gdf["season"] = vic_gdf["ignition_date"].dt.month.apply(get_season)
    
    # Project to meters for accurate area/perimeter calculation
    vic_gdf = vic_gdf.to_crs(epsg=7855)
    
    vic_gdf["area_m2"] = vic_gdf.geometry.area
    vic_gdf["perimeter_m"] = vic_gdf.geometry.length
    
    # Compactness metric (4π × area / perimeter²)
    vic_gdf["compactness"] = (4 * np.pi * vic_gdf["area_m2"]) / (vic_gdf["perimeter_m"] ** 2)
    
    # Log-transformed area
    vic_gdf["log_area"] = np.log1p(vic_gdf["area_ha"])
    
    # Size classification
    bins = [0, 10, 100, 1000, np.inf]
    labels = ["small", "medium", "large", "mega"]
    vic_gdf["size_class"] = pd.cut(vic_gdf["area_ha"], bins=bins, labels=labels)
    
    # Return to lat/lon
    vic_gdf = vic_gdf.to_crs(epsg=4326)
    
    return vic_gdf


def filter_to_bushfires(vic_gdf):
    """Filter dataset to bushfire events only (exclude prescribed burns)."""
    vic_gdf = vic_gdf[vic_gdf["fire_type"] == "Bushfire"].reset_index(drop=True)
    return vic_gdf


def finalize_and_export(vic_gdf, output_csv, output_geojson):
    """Reorder columns and export to CSV and GeoJSON."""
    column_order = [
        "fire_id", "fire_name", "ignition_date", "season",
        "fire_type", "size_class", "area_ha", "perim_km", "compactness", "log_area",
        "SHAPE_Length", "SHAPE_Area", "geometry"
    ]
    
    vic_gdf = vic_gdf[column_order]
    
    # Export
    vic_gdf.to_csv(output_csv, index=False)
    vic_gdf.to_file(output_geojson, driver="GeoJSON")
    
    print(f"✓ Exported {len(vic_gdf)} records to {output_csv}")
    print(f"✓ Exported GeoJSON to {output_geojson}")
    return vic_gdf


def main(output_csv="historic_fire_extents_data.csv", output_geojson="historic_fire_extents_data.geojson"):
    """Main processing pipeline."""
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "data")
    gdb_path = os.path.join(data_dir, "BushfireEvents.gdb/")
    
    output_csv = os.path.join(script_dir, output_csv)
    output_geojson = os.path.join(script_dir, output_geojson)
    
    print("Loading GeoDatabase...")
    vic_gdf = load_data(gdb_path)
    print(f"  Loaded {len(vic_gdf)} Victorian records")
    
    print("Checking data quality...")
    vic_gdf = data_quality_check(vic_gdf)
    
    print("Filtering to 2018–2022...")
    vic_gdf = filter_to_period(vic_gdf)
    print(f"  Filtered to {len(vic_gdf)} records")
    
    print("Engineering features...")
    vic_gdf = engineer_features(vic_gdf)
    
    print("Filtering to bushfires only...")
    vic_gdf = filter_to_bushfires(vic_gdf)
    print(f"  Retained {len(vic_gdf)} bushfire records")
    
    print("Finalizing and exporting...")
    vic_gdf = finalize_and_export(vic_gdf, output_csv, output_geojson)
    
    return vic_gdf

if __name__ == "__main__":
    result = main()
    print("\nProcessing complete!")
    print(result.head())
