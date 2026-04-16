"""
Visualization utilities for Earth Engine data analysis and model evaluation.

Includes:
- Line plots for time series visualization
- Map visualization for spatial data using Earth Engine thumbnails
"""
import matplotlib.pyplot as plt
from IPython.display import Image

# Line plot for time series visualization
def line_plot(df, feature: str, title: str):
    """
    Generates a multi-panel line chart for the collected forest data.

    Args:
        df (pd.DataFrame): DataFrame containing 'datetime' and feature columns
        feature (str): Name of the feature to plot
        title (str): Title for the plot

    Example:
        plot_forest_trends(df, feature='surface_temperature', title='Forest Temperature Trends')
    """
    fig, ax = plt.subplots(figsize=(14, 6))
    plt.title(title)
    ax.plot(df['datetime'], df[feature], 
            color='teal')
    plt.xlabel('Time')
    plt.ylabel(feature)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# Map visualization for spatial data
def visualize_map(
        collection, region, 
        band=None, min_val=-100, max_val=100, 
        palette=None, dimensions=512):
    if palette is None:
        palette = ['blue', 'green', 'yellow', 'orange', 'red']
    
    # Select specified band for visualization in the dataset
    image = collection.mean().select(band) if band else collection.mean().select([0])
    
    url = image.getThumbUrl({
        'min': min_val,
        'max': max_val,
        'dimensions': dimensions,
        'region': region,
        'palette': palette
    })
    
    print(f"Thumbnail URL: {url}")
    return Image(url=url)