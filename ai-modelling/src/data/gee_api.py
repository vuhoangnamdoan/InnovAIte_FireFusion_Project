"""
FireFusion GEE API Module

Comprehensive module for Earth Engine authentication and data retrieval.

For raw data collection, 
please use a large scale (500+) for raw extraction to prevent memory issues.
"""
import ee
import pandas as pd
import numpy as np
from typing import List

# Data conversion from array to DataFrame
def ee_features_to_df(features: List, bands: List[str], lat: float, lon: float) -> pd.DataFrame:
    """
    Convert Earth Engine getRegion array to pandas DataFrame.
    
    Transforms raw EE array (header row + data rows) into a structured DataFrame
    with proper dtypes, datetime conversion, and selected columns.
    
    Args:
        features (List): Raw feature array
        bands (List[str]): Band names to extract and keep
        lat (float): Latitude of the point of interest
        lon (float): Longitude of the point of interest

    Returns:
        pd.DataFrame: Cleaned DataFrame with columns: time, datetime, [band names]
    """
    if not features: 
        return pd.DataFrame()
    
    # The first row contains column names, the rest are data
    df = pd.DataFrame.from_records([f['properties'] for f in features])

    # Latitude and longitude columns
    df['latitude'] = lat
    df['longitude'] = lon

    # Convert time from milliseconds to datetime and ensure numeric types for bands
    df['datetime'] = pd.to_datetime(df['system:time_start'], unit='ms', utc=True)
    df.rename(columns={'system:time_start': 'time'}, inplace=True)
    df[bands] = df[bands].apply(pd.to_numeric, errors='coerce')

    # Reorder columns
    cols = ['time', 'datetime', 'latitude', 'longitude'] + bands
    return df.sort_values('time')[cols]


# Class for Earth Engine API interactions and data collection
class EarthEngineAPI:
    def __init__(self, project_id: str):
        ee.Initialize(project=project_id)
        print(f"Earth Engine initialized - Project: {project_id}")
        print(f"  Version: {ee.__version__}")

    def create_area(self, lat: float, lon: float, area_km: float) -> ee.Geometry:
        """
        Internal helper to create consistent square boundaries.

        Args:
            lat (float): Latitude of the center point
            lon (float): Longitude of the center point
            area_km (float): Area in square kilometers

        Returns:
            ee.Geometry: Square geometry centered on (lat, lon) with specified area
        """
        half_side = (np.sqrt(area_km) * 1000) / 2
        return ee.Geometry.Point([lon, lat]).buffer(half_side).bounds()
    
    def get_collection(self, dataset: str, bands: List[str], 
                       start_date: str, end_date: str) -> ee.ImageCollection:
        """
        Load an Earth Engine ImageCollection with specified bands and date range.

        Args:
            dataset (str): GEE dataset path (e.g., 'MODIS/061/MOD11A1')
            bands (List[str]): List of band names to select
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format

        Returns:
            ee.ImageCollection: Filtered collection with selected bands
        """
        return ee.ImageCollection(dataset).select(bands).filterDate(start_date, end_date)


    def collect_raw_data(self, dataset: str, bands: List[str], 
                         lat: float, lon: float, area_km: float,
                         start_date: str, end_date: str,
                         scale: int) -> np.ndarray:
        """
        Collects a spatially time series for an area, returning raw pixel values.

        Args:
            dataset (str): The GEE path to the dataset
            bands (List[str]): List of band names to collect
            lat (float): Latitude of the point of interest
            lon (float): Longitude of the point of interest
            area_km (float): Area around the point in square kilometers
            scale (int): Scale for the spatial averaging
        
        Returns:
            np.ndarray: Raw array of pixel values with time, lat, lon, and band values
        """
        area = self.create_area(lat, lon, area_km)
        collection = self.get_collection(dataset, bands, start_date, end_date)

        raw_array = collection.getRegion(area, scale).getInfo()
        return raw_array


    def collect_mean_data(self, dataset: str, bands: List[str],
                          lat: float, lon: float, area_km: float, 
                          start_date: str, end_date: str) -> pd.DataFrame:
        """
        Collects a spatially-averaged time series for a forest area.

        Args:
            dataset (str): The GEE path to the dataset
            bands (List[str]): List of band names to collect
            lat (float): Latitude of the point of interest
            lon (float): Longitude of the point of interest
            area_km (float): Area around the point in square kilometers
            start_date (str): 'YYYY-MM-DD'
            end_date (str): 'YYYY-MM-DD'

        Returns:
            pd.DataFrame: DataFrame with mean values for the area over time
        """
        area = self.create_area(lat, lon, area_km)
        collection = self.get_collection(dataset, bands, start_date, end_date)

        def reduce_image(image):
            stats = image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=area,
                scale=500,
                bestEffort=True
            )
            return ee.Feature(None, stats).set('system:time_start', image.get('system:time_start'))

        features = collection.map(reduce_image).getInfo()['features']
        return ee_features_to_df(features, bands, lat, lon)
    