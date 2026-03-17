from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Alert, Order, TelemetryEvent, Vehicle
from app.models.enums import OrderStatus
from app.schemas.kpi import KPIRead


class KPIService:
    def get_operational_kpis(self, db: Session) -> KPIRead:
        active_vehicles = db.scalar(select(func.count(Vehicle.id)).where(Vehicle.status == "EM_MOVIMENTO")) or 0
        open_alerts = db.scalar(select(func.count(Alert.id)).where(Alert.resolved.is_(False))) or 0
        orders_in_route = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.IN_ROUTE)) or 0
        pending_orders = db.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)) or 0

        average_delivery_hours = (
            db.scalar(
                select(
                    func.avg(
                        (func.julianday(Order.delivered_at) - func.julianday(Order.shipped_at)) * 24
                    )
                ).where(Order.delivered_at.is_not(None), Order.shipped_at.is_not(None))
            )
            or 0
        )
        average_fleet_occupancy = db.scalar(select(func.avg(TelemetryEvent.cargo_occupancy))) or 0
        average_fuel_level = db.scalar(select(func.avg(TelemetryEvent.fuel_level))) or 0

        return KPIRead(
            active_vehicles=int(active_vehicles),
            open_alerts=int(open_alerts),
            orders_in_route=int(orders_in_route),
            pending_orders=int(pending_orders),
            average_delivery_hours=round(float(average_delivery_hours), 2),
            average_fleet_occupancy=round(float(average_fleet_occupancy), 2),
            average_fuel_level=round(float(average_fuel_level), 2),
        )
