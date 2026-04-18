import pandas as pd

# -------------------------------
# STEP 1: Load raw data
# -------------------------------
df = pd.read_csv(
    "../../data/raw/firms_data.csv",
    low_memory=False
)

print("Raw data loaded. Rows:", len(df))

# -------------------------------
# STEP 2: Remove duplicate header rows (if any)
# -------------------------------
df = df[df['acq_date'] != 'acq_date']

# -------------------------------
# STEP 3: Convert date column
# -------------------------------
df['acq_date'] = pd.to_datetime(df['acq_date'], errors='coerce')

# Remove invalid dates
df = df.dropna(subset=['acq_date'])

print("Valid dates:", len(df))

# -------------------------------
# STEP 4: Filter Black Summer period
# -------------------------------
df = df[
    (df['acq_date'] >= '2019-01-01') &
    (df['acq_date'] <= '2020-05-31')
]

print("Rows after date filtering:", len(df))

# -------------------------------
# STEP 5: Clean numeric columns
# -------------------------------
df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')
df['confidence'] = pd.to_numeric(df['confidence'], errors='coerce')

# Drop invalid rows
df = df.dropna(subset=['latitude', 'longitude', 'confidence'])

print("Rows after cleaning:", len(df))

# -------------------------------
# STEP 6: Create Fire_Events table
# -------------------------------
fire_df = pd.DataFrame()

# Primary key
fire_df['event_id'] = range(1, len(df) + 1)

# Foreign keys (left NULL for integration phase)
fire_df['weather_id'] = None
fire_df['topo_id'] = None
fire_df['fuel_id'] = None
fire_df['facility_id'] = None

# Core columns
fire_df['latitude'] = df['latitude']
fire_df['longitude'] = df['longitude']
fire_df['event_date'] = df['acq_date']
fire_df['confidence_score'] = df['confidence']
fire_df['source_system'] = 'NASA FIRMS'

# -------------------------------
# STEP 7: Reorder columns (IMPORTANT)
# -------------------------------
fire_df = fire_df[
    [
        'event_id',
        'weather_id',
        'topo_id',
        'fuel_id',
        'facility_id',
        'latitude',
        'longitude',
        'event_date',
        'confidence_score',
        'source_system'
    ]
]

# -------------------------------
# STEP 8: Save processed data
# -------------------------------
output_path = "../../data/processed/fire_events.csv"
fire_df.to_csv(output_path, index=False)

# -------------------------------
# STEP 9: Final Output
# -------------------------------
print("\nFire_Events table created successfully!")
print("Saved at:", output_path)
print("\n Preview:")
print(fire_df.head())