import json
from .caching_service import cache_client
from .websocket_connection_manager import ws_manager
from ..models.geojson import FeatureCollection

class ForecastService:
    async def on_prediction_message(self, message):
        async with message.process(): # handles deleting from queue but not on exceptions
            print("Processed message")


            payload = json.loads(message.body)
            geojson = FeatureCollection(**payload)
            await ws_manager.broadcast(geojson.model_dump())

            await cache_client.set('predictions', message.body)

    async def fetch_predictions(self):
        data = await cache_client.get('predictions')
        if data is None:
            return None
        return json.loads(data)