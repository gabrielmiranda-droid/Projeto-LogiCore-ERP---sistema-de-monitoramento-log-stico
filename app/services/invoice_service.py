from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Invoice, Order
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.order_repository import OrderRepository
from app.utils.identifiers import make_invoice_number


class InvoiceService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.invoice_repository = InvoiceRepository()
        self.order_repository = OrderRepository()

    def list_invoices(self, db: Session) -> list[Invoice]:
        return self.invoice_repository.list_all(db)

    def get_invoice(self, db: Session, invoice_id: int) -> Invoice:
        invoice = self.invoice_repository.get_with_relations(db, invoice_id)
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nota fiscal nao encontrada")
        return invoice

    def generate_for_order(self, db: Session, order_id: int) -> Invoice:
        order = self.order_repository.get_with_items(db, order_id)
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido nao encontrado")
        return self.ensure_invoice(db, order)

    def ensure_invoice(self, db: Session, order: Order) -> Invoice:
        existing = self.invoice_repository.get_by_order(db, order.id)
        if existing:
            return existing

        invoice_number = make_invoice_number(order.id)
        pdf_path = self._build_pdf(order, invoice_number)
        xml_path = self._build_xml(order, invoice_number)
        invoice = Invoice(
            order_id=order.id,
            invoice_number=invoice_number,
            issue_date=datetime.utcnow(),
            pdf_path=str(pdf_path),
            xml_path=str(xml_path),
        )
        db.add(invoice)
        db.flush()
        return invoice

    def _build_pdf(self, order: Order, invoice_number: str) -> Path:
        path = self.settings.invoice_dir / f"{invoice_number}.pdf"
        issue_date = datetime.utcnow()
        subtotal = float(order.total_amount)
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(
            str(path),
            pagesize=A4,
            topMargin=18 * mm,
            bottomMargin=16 * mm,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            title=f"Nota Fiscal Simulada {invoice_number}",
        )

        brand_style = ParagraphStyle(
            "Brand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#0b3f5c"),
            alignment=TA_LEFT,
        )
        title_style = ParagraphStyle(
            "Title",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#17324d"),
            alignment=TA_LEFT,
        )
        meta_style = ParagraphStyle(
            "Meta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334e68"),
            alignment=TA_RIGHT,
        )
        section_label_style = ParagraphStyle(
            "SectionLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#486581"),
            alignment=TA_LEFT,
        )
        value_style = ParagraphStyle(
            "Value",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#102a43"),
            alignment=TA_LEFT,
        )
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#7b8794"),
            alignment=TA_LEFT,
        )
        summary_label_style = ParagraphStyle(
            "SummaryLabel",
            parent=value_style,
            alignment=TA_RIGHT,
        )
        summary_total_style = ParagraphStyle(
            "SummaryTotal",
            parent=value_style,
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=colors.HexColor("#0b3f5c"),
            alignment=TA_RIGHT,
        )

        story: list = []

        header_data = [
            [
                Paragraph("LogiCore ERP", brand_style),
                Paragraph(
                    "<br/>".join(
                        [
                            f"Nota: <b>{invoice_number}</b>",
                            f"Emissao: {issue_date:%d/%m/%Y %H:%M}",
                            "Status: <b>EMITIDA</b>",
                        ]
                    ),
                    meta_style,
                ),
            ],
            [
                Paragraph("NOTA FISCAL SIMULADA", title_style),
                "",
            ],
        ]
        header_table = Table(header_data, colWidths=[110 * mm, 60 * mm])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("SPAN", (0, 1), (1, 1)),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ("LINEBELOW", (0, 1), (-1, 1), 1, colors.HexColor("#bcccdc")),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 7 * mm))

        address = f"{order.customer.address}, {order.customer.city}/{order.customer.state}"
        info_left = [
            Paragraph("CLIENTE", section_label_style),
            Paragraph(order.customer.name, value_style),
            Paragraph("DOCUMENTO", section_label_style),
            Paragraph(order.customer.tax_id, value_style),
            Paragraph("ENDERECO", section_label_style),
            Paragraph(address, value_style),
        ]
        info_right = [
            Paragraph("NUMERO DO PEDIDO", section_label_style),
            Paragraph(order.order_number, value_style),
            Paragraph("DATA DE EMISSAO", section_label_style),
            Paragraph(f"{issue_date:%d/%m/%Y %H:%M}", value_style),
            Paragraph("STATUS", section_label_style),
            Paragraph("EMITIDA", value_style),
            Paragraph("NUMERO DA NOTA", section_label_style),
            Paragraph(invoice_number, value_style),
        ]
        info_table = Table(
            [[info_left, info_right]],
            colWidths=[85 * mm, 85 * mm],
        )
        info_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#d9e2ec")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 10),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ]
            )
        )
        story.append(info_table)
        story.append(Spacer(1, 8 * mm))

        item_rows = [
            [
                Paragraph("<b>Item</b>", value_style),
                Paragraph("<b>Descricao</b>", value_style),
                Paragraph("<b>Quantidade</b>", value_style),
                Paragraph("<b>Valor Unitario</b>", value_style),
                Paragraph("<b>Total</b>", value_style),
            ]
        ]
        for index, item in enumerate(order.items, start=1):
            line_total = float(item.unit_price) * item.quantity
            item_rows.append(
                [
                    Paragraph(str(index), value_style),
                    Paragraph(item.product.name, value_style),
                    Paragraph(str(item.quantity), value_style),
                    Paragraph(f"R$ {float(item.unit_price):.2f}", value_style),
                    Paragraph(f"R$ {line_total:.2f}", value_style),
                ]
            )

        item_table = Table(
            item_rows,
            colWidths=[14 * mm, 78 * mm, 22 * mm, 34 * mm, 32 * mm],
            repeatRows=1,
        )
        item_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3f5c")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("LEADING", (0, 0), (-1, -1), 11),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fbff")]),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ]
            )
        )
        story.append(item_table)
        story.append(Spacer(1, 8 * mm))

        summary_data = [
            [Paragraph("Subtotal", summary_label_style), Paragraph(f"R$ {subtotal:.2f}", summary_label_style)],
            [Paragraph("Total Geral", summary_total_style), Paragraph(f"R$ {subtotal:.2f}", summary_total_style)],
        ]
        summary_table = Table(summary_data, colWidths=[35 * mm, 35 * mm], hAlign="RIGHT")
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f7fa")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#bcccdc")),
                    ("LINEABOVE", (0, 1), (-1, 1), 0.75, colors.HexColor("#829ab1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )
        story.append(summary_table)
        story.append(Spacer(1, 10 * mm))
        story.append(
            Paragraph(
                "Documento simulado gerado automaticamente pelo LogiCore ERP para fins de demonstracao.",
                footer_style,
            )
        )

        doc.build(story)
        return path

    def _build_xml(self, order: Order, invoice_number: str) -> Path:
        path = self.settings.xml_dir / f"{invoice_number}.xml"
        root = ET.Element("nfe")
        ide = ET.SubElement(root, "identificacao")
        ET.SubElement(ide, "numero").text = invoice_number
        ET.SubElement(ide, "pedido").text = order.order_number
        ET.SubElement(ide, "emissao").text = datetime.utcnow().isoformat()
        ET.SubElement(ide, "status").text = "EMITIDA"

        emit = ET.SubElement(root, "emitente")
        ET.SubElement(emit, "razao_social").text = "LogiCore Distribuicao LTDA"
        ET.SubElement(emit, "cnpj").text = "12345678000199"

        dest = ET.SubElement(root, "destinatario")
        ET.SubElement(dest, "nome").text = order.customer.name
        ET.SubElement(dest, "documento").text = order.customer.tax_id
        ET.SubElement(dest, "endereco").text = order.customer.address

        items = ET.SubElement(root, "itens")
        for idx, item in enumerate(order.items, start=1):
            node = ET.SubElement(items, "item", numero=str(idx))
            ET.SubElement(node, "descricao").text = item.product.name
            ET.SubElement(node, "quantidade").text = str(item.quantity)
            ET.SubElement(node, "valor_unitario").text = f"{float(item.unit_price):.2f}"

        totals = ET.SubElement(root, "totais")
        ET.SubElement(totals, "valor_total").text = f"{float(order.total_amount):.2f}"

        tree = ET.ElementTree(root)
        tree.write(path, encoding="utf-8", xml_declaration=True)
        return path
