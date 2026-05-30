"""
Unit tests for gst_autoflow.reconciler
Run: pytest tests/ -v
"""
import pandas as pd
import pytest
from gst_autoflow.reconciler import reconcile, TOLERANCE


# ── Helpers ──────────────────────────────────────────────────────────────────

def _excel(df: pd.DataFrame, path: str) -> str:
    df.to_excel(path, index=False)
    return path


def _pr_row(**kw) -> dict:
    base = {
        "supplier_gstin": "29AABCU9603R1ZX",
        "invoice_number": "INV-001",
        "invoice_date": "2024-04-01",
        "taxable_amount": 10000.0,
        "igst": 1800.0, "cgst": 0.0, "sgst": 0.0, "total": 11800.0,
    }
    base.update(kw)
    return base


def _g2a_row(**kw) -> dict:
    base = {
        "supplier_gstin": "29AABCU9603R1ZX",
        "invoice_number": "INV-001",
        "invoice_date": "2024-04-01",
        "taxable_amount": 10000.0,
        "igst": 1800.0, "cgst": 0.0, "sgst": 0.0, "total": 11800.0,
    }
    base.update(kw)
    return base


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_perfect_match(tmp_path):
    """Clean matching row lands in matched, not mismatch/missing."""
    pr  = _excel(pd.DataFrame([_pr_row()]),  str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row()]), str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["matched"]) == 1
    assert len(r["amount_mismatch"]) == 0
    assert len(r["missing_in_gstr2a"]) == 0
    assert len(r["not_in_books"]) == 0


def test_amount_mismatch_above_tolerance(tmp_path):
    """Amount diff > TOLERANCE is flagged as mismatch."""
    pr  = _excel(pd.DataFrame([_pr_row(igst=1800.0)]),                str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row(igst=1800.0 + TOLERANCE + 1)]), str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["amount_mismatch"]) == 1
    assert len(r["matched"]) == 0


def test_amount_within_tolerance(tmp_path):
    """Amount diff just inside TOLERANCE boundary stays a clean match."""
    pr  = _excel(pd.DataFrame([_pr_row(igst=1800.0)]),                    str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row(igst=1800.0 + TOLERANCE - 0.01)]), str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["matched"]) == 1
    assert len(r["amount_mismatch"]) == 0


def test_missing_in_gstr2a_raises_itc_risk(tmp_path):
    """Row only in PR (not in 2A) → itc_at_risk > 0."""
    pr  = _excel(pd.DataFrame([_pr_row(invoice_number="ONLY-PR")]),  str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row(invoice_number="ONLY-G2A")]), str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["missing_in_gstr2a"]) == 1
    assert r["summary"]["itc_at_risk"] > 0


def test_gstin_normalisation_matches(tmp_path):
    """Lowercase/padded GSTIN in PR still matches GSTR-2A after normalisation."""
    pr  = _excel(pd.DataFrame([_pr_row(supplier_gstin=" 29aabcu9603r1zx ")]), str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row(supplier_gstin="29AABCU9603R1ZX")]),   str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["missing_in_gstr2a"]) == 0
    assert len(r["not_in_books"]) == 0


def test_claimable_itc_excludes_mismatched_rows(tmp_path):
    """claimable_itc counts only cleanly matched rows, never mismatched ones."""
    pr_df = pd.DataFrame([
        _pr_row(invoice_number="CLEAN", igst=900.0),
        _pr_row(invoice_number="BAD",   igst=900.0),
    ])
    g2a_df = pd.DataFrame([
        _g2a_row(invoice_number="CLEAN", igst=900.0),
        _g2a_row(invoice_number="BAD",   igst=900.0 + TOLERANCE + 5),
    ])

    r = reconcile(
        _excel(pr_df,  str(tmp_path / "pr.xlsx")),
        _excel(g2a_df, str(tmp_path / "g2a.xlsx")),
    )

    assert len(r["matched"]) == 1
    assert len(r["amount_mismatch"]) == 1
    # only CLEAN row's IGST counts
    assert r["summary"]["claimable_itc"] == pytest.approx(900.0, abs=1.0)


def test_amount_at_exact_tolerance_boundary(tmp_path):
    """diff == TOLERANCE exactly is NOT flagged — boundary check is strict (> not >=)."""
    pr  = _excel(pd.DataFrame([_pr_row(igst=1800.0)]),              str(tmp_path / "pr.xlsx"))
    g2a = _excel(pd.DataFrame([_g2a_row(igst=1800.0 + TOLERANCE)]), str(tmp_path / "g2a.xlsx"))

    r = reconcile(pr, g2a)

    assert len(r["matched"]) == 1, (
        f"diff == TOLERANCE should be a clean match (TOLERANCE={TOLERANCE})"
    )
    assert len(r["amount_mismatch"]) == 0
