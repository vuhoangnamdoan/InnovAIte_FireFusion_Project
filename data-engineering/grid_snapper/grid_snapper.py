"""
FireFusion Grid Snapper Utility
================================
Converts raw GPS coordinates from any data source (NASA FIRMS, Open-Meteo, ELVIS)
into a unified location_id from the Location_Registry table.

Usage (for team members):
--------------------------
    from src.grid_snapper import GridSnapper

    snapper = GridSnapper()
    location_id = snapper.get_location_id(-37.8147, 145.0892)
    print(location_id)  # Returns: 4521

Author: Dhruv Surti (Data Engineering Lead)
Project: FireFusion - Deakin University Capstone
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()

# Victoria bounding box (used to validate coordinates)
VICTORIA_BOUNDS = {
    "lat_min": -39.2,
    "lat_max": -34.0,
    "lon_min": 140.96,
    "lon_max": 150.0
}

# Grid resolution in degrees
# 0.1 degrees ≈ 11 km — fine enough to distinguish fire locations
GRID_SIZE = 0.1


class GridSnapper:
    """
    Converts raw coordinates to location_id.

    All pipelines (fire, weather, vegetation, topography) use this
    tool to align their data to the universal Victorian grid.
    """

    def __init__(self):
        """Connect to Supabase on initialization."""
        try:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                port=os.getenv("DB_PORT"),
                database=os.getenv("DB_NAME")
            )
            self.cursor = self.conn.cursor()
            print("✅ GridSnapper connected to Supabase")
        except Exception as e:
            print(f"❌ GridSnapper connection failed: {e}")
            raise

    # -------------------------
    # STEP 1: Validate
    # -------------------------
    def is_valid_victoria(self, latitude, longitude):
        """
        Check if the coordinate is within Victoria bounds.

        Returns True if valid, False if outside Victoria.
        """
        if latitude is None or longitude is None:
            return False

        in_lat = VICTORIA_BOUNDS["lat_min"] <= latitude <= VICTORIA_BOUNDS["lat_max"]
        in_lon = VICTORIA_BOUNDS["lon_min"] <= longitude <= VICTORIA_BOUNDS["lon_max"]

        return in_lat and in_lon

    # -------------------------
    # STEP 2: Snap to Grid
    # -------------------------
    def snap(self, latitude, longitude):
        """
        Round raw coordinates to the nearest 0.1° grid point.

        Example:
            snap(-37.8147, 145.0892)
            → (-37.8, 145.1)
        """
        snapped_lat = round(round(latitude / GRID_SIZE) * GRID_SIZE, 4)
        snapped_lon = round(round(longitude / GRID_SIZE) * GRID_SIZE, 4)
        return snapped_lat, snapped_lon

    # -------------------------
    # STEP 3: Get or Create location_id
    # -------------------------
    def get_location_id(self, latitude, longitude):
        """
        Main function used by all pipelines.

        Takes raw coordinates, validates them, snaps to grid,
        then looks up or creates a location_id in Location_Registry.

        Returns:
            location_id (int) if successful
            None if coordinates are invalid or outside Victoria
        
        Example:
            snapper = GridSnapper()
            location_id = snapper.get_location_id(-37.8147, 145.0892)
            → Returns: 4521
        """

        # Step 1: Validate coordinates
        if not self.is_valid_victoria(latitude, longitude):
            print(f"⚠️  Skipped: ({latitude}, {longitude}) is outside Victoria bounds")
            return None

        # Step 2: Snap to grid
        snapped_lat, snapped_lon = self.snap(latitude, longitude)

        # Step 3: Check if location already exists in registry
        self.cursor.execute(
            """
            SELECT location_id FROM location_registry
            WHERE grid_latitude = %s AND grid_longitude = %s
            """,
            (snapped_lat, snapped_lon)
        )
        result = self.cursor.fetchone()

        # Step 4: If exists, return its ID
        if result:
            return result[0]

        # Step 5: If not exists, create new location entry
        self.cursor.execute(
            """
            INSERT INTO location_registry (grid_latitude, grid_longitude, region_name)
            VALUES (%s, %s, %s)
            RETURNING location_id
            """,
            (snapped_lat, snapped_lon, "Victoria")
        )
        self.conn.commit()
        new_id = self.cursor.fetchone()[0]
        print(f"📍 New location created: ID={new_id} ({snapped_lat}, {snapped_lon})")
        return new_id

    # -------------------------
    # UTILITY: Close connection
    # -------------------------
    def close(self):
        """Close the database connection when done."""
        self.cursor.close()
        self.conn.close()
        print("🔒 GridSnapper connection closed")


# -------------------------
# Quick Test (run this file directly to test)
# -------------------------
if __name__ == "__main__":
    print("Testing GridSnapper...")
    print("=" * 40)

    snapper = GridSnapper()

    # Test 1: Valid Victoria coordinate
    print("\nTest 1: Valid Victorian coordinate")
    loc_id = snapper.get_location_id(-37.8147, 145.0892)
    print(f"location_id: {loc_id}")

    # Test 2: Same location (slightly different coordinate — should return same ID)
    print("\nTest 2: Slightly different coordinate (should return same ID)")
    loc_id2 = snapper.get_location_id(-37.8199, 145.0901)
    print(f"location_id: {loc_id2}")
    print(f"Match: {loc_id == loc_id2} ✅" if loc_id == loc_id2 else f"No match ❌")

    # Test 3: Outside Victoria
    print("\nTest 3: Outside Victoria (Sydney)")
    loc_id3 = snapper.get_location_id(-33.8688, 151.2093)
    print(f"location_id: {loc_id3}")

    # Test 4: Null coordinate
    print("\nTest 4: Null coordinate")
    loc_id4 = snapper.get_location_id(None, None)
    print(f"location_id: {loc_id4}")

    snapper.close()
    print("\n✅ All tests complete!")