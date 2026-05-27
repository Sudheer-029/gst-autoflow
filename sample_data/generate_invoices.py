"""
Generate realistic sample PDF invoices for Module 2 testing.
Creates 6 invoices with varying formats and amounts.
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os

os.makedirs("sample_data/invoices", exist_ok=True)

INVOICES = [
    {
        "vendor": "Apex Traders", "vendor_gstin": "27AABCT1234A1Z5",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "APX-2024-001", "inv_date": "05/04/2024",
        "items": [("Premium Fabric Roll 50m", 10, 4500.0)],
        "cgst_rate": 2.5, "sgst_rate": 2.5, "igst_rate": 0,
    },
    {
        "vendor": "Blue Star Supplies", "vendor_gstin": "29AABCB5678B1Z3",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "BSS/2024/102", "inv_date": "12/04/2024",
        "items": [("Wooden Handles Batch", 50, 320.0), ("Brass Fittings Set", 20, 180.0)],
        "cgst_rate": 0, "sgst_rate": 0, "igst_rate": 18,
    },
    {
        "vendor": "Crown Enterprises", "vendor_gstin": "06AABCC9012C1Z1",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "CRN-INV-2024-0045", "inv_date": "18/04/2024",
        "items": [("Velvet Lining Material", 30, 1200.0)],
        "cgst_rate": 0, "sgst_rate": 0, "igst_rate": 12,
    },
    {
        "vendor": "Delta Industries", "vendor_gstin": "33AABCD3456D1Z9",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "DLT2024050", "inv_date": "03/05/2024",
        "items": [("Leather Strip 5mm x 100m", 5, 8500.0), ("Thread Spool Pack", 10, 250.0)],
        "cgst_rate": 2.5, "sgst_rate": 2.5, "igst_rate": 0,
    },
    {
        "vendor": "Eagle Exports", "vendor_gstin": "24AABCE7890E1Z7",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "EGL/INV/24-55", "inv_date": "22/05/2024",
        "items": [("Hand-tooled Emboss Plate", 8, 3750.0)],
        "cgst_rate": 0, "sgst_rate": 0, "igst_rate": 18,
    },
    {
        "vendor": "Fortune Goods", "vendor_gstin": "07AABCF1234F1Z4",
        "buyer": "Jaipur Trunks Pvt Ltd", "buyer_gstin": "08AABCJ1234A1Z5",
        "inv_no": "FG-2024-0312", "inv_date": "28/05/2024",
        "items": [("Rivets Brass Pack 500", 20, 180.0), ("Zinc Alloy Locks", 15, 420.0)],
        "cgst_rate": 6.0, "sgst_rate": 6.0, "igst_rate": 0,
    },
]


def make_invoice(data: dict, output_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=16, spaceAfter=4)
    SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=9)
    BOLD  = ParagraphStyle("BOLD", parent=styles["Normal"], fontSize=9, fontName="Helvetica-Bold")

    elems = []

    # Header
    elems.append(Paragraph("TAX INVOICE", H1))
    elems.append(Spacer(1, 4*mm))

    # Vendor / Buyer info
    info = [
        ["Vendor / Supplier", "", "Invoice Details", ""],
        [data["vendor"], "", f"Invoice No: {data['inv_no']}", ""],
        [f"GSTIN: {data['vendor_gstin']}", "", f"Invoice Date: {data['inv_date']}", ""],
        ["", "", "", ""],
        ["Bill To (Buyer)", "", "", ""],
        [data["buyer"], "", "", ""],
        [f"GSTIN: {data['buyer_gstin']}", "", "", ""],
    ]
    info_table = Table(info, colWidths=[80*mm, 10*mm, 80*mm, 10*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME",  (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTNAME",  (2,0), (2,0), "Helvetica-Bold"),
        ("FONTSIZE",  (0,0), (-1,-1), 9),
        ("VALIGN",    (0,0), (-1,-1), "TOP"),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    elems.append(info_table)
    elems.append(Spacer(1, 6*mm))

    # Items table
    item_header = ["#", "Description", "Qty", "Unit Price (₹)", "Amount (₹)"]
    item_rows   = [item_header]
    subtotal    = 0.0

    for i, (desc, qty, unit) in enumerate(data["items"], 1):
        amt = round(qty * unit, 2)
        subtotal += amt
        item_rows.append([str(i), desc, str(qty), f"{unit:,.2f}", f"{amt:,.2f}"])

    item_rows.append(["", "", "", "Taxable Value:", f"{subtotal:,.2f}"])

    cgst = round(subtotal * data["cgst_rate"] / 100, 2)
    sgst = round(subtotal * data["sgst_rate"] / 100, 2)
    igst = round(subtotal * data["igst_rate"] / 100, 2)

    if igst > 0:
        item_rows.append(["", "", "", f"IGST @ {data['igst_rate']}%:", f"{igst:,.2f}"])
    if cgst > 0:
        item_rows.append(["", "", "", f"CGST @ {data['cgst_rate']}%:", f"{cgst:,.2f}"])
    if sgst > 0:
        item_rows.append(["", "", "", f"SGST @ {data['sgst_rate']}%:", f"{sgst:,.2f}"])

    grand_total = round(subtotal + igst + cgst + sgst, 2)
    item_rows.append(["", "", "", "Grand Total:", f"{grand_total:,.2f}"])

    col_widths = [10*mm, 80*mm, 15*mm, 35*mm, 30*mm]
    tbl = Table(item_rows, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), colors.HexColor("#1F3864")),
        ("TEXTCOLOR",    (0, 0), (-1, 0), colors.white),
        ("FONTNAME",     (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",     (3,-1), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1,-1), 9),
        ("ALIGN",        (2, 0), (-1,-1), "RIGHT"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("LINEBELOW",    (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEABOVE",    (0,-1), (-1,-1), 0.5, colors.black),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    elems.append(tbl)

    elems.append(Spacer(1, 8*mm))
    elems.append(Paragraph(
        "This is a computer-generated invoice. No signature required.", SMALL
    ))

    doc.build(elems)
    print(f"  Created: {output_path}")


if __name__ == "__main__":
    for i, inv in enumerate(INVOICES, 1):
        path = f"sample_data/invoices/invoice_{i:02d}_{inv['vendor'].replace(' ','_')}.pdf"
        make_invoice(inv, path)
    print(f"\n6 sample invoices created in sample_data/invoices/")
