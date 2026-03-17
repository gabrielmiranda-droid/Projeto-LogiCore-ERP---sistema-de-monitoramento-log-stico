from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ModuleNotFoundError:
    from pydantic import BaseModel

    BaseSettings = BaseModel  # type: ignore[assignment]
    SettingsConfigDict = None


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    app_name: str = "LogiCore ERP"
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    dashboard_port: int = 8501
    database_url: str = "sqlite:///./logi_core.db"
    log_level: str = "INFO"
    simulator_interval_seconds: int = 5
    geofence_tolerance_km: float = 1.2
    critical_fuel_level: float = 15.0
    speed_limit_kmh: float = 90.0
    alert_delay_minutes: int = 20
    osrm_directions_url: str = "https://router.project-osrm.org/route/v1/driving"
    storage_dir: Path = BASE_DIR / "storage"
    invoice_dir: Path = BASE_DIR / "storage" / "invoices"
    xml_dir: Path = BASE_DIR / "storage" / "xml"

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def __init__(self, **kwargs):
        if SettingsConfigDict is None:
            env_values = {
                "app_name": os.getenv("APP_NAME", "LogiCore ERP"),
                "app_env": os.getenv("APP_ENV", "development"),
                "api_host": os.getenv("API_HOST", "0.0.0.0"),
                "api_port": int(os.getenv("API_PORT", "8000")),
                "dashboard_port": int(os.getenv("DASHBOARD_PORT", "8501")),
                "database_url": os.getenv("DATABASE_URL", "sqlite:///./logi_core.db"),
                "log_level": os.getenv("LOG_LEVEL", "INFO"),
                "simulator_interval_seconds": int(os.getenv("SIMULATOR_INTERVAL_SECONDS", "5")),
                "geofence_tolerance_km": float(os.getenv("GEOFENCE_TOLERANCE_KM", "1.2")),
                "critical_fuel_level": float(os.getenv("CRITICAL_FUEL_LEVEL", "15")),
                "speed_limit_kmh": float(os.getenv("SPEED_LIMIT_KMH", "90")),
                "alert_delay_minutes": int(os.getenv("ALERT_DELAY_MINUTES", "20")),
                "osrm_directions_url": os.getenv(
                    "OSRM_DIRECTIONS_URL",
                    "https://router.project-osrm.org/route/v1/driving",
                ),
                "storage_dir": BASE_DIR / "storage",
                "invoice_dir": BASE_DIR / "storage" / "invoices",
                "xml_dir": BASE_DIR / "storage" / "xml",
            }
            env_values.update(kwargs)
            super().__init__(**env_values)
            return
        super().__init__(**kwargs)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.invoice_dir.mkdir(parents=True, exist_ok=True)
    settings.xml_dir.mkdir(parents=True, exist_ok=True)
    return settings
