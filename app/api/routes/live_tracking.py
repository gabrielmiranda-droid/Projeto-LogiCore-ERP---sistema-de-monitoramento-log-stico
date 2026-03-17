import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status

from app.db.session import SessionLocal
from app.services.live_tracking_service import live_tracking_manager, live_tracking_service


router = APIRouter(prefix="/live", tags=["Live Tracking"])
ws_router = APIRouter(tags=["Live Tracking"])


@router.get("/vehicles/{vehicle_id}/bootstrap")
def get_live_vehicle_bootstrap(vehicle_id: int) -> dict:
    with SessionLocal() as db:
        payload = live_tracking_service.build_vehicle_payload(db, vehicle_id)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veiculo nao encontrado")
    return payload


@ws_router.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_live_tracking(websocket: WebSocket, vehicle_id: int) -> None:
    await websocket.accept()
    queue = live_tracking_manager.subscribe(vehicle_id)
    try:
        with SessionLocal() as db:
            payload = live_tracking_service.build_vehicle_payload(db, vehicle_id)
        if payload is not None:
            await websocket.send_json(payload)
        while True:
            try:
                message = await asyncio.wait_for(queue.get(), timeout=25)
                await websocket.send_json(message)
            except asyncio.TimeoutError:
                await websocket.send_json({"message_type": "heartbeat"})
    except WebSocketDisconnect:
        live_tracking_manager.unsubscribe(vehicle_id, queue)
    except Exception:
        live_tracking_manager.unsubscribe(vehicle_id, queue)
