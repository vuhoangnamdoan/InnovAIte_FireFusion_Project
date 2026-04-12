import json
from .websocket_connection_manager import ws_manager
from ..models.geojson import FeatureCollection

class ForecastService:
    async def on_prediction_message(self, message):
        async with message.process(): # handles deleting from queue but not on exceptions
            print("Processed message")
            payload = json.loads(message.body)
            geojson = FeatureCollection(**payload)
            print(geojson)
            await ws_manager.broadcast(geojson.model_dump())