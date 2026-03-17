from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import alerts, dashboard, invoices, live_tracking, orders, routes, telemetry, vehicles
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.seed_service import SeedService


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    init_db()
    with SessionLocal() as db:
        SeedService().seed(db)
    yield


settings = get_settings()
app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan)

app.include_router(telemetry.router, prefix="/api")
app.include_router(vehicles.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(invoices.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(live_tracking.router, prefix="/api")
app.include_router(live_tracking.ws_router)

live_tracking_dir = Path(__file__).resolve().parents[1] / "live_tracking"
app.mount("/live-tracking", StaticFiles(directory=live_tracking_dir, html=True), name="live-tracking")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "LogiCore ERP API online"}
