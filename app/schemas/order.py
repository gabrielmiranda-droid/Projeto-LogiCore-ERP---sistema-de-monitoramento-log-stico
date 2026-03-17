from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedSchema
from app.schemas.customer import CustomerRead
from app.schemas.product import ProductRead
from app.schemas.vehicle import VehicleRead


class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    customer_id: int
    vehicle_id: int | None = None
    route_id: int | None = None
    expected_delivery_at: datetime | None = None
    items: list[OrderItemCreate]


class OrderStatusUpdate(BaseModel):
    status: str


class OrderItemRead(ORMModel):
    id: int
    quantity: int
    unit_price: Decimal
    product: ProductRead


class OrderRead(TimestampedSchema):
    order_number: str
    customer: CustomerRead
    vehicle: VehicleRead | None
    route_id: int | None
    status: str
    total_amount: Decimal
    expected_delivery_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    items: list[OrderItemRead]
