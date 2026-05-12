import os
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

_df_grid = None  # Private


def fetch_grid():
    """
    Loads the full location_registry from Supabase into _df_grid.
    Only needs to be called ONCE per session — the grid never changes.
    """
    global _df_grid
    all_rows = []
    offset = 0
    chunk = 1000
    while True:
        rows = supabase.table("location_registry").select("*").range(offset, offset + chunk - 1).execute().data
        all_rows.extend(rows)
        if len(rows) < chunk:
            break
        offset += chunk
    _df_grid = pd.DataFrame(all_rows)
    print(f"Grid loaded: {len(_df_grid)} points")
    return _df_grid


def interpolate_to_grid(df_source, lat_col, lon_col, method="cubic"):
    """
    Interpolates sparse observation data onto the full location_registry grid.

    Args:
        df_source:  Sparse observation DataFrame. Requirements:
                      - Single timestamp only — filter before passing in.
                      - Source points should extend BEYOND Victoria's boundary
                        (lat -33.5 to -40, lon 140 to 151) so cubic interpolation
                        covers edge grid points without falling back to nearest.
        lat_col:    Name of the latitude column in df_source.
        lon_col:    Name of the longitude column in df_source.
        method:     "cubic" smooth, for continuous fields (weather, vegetation, elevation).
                    "nearest" for discrete/point events (fire incidents, infrastructure).

    Returns:
        Copy of _df_grid with interpolated columns added.
    """
    global _df_grid
    if _df_grid is None:
        print("Grid not loaded, running fetch_grid() automatically.")
        fetch_grid()

    df_out = _df_grid.copy()

    skip = {lat_col, lon_col}
    interp_cols = [
        c for c in df_source.columns
        if c not in skip and pd.api.types.is_numeric_dtype(df_source[c])
    ]

    points = df_source[[lon_col, lat_col]].values
    targets = df_out[["grid_longitude", "grid_latitude"]].values

    for col in interp_cols:
        interpolated = griddata(points, df_source[col].values, targets, method=method)
        nan_mask = np.isnan(interpolated)
        if nan_mask.any():
            interpolated[nan_mask] = griddata(
                points, df_source[col].values, targets[nan_mask], method="nearest"
            )
        df_out[col] = interpolated

    return df_out