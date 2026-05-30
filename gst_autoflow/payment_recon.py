"""
Module 3 — Payment Reconciliation
Uses bank_parser for format-agnostic bank statement handling.
"""
import pandas as pd
from .validators  import validate_excel
from .bank_parser import parse_bank_statement, filter_gst_payments

TOLERANCE = 1.0


def _normalise_liability(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    for col in ["period", "tax_type"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    if "liability_amount" in df.columns:
        df["liability_amount"] = pd.to_numeric(
            df["liability_amount"], errors="coerce"
        ).fillna(0.0)
    if "due_date" in df.columns:
        df["due_date"] = pd.to_datetime(
            df["due_date"], dayfirst=True, errors="coerce"
        )
    return df


def reconcile_payments(bank_path: str, liability_path: str) -> dict:
    """
    Match bank GST payments against GSTR-3B liability.
    Handles all Indian bank export formats via bank_parser.
    """
    bank_path      = validate_excel(bank_path)
    liability_path = validate_excel(liability_path)

    # Parse bank statement (auto-detect format)
    bank_result = parse_bank_statement(bank_path)
    warnings    = list(bank_result.warnings)

    if not bank_result.is_valid:
        raise ValueError(
            "Could not parse bank statement. " +
            " ".join(bank_result.warnings)
        )

    bank_df      = bank_result.df
    gst_payments = filter_gst_payments(bank_df)
    bank_name    = bank_result.bank_name

    # Load liability
    liab = _normalise_liability(pd.read_excel(liability_path))

    if "liability_amount" not in liab.columns:
        raise ValueError("GST liability file must have a 'liability_amount' column.")

    results              = []
    matched_bank_idxs    = set()
    desc_col             = "description"

    for _, liab_row in liab.iterrows():
        period   = str(liab_row.get("period", ""))
        tax_type = str(liab_row.get("tax_type", "")).lower()
        liab_amt = float(liab_row.get("liability_amount", 0))
        due_date = liab_row.get("due_date")

        # Filter candidates: match description containing tax_type + period hint
        candidate_mask = pd.Series(True, index=gst_payments.index)
        if desc_col in gst_payments.columns:
            period_hint = period[:3].lower() if len(period) >= 3 else ""
            candidate_mask = (
                gst_payments[desc_col].str.lower().str.contains(tax_type, na=False) |
                (gst_payments[desc_col].str.lower().str.contains(period_hint, na=False)
                 if period_hint else pd.Series(True, index=gst_payments.index))
            )

        candidates = gst_payments[
            candidate_mask &
            ~gst_payments.index.isin(matched_bank_idxs)
        ]

        # Match by closest amount among description-matched candidates.
        # Description is the primary key; amount diff determines Matched/Underpaid/Overpaid.
        # A hard amount filter would swallow underpayments as "Unpaid" — wrong for GST filings.
        amt_col   = "debit"
        amt_match = pd.DataFrame()
        if amt_col in candidates.columns and not candidates.empty:
            closest_idx = (candidates[amt_col] - liab_amt).abs().idxmin()
            amt_match   = candidates.loc[[closest_idx]]

        if not amt_match.empty:
            bank_row = amt_match.iloc[0]
            pay_date = bank_row.get("date")
            late     = (
                pd.notna(pay_date) and pd.notna(due_date) and pay_date > due_date
            )
            diff   = round(float(bank_row[amt_col]) - liab_amt, 2)
            status = (
                "✅ Matched"   if abs(diff) <= TOLERANCE else
                "⚠️ Overpaid"  if diff > 0 else
                "⚠️ Underpaid"
            )
            results.append({
                "period"          : period,
                "tax_type"        : liab_row.get("tax_type"),
                "liability_amount": liab_amt,
                "payment_amount"  : round(float(bank_row[amt_col]), 2),
                "difference"      : diff,
                "payment_date"    : str(pay_date)[:10] if pd.notna(pay_date) else "",
                "due_date"        : str(due_date)[:10] if pd.notna(due_date) else "",
                "late_payment"    : "Yes" if late else "No",
                "status"          : status,
            })
            matched_bank_idxs.add(amt_match.index[0])
        else:
            results.append({
                "period"          : period,
                "tax_type"        : liab_row.get("tax_type"),
                "liability_amount": liab_amt,
                "payment_amount"  : 0.0,
                "difference"      : -liab_amt,
                "payment_date"    : "",
                "due_date"        : str(due_date)[:10] if pd.notna(due_date) else "",
                "late_payment"    : "—",
                "status"          : "🔴 Unpaid",
            })

    unmatched_bank = gst_payments[~gst_payments.index.isin(matched_bank_idxs)].copy()
    recon_df       = pd.DataFrame(results)

    total_paid = recon_df["payment_amount"].sum() if not recon_df.empty else 0
    summary    = {
        "bank_detected"      : bank_name,
        "total_liabilities"  : len(liab),
        "matched"            : len(recon_df[recon_df["status"] == "✅ Matched"]) if not recon_df.empty else 0,
        "unpaid"             : len(recon_df[recon_df["status"] == "🔴 Unpaid"])  if not recon_df.empty else 0,
        "overpaid"           : len(recon_df[recon_df["status"].str.contains("Overpaid",  na=False)]) if not recon_df.empty else 0,
        "underpaid"          : len(recon_df[recon_df["status"].str.contains("Underpaid", na=False)]) if not recon_df.empty else 0,
        "late_payments"      : len(recon_df[recon_df["late_payment"] == "Yes"]) if not recon_df.empty else 0,
        "unmatched_bank"     : len(unmatched_bank),
        "total_liability_amt": liab["liability_amount"].sum(),
        "total_paid_amt"     : total_paid,
        "outstanding"        : liab["liability_amount"].sum() - total_paid,
        "warnings"           : warnings,
    }

    return {
        "reconciliation": recon_df,
        "unmatched_bank": unmatched_bank,
        "summary"       : summary,
    }
