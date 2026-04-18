from fastapi import FastAPI
from contextlib import asynccontextmanager
from .routers.model_router import router as model_router
from .internal.services.messaging_service import MessagingService
from .internal.services.model_service import ModelService

@asynccontextmanager
async def init_lifespan_object(app: FastAPI):
    messaging_service = await MessagingService.create()
    try:
        model_service = ModelService(messaging_service)
        await messaging_service.consume_data(model_service.consume_data_publish_prediction)
        yield
    finally:
        await messaging_service.close()

app = FastAPI(title="Model API", version="1.0.0", lifespan=init_lifespan_object)
app.include_router(model_router)