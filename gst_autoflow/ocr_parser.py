"""
Module 2 — Invoice OCR Parser
Uses ocr_patterns.py for comprehensive field extraction.
"""
import os, logging
import pdfplumber
import pandas as pd
from pathlib import Path
from .validators import validate_pdf
from .ocr_patterns import extract_fields

logger = logging.getLogger(__name__)

MAX_PAGES        = 20
MAX_FILE_SIZE_MB = 10


def _extract_text_pdfplumber(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:MAX_PAGES]
        return "\n".join((p.extract_text() or "") for p in pages)


def _ocr_fallback(pdf_path: str) -> str:
    """Tesseract fallback for scanned PDFs. Optional dependency."""
    try:
        from pdf2image import convert_from_path
        import pytesseract
        pages = convert_from_path(pdf_path, dpi=200)[:MAX_PAGES]
        return "\n".join(pytesseract.image_to_string(p) for p in pages)
    except ImportError:
        logger.warning("pytesseract/pdf2image not installed — OCR fallback unavailable.")
        return ""
    except Exception as e:
        logger.error("OCR fallback failed: %s", type(e).__name__)
        return ""


def parse_invoice(pdf_path: str) -> dict:
    """Parse a single PDF. Raises ValidationError on bad input."""
    safe_path = validate_pdf(pdf_path)
    filename  = Path(safe_path).name
    text      = ""

    try:
        text = _extract_text_pdfplumber(safe_path)
    except Exception as e:
        logger.error("pdfplumber failed on %s: %s", filename, type(e).__name__)
        return {"file": filename, "error": "Could not read PDF."}

    if len(text.strip()) < 50:
        text = _ocr_fallback(safe_path)

    if not text.strip():
        return {"file": filename, "error": "No extractable text found."}

    result = extract_fields(text, filename)
    result["extraction_method"] = "pdfplumber" if len(text.strip()) >= 50 else "ocr_fallback"

    # Classify extraction quality for testers:
    #   ok      → key fields present, confidence medium/high
    #   partial → some fields missing or confidence low (needs manual review)
    # Complete failures already return early with {"error": ...} above.
    _required = ("vendor_gstin", "invoice_no", "total_amount")
    _missing  = sum(1 for k in _required if not result.get(k))
    _conf     = result.get("confidence", "low")
    if _missing == 0 and _conf in ("medium", "high"):
        result["extraction_status"] = "ok"
    else:
        result["extraction_status"] = "partial"

    return result


def parse_invoice_folder(folder_path: str) -> pd.DataFrame:
    """Batch-parse all PDFs in a folder. Never raises on individual failures."""
    folder = Path(folder_path).resolve()
    if not folder.is_dir():
        raise ValueError("Not a directory.")

    pdfs = list(folder.glob("*.pdf"))
    if not pdfs:
        return pd.DataFrame()

    rows = []
    for p in pdfs:
        try:
            rows.append(parse_invoice(str(p)))
        except Exception as e:
            rows.append({"file": p.name, "error": str(e)})

    df       = pd.DataFrame(rows)
    col_order = [
        "file", "vendor_gstin", "buyer_gstin", "invoice_no", "invoice_date",
        "taxable_amount", "igst", "cgst", "sgst", "total_amount",
        "hsn_sac", "confidence", "extraction_method", "error",
    ]
    present = [c for c in col_order if c in df.columns]
    return df[present]
