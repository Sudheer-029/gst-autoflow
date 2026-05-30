"""
Unit tests for gst_autoflow.payment_recon
Run: pytest tests/ -v

bank_parser requires >=2 data rows to detect tabular format; test helpers
include a padding non-GST row that does not affect reconciliation results.
"""
import pandas as pd
import pytest
from datetime import date, timedelta
from gst_autoflow.payment_recon import reconcile_payments, TOLERANCE


# ── Helpers ──────────────────────────────────────────────────────────────────

def _excel(df: pd.DataFrame, path: str) -> str:
    df.to_excel(path, index=False)
    return path


def _bank_rows(amount: float = 10000.0, days_after_due: int = -3,
               description: str = "NEFT GST CGST APR2024") -> list[dict]:
    """Return [real GST row, padding non-GST row] — bank_parser needs >=2 rows."""
    pay_date = date(2024, 4, 20) + timedelta(days=days_after_due)
    return [
        {
            "date"       : str(pay_date),
            "description": description,
            "debit"      : amount,
            "credit"     : 0.0,
            "balance"    : 50000.0,
        },
        # padding row — non-GST; won't match any liability
        {
            "date"       : "2024-04-10",
            "description": "SALARY CREDIT",
            "debit"      : 0.0,
            "credit"     : 80000.0,
            "balance"    : 130000.0,
        },
    ]


def _liab_row(period: str = "APR2024", tax_type: str = "CGST",
              amount: float = 10000.0, due: str = "2024-04-20") -> dict:
    return {
        "period"           : period,
        "tax_type"         : tax_type,
        "liability_amount" : amount,
        "due_date"         : due,
    }


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_matched_on_time(tmp_path):
    """Bank entry matches liability amount on time → Matched, not late."""
    bank = _excel(pd.DataFrame(_bank_rows(amount=10000.0, days_after_due=-3)), str(tmp_path / "bank.xlsx"))
    liab = _excel(pd.DataFrame([_liab_row(amount=10000.0)]),                    str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    recon = r["reconciliation"]

    assert len(recon) == 1
    assert "Matched" in recon.iloc[0]["status"]
    assert recon.iloc[0]["late_payment"] == "No"
    assert r["summary"]["matched"] == 1
    assert r["summary"]["unpaid"] == 0


def test_late_payment_detected(tmp_path):
    """Payment made AFTER due date → late_payment flagged Yes."""
    bank = _excel(pd.DataFrame(_bank_rows(amount=10000.0, days_after_due=5)), str(tmp_path / "bank.xlsx"))
    liab = _excel(pd.DataFrame([_liab_row(amount=10000.0)]),                  str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    recon = r["reconciliation"]

    assert recon.iloc[0]["late_payment"] == "Yes"
    assert r["summary"]["late_payments"] == 1


def test_unpaid_liability(tmp_path):
    """No matching bank entry for a liability → status Unpaid, outstanding equals full amount."""
    # Bank has only irrelevant entries
    bank = _excel(
        pd.DataFrame(_bank_rows(amount=99999.0, description="SALARY DEBIT OTHER")),
        str(tmp_path / "bank.xlsx"),
    )
    liab = _excel(pd.DataFrame([_liab_row(amount=10000.0)]), str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    recon = r["reconciliation"]

    assert "Unpaid" in recon.iloc[0]["status"]
    assert r["summary"]["unpaid"] == 1
    assert r["summary"]["outstanding"] == pytest.approx(10000.0)


def test_underpayment_flagged(tmp_path):
    """Bank payment significantly below liability → status Underpaid, not Unpaid."""
    shortfall = TOLERANCE + 50.0
    bank = _excel(pd.DataFrame(_bank_rows(amount=10000.0 - shortfall)), str(tmp_path / "bank.xlsx"))
    liab = _excel(pd.DataFrame([_liab_row(amount=10000.0)]),            str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    recon = r["reconciliation"]

    assert "Underpaid" in recon.iloc[0]["status"]
    assert recon.iloc[0]["difference"] == pytest.approx(-shortfall, abs=0.01)


def test_overpayment_flagged(tmp_path):
    """Bank payment above liability by more than TOLERANCE → status Overpaid."""
    surplus = TOLERANCE + 20.0
    bank = _excel(pd.DataFrame(_bank_rows(amount=10000.0 + surplus)), str(tmp_path / "bank.xlsx"))
    liab = _excel(pd.DataFrame([_liab_row(amount=10000.0)]),          str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    recon = r["reconciliation"]

    assert "Overpaid" in recon.iloc[0]["status"]
    assert recon.iloc[0]["difference"] == pytest.approx(surplus, abs=0.01)


def test_outstanding_is_total_minus_paid(tmp_path):
    """outstanding = sum(liability) - sum(payment_amount) across all rows."""
    bank_data = [
        *_bank_rows(amount=5000.0, description="NEFT GST CGST APR2024"),
        {"date": "2024-04-15", "description": "NEFT GST SGST APR2024",
         "debit": 3000.0, "credit": 0.0, "balance": 40000.0},
    ]
    liab_rows = [
        _liab_row(period="APR2024", tax_type="CGST", amount=5000.0),
        _liab_row(period="APR2024", tax_type="SGST", amount=3000.0),
    ]
    bank = _excel(pd.DataFrame(bank_data), str(tmp_path / "bank.xlsx"))
    liab = _excel(pd.DataFrame(liab_rows), str(tmp_path / "liab.xlsx"))

    r = reconcile_payments(bank, liab)
    s = r["summary"]

    assert s["outstanding"] == pytest.approx(0.0, abs=1.0)
    assert s["total_liability_amt"] == pytest.approx(8000.0)
    assert s["total_paid_amt"]      == pytest.approx(8000.0)
