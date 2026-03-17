from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Product
from app.repositories.base import Repository


class ProductRepository(Repository[Product]):
    def __init__(self) -> None:
        super().__init__(Product)

    def list_by_ids(self, db: Session, product_ids: list[int]) -> list[Product]:
        if not product_ids:
            return []
        query = select(Product).where(Product.id.in_(product_ids))
        return list(db.scalars(query).all())
