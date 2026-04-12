from pydantic import BaseModel
from typing import Any

class Geometry(BaseModel):
    type: str  # "Point", "Polygon", etc.
    coordinates: list[Any]

class Properties(BaseModel):
    risk_factor: int

class Feature(BaseModel):
    type: str = "Feature"
    geometry: Geometry
    properties: Properties

class FeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: list[Feature]