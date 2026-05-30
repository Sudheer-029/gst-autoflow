"""
Unit tests for gst_autoflow.ocr_parser
Run: pytest tests/ -v

PDF fixtures are generated at test-time using reportlab (no committed binaries).
"""
import pathlib
import pytest
from reportlab.pdfgen import canvas
from gst_autoflow.ocr_parser import parse_invoice, parse_invoice_folder


# ── Fixture builders ─────────────────────────────────────────────────────────

# Canonical invoice text: every field present, all patterns match
_GOOD_INVOICE_TEXT = """
PURCHASE INVOICE

Vendor: Acme Supplies Pvt Ltd
GSTIN: 29AABCU9603R1ZX
Bill To: Beta Traders
GSTIN: 27AABCT1234D1Z5

Invoice No: INV-TEST-001
Invoice Date: 01/04/2024
HSN Code: 998314

Taxable Amount: 10,000.00
IGST @ 18%: 1,800.00
Total Amount: 11,800.00
"""

# Partial text: GSTIN present but no amounts
_PARTIAL_INVOICE_TEXT = """
PURCHASE INVOICE

Vendor GSTIN: 29AABCU9603R1ZX
Invoice No: INV-PARTIAL-001
"""


def _pdf_with_text(path: str, text: str) -> str:
    """Write a text-searchable PDF using reportlab."""
    c = canvas.Canvas(path)
    y = 750
    for line in text.strip().splitlines():
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = 750
    c.save()
    return path


def _blank_pdf(path: str) -> str:
    """Write a valid PDF with no text drawn on any page."""
    c = canvas.Canvas(path)
    c.showPage()   # empty page
    c.save()
    return path


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_known_invoice_fields_extracted_correctly(tmp_path):
    """PDF with a complete invoice → key fields match expected values exactly."""
    pdf = _pdf_with_text(str(tmp_path / "invoice.pdf"), _GOOD_INVOICE_TEXT)
    result = parse_invoice(pdf)

    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["vendor_gstin"]   == "29AABCU9603R1ZX"
    assert result["buyer_gstin"]    == "27AABCT1234D1Z5"
    assert result["invoice_no"]     == "INV-TEST-001"
    assert result["invoice_date"]   == "01/04/2024"
    assert result["taxable_amount"] == pytest.approx(10000.0)
    assert result["igst"]           == pytest.approx(1800.0)
    assert result["total_amount"]   == pytest.approx(11800.0)
    assert result["hsn_sac"]        == "998314"
    assert result["confidence"]     == "high"
    assert result["extraction_status"] == "ok"


def test_blank_pdf_returns_error_not_exception(tmp_path):
    """Blank PDF (no text) → error key returned, no exception raised."""
    pdf = _blank_pdf(str(tmp_path / "blank.pdf"))
    result = parse_invoice(pdf)   # must NOT raise

    assert "error" in result, "Expected error key for blank PDF"
    assert "invoice_no" not in result or not result.get("invoice_no")
    # extraction_status is not set on the early-return error path
    assert "extraction_status" not in result


def test_partial_extraction_returns_partial_status(tmp_path):
    """PDF with only GSTIN + invoice number (no amounts) → extraction_status partial."""
    pdf = _pdf_with_text(str(tmp_path / "partial.pdf"), _PARTIAL_INVOICE_TEXT)
    result = parse_invoice(pdf)

    assert "error" not in result, f"Unexpected error: {result.get('error')}"
    assert result["vendor_gstin"]      == "29AABCU9603R1ZX"
    assert result["taxable_amount"]    == 0.0
    assert result["extraction_status"] == "partial"


def test_parse_invoice_folder_returns_expected_columns(tmp_path):
    """Batch parse: 2 PDFs → DataFrame with correct columns and 2 rows."""
    _pdf_with_text(str(tmp_path / "inv1.pdf"), _GOOD_INVOICE_TEXT)
    _pdf_with_text(str(tmp_path / "inv2.pdf"), _PARTIAL_INVOICE_TEXT)

    df = parse_invoice_folder(str(tmp_path))

    assert len(df) == 2
    # extraction_status must survive the col_order filter in parse_invoice_folder
    assert "extraction_status" in df.columns
    assert "vendor_gstin"      in df.columns
    assert "confidence"        in df.columns


def test_parse_invoice_folder_blank_pdf_no_crash(tmp_path):
    """Folder with one blank PDF → parse_invoice_folder returns 1-row DataFrame without raising."""
    _blank_pdf(str(tmp_path / "blank.pdf"))

    df = parse_invoice_folder(str(tmp_path))

    assert len(df) == 1
    # blank PDF row carries an error column
    assert "error" in df.columns
    assert df.iloc[0]["error"] != ""
