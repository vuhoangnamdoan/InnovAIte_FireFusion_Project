"""
Training script for ConvLSTM with data already in gridded format.

Assumes data is loaded as: [n_timesteps, height, width, n_features]
"""

import os
import joblib
import numpy as np
import pandas as pd
import torch
import json
from torch import nn
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from ..models.bushfire.ts_convlstm_forecaster import ForecasterConfig, MultivariateTSForecaster

# Paths
DATA_PATH = "src/data/bushfire/forecaster_test_data.csv"
MODEL_SAVE_PATH = "src/models/bushfire/checkpoints/convlstm_forecaster.pth"
SCALER_SAVE_PATH = "src/models/bushfire/checkpoints/convlstm_scaler.pkl"

# Model hyperparameters
INPUT_STEPS = 60
HORIZON = 2
BATCH_SIZE = 8
EPOCHS = 50
LEARNING_RATE = 0.001

TRAIN_VAL_RATIO = 0.9
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Environmental features
FEATURES = [
    "skin_temperature_c",
    "soil_temperature_level_1_c",
    "surface_solar_radiation_downwards",
    "surface_thermal_radiation_downwards",
    "temperature_2m_c",
    "u_component_of_wind_10m",
    "v_component_of_wind_10m"
]

class MaskedMSELoss(nn.Module):
    """
    MSE loss that only considers valid (land) cells.
 
    Invalid cells (ocean, out-of-bounds) are excluded from both the
    numerator and denominator, so they don't influence gradients and
    the reported loss reflects true performance on real data.
 
    Inputs:
        valid_mask (Tensor): Boolean [H, W] tensor — True where cells are valid.
    """
    def __init__(self, valid_mask: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer(
            'mask',
            valid_mask.float().unsqueeze(0).unsqueeze(0).unsqueeze(-1)
        )
 
    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """
        Inputs:
            pred   (Tensor): [B, horizon, H, W, F]
            target (Tensor): [B, horizon, H, W, F]
 
        Outputs:
            Tensor: scalar masked MSE loss
        """
        squared_error = (pred - target) ** 2
        masked = squared_error * self.mask

        n_valid = self.mask.sum() * pred.shape[0] * pred.shape[1] * pred.shape[-1]
        return masked.sum() / n_valid

class GriddedTimeSeriesDataset(Dataset):
    """
    Dataset that generates sequences on the fly.
    """
    def __init__(self, data_grid, input_steps, horizon):
        """
        Inputs:
            data_grid (np.ndarray): [n_timesteps, height, width, n_features]
            input_steps (int): number of input timesteps
            horizon (int): number of output timesteps
        """
        self.data = torch.tensor(data_grid, dtype=torch.float32)
        self.input_steps = input_steps
        self.horizon = horizon

    def __len__(self):
        return len(self.data) - self.input_steps - self.horizon + 1

    def __getitem__(self, idx):
        X = self.data[idx : idx + self.input_steps]
        y = self.data[idx + self.input_steps : idx + self.input_steps + self.horizon]
        return X, y

def create_grid_sequences(data_grid, input_steps, horizon):
    """
    Create sliding-window sequences from gridded spatiotemporal data.
    
    Inputs:
        data_grid (np.ndarray): Input grid of shape [n_timesteps, height, width, n_features]
        input_steps (int): Length of input sequence (lookback window)
        horizon (int): Number of future timesteps to predict
    
    Outputs:
        tuple: (X, y) where:
            - X (np.ndarray): Input sequences [n_samples, input_steps, height, width, n_features]
            - y (np.ndarray): Target sequences [n_samples, horizon, height, width, n_features]
    """
    n_timesteps, height, width, n_features = data_grid.shape
    
    max_samples = n_timesteps - input_steps - horizon + 1
    
    if max_samples <= 0:
        print(f"Not enough timesteps: {n_timesteps} < {input_steps + horizon}")
        return np.array([]), np.array([])
    
    # Pre-allocate arrays
    X = np.zeros((max_samples, input_steps, height, width, n_features), dtype=np.float32)
    y = np.zeros((max_samples, horizon, height, width, n_features), dtype=np.float32)
    
    for i in range(max_samples):
        X[i] = data_grid[i:i + input_steps]
        y[i] = data_grid[i + input_steps:i + input_steps + horizon]
    
    print(f"  X shape: {X.shape}, y shape: {y.shape}")
    
    return X, y

def train_one_epoch(model, dataloader, criterion, optimizer, device):
    """
    Execute one complete training epoch on the training dataloader.
    
    Inputs:
        model (nn.Module): The neural network model to train
        dataloader (DataLoader): Training dataloader with (X, y) batches
        criterion (nn.Module): Loss function (e.g., MSELoss)
        optimizer (torch.optim.Optimizer): Optimizer for parameter updates (e.g., Adam)
        device (torch.device): Device to run training on (cuda or cpu)
    
    Outputs:
        float: Mean loss across all batches in the epoch
    """
    model.train()
    losses = []
    for X_batch, y_batch in dataloader:
        X_batch = X_batch.to(device)
        y_batch = y_batch.to(device)
        optimizer.zero_grad()
        preds = model(X_batch)
        loss = criterion(preds, y_batch)
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
    return np.mean(losses)

def evaluate(model, dataloader, criterion, device):
    """
    Evaluate model performance on validation/test data without updating weights.
    
    Inputs:
        model (nn.Module): The neural network model to evaluate
        dataloader (DataLoader): Validation/test dataloader with (X, y) batches
        criterion (nn.Module): Loss function to compute (e.g., MSELoss)
        device (torch.device): Device to run evaluation on (cuda or cpu)
    
    Outputs:
        float: Mean loss across all batches in the dataloader
    """
    model.eval()
    losses = []
    with torch.no_grad():
        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            preds = model(X_batch)
            loss = criterion(preds, y_batch)
            losses.append(loss.item())
    return np.mean(losses)

def predict(model, dataloader, device):
    """
    Generate predictions on a dataloader without computing gradients.
    
    Inputs:
        model (nn.Module): The neural network model to generate predictions
        dataloader (DataLoader): Dataloader with (X, y) batches
        device (torch.device): Device to run predictions on (cuda or cpu)
    
    Outputs:
        tuple: (predictions, actuals) where:
            - predictions (np.ndarray): Model outputs [n_samples, horizon, height, width, n_features]
            - actuals (np.ndarray): Ground truth targets [n_samples, horizon, height, width, n_features]
    """
    model.eval()
    predictions = []
    actuals = []
    with torch.no_grad():
        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(device)
            preds = model(X_batch).cpu().numpy()
            predictions.append(preds)
            actuals.append(y_batch.numpy())
    return np.concatenate(predictions), np.concatenate(actuals)

def load_and_format_gridded_data(csv_path, feature_cols=None):
    """
    Load CSV data and format it into gridded spatiotemporal format.
    
    Extracts coordinates from GeoJSON polygons, organizes data by timestamp and location,
    and returns a properly structured 4D numpy array.
    
    Inputs:
        csv_path (str): Path to the CSV file containing:
            - datetime column: Timestamp of observation
            - .geo column: GeoJSON polygon defining grid cell location
            - feature columns: Environmental measurements (7 features by default)
        feature_cols (list, optional): List of feature column names. Defaults to the 7 environmental features.
    
    Outputs:
        np.ndarray: Gridded data of shape [n_timesteps, height, width, n_features] with dtype=float32
    """    
    if feature_cols is None:
        feature_cols = [
            "skin_temperature_c",
            "soil_temperature_level_1_c",
            "surface_solar_radiation_downwards",
            "surface_thermal_radiation_downwards",
            "temperature_2m_c",
            "u_component_of_wind_10m",
            "v_component_of_wind_10m"
        ]
    
    # Load CSV
    df = pd.read_csv(csv_path)
    print(f"Loaded CSV: {df.shape}")
    
    # Extract coordinates from GeoJSON
    print(f"Extracting coordinates...")
    
    def extract_coords(geojson_str):
        """
        Extract minimum longitude and latitude from GeoJSON polygon.
        
        Inputs:
            geojson_str (str): GeoJSON string representation of a polygon
        
        Outputs:
            tuple: (min_lon, min_lat) - bottom-left corner of the polygon
        """
        geojson = json.loads(geojson_str)
        coords = geojson['coordinates']
        
        # Flatten to get all individual [lon, lat] pairs
        all_lons = []
        all_lats = []
        
        # Handle nested structure: coordinates[ring][point]
        for ring in coords:
            for point in ring:
                all_lons.append(float(point[0]))
                all_lats.append(float(point[1]))
        
        return min(all_lons), min(all_lats)
    
    coords_data = []
    for idx, geojson_str in enumerate(df['.geo']):
        if idx % 100000 == 0 and idx > 0:
            print(f"Extracted {idx} coordinates...")
        
        try:
            lon, lat = extract_coords(geojson_str)
            coords_data.append({'lon': lon, 'lat': lat})
        except Exception as e:
            coords_data.append({'lon': 0.0, 'lat': 0.0})
    
    # Create DataFrame from extracted coords, merge
    coords_df = pd.DataFrame(coords_data)
    df = pd.concat([df.reset_index(drop=True), coords_df.reset_index(drop=True)], axis=1)
    
    print(f"Extracted {len(coords_data)} coordinates")
    
    # Get unique lat/lon values (sorted)
    unique_lats = sorted(df['lat'].unique().tolist())
    unique_lons = sorted(df['lon'].unique().tolist())
    print(f"Grid dimensions: {len(unique_lats)} x {len(unique_lons)}")
    
    # Create mapping
    lat_to_row = {lat: i for i, lat in enumerate(unique_lats)}
    lon_to_col = {lon: j for j, lon in enumerate(unique_lons)}
    
    # Get unique timestamps
    df['datetime'] = pd.to_datetime(df['datetime'])
    unique_times = sorted(df['datetime'].unique().tolist())
    print(f"Timesteps: {len(unique_times)}")
    
    # Initialize array
    n_timesteps = len(unique_times)
    height = len(unique_lats)
    width = len(unique_lons)
    n_features = len(feature_cols)
    
    data_grid = np.full((n_timesteps, height, width, n_features), np.nan, dtype=np.float32)
    
    print(f"Filling grid ({n_timesteps} x {height} x {width} x {n_features})...")
    # Fill the grid
    for idx, row in df.iterrows():
        if idx % 100000 == 0 and idx > 0:
            print(f"  Filled {idx} rows...")
        
        try:
            t_idx = unique_times.index(row['datetime'])
            h_idx = lat_to_row[row['lat']]
            w_idx = lon_to_col[row['lon']]
            
            data_grid[t_idx, h_idx, w_idx, :] = np.array(
                row[feature_cols].values, 
                dtype=np.float32
            )
        except (ValueError, KeyError) as e:
            continue
    
    print(f"Grid formatted: {data_grid.shape}")
    print(f"[n_timesteps={n_timesteps}, height={height}, width={width}, features={n_features}]\n")
    
    return data_grid

def main():
    """
    Training pipeline for ConvLSTM on gridded spatiotemporal data.
    
    Workflow:
    1. Load gridded data or format csv into needed format [n_timesteps, height, width, n_features]
    2. Split into train/val/test in time order
    3. Fit scaler on training data
    4. Append land mask
    5. Create sliding-window sequences
    6. Create DataLoaders
    7. Initialise convLSTM model
    8. Train ConvLSTM
    9. Load best model
    10. Evaluate
    11. Save trained model and scaler
    """
    os.makedirs("models", exist_ok=True)
    print("Using device:", DEVICE)
    
    print("STEP 1: Load Gridded Data")
    
    GRID_CACHE_PATH = "src/data/bushfire/data_grid_cache.npy"

    if os.path.exists(GRID_CACHE_PATH):
        print("Found cached grid, loading...")
        data_grid = np.load(GRID_CACHE_PATH)
        print(f"Loaded grid: {data_grid.shape}")
    else:
        print("No cache found, building grid from CSV...")
        data_grid = load_and_format_gridded_data(DATA_PATH)
        np.save(GRID_CACHE_PATH, data_grid)
        print(f"Grid saved to {GRID_CACHE_PATH}")

    
    n_timesteps, grid_height, grid_width, n_features = data_grid.shape
    assert n_features == len(FEATURES), f"Expected {len(FEATURES)} features, got {n_features}"

    valid_mask = ~np.all(np.isnan(data_grid), axis=(0, -1))
 
    total_cells = grid_height * grid_width
    valid_cells = valid_mask.sum()
    print(f"Valid cells: {valid_cells} / {total_cells} ({valid_cells/total_cells*100:.1f}%)")
 
    print("STEP 2: Split Data into Train/Val/Test")
    
    split_idx = int(len(data_grid) * TRAIN_VAL_RATIO)
    train_val_grid = data_grid[:split_idx]
    test_grid = data_grid[split_idx:]
    
    print(f"Train/Val: {len(train_val_grid)} timesteps")
    print(f"Test: {len(test_grid)} timesteps")
    print(f"(Split at {TRAIN_VAL_RATIO*100}% to preserve temporal order)")
    
    print("STEP 3: Fit Scaler on Training Data")
 
    # Flatten to [N, F] for sklearn on valid cells
    train_val_flat = train_val_grid.reshape(-1, n_features)

    # Keep only rows where at least one feature is not NaN - Used for evaluation
    valid_rows = ~np.all(np.isnan(train_val_flat), axis=1)
 
    scaler = StandardScaler()
    scaler.fit(train_val_flat[valid_rows])
 
    print(f"Scaler fitted on {valid_rows.sum()} valid cell-timesteps")
    print(f"Feature means: {scaler.mean_}")
    print(f"Feature scales: {scaler.scale_}")
 
    def scale_and_fill(grid: np.ndarray) -> np.ndarray:
        """Scale [T, H, W, F] grid and replace NaNs with 0."""
        shape = grid.shape
        flat = grid.reshape(-1, n_features)
        scaled = scaler.transform(flat)
        scaled[np.isnan(scaled)] = 0.0
        return scaled.reshape(shape)
 
    train_val_scaled = scale_and_fill(train_val_grid)
    test_scaled = scale_and_fill(test_grid)

    print("STEP 4: Create Datasets with Sliding Window")

    # Split train_val into train/val
    val_split_idx = int(len(train_val_scaled) * 0.85)
    train_grid = train_val_scaled[:val_split_idx]
    val_grid   = train_val_scaled[val_split_idx:]

    train_dataset = GriddedTimeSeriesDataset(train_grid, INPUT_STEPS, HORIZON)
    val_dataset   = GriddedTimeSeriesDataset(val_grid, INPUT_STEPS, HORIZON)
    test_dataset  = GriddedTimeSeriesDataset(test_scaled, INPUT_STEPS, HORIZON)

    print(f"train_val timesteps: {len(train_val_scaled)}")
    print(f"train timesteps: {val_split_idx}")
    print(f"val timesteps: {len(train_val_scaled) - val_split_idx}")
    print(f"Minimum needed: {INPUT_STEPS + HORIZON}")

    print(f"Train sequences: {len(train_dataset)}")
    print(f"Val sequences: {len(val_dataset)}")
    print(f"Test sequences: {len(test_dataset)}")

    print("STEP 5: Create DataLoaders")

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True,  num_workers=0)
    val_loader = DataLoader(val_dataset,   batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_dataset,  batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    
    print(f"Train batches: {len(train_loader)} batches of {BATCH_SIZE}")
    print(f"Val batches: {len(val_loader)} batches of {BATCH_SIZE}")
    print(f"Test batches: {len(test_loader)} batches of {BATCH_SIZE}")
    
    print("STEP 6: Initialise ConvLSTM Model")
    
    config = ForecasterConfig(
        input_channels=n_features,
        horizon=HORIZON,
        output_channels=n_features,
        hidden_size_1=32,
        hidden_size_2=16,
        dropout=0.2
    )
    
    model = MultivariateTSForecaster(config).to(DEVICE)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"Model created")
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    print("STEP 7: Train Model")
    
    valid_mask_tensor = torch.tensor(valid_mask, dtype=torch.bool)
    criterion = MaskedMSELoss(valid_mask_tensor).to(DEVICE)
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    
    best_val_loss = float("inf")
    best_state = None
    patience = 10
    patience_counter = 0
    
    print(f"Training config:")
    print(f"Loss: MSELoss")
    print(f"Learning Rate: {LEARNING_RATE}")
    print(f"Epochs: {EPOCHS}")
    print(f"Early stopping patience: {patience}")
    
    print(f"\n{'Epoch':<8} {'Train Loss':<15} {'Val Loss':<15} {'Status':<15}")
    print("-" * 60)
    for epoch in range(1, EPOCHS + 1):
        train_loss = train_one_epoch(model, train_loader, criterion, optimizer, DEVICE)
        val_loss = evaluate(model, val_loader, criterion, DEVICE)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.state_dict()
            patience_counter = 0
            status = "BEST"
        else:
            patience_counter += 1
            status = f"Wait {patience_counter}/{patience}"
        
        print(f"{epoch:<8} {train_loss:<15.6f} {val_loss:<15.6f} {status:<15}")
        
        if patience_counter >= patience:
            print(f"\nEarly stopping triggered at epoch {epoch}")
            break
    
    print("STEP 8: Load Best Model")
    
    if best_state is not None:
        model.load_state_dict(best_state)
        print(f"Loaded best model (val_loss={best_val_loss:.6f})")
    else:
        print(f"Using final model")
    
    print("STEP 9: Evaluate on Test Set")
    
    y_pred_scaled, y_true_scaled = predict(model, test_loader, DEVICE)
    
    # Reshape for inverse scaling
    y_pred_flat = y_pred_scaled.reshape(-1, n_features)
    y_true_flat = y_true_scaled.reshape(-1, n_features)
    
    # Inverse transform
    y_pred_original = scaler.inverse_transform(y_pred_flat)
    y_true_original = scaler.inverse_transform(y_true_flat)

    pred_spatial = y_pred_original.reshape(y_pred_scaled.shape)
    true_spatial = y_true_original.reshape(y_true_scaled.shape)
    
    mask_expanded = valid_mask[np.newaxis, np.newaxis, :, :, np.newaxis]
    mask_tiled = np.broadcast_to(mask_expanded, pred_spatial.shape)
 
    pred_valid = pred_spatial[mask_tiled].reshape(-1, n_features)
    true_valid = true_spatial[mask_tiled].reshape(-1, n_features)
    
    print(f"\nPer-feature Test Metrics:")
    print(f"  {'Feature':<40} {'MAE':<12} {'RMSE':<12} {'R2':<10}")
    print("-" * 80)
    
    for i, feature in enumerate(FEATURES):
        feature_mae  = mean_absolute_error(true_valid[:, i], pred_valid[:, i])
        feature_rmse = np.sqrt(mean_squared_error(true_valid[:, i], pred_valid[:, i]))
        feature_r2   = r2_score(true_valid[:, i], pred_valid[:, i])
        print(f"  {feature:<40} {feature_mae:<12.4f} {feature_rmse:<12.4f} {feature_r2:<10.4f}")
    
    print("STEP 11: Save Model and Scaler")
    
    model.save(MODEL_SAVE_PATH)
    
    joblib.dump(
        {
            "scaler": scaler,
            "features": FEATURES,
            "input_steps": INPUT_STEPS,
            "horizon": HORIZON,
            "grid_shape": (grid_height, grid_width),
        },
        SCALER_SAVE_PATH
    )
    
    print(f"Saved model: models/convlstm_forecaster.pth")
    print(f"Saved scaler: models/scaler.pkl")
    
    print("TRAINING COMPLETE")

if __name__ == "__main__":
    main()
