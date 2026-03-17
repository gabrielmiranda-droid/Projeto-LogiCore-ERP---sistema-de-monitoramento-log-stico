from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class TimestampedSchema(ORMModel):
    id: int
    created_at: datetime
    updated_at: datetime
