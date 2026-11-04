from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

GST_RATE = 0.18
SELLER = "Online Marketplace for Handcrafted Goods"


def _text(value):
    return escape(str(value or "")).replace("\n", "<br/>")


def money(value):
    return f"INR {value:,.2f}"


def split_tax(total):
    # Prices already include GST, so split the total instead of adding tax.
    net = round(total / (1 + GST_RATE), 2)
    return net, round(total - net, 2)


def build_invoice_pdf(path, number, issued_at, order_id, buyer_name,
                      buyer_email, address, lines, total):
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    heading = ParagraphStyle(
        "inv_heading", parent=styles["Title"], fontSize=20, alignment=0)
    small = ParagraphStyle(
        "inv_small", parent=body, fontSize=8, textColor=colors.grey)
    doc = SimpleDocTemplate(
        path, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm, title=number, author=SELLER)

    meta = Table(
        [["Invoice no.", number, "Order no.", str(order_id)],
         ["Date", issued_at.strftime("%d %b %Y"), "Payment", "Paid"]],
        colWidths=[28 * mm, 52 * mm, 28 * mm, 52 * mm])
    meta.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    bill = Paragraph(
        "<b>Billed to</b><br/>" + _text(buyer_name) + "<br/>"
        + _text(buyer_email) + "<br/><br/><b>Ship to</b><br/>"
        + _text(address), body)

    rows = [["Item", "Qty", "Unit price", "Amount"]]
    for line in lines:
        rows.append([
            Paragraph(_text(line["title"]), body),
            str(line["quantity"]),
            money(line["unit_price"]),
            money(line["line_total"]),
        ])
    items = Table(rows, colWidths=[82 * mm, 18 * mm, 35 * mm, 35 * mm],
                  repeatRows=1)
    items.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F2")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))

    net, tax = split_tax(total)
    totals = Table(
        [["Amount before tax", money(net)],
         ["GST included (18%)", money(tax)],
         ["Total paid", money(total)]],
        colWidths=[135 * mm, 35 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("LINEABOVE", (0, 2), (-1, 2), 0.8, colors.black),
    ]))

    doc.build([
        Paragraph("TAX INVOICE", heading),
        Paragraph(_text(SELLER), body),
        Spacer(1, 6 * mm), meta, Spacer(1, 6 * mm),
        bill, Spacer(1, 6 * mm),
        items, Spacer(1, 4 * mm), totals, Spacer(1, 10 * mm),
        Paragraph("Prices include GST. This is a computer-generated "
                  "invoice and needs no signature.", small),
    ])
