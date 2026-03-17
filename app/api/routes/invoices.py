from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.invoice import InvoiceRead
from app.services.invoice_service import InvoiceService


router = APIRouter(prefix="/invoices", tags=["Invoices"])
service = InvoiceService()


def to_invoice_read(invoice) -> InvoiceRead:
    payload = InvoiceRead.model_validate(invoice)
    payload.pdf_download_url = f"/api/invoices/{invoice.id}/pdf"
    payload.xml_download_url = f"/api/invoices/{invoice.id}/xml"
    return payload


@router.get("", response_model=list[InvoiceRead])
def list_invoices(db: Session = Depends(get_db)) -> list[InvoiceRead]:
    invoices = service.list_invoices(db)
    return [to_invoice_read(invoice) for invoice in invoices]


@router.get("/{invoice_id}", response_model=InvoiceRead)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)) -> InvoiceRead:
    invoice = service.get_invoice(db, invoice_id)
    return to_invoice_read(invoice)


@router.post("/generate/{order_id}", response_model=InvoiceRead, status_code=201)
def generate_invoice(order_id: int, db: Session = Depends(get_db)) -> InvoiceRead:
    invoice = service.generate_for_order(db, order_id)
    db.commit()
    return to_invoice_read(invoice)


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db)) -> FileResponse:
    invoice = service.get_invoice(db, invoice_id)
    return FileResponse(path=Path(invoice.pdf_path), media_type="application/pdf", filename=Path(invoice.pdf_path).name)


@router.get("/{invoice_id}/xml")
def download_invoice_xml(invoice_id: int, db: Session = Depends(get_db)) -> FileResponse:
    invoice = service.get_invoice(db, invoice_id)
    return FileResponse(path=Path(invoice.xml_path), media_type="application/xml", filename=Path(invoice.xml_path).name)
