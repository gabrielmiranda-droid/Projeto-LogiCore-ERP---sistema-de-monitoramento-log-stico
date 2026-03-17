from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.invoice import InvoiceRead
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.order_service import OrderService


router = APIRouter(prefix="/orders", tags=["Orders"])
service = OrderService()


def to_invoice_read(invoice) -> InvoiceRead:
    payload = InvoiceRead.model_validate(invoice)
    payload.pdf_download_url = f"/api/invoices/{invoice.id}/pdf"
    payload.xml_download_url = f"/api/invoices/{invoice.id}/xml"
    return payload


@router.post("", response_model=OrderRead, status_code=201)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)) -> OrderRead:
    order = service.create_order(db, payload)
    return OrderRead.model_validate(order)


@router.get("", response_model=list[OrderRead])
def list_orders(db: Session = Depends(get_db)) -> list[OrderRead]:
    orders = service.list_orders(db)
    return [OrderRead.model_validate(order) for order in orders]


@router.patch("/{order_id}/status", response_model=OrderRead)
def update_order_status(order_id: int, payload: OrderStatusUpdate, db: Session = Depends(get_db)) -> OrderRead:
    order = service.update_status(db, order_id, payload.status)
    return OrderRead.model_validate(order)


@router.get("/{order_id}/invoice", response_model=InvoiceRead)
def get_order_invoice(order_id: int, db: Session = Depends(get_db)) -> InvoiceRead:
    order = service.get_order(db, order_id)
    if not order.invoices:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal ainda nao gerada")
    invoice = order.invoices[0]
    return to_invoice_read(invoice)
