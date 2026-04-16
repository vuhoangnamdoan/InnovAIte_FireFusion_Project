# Data reshaping for LSTM/ConvLSTM models
"""
Pre-processing utilities for Earth Engine data for LSTM models.

Includes:
- Reshaping DataFrames to 3D arrays for LSTM/GRU models
- Temperature conversion from raw satellite values to Celsius
"""
import pandas as pd
import numpy as np
from typing import List
    

def reshape_to_3d(df: pd.DataFrame, bands: List[str], window_size: int, step: int = 1) -> np.ndarray:
    """
    Reshape DataFrame to 3D array for Standard LSTM/GRU models: (T, F*H*W).
    
    Flattens spatial dimensions while preserving temporal axis.
    
    Args:
        df (pd.DataFrame): Time-series DataFrame
        bands (List[str]): Band names
        window_size (int): Size of the sliding window for sequence generation
        step (int): Step size for the sliding window (default=1)
    Returns:
        np.ndarray: 3D array (T, F*H*W)
    
    Example:
        data_3d = reshape_to_3d(df, bands=['LST_Day_1km', 'temperature_2m'])
    """
    data = df[bands].values  # Shape: (T, F)
    X = []

    for i in range(0, len(data) - window_size, step):
        # Grab a slice of the data
        window = data[i : i + window_size]
        X.append(window)

    return np.array(X)


# Temperature conversion and quality filtering
def convert_temperature(temp_raw: float, source: str = 'modis') -> float:
    """
    Convert temperature from raw satellite values to Celsius.
    
    Args:
        temp_raw (float): Raw temperature value
        source (str): Source format ('modis', 'kelvin', 'raw')
                      - 'modis': MODIS value
                      - 'kelvin': Direct Kelvin to Celsius
                      - 'raw': Direct raw units to Celsius
    
    Returns:
        float: Temperature in Celsius
    """
    if source == 'modis':
        return 0.02 * temp_raw - 273.15
    elif source == 'kelvin':
        return temp_raw - 273.15
    else:
        return temp_raw


# Apply temperature conversion to multiple bands in a DataFrame
def apply_temperature_conversion(df: pd.DataFrame, bands: List[str], 
                                  source: str = 'modis') -> pd.DataFrame:
    """
    Apply temperature conversion to multiple bands in a DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame with temperature bands
        bands (List[str]): Names of bands to convert
        source (str): Temperature source format (see convert_temperature)
    
    Returns:
        pd.DataFrame: DataFrame with converted bands
    """
    df_copy = df.copy()
    for band in bands:
        df_copy[band] = df_copy[band].apply(lambda x: convert_temperature(x, source))
    return df_copy