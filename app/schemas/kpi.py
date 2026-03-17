from pydantic import BaseModel


class KPIRead(BaseModel):
    active_vehicles: int
    open_alerts: int
    orders_in_route: int
    pending_orders: int
    average_delivery_hours: float
    average_fleet_occupancy: float
    average_fuel_level: float
