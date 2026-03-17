from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Vehicle
from app.repositories.base import Repository


class VehicleRepository(Repository[Vehicle]):
    def __init__(self) -> None:
        super().__init__(Vehicle)

    def list_with_latest_positions(self, db: Session) -> list[Vehicle]:
        query = select(Vehicle).order_by(Vehicle.code)
        return list(db.scalars(query).all())
