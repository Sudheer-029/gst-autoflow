"""
Module 1 — GST Reconciliation Engine
Uses column_mapper to handle Tally, ERPNext, Zoho, and manual exports.
"""
import pandas as pd
from .validators    import validate_excel
from .column_mapper import map_columns, MappingResult

MATCH_KEY   = ["gstin", "invoice_no"]
AMOUNT_COLS = ["taxable_amount", "igst", "cgst", "sgst", "total"]

# Paise tolerance for amount comparisons.
# Indian purchase registers typically round to the nearest rupee, while the
# GST portal calculates breakdowns to the paise. A ±₹10 micro-tolerance kills
# false-positive "mismatch" warnings for routine rounding differences while
# still surfacing real discrepancies.
TOLERANCE = 10.0


def _normalise_amounts(df: pd.DataFrame) -> pd.DataFrame:
    for col in AMOUNT_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _normalise_keys(df: pd.DataFrame) -> pd.DataFrame:
    for col in ["gstin", "invoice_no", "vendor_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().str.upper()
    return df


def _pick(df: pd.DataFrame, col: str) -> pd.Series:
    for candidate in [col, f"{col}_pr", f"{col}_g2a"]:
        if candidate in df.columns:
            return df[candidate]
    return pd.Series(0.0, index=df.index)


def reconcile(pr_path: str, gstr2a_path: str, *, mode: str = "2B") -> dict:
    """
    Reconcile Purchase Register vs GSTR-2B (or 2A).

    Args:
        pr_path:     Path to the Purchase Register Excel file.
        gstr2a_path: Path to the GSTR-2B (preferred) or GSTR-2A Excel file.
                     Despite the legacy parameter name, 2B is the recommended
                     input under current CGST rules — ITC may only be claimed
                     against the static GSTR-2B statement.
        mode:        "2B" (default, recommended) or "2A". Affects only the
                     summary labels; the matching logic is identical because
                     2A and 2B share the same row schema.

    Returns:
        A dict with matched/mismatch/missing dataframes plus a summary block.
        The summary's "source_statement" key reflects the chosen mode so the
        UI can show accurate copy.
    """
    pr_path     = validate_excel(pr_path)
    gstr2a_path = validate_excel(gstr2a_path)

    pr_raw  = pd.read_excel(pr_path)
    g2a_raw = pd.read_excel(gstr2a_path)

    # Map columns from any source format → our schema
    pr_map  = map_columns(pr_raw,  source_hint="auto")
    g2a_map = map_columns(g2a_raw, source_hint="auto")

    mapping_warnings = pr_map.warnings + g2a_map.warnings

    # Validate required columns exist after mapping
    if not pr_map.is_valid:
        raise ValueError(
            f"Purchase Register is missing required columns: "
            f"{', '.join(pr_map.missing_required)}. "
            f"Mapping attempted: {pr_map.col_map}"
        )
    if not g2a_map.is_valid:
        raise ValueError(
            f"GSTR-2A is missing required columns: "
            f"{', '.join(g2a_map.missing_required)}."
        )

    pr  = _normalise_amounts(_normalise_keys(pr_map.renamed_df.copy()))
    g2a = _normalise_amounts(_normalise_keys(g2a_map.renamed_df.copy()))

    # Ensure all AMOUNT_COLS exist (fill 0 if absent)
    for col in AMOUNT_COLS:
        for df in [pr, g2a]:
            if col not in df.columns:
                df[col] = 0.0

    merged = pr.merge(
        g2a, on=MATCH_KEY, how="outer",
        suffixes=("_pr", "_g2a"), indicator=True
    )

    both     = merged[merged["_merge"] == "both"].copy()
    only_pr  = merged[merged["_merge"] == "left_only"].copy()
    only_g2a = merged[merged["_merge"] == "right_only"].copy()

    mismatch_mask = pd.Series(False, index=both.index)
    for col in AMOUNT_COLS:
        pr_col, g2a_col = f"{col}_pr", f"{col}_g2a"
        if pr_col in both.columns and g2a_col in both.columns:
            diff = (both[pr_col] - both[g2a_col]).abs()
            mismatch_mask |= (diff > TOLERANCE)
            both[f"diff_{col}"] = both[pr_col] - both[g2a_col]

    matched         = both[~mismatch_mask].copy()
    amount_mismatch = both[mismatch_mask].copy()

    for df in [matched, amount_mismatch, only_pr, only_g2a]:
        df.drop(columns=["_merge"], errors="ignore", inplace=True)

    # Total claimable ITC = sum of tax on cleanly matched invoices
    # (these are the ones safe to claim against 2B/2A)
    claimable_itc = 0.0
    for col in ("igst_pr", "cgst_pr", "sgst_pr", "igst", "cgst", "sgst"):
        if col in matched.columns:
            claimable_itc += pd.to_numeric(matched[col], errors="coerce").fillna(0.0).sum()

    summary = {
        "source_statement"  : f"GSTR-{mode}",
        "total_pr"          : len(pr),
        "total_gstr2a"      : len(g2a),
        "matched_clean"     : len(matched),
        "amount_mismatch"   : len(amount_mismatch),
        "missing_in_gstr2a" : len(only_pr),
        "not_in_books"      : len(only_g2a),
        "pr_taxable_total"  : pr["taxable_amount"].sum(),
        "g2a_taxable_total" : g2a["taxable_amount"].sum(),
        "itc_at_risk"       : _pick(only_pr, "taxable_amount").sum() if len(only_pr) else 0.0,
        "claimable_itc"     : float(claimable_itc),
    }

    return {
        "matched"           : matched,
        "amount_mismatch"   : amount_mismatch,
        "missing_in_gstr2a" : only_pr,
        "not_in_books"      : only_g2a,
        "summary"           : summary,
        "mapping_warnings"  : mapping_warnings,
        "pr_col_map"        : pr_map.col_map,
        "g2a_col_map"       : g2a_map.col_map,
    }
