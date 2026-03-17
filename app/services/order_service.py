from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import Customer, Order, OrderItem, Product, Route, Vehicle
from app.models.enums import OrderStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import OrderCreate
from app.services.invoice_service import InvoiceService
from app.utils.identifiers import make_order_number


class OrderService:
    def __init__(self) -> None:
        self.order_repository = OrderRepository()
        self.product_repository = ProductRepository()
        self.invoice_service = InvoiceService()

    def create_order(self, db: Session, payload: OrderCreate) -> Order:
        customer = db.get(Customer, payload.customer_id)
        if not customer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cliente nao encontrado")

        vehicle = db.get(Vehicle, payload.vehicle_id) if payload.vehicle_id else None
        route = db.get(Route, payload.route_id) if payload.route_id else None

        product_ids = [item.product_id for item in payload.items]
        products = self.product_repository.list_by_ids(db, product_ids)
        products_by_id = {product.id: product for product in products}
        if len(products_by_id) != len(set(product_ids)):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto nao encontrado")

        order = Order(
            order_number="PENDING",
            customer_id=customer.id,
            vehicle_id=vehicle.id if vehicle else None,
            route_id=route.id if route else None,
            status=OrderStatus.PENDING,
            expected_delivery_at=payload.expected_delivery_at,
        )
        db.add(order)
        db.flush()
        order.order_number = make_order_number(order.id)

        total = Decimal("0")
        for item in payload.items:
            product = products_by_id[item.product_id]
            if product.stock_quantity < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Estoque insuficiente para {product.name}",
                )
            product.stock_quantity -= item.quantity
            line_total = Decimal(str(product.unit_price)) * item.quantity
            total += line_total
            db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item.quantity,
                    unit_price=product.unit_price,
                )
            )

        order.total_amount = total
        db.commit()
        return self.get_order(db, order.id)

    def get_order(self, db: Session, order_id: int) -> Order:
        order = self.order_repository.get_with_items(db, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido nao encontrado")
        return order

    def list_orders(self, db: Session) -> list[Order]:
        return self.order_repository.list_all_with_relations(db)

    def update_status(self, db: Session, order_id: int, status_value: str) -> Order:
        order = db.scalar(
            select(Order)
            .where(Order.id == order_id)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.customer),
                selectinload(Order.vehicle),
                selectinload(Order.invoices),
            )
        )
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido nao encontrado")

        try:
            new_status = OrderStatus(status_value)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status invalido") from exc

        order.status = new_status
        if new_status == OrderStatus.IN_ROUTE:
            order.shipped_at = datetime.utcnow()
            self.invoice_service.ensure_invoice(db, order)
        elif new_status == OrderStatus.DELIVERED:
            order.delivered_at = datetime.utcnow()

        db.commit()
        return self.get_order(db, order.id)
