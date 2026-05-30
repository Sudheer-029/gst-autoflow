"""
OCR Pattern Library -- comprehensive regex for Indian GST invoices.
Covers 25+ label variants per field, compiled once at module load.

Design rules:
  - Separator allows optional colon OR plain whitespace (Tally exports no colon)
  - net_total / net[_]total handles ERPNext underscore style
  - All patterns case-insensitive
"""
import re

# Amount capture: optional Rs/INR/rupee symbol, then digits+commas, optional decimals
_AMT = r'(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d{1,2})?)'

# Separator: skip rate/percent info, allow colon optional + whitespace
# Handles: "Taxable Value: 9,900" AND "Taxable Value 9,900" AND "CGST @ 6%: 594"
_SEP = r'[^:\n]*:?\s+'


def _c(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


# ── GSTIN ─────────────────────────────────────────────────────────────────
RE_GSTIN = _c(r'\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z])\b')

# ── Invoice Number ────────────────────────────────────────────────────────
RE_INV_NO = _c(
    r'(?:'
    r'invoice\s*(?:no|number|#|num)|'
    r'bill\s*(?:no|number|#)|'
    r'inv\s*(?:no|number|#)|'
    r'tax\s*invoice\s*(?:no|number|#|num)|'
    r'document\s*(?:no|number)|'
    r'ref(?:erence)?\s*(?:no|number)|'
    r'voucher\s*(?:no\.?|number)|'
    r'challan\s*(?:no|number|#|num)|'
    r'receipt\s*(?:no|number)'
    r')[.:\s#\-]*([A-Z0-9][A-Z0-9\-/_.]{1,30})'
)

# ── Date ──────────────────────────────────────────────────────────────────
_DATE_VAL = r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4})'
RE_DATE = _c(
    r'(?:'
    r'invoice\s*date|bill\s*date|tax\s*invoice\s*date|'
    r'document\s*date|invoice\s*dt\.?|bill\s*dt\.?|'
    r'date\s*of\s*invoice|issue\s*date|dated?'
    r')[^:\n]*:?\s*' + _DATE_VAL
)

# ── Taxable / Base Amount ─────────────────────────────────────────────────
RE_TAXABLE = _c(
    r'(?:'
    r'taxable\s*(?:value|amount|amt)|'
    r'assessable\s*value|'
    r'value\s*of\s*(?:supply|goods|service)|'
    r'basic\s*(?:amount|value|amt)|'
    r'net[\s_](?:amount|value|amt|total)|'  # net amount, net_total
    r'net_total|'                            # ERPNext exact
    r'sub\s*[-\s]?total|'
    r'total\s*before\s*(?:tax|gst)|'
    r'amount\s*before\s*(?:tax|gst)|'
    r'base[\s_](?:amount|value)|'
    r'base_net_total|'                       # ERPNext
    r'supply\s*value|'
    r'transaction\s*value|'
    r'chargeable\s*amount'
    r')' + _SEP + _AMT
)

# ── IGST ──────────────────────────────────────────────────────────────────
RE_IGST = _c(
    r'(?:'
    r'igst|i\.g\.s\.t\.?|i\.gst|'
    r'igst[\s_]amount|'                      # igst_amount (ERPNext)
    r'integrated[\s_](?:gst|tax|goods[\s_](?:and|&)[\s_]services[\s_]tax)'
    r')' + _SEP + _AMT
)

# ── CGST ──────────────────────────────────────────────────────────────────
RE_CGST = _c(
    r'(?:'
    r'cgst|c\.g\.s\.t\.?|c\.gst|'
    r'cgst[\s_]amount|'
    r'central[\s_](?:gst|tax|goods[\s_](?:and|&)[\s_]services[\s_]tax)'
    r')' + _SEP + _AMT
)

# ── SGST / UTGST ──────────────────────────────────────────────────────────
RE_SGST = _c(
    r'(?:'
    r'sgst|utgst|s\.g\.s\.t\.?|u\.t\.g\.s\.t\.?|s\.gst|'
    r'sgst[\s_]amount|utgst[\s_]amount|'
    r'state[\s_](?:gst|tax)|'
    r'union[\s_]territory[\s_](?:gst|tax)|'
    r'sgst/utgst[\s_]amount'                 # Tally exact
    r')' + _SEP + _AMT
)

# ── Grand Total ───────────────────────────────────────────────────────────
RE_TOTAL = _c(
    r'(?:'
    r'grand[\s_]total|'
    r'total[\s_](?:amount|value|invoice[\s_]value|due|payable|inr)?|'
    r'invoice[\s_](?:total|value|amount)|'
    r'net[\s_]payable|'
    r'amount[\s_](?:payable|due)|'
    r'bill[\s_](?:total|amount)|'
    r'final[\s_](?:amount|total)|'
    r'payable[\s_]amount|'
    r'grand[\s_]total[\s_](?:inr|\(inr\))?|'
    r'rounded[\s_]total'                     # ERPNext
    r')' + _SEP + _AMT
)

# ── HSN/SAC ───────────────────────────────────────────────────────────────
RE_HSN = _c(r'(?:hsn|sac|hsn/sac)\s*(?:code)?[.:\s]*([0-9]{4,8})')


# ── Extraction helper ─────────────────────────────────────────────────────

def extract_fields(text: str, filename: str = "") -> dict:
    """
    Run all patterns. First match per field wins.
    Returns 0.0/"" for unmatched fields — never raises.
    """
    def _first_str(pat: re.Pattern) -> str:
        m = pat.search(text)
        return m.group(1).strip() if m else ""

    def _first_amt(pat: re.Pattern) -> float:
        m = pat.search(text)
        if not m:
            return 0.0
        try:
            return round(float(m.group(1).replace(",", "")), 2)
        except ValueError:
            return 0.0

    gstins  = RE_GSTIN.findall(text)
    taxable = _first_amt(RE_TAXABLE)
    igst    = _first_amt(RE_IGST)
    cgst    = _first_amt(RE_CGST)
    sgst    = _first_amt(RE_SGST)
    total   = _first_amt(RE_TOTAL)

    if total == 0.0 and taxable > 0:
        total = round(taxable + igst + cgst + sgst, 2)

    gst_sum    = igst + cgst + sgst
    confidence = (
        "high"    if taxable > 0 and gst_sum > 0 else
        "partial" if taxable > 0 else
        "low"
    )

    return {
        "file"              : filename,
        "vendor_gstin"      : gstins[0] if gstins else "",
        "buyer_gstin"       : gstins[1] if len(gstins) > 1 else "",
        "invoice_no"        : _first_str(RE_INV_NO),
        "invoice_date"      : _first_str(RE_DATE),
        "taxable_amount"    : taxable,
        "igst"              : igst,
        "cgst"              : cgst,
        "sgst"              : sgst,
        "total_amount"      : total,
        "hsn_sac"           : _first_str(RE_HSN),
        "confidence"        : confidence,
        "extraction_method" : "pdfplumber",
    }
