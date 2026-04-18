from fastapi import FastAPI
from app.routers import hello
from app.routers import forecast
from contextlib import asynccontextmanager
from .internal.services.forecast_service import ForecastService
from .internal.services.messaging_service import MessagingService
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def init_lifespan_objects(app: FastAPI):
    messaging_service = await MessagingService.create()
    forecast_service = ForecastService()

    await messaging_service.consume_predictions(forecast_service.on_prediction_message)

    yield

    await messaging_service.close()

app = FastAPI(lifespan=init_lifespan_objects)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(hello.router)
app.include_router(forecast.router)