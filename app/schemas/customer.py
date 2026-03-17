from app.schemas.common import TimestampedSchema


class CustomerRead(TimestampedSchema):
    name: str
    tax_id: str
    email: str
    address: str
    city: str
    state: str
