import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


TEST_DB = Path("test_logi_core.db")
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.resolve().as_posix()}"

from app.db.init_db import init_db  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services.seed_service import SeedService  # noqa: E402


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    with SessionLocal() as db:
        for table_name in [
            "alerts",
            "telemetry_events",
            "invoices",
            "order_items",
            "orders",
            "vehicles",
            "drivers",
            "routes",
            "products",
            "customers",
        ]:
            db.execute(text(f"DELETE FROM {table_name}"))
        db.commit()
        SeedService().seed(db)
    yield


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
