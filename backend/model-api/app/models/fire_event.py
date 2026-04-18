from pydantic import BaseModel
from datetime import date

# uses defined view from database
# left joins on all foreign keys of fire_event table
# left joins can be empty hence None
class FireEvent(BaseModel):
    event_id: int
    latitude: float
    longitude: float
    event_date: date
    confidence_score: int
    temperature_c: float | None = None
    wind_speed_kmh: float | None = None
    relative_humidity: float | None = None
    elevation_meters: float | None = None
    slope_angle: float | None = None
    vegetation_class: str | None = None
    dryness_index: float | None = None
    soil_moisture: float | None = None
    facility_name: str | None = None
    category: str | None = None # infrastructure category