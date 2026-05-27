"""
Bank Statement Parser — auto-detects Indian bank export formats and
normalises to a standard schema: date | description | debit | credit.

Supported banks:
  HDFC, SBI, ICICI, Kotak, Axis, Yes Bank, IndusInd, PNB, Canara, IDFC First

Also handles generic/manual Excel bank statements.
"""
import re
import pandas as pd
from dataclasses import dataclass
from typing import Optional

# ── Bank schema definitions ───────────────────────────────────────────────
# Each entry: (bank_name, signature_columns, column_map, date_col, skip_rows)
# signature_columns: a set of column name fragments that identify the bank
# column_map: their_col → our_col (date|description|debit|credit)

BANK_SCHEMAS = [
    {
        "bank"       : "HDFC",
        "signatures" : {"narration", "withdrawal amt", "deposit amt", "closing balance"},
        "col_map"    : {
            "date"                  : "date",
            "narration"             : "description",
            "withdrawal amt.(inr )" : "debit",
            "deposit amt.(inr )"    : "credit",
            # also handle space variants
            "withdrawal amt.(inr)"  : "debit",
            "deposit amt.(inr)"     : "credit",
            "withdrawal amt"        : "debit",
            "deposit amt"           : "credit",
        },
    },
    {
        "bank"       : "SBI",
        "signatures" : {"txn date", "value date", "ref no./cheque no."},
        "col_map"    : {
            "txn date"             : "date",
            "description"          : "description",
            "debit"                : "debit",
            "credit"               : "credit",
        },
    },
    {
        "bank"       : "ICICI",
        "signatures" : {"transaction date", "withdrawal amount (inr", "deposit amount (inr"},
        "col_map"    : {
            "transaction date"          : "date",
            "description"               : "description",
            "withdrawal amount (inr )"  : "debit",
            "deposit amount (inr )"     : "credit",
            "withdrawal amount (inr)"   : "debit",
            "deposit amount (inr)"      : "credit",
        },
    },
    {
        "bank"       : "Kotak",
        "signatures" : {"transaction date", "chq / ref number", "narration", "withdrawal amt."},
        "col_map"    : {
            "transaction date" : "date",
            "narration"        : "description",
            "withdrawal amt."  : "debit",
            "deposit amt."     : "credit",
        },
    },
    {
        "bank"       : "Axis",
        "signatures" : {"tran date", "chqno", "particulars", "dr", "cr"},
        "col_map"    : {
            "tran date"  : "date",
            "particulars": "description",
            "dr"         : "debit",
            "cr"         : "credit",
        },
    },
    {
        "bank"       : "Yes Bank",
        "signatures" : {"transaction id", "transaction remarks", "withdrawal amount", "deposit amount"},
        "col_map"    : {
            "date"                 : "date",
            "transaction remarks"  : "description",
            "withdrawal amount"    : "debit",
            "deposit amount"       : "credit",
        },
    },
    {
        "bank"       : "IndusInd",
        "signatures" : {"value date", "transaction remarks", "debit amount", "credit amount"},
        "col_map"    : {
            "date"                : "date",
            "transaction remarks" : "description",
            "debit amount"        : "debit",
            "credit amount"       : "credit",
        },
    },
    {
        "bank"       : "PNB",
        "signatures" : {"posting date", "particulars", "withdrawals", "deposits"},
        "col_map"    : {
            "posting date" : "date",
            "particulars"  : "description",
            "withdrawals"  : "debit",
            "deposits"     : "credit",
        },
    },
    {
        "bank"       : "Canara",
        "signatures" : {"transaction date", "particulars", "debit", "credit"},
        "col_map"    : {
            "transaction date" : "date",
            "particulars"      : "description",
            "debit"            : "debit",
            "credit"           : "credit",
        },
    },
    {
        "bank"       : "IDFC First",
        "signatures" : {"transaction date", "transaction details", "debit (inr)", "credit (inr)"},
        "col_map"    : {
            "transaction date"    : "date",
            "transaction details" : "description",
            "debit (inr)"         : "debit",
            "credit (inr)"        : "credit",
        },
    },
]

# Generic fallback — common column name patterns
GENERIC_ALIASES = {
    "date"       : ["date", "txn date", "tran date", "transaction date",
                    "value date", "posting date", "entry date"],
    "description": ["description", "narration", "particulars", "remarks",
                    "transaction details", "transaction remarks", "details",
                    "transaction narration", "transaction description"],
    "debit"      : ["debit", "dr", "withdrawal", "withdrawals",
                    "withdrawal amount", "withdrawal amt", "debit amount",
                    "debit (inr)", "paid out", "outflow"],
    "credit"     : ["credit", "cr", "deposit", "deposits",
                    "deposit amount", "deposit amt", "credit amount",
                    "credit (inr)", "paid in", "inflow"],
}

# GST-related keywords for payment filtering
GST_KEYWORDS = [
    "gst", "igst", "cgst", "sgst", "gstr", "tax payment",
    "challan", "pmtgst", "integrated tax", "central tax",
    "state tax", "gst challan", "gst payment", "gst remittance",
    "tds", "advance tax",  # sometimes mixed in GST reports
]


@dataclass
class ParseResult:
    df          : pd.DataFrame   # normalised: date | description | debit | credit
    bank_name   : str            # detected bank or "Generic"
    warnings    : list[str]
    is_valid    : bool


def parse_bank_statement(path: str) -> ParseResult:
    """
    Load and normalise a bank statement Excel file.
    Auto-detects bank format. Falls back to generic mapping.

    Returns ParseResult — check .is_valid before using .df
    """
    from .validators import validate_excel
    path = validate_excel(path)

    # Try loading — skip up to 10 header rows (some banks have metadata at top)
    df, skip = _load_with_header_detection(path)
    if df is None:
        return ParseResult(df=pd.DataFrame(), bank_name="Unknown",
                           warnings=["Could not parse file — no tabular data found."],
                           is_valid=False)

    cols_lower = [c.strip().lower() for c in df.columns]
    warnings   = []

    # Detect bank
    schema, bank_name = _detect_bank(cols_lower)

    if schema:
        df, w = _apply_schema(df, schema["col_map"])
        warnings.extend(w)
    else:
        # Generic fallback
        df, w = _generic_map(df, cols_lower)
        warnings.extend(w)

    # Validate required columns present
    required = {"date", "description", "debit"}
    missing  = required - set(df.columns)
    if missing:
        warnings.append(
            f"Could not find columns: {', '.join(missing)}. "
            f"Detected bank: {bank_name}. "
            "Please rename columns to: date, description, debit, credit."
        )
        return ParseResult(df=df, bank_name=bank_name,
                           warnings=warnings, is_valid=False)

    # Normalise types
    df = _normalise_types(df)

    # Add gst_related flag
    df["gst_related"] = df["description"].str.lower().str.contains(
        "|".join(GST_KEYWORDS), na=False
    )

    return ParseResult(df=df, bank_name=bank_name,
                       warnings=warnings, is_valid=True)


def filter_gst_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Return only rows flagged as GST-related."""
    if "gst_related" in df.columns:
        return df[df["gst_related"]].copy()
    # Fallback: filter by keyword in description
    desc_col = "description" if "description" in df.columns else df.columns[0]
    mask = df[desc_col].str.lower().str.contains(
        "|".join(GST_KEYWORDS), na=False
    )
    return df[mask].copy()


# ── Internal helpers ──────────────────────────────────────────────────────

def _load_with_header_detection(path: str, max_skip: int = 10):
    """Try loading with 0–max_skip skipped rows until we get a usable table."""
    import warnings
    for skip in range(max_skip + 1):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                df = pd.read_excel(path, skiprows=skip, dtype=str)
            # Usable: has at least 3 columns and at least 2 data rows
            df = df.dropna(how="all")
            if len(df.columns) >= 3 and len(df) >= 2:
                return df, skip
        except Exception:
            continue
    return None, 0


def _detect_bank(cols_lower: list[str]) -> tuple:
    """Return (schema_dict, bank_name) or (None, 'Generic')."""
    cols_set = set(cols_lower)
    best_match, best_score = None, 0

    for schema in BANK_SCHEMAS:
        sigs   = schema["signatures"]
        # Score = how many signature fragments appear in actual columns
        score  = sum(
            1 for sig in sigs
            if any(sig in col for col in cols_set)
        )
        ratio  = score / len(sigs)
        if ratio > best_score:
            best_score = ratio
            best_match = schema

    if best_match and best_score >= 0.5:
        return best_match, best_match["bank"]
    return None, "Generic"


def _apply_schema(df: pd.DataFrame, col_map: dict) -> tuple:
    """Rename columns using a bank-specific map."""
    cols_lower = {c: c.strip().lower() for c in df.columns}
    rename_map = {}
    warnings   = []

    for orig, normalised in cols_lower.items():
        if normalised in col_map:
            rename_map[orig] = col_map[normalised]

    unmapped = [c for c in df.columns if c not in rename_map
                and c.strip().lower() not in {"balance", "closing balance",
                                               "chq./ref.no.", "value dt",
                                               "transaction id", "sl. no.",
                                               "sr. no.", "sno", "serial no"}]
    if unmapped:
        warnings.append(f"Unrecognised columns ignored: {', '.join(unmapped)}")

    renamed = df.rename(columns=rename_map)
    # Keep only standard columns
    keep = [c for c in ["date", "description", "debit", "credit"] if c in renamed.columns]
    return renamed[keep], warnings


def _generic_map(df: pd.DataFrame, cols_lower: list[str]) -> tuple:
    """Best-effort mapping using generic alias lists."""
    import difflib
    rename_map = {}
    warnings   = ["Bank format not recognised — using generic column detection."]
    used       = set()

    for target, aliases in GENERIC_ALIASES.items():
        for i, col_norm in enumerate(cols_lower):
            orig = df.columns[i]
            if orig in rename_map or target in used:
                continue
            if col_norm in aliases:
                rename_map[orig] = target
                used.add(target)
                break
        if target not in used:
            # Fuzzy fallback
            matches = difflib.get_close_matches(target, cols_lower, n=1, cutoff=0.65)
            if matches:
                orig_col = df.columns[cols_lower.index(matches[0])]
                if orig_col not in rename_map:
                    rename_map[orig_col] = target
                    used.add(target)

    renamed = df.rename(columns=rename_map)
    keep    = [c for c in ["date", "description", "debit", "credit"] if c in renamed.columns]
    return renamed[keep], warnings


def _normalise_types(df: pd.DataFrame) -> pd.DataFrame:
    """Parse dates and amounts to correct types."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(
            df["date"], dayfirst=True, errors="coerce"
        )
    for col in ["debit", "credit"]:
        if col in df.columns:
            # Remove currency symbols, commas, spaces
            df[col] = (
                df[col].astype(str)
                    .str.replace(r"[₹,\s]", "", regex=True)
                    .str.replace(r"[^\d.]", "", regex=True)
            )
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df
