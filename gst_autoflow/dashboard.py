"""
Dashboard analytics — pure functions that take result dicts and return
Plotly figures. No I/O, no Streamlit imports here — keeps logic testable.
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

PALETTE = {
    "green"  : "#2ECC71",
    "red"    : "#E74C3C",
    "yellow" : "#F39C12",
    "blue"   : "#3498DB",
    "navy"   : "#1F3864",
    "light"  : "#F8F9FA",
}


# ── Module 1 Dashboard ────────────────────────────────────────────────────

def itc_risk_by_vendor(missing_df: pd.DataFrame) -> go.Figure:
    """
    Bar chart: ITC at risk per vendor (missing in GSTR-2A).
    Helps owner immediately see which supplier to chase.
    """
    if missing_df.empty:
        return _empty_fig("No ITC at risk — all suppliers have filed ✅")

    # Pick vendor name column (may have _pr suffix after outer merge)
    name_col = next(
        (c for c in ["vendor_name_pr", "vendor_name", "vendor"] if c in missing_df.columns),
        None
    )
    amt_col = next(
        (c for c in ["taxable_amount_pr", "taxable_amount"] if c in missing_df.columns),
        None
    )
    if not name_col or not amt_col:
        return _empty_fig("Vendor/amount columns not found")

    df = (
        missing_df.groupby(name_col)[amt_col]
        .sum()
        .reset_index()
        .sort_values(amt_col, ascending=True)
        .rename(columns={name_col: "Vendor", amt_col: "ITC at Risk (₹)"})
    )

    fig = go.Figure(go.Bar(
        x=df["ITC at Risk (₹)"],
        y=df["Vendor"],
        orientation="h",
        marker_color=PALETTE["red"],
        text=[f"₹{v:,.0f}" for v in df["ITC at Risk (₹)"]],
        textposition="outside",
    ))
    fig.update_layout(
        title="🔴 ITC at Risk by Vendor (Supplier Didn't File)",
        xaxis_title="Taxable Amount (₹)",
        yaxis_title="",
        plot_bgcolor=PALETTE["light"],
        height=max(280, len(df) * 48),
        margin=dict(l=20, r=80, t=50, b=20),
    )
    return fig


def reconciliation_summary_donut(summary: dict) -> go.Figure:
    """Donut showing matched vs issues — quick health indicator."""
    labels = ["✅ Matched Clean", "⚠️ Amount Mismatch",
              "🔴 Missing in GSTR-2A", "🔵 Not in Books"]
    values = [
        summary.get("matched_clean", 0),
        summary.get("amount_mismatch", 0),
        summary.get("missing_in_gstr2a", 0),
        summary.get("not_in_books", 0),
    ]
    colors = [PALETTE["green"], PALETTE["yellow"], PALETTE["red"], PALETTE["blue"]]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker_colors=colors,
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} invoices<extra></extra>",
    ))
    total = sum(values)
    fig.update_layout(
        title="Invoice Reconciliation Breakdown",
        annotations=[dict(text=f"<b>{total}</b><br>Total", x=0.5, y=0.5,
                          font_size=14, showarrow=False)],
        height=340,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def mismatch_detail_bar(mismatch_df: pd.DataFrame) -> go.Figure:
    """Bar chart showing PR amount vs GSTR-2A amount for mismatched invoices."""
    if mismatch_df.empty:
        return _empty_fig("No amount mismatches found ✅")

    inv_col = "invoice_no" if "invoice_no" in mismatch_df.columns else mismatch_df.columns[0]
    pr_col  = next((c for c in ["taxable_amount_pr",  "taxable_amount"]  if c in mismatch_df.columns), None)
    g2a_col = next((c for c in ["taxable_amount_g2a"] if c in mismatch_df.columns), None)

    if not pr_col:
        return _empty_fig("Amount columns not found")

    df = mismatch_df[[inv_col, pr_col] + ([g2a_col] if g2a_col else [])].head(15)

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Your Books (PR)", x=df[inv_col],
                         y=df[pr_col], marker_color=PALETTE["blue"]))
    if g2a_col:
        fig.add_trace(go.Bar(name="GSTR-2A (Supplier Filed)", x=df[inv_col],
                             y=df[g2a_col], marker_color=PALETTE["yellow"]))

    fig.update_layout(
        title="⚠️ Amount Mismatches — Your Books vs GSTR-2A",
        barmode="group",
        xaxis_title="Invoice No",
        yaxis_title="Taxable Amount (₹)",
        plot_bgcolor=PALETTE["light"],
        height=340,
        margin=dict(l=20, r=20, t=50, b=80),
        xaxis_tickangle=-30,
    )
    return fig


# ── Module 3 Dashboard ────────────────────────────────────────────────────

def payment_status_chart(recon_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: liability vs paid per period+tax_type."""
    if recon_df.empty:
        return _empty_fig("No payment data")

    recon_df = recon_df.copy()
    recon_df["label"] = recon_df["period"] + " – " + recon_df["tax_type"].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Liability (₹)", x=recon_df["label"],
        y=recon_df["liability_amount"], marker_color=PALETTE["navy"],
    ))
    fig.add_trace(go.Bar(
        name="Paid (₹)", x=recon_df["label"],
        y=recon_df["payment_amount"], marker_color=PALETTE["green"],
    ))

    fig.update_layout(
        title="💳 GST Liability vs Payments by Period",
        barmode="group",
        xaxis_title="", yaxis_title="Amount (₹)",
        plot_bgcolor=PALETTE["light"],
        height=360,
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=50, b=100),
    )
    return fig


def payment_status_donut(summary: dict) -> go.Figure:
    """Donut: payment compliance breakdown."""
    labels = ["✅ Matched", "🔴 Unpaid", "⚠️ Underpaid", "⏰ Late"]
    values = [
        summary.get("matched", 0),
        summary.get("unpaid", 0),
        summary.get("underpaid", 0),
        summary.get("late_payments", 0),
    ]
    colors = [PALETTE["green"], PALETTE["red"], PALETTE["yellow"], PALETTE["blue"]]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker_colors=colors, textinfo="label+percent",
    ))
    fig.update_layout(
        title="Payment Compliance Breakdown",
        height=320,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


# ── Module 2 Dashboard ────────────────────────────────────────────────────

def ocr_confidence_chart(df: pd.DataFrame) -> go.Figure:
    """Bar: invoice confidence level breakdown."""
    if df.empty or "confidence" not in df.columns:
        return _empty_fig("No OCR data")

    counts  = df["confidence"].value_counts().reset_index()
    counts.columns = ["Confidence", "Count"]
    color_map = {"high": PALETTE["green"], "partial": PALETTE["yellow"], "low": PALETTE["red"]}
    colors    = [color_map.get(c, PALETTE["blue"]) for c in counts["Confidence"]]

    fig = go.Figure(go.Bar(
        x=counts["Confidence"], y=counts["Count"],
        marker_color=colors,
        text=counts["Count"], textposition="outside",
    ))
    fig.update_layout(
        title="🧾 Invoice Extraction Confidence",
        xaxis_title="Confidence Level", yaxis_title="Invoice Count",
        plot_bgcolor=PALETTE["light"],
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def ocr_amount_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean display DataFrame for OCR results."""
    cols = ["file", "vendor_gstin", "invoice_no", "invoice_date",
            "taxable_amount", "igst", "cgst", "sgst", "total_amount", "confidence"]
    present = [c for c in cols if c in df.columns]
    return df[present].copy()


# ── Helper ────────────────────────────────────────────────────────────────

def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, xref="paper", yref="paper",
                       x=0.5, y=0.5, showarrow=False, font_size=14)
    fig.update_layout(height=240, plot_bgcolor=PALETTE["light"],
                      xaxis_visible=False, yaxis_visible=False)
    return fig
