import joblib
import json
import numpy as np
from pathlib import Path
from .messaging_service import MessagingService
from .geojson_service import GeoJsonService
from ...models.geojson_model import FeatureCollection
from ...models.fire_event import FireEvent


class ModelService:
    def __init__(self, messaging: MessagingService, ):

        self.messaging = messaging
        self.geojson = GeoJsonService()

        # Get absolute path to model.pkl
        model_path = Path(__file__).resolve().parents[2] / "models" / "model.pkl"
        
        print("Loading model from:", model_path)  # optional debug
        
        self.model = joblib.load(model_path)

    async def predict(self, features: list[float]) -> float:
        data = np.array(features).reshape(1, -1)
        prediction = self.model.predict(data)
        return float(prediction[0])
    
    async def consume_data_publish_prediction(self, message):
        async with message.process():
            print("recieved fire_event data")
            body = json.loads(message.body.decode("utf-8"))
            fire_events: list[FireEvent] = [FireEvent.model_validate(item) for item in body]
            # map data to FireEvent
            # no need to send data to prediction function (prediction uses mock data)
            # TODO: implement sending data to actual AI model

            # model forms a prediction
            prediction: FeatureCollection = self.geojson.get_geojson()

            # send off to 'predictions' queue
            await self.messaging.publish_prediction(prediction)