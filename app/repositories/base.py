from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class Repository(Generic[ModelType]):
    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    def get(self, db: Session, obj_id: int) -> ModelType | None:
        return db.get(self.model, obj_id)

    def list_all(self, db: Session) -> list[ModelType]:
        return list(db.scalars(select(self.model)).all())
