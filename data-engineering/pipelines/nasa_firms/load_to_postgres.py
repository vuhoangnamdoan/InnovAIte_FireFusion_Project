import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

csv_path = "../../data/processed/fire_events.csv"
df = pd.read_csv(csv_path)

df["event_id"] = pd.to_numeric(df["event_id"], errors="coerce").astype("Int64")
df["weather_id"] = pd.to_numeric(df["weather_id"], errors="coerce").astype("Int64")
df["topo_id"] = pd.to_numeric(df["topo_id"], errors="coerce").astype("Int64")
df["fuel_id"] = pd.to_numeric(df["fuel_id"], errors="coerce").astype("Int64")
df["facility_id"] = pd.to_numeric(df["facility_id"], errors="coerce").astype("Int64")
df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce").astype("Int64")
df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce").dt.date

create_table_sql = """
CREATE TABLE IF NOT EXISTS "Fire_Events" (
    event_id INTEGER PRIMARY KEY,
    weather_id INTEGER,
    topo_id INTEGER,
    fuel_id INTEGER,
    facility_id INTEGER,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    event_date DATE,
    confidence_score INTEGER,
    source_system VARCHAR(100)
);
"""

truncate_sql = 'TRUNCATE TABLE "Fire_Events";'

with engine.begin() as connection:
    connection.execute(text(create_table_sql))
    connection.execute(text(truncate_sql))

df.to_sql(
    "Fire_Events",
    con=engine,
    if_exists="append",
    index=False,
    method="multi"
)

print("Fire_Events data loaded successfully into PostgreSQL.")
print(f"Rows inserted: {len(df)}")