from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Invoice, Order, OrderItem
from app.repositories.base import Repository


class InvoiceRepository(Repository[Invoice]):
    def __init__(self) -> None:
        super().__init__(Invoice)

    def get_by_order(self, db: Session, order_id: int) -> Invoice | None:
        query = (
            select(Invoice)
            .where(Invoice.order_id == order_id)
            .options(
                selectinload(Invoice.order).selectinload(Order.customer),
                selectinload(Invoice.order).selectinload(Order.items).selectinload(OrderItem.product),
            )
        )
        return db.scalar(query)

    def list_all(self, db: Session) -> list[Invoice]:
        query = (
            select(Invoice)
            .options(
                selectinload(Invoice.order).selectinload(Order.customer),
                selectinload(Invoice.order).selectinload(Order.items).selectinload(OrderItem.product),
            )
            .order_by(Invoice.issue_date.desc())
        )
        return list(db.scalars(query).all())

    def get_with_relations(self, db: Session, invoice_id: int) -> Invoice | None:
        query = (
            select(Invoice)
            .where(Invoice.id == invoice_id)
            .options(
                selectinload(Invoice.order).selectinload(Order.customer),
                selectinload(Invoice.order).selectinload(Order.items).selectinload(OrderItem.product),
            )
        )
        return db.scalar(query)
