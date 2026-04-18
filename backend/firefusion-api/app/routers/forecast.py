from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from ..internal.services.forecast_service import ForecastService
from ..internal.services.websocket_connection_manager import ws_manager
from ..internal.services.caching_service import cache_client

router = APIRouter(prefix="/api", tags=["bushfire"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text() # leave connection open until user dc
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)

@router.get("/bushfire-forecast", tags=["bushfire"])
async def get_bushfire_forecast(service: ForecastService = Depends(ForecastService)):
    return await service.fetch_predictions()