from datetime import datetime

from app.schemas.common import TimestampedSchema


class InvoiceRead(TimestampedSchema):
    invoice_number: str
    order_id: int
    customer_name: str
    customer_document: str
    product_description: str
    quantity: int
    unit_price: float
    total_value: float
    issue_date: datetime
    status: str
    pdf_path: str
    xml_path: str
    pdf_file_path: str
    pdf_download_url: str | None = None
    xml_download_url: str | None = None
