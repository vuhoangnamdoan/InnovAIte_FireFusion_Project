# Grid Snapper

A utility that converts raw GPS coordinates from different data sources into a unified location ID for the FireFusion database.

## What It Does

Grid Snapper solves a simple problem: different data sources (NASA FIRMS, Open-Meteo, ELVIS) give slightly different coordinates for the same location.

Example:
- Fire data: latitude -37.8147, longitude 145.0892
- Weather data: latitude -37.8149, longitude 145.0891

These are the same location but the numbers don't match exactly. Grid Snapper rounds both to the same grid point (-37.8, 145.1) and assigns them the same location_id (4521). Now they can be joined in a query.

## How It Works

Grid Snapper does 4 steps:

1. **Validate** - Check if coordinate is inside Victoria bounds
2. **Snap to Grid** - Round to nearest 0.1 degree (approximately 11 km)
3. **Lookup** - Check if this snapped coordinate exists in Location_Registry
4. **Get or Create** - Return existing location_id or create new one

## Installation

```bash
pip install psycopg2-binary python-dotenv
```

## Setup

Create a `.env` file in the data-engineering folder:

```
DB_HOST=aws-1-ap-south-1.pooler.supabase.com
DB_USER=postgres.zbgxliqmanojoknnetec
DB_PASSWORD=your_database_password
DB_PORT=5432
DB_NAME=postgres
```

## Usage

```python
from grid_snapper.grid_snapper import GridSnapper

# Initialize
snapper = GridSnapper()

# Get location_id for any coordinate
location_id = snapper.get_location_id(-37.8147, 145.0892)

# Returns: 4521 (or new ID if first time)
print(location_id)

# Close when done
snapper.close()
```

## Use in Pipelines

Every extraction pipeline (fire, weather, vegetation, topography) should use Grid Snapper to align coordinates before inserting data:

```python
from grid_snapper.grid_snapper import GridSnapper

snapper = GridSnapper()

for record in data:
    location_id = snapper.get_location_id(
        latitude=record['latitude'],
        longitude=record['longitude']
    )
    
    if location_id is None:
        continue  # Skip if outside Victoria
    
    insert_to_database(
        location_id=location_id,
        original_latitude=record['latitude'],
        original_longitude=record['longitude'],
        ...
    )

snapper.close()
```

## Important Notes

- Always preserve original coordinates in the database (original_latitude, original_longitude). Grid snapper creates location_id for joining, not for replacing the raw data.
- Grid Snapper only works for Victoria. Coordinates outside Victoria bounds will return None.
- Always check for None before inserting: `if location_id is None: continue`

## Testing

Run the built-in tests:

```bash
python3 grid_snapper/grid_snapper.py
```

Expected output:
```
✅ GridSnapper connected to Supabase
Test 1: Valid Victorian coordinate → location_id created
Test 2: Same grid cell → same location_id returned
Test 3: Outside Victoria → rejected (None)
Test 4: Null coordinate → handled gracefully (None)
✅ All tests complete!
```

## Files in This Folder

```
grid_snapper/
├── grid_snapper.py           # Main utility
├── README.md                 # This file
└── docs/
    └── GRID_SNAPPER_DETAILED.md  # Architecture explanation
```

