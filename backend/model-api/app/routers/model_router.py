from fastapi import APIRouter
from ..internal.services.geojson_service import GeoJsonService

router = APIRouter(
    prefix="/model",
    tags=["model"]
)
geojson_service = GeoJsonService()

@router.get("/hello")
async def hello():
    return {"message": "Hello from model-api"}


@router.get("/geojson")
async def get_geojson():
    return geojson_service.get_geojson()