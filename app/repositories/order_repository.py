from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Order, OrderItem
from app.repositories.base import Repository


class OrderRepository(Repository[Order]):
    def __init__(self) -> None:
        super().__init__(Order)

    def get_with_items(self, db: Session, order_id: int) -> Order | None:
        query = (
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.customer),
                selectinload(Order.vehicle),
                selectinload(Order.invoices),
            )
        )
        return db.scalar(query)

    def list_all_with_relations(self, db: Session) -> list[Order]:
        query = (
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.customer),
                selectinload(Order.vehicle),
                selectinload(Order.invoices),
            )
            .order_by(desc(Order.created_at))
        )
        return list(db.scalars(query).all())
