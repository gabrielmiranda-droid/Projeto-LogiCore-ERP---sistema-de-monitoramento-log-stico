from decimal import Decimal

from app.schemas.common import TimestampedSchema


class ProductRead(TimestampedSchema):
    sku: str
    name: str
    description: str
    unit_price: Decimal
    stock_quantity: int
    weight_kg: float
