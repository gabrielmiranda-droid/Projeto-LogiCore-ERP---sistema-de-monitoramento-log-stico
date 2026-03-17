from datetime import datetime


def make_order_number(order_id: int) -> str:
    return f"ORD-{datetime.utcnow():%Y%m%d}-{order_id:05d}"


def make_invoice_number(order_id: int) -> str:
    return f"NF-{datetime.utcnow():%Y%m%d}-{order_id:05d}"
