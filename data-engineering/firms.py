import pandas as pd
import requests
from io import StringIO
from datetime import datetime, timedelta

# -----------------------------
# CONFIG
# -----------------------------
PRODUCT = "VIIRS_SNPP_NRT"

START_DATE = datetime(2019, 1, 1)
END_DATE = datetime(2020, 12, 31)

all_data = []

current_date = START_DATE

# -----------------------------
# LOOP THROUGH EACH DAY
# -----------------------------
while current_date <= END_DATE:

    year = current_date.year
    day_of_year = current_date.timetuple().tm_yday

    # Format day as 3 digits (001, 032, etc.)
    doy_str = str(day_of_year).zfill(3)

    url = f"https://firms.modaps.eosdis.nasa.gov/data/active_fire/{PRODUCT}/{year}/{doy_str}.csv"

    print(f"Downloading {current_date.strftime('%Y-%m-%d')}")

    response = requests.get(url)

    if response.status_code == 200:
        try:
            df = pd.read_csv(StringIO(response.text))

            # -----------------------------
            # FILTER AUSTRALIA
            # -----------------------------
            df = df[
                (df["longitude"] >= 112) &
                (df["longitude"] <= 154) &
                (df["latitude"] >= -44) &
                (df["latitude"] <= -10)
            ]

            all_data.append(df)

        except Exception as e:
            print(f"Error reading data for {current_date}: {e}")
    else:
        print(f"Missing data for {current_date}")

    current_date += timedelta(days=1)

# -----------------------------
# COMBINE DATA
# -----------------------------
if all_data:
    final_df = pd.concat(all_data, ignore_index=True)

    print(f"Total records: {len(final_df)}")

    final_df.to_csv("firms_australia_2019_2020.csv", index=False)

    print("✅ Data saved successfully!")
else:
    print("❌ No data downloaded.")