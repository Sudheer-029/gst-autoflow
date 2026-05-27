"""
Excel Report Generator — color-coded, client-ready output.
"""
import pandas as pd
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from datetime import datetime
import os

# Colour palette
GREEN  = "C6EFCE"   # matched clean
YELLOW = "FFEB9C"   # amount mismatch
RED    = "FFC7CE"   # missing in GSTR-2A (ITC at risk)
BLUE   = "BDD7EE"   # extra in GSTR-2A (not in books)
HEADER = "1F3864"   # dark navy header

def _header_style(ws, row=1):
    for cell in ws[row]:
        cell.font = Font(color="FFFFFF", bold=True)
        cell.fill = PatternFill("solid", fgColor=HEADER)
        cell.alignment = Alignment(horizontal="center", vertical="center")

def _fill_rows(ws, fill_color, start_row=2):
    fill = PatternFill("solid", fgColor=fill_color)
    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row):
        for cell in row:
            cell.fill = fill

def _autofit(ws):
    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=8)
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 40)

def _write_sheet(wb, title, df, fill_color, note=None):
    ws = wb.create_sheet(title=title)
    if note:
        ws.append([f"ℹ  {note}"])
        ws["A1"].font = Font(italic=True, color="595959")
        ws.append([])  # blank row
        start_data = 3
    else:
        start_data = 1

    if df.empty:
        ws.append(["No records in this category."])
        return

    # Headers
    headers = list(df.columns)
    ws.append(headers)
    _header_style(ws, row=start_data)

    for _, row in df.iterrows():
        ws.append([row[c] for c in headers])

    _fill_rows(ws, fill_color, start_row=start_data + 1)
    _autofit(ws)


def generate_report(results: dict, output_dir: str = "output") -> str:
    from openpyxl import Workbook

    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"GST_Reconciliation_Report_{ts}.xlsx")

    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    s = results["summary"]

    # --- Summary Sheet ---
    ws_sum = wb.create_sheet("Summary", 0)
    ws_sum.sheet_view.showGridLines = False

    summary_data = [
        ["GST RECONCILIATION REPORT", ""],
        [f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", ""],
        ["", ""],
        ["Category", "Count / Value"],
        ["Purchase Register — Total Invoices", s["total_pr"]],
        ["GSTR-2A — Total Invoices", s["total_gstr2a"]],
        ["", ""],
        ["✅  Matched (Clean)", s["matched_clean"]],
        ["⚠️  Amount Mismatch", s["amount_mismatch"]],
        ["🔴  Missing in GSTR-2A (ITC at Risk)", s["missing_in_gstr2a"]],
        ["🔵  In GSTR-2A but Not in Books", s["not_in_books"]],
        ["", ""],
        ["Purchase Register — Total Taxable (₹)", f"₹{s['pr_taxable_total']:,.2f}"],
        ["GSTR-2A — Total Taxable (₹)", f"₹{s['g2a_taxable_total']:,.2f}"],
        ["ITC at Risk (₹)", f"₹{s['itc_at_risk']:,.2f}"],
    ]

    for row_data in summary_data:
        ws_sum.append(row_data)

    # Style summary
    ws_sum["A1"].font = Font(size=14, bold=True, color=HEADER)
    ws_sum["A4"].font = Font(bold=True, color="FFFFFF")
    ws_sum["A4"].fill = PatternFill("solid", fgColor=HEADER)
    ws_sum["B4"].font = Font(bold=True, color="FFFFFF")
    ws_sum["B4"].fill = PatternFill("solid", fgColor=HEADER)

    # Highlight ITC at risk in red
    ws_sum["B15"].fill = PatternFill("solid", fgColor=RED)
    ws_sum["B15"].font = Font(bold=True)

    ws_sum.column_dimensions["A"].width = 42
    ws_sum.column_dimensions["B"].width = 28

    # --- Detail Sheets ---
    _write_sheet(wb, "✅ Matched",
                 results["matched"], GREEN,
                 note="Invoices matched in both Purchase Register and GSTR-2A with no discrepancy.")

    _write_sheet(wb, "⚠ Amount Mismatch",
                 results["amount_mismatch"], YELLOW,
                 note="Invoices found in both files but with different taxable/GST amounts. Review with supplier.")

    _write_sheet(wb, "🔴 Missing in GSTR2A",
                 results["missing_in_gstr2a"], RED,
                 note="In your Purchase Register but NOT filed by supplier. ITC cannot be claimed. Chase supplier to file.")

    _write_sheet(wb, "🔵 Not in Books",
                 results["not_in_books"], BLUE,
                 note="In GSTR-2A (supplier filed) but missing from your Purchase Register. Check if invoice was received.")

    wb.save(path)
    return path


# ─────────────────────────────────────────────
#  Module 2 — Invoice OCR Report
# ─────────────────────────────────────────────

def generate_ocr_report(df: pd.DataFrame, output_dir: str = "output") -> str:
    from openpyxl import Workbook
    os.makedirs(output_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"Invoice_OCR_Report_{ts}.xlsx")
    wb   = Workbook()
    ws   = wb.active
    ws.title = "Extracted Invoices"

    if df.empty:
        ws.append(["No invoices found."])
        wb.save(path)
        return path

    ws.append(list(df.columns))
    _header_style(ws, row=1)

    for _, row in df.iterrows():
        ws.append([row[c] for c in df.columns])

    # Colour low-confidence rows yellow
    for i, row_vals in enumerate(df.itertuples(), start=2):
        fill_color = GREEN if getattr(row_vals, "confidence", "") == "high" else YELLOW
        fill = PatternFill("solid", fgColor=fill_color)
        for cell in ws[i]:
            cell.fill = fill

    _autofit(ws)
    wb.save(path)
    return path


# ─────────────────────────────────────────────
#  Module 3 — Payment Recon Report
# ─────────────────────────────────────────────

def generate_payment_report(results: dict, output_dir: str = "output") -> str:
    from openpyxl import Workbook
    os.makedirs(output_dir, exist_ok=True)
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"Payment_Recon_Report_{ts}.xlsx")

    wb = Workbook()
    wb.remove(wb.active)
    s  = results["summary"]

    # Summary sheet
    ws_sum = wb.create_sheet("Summary", 0)
    ws_sum.sheet_view.showGridLines = False

    summary_rows = [
        ["GST PAYMENT RECONCILIATION", ""],
        [f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", ""],
        ["", ""],
        ["Category", "Count / Value"],
        ["Total Liabilities",    s["total_liabilities"]],
        ["✅ Matched",            s["matched"]],
        ["🔴 Unpaid",             s["unpaid"]],
        ["⚠️ Overpaid",           s["overpaid"]],
        ["⚠️ Underpaid",          s["underpaid"]],
        ["⏰ Late Payments",       s["late_payments"]],
        ["Unmatched Bank Entries", s["unmatched_bank"]],
        ["", ""],
        ["Total Liability (₹)",  f"₹{s['total_liability_amt']:,.2f}"],
        ["Total Paid (₹)",       f"₹{s['total_paid_amt']:,.2f}"],
        ["Outstanding (₹)",      f"₹{s['outstanding']:,.2f}"],
    ]
    for row_data in summary_rows:
        ws_sum.append(row_data)

    ws_sum["A1"].font = Font(size=14, bold=True, color=HEADER)
    ws_sum["A4"].font = Font(bold=True, color="FFFFFF")
    ws_sum["A4"].fill = PatternFill("solid", fgColor=HEADER)
    ws_sum["B4"].font = Font(bold=True, color="FFFFFF")
    ws_sum["B4"].fill = PatternFill("solid", fgColor=HEADER)
    if s["outstanding"] > 0:
        ws_sum["B15"].fill = PatternFill("solid", fgColor=RED)
        ws_sum["B15"].font = Font(bold=True)
    ws_sum.column_dimensions["A"].width = 36
    ws_sum.column_dimensions["B"].width = 28

    # Reconciliation detail
    recon_df = results["reconciliation"]
    if not recon_df.empty:
        ws_r = wb.create_sheet("Reconciliation Detail")
        ws_r.append(list(recon_df.columns))
        _header_style(ws_r, row=1)
        for _, row in recon_df.iterrows():
            ws_r.append([str(v) if pd.isna(v) is False else "" for v in row])
        # Colour by status
        status_col_idx = list(recon_df.columns).index("status") + 1
        color_map = {"✅ Matched": GREEN, "🔴 Unpaid": RED, "⚠️": YELLOW}
        for i, row_vals in enumerate(recon_df.itertuples(), start=2):
            status = str(row_vals.status)
            fgc = GREEN if "Matched" in status else RED if "Unpaid" in status else YELLOW
            fill = PatternFill("solid", fgColor=fgc)
            for cell in ws_r[i]:
                cell.fill = fill
        _autofit(ws_r)

    # Unmatched bank entries
    unmatched = results["unmatched_bank"]
    if not unmatched.empty:
        ws_u = wb.create_sheet("Unmatched Bank Entries")
        ws_u.append(["ℹ Entries in bank statement not matched to any GST liability", ""])
        ws_u.append([])
        ws_u.append(list(unmatched.columns))
        _header_style(ws_u, row=3)
        for _, row in unmatched.iterrows():
            ws_u.append(list(row))
        _fill_rows(ws_u, BLUE, start_row=4)
        _autofit(ws_u)

    wb.save(path)
    return path
