"""
Column Name Mapper — normalises any DataFrame's columns to our internal schema.

Handles exports from:
  Tally ERP 9 / Tally Prime, ERPNext / Frappe, Busy Accounting,
  Zoho Books, QuickBooks India, manual Excel sheets.

Strategy:
  1. Exact match (case-insensitive, stripped)
  2. Alias match from curated synonym table
  3. Fuzzy match via difflib (threshold 0.72)
  4. If still unresolved — flag as UNMAPPED for user review

Never silently drops a column — always returns a mapping report.
"""
import difflib
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

# ── Canonical schema ──────────────────────────────────────────────────────
# target_col : [known aliases across all accounting tools]

SCHEMA: dict[str, list[str]] = {
    # ── Identity ──────────────────────────────────────────────
    "vendor_name": [
        "party name", "supplier name", "supplier", "vendor", "vendor name",
        "party", "seller name", "sold by", "from", "bill from",
        "creditor name", "account name", "ledger name",
        # ERPNext
        "supplier_name", "party_name",
        # Zoho
        "vendor name", "contact name",
    ],
    "gstin": [
        "gstin", "gst no", "gst number", "gstin no", "gstin number",
        "supplier gstin", "vendor gstin", "party gstin",
        "supplier gst", "gst registration no", "gstin/uin",
        # Tally
        "gst registration number",
        # ERPNext
        "supplier_gstin", "gstin_of_supplier",
    ],
    "invoice_no": [
        "invoice no", "invoice number", "invoice #", "inv no", "inv number",
        "bill no", "bill number", "bill #", "voucher no", "voucher number",
        "document no", "document number", "ref no", "reference number",
        "challan no", "purchase order no", "po number",
        # Tally
        "voucher no.", "reference no.",
        # ERPNext
        "bill_no", "name", "purchase_invoice",
    ],
    "invoice_date": [
        "invoice date", "bill date", "date", "voucher date", "document date",
        "transaction date", "purchase date", "entry date",
        "tax invoice date", "inv date",
        # Tally
        "date", "voucher date",
        # ERPNext
        "posting_date", "bill_date",
    ],
    # ── Amounts ───────────────────────────────────────────────
    "taxable_amount": [
        "taxable amount", "taxable value", "assessable value",
        "basic amount", "basic value", "net amount", "net value",
        "value of supply", "sub total", "subtotal", "taxable",
        "total before tax", "amount before tax", "base amount",
        "supply value", "transaction value",
        # Tally
        "taxable value",
        # ERPNext
        "net_total", "taxable_amount", "base_net_total",
        # Zoho
        "sub total", "taxable amount",
    ],
    "igst": [
        "igst", "igst amount", "igst amt", "integrated gst",
        "integrated tax", "i.g.s.t", "igst value",
        # Tally
        "igst amount",
        # ERPNext
        "igst_amount",
    ],
    "cgst": [
        "cgst", "cgst amount", "cgst amt", "central gst",
        "central tax", "c.g.s.t", "cgst value",
        # Tally
        "cgst amount",
        # ERPNext
        "cgst_amount",
    ],
    "sgst": [
        "sgst", "sgst amount", "sgst amt", "state gst",
        "state tax", "s.g.s.t", "sgst value", "utgst", "utgst amount",
        # Tally
        "sgst/utgst amount",
        # ERPNext
        "sgst_amount",
    ],
    "total": [
        "total", "total amount", "grand total", "invoice total",
        "invoice value", "total invoice value", "net payable",
        "amount payable", "total due", "bill amount", "total value",
        "round off total", "total (inr)", "total amount (inr)",
        # Tally
        "amount",
        # ERPNext
        "grand_total", "rounded_total",
        # Zoho
        "total",
    ],
}

FUZZY_THRESHOLD = 0.72   # below this → UNMAPPED
REQUIRED_COLS   = {"gstin", "invoice_no", "taxable_amount"}  # must be present


# ── Public API ────────────────────────────────────────────────────────────

@dataclass
class MappingResult:
    renamed_df    : pd.DataFrame
    col_map       : dict           # original_col → canonical_col
    unmapped      : list[str]      # cols we couldn't resolve
    missing_required: list[str]    # required cols not found
    warnings      : list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.missing_required) == 0


def map_columns(df: pd.DataFrame, source_hint: str = "auto") -> MappingResult:
    """
    Normalise df columns to our internal schema.
    source_hint: "tally" | "erpnext" | "zoho" | "manual" | "auto"

    Returns MappingResult — check .is_valid before proceeding.
    """
    incoming = {c: c.strip().lower() for c in df.columns}
    resolved : dict[str, str] = {}   # original → canonical
    used_targets: set[str]    = set()

    for orig_col, normalised in incoming.items():
        canon = _resolve(normalised, used_targets)
        if canon:
            resolved[orig_col] = canon
            used_targets.add(canon)

    # Rename DataFrame
    renamed = df.rename(columns=resolved)

    unmapped = [c for c in df.columns if c not in resolved]
    missing_required = [r for r in REQUIRED_COLS if r not in resolved.values()]

    warnings = []
    if unmapped:
        warnings.append(
            f"Could not map {len(unmapped)} column(s): {', '.join(unmapped)}. "
            "These will be ignored during reconciliation."
        )
    if missing_required:
        warnings.append(
            f"Required column(s) missing: {', '.join(missing_required)}. "
            "Check your file has GSTIN, Invoice No, and Taxable Amount columns."
        )

    return MappingResult(
        renamed_df       = renamed,
        col_map          = resolved,
        unmapped         = unmapped,
        missing_required = missing_required,
        warnings         = warnings,
    )


def mapping_report(result: MappingResult) -> str:
    """Human-readable report for UI display."""
    lines = []
    lines.append("Column Mapping Report")
    lines.append("─" * 40)
    for orig, canon in result.col_map.items():
        lines.append(f"  ✅  '{orig}'  →  '{canon}'")
    for u in result.unmapped:
        lines.append(f"  ⚠️  '{u}'  →  UNMAPPED (ignored)")
    for m in result.missing_required:
        lines.append(f"  🔴  '{m}'  →  MISSING (required)")
    return "\n".join(lines)


# ── Internal helpers ──────────────────────────────────────────────────────

def _resolve(normalised: str, used: set[str]) -> Optional[str]:
    """Try exact → alias → fuzzy. Return canonical name or None."""
    # 1. Exact match against canonical names
    if normalised in SCHEMA and normalised not in used:
        return normalised

    # 2. Alias match
    for canon, aliases in SCHEMA.items():
        if canon in used:
            continue
        if normalised in [a.lower() for a in aliases]:
            return canon

    # 3. Fuzzy match across all aliases + canonical names
    all_targets = []
    target_map  = {}
    for canon, aliases in SCHEMA.items():
        if canon in used:
            continue
        for alias in [canon] + aliases:
            key = alias.lower()
            all_targets.append(key)
            target_map[key] = canon

    matches = difflib.get_close_matches(normalised, all_targets,
                                        n=1, cutoff=FUZZY_THRESHOLD)
    if matches:
        return target_map[matches[0]]

    return None
