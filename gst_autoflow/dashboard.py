"""
Dashboard analytics — pure functions that take result dicts and return
Plotly figures. No I/O, no Streamlit imports here — keeps logic testable.
"""
import pandas as pd
import plotly.graph_objects as go


# Calm, finance-tool palette. Avoids saturated reds/greens used as primary fills.
PALETTE = {
    "primary":   "#3949AB",   # indigo
    "secondary": "#5C6BC0",
    "success":   "#16A34A",
    "danger":    "#DC2626",
    "warning":   "#D97706",
    "muted":     "#94A3B8",
    "ink":       "#0F172A",
    "subtle":    "#F8FAFC",
    "grid":      "#E2E8F0",
}

# Shared layout defaults — applied to every chart for visual consistency.
_LAYOUT_BASE = dict(
    font=dict(family="Inter, system-ui, sans-serif", size=12, color=PALETTE["ink"]),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=20, r=20, t=56, b=40),
    title=dict(font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
    hoverlabel=dict(font_family="Inter, system-ui, sans-serif"),
    legend=dict(
        orientation="h", yanchor="bottom", y=-0.25,
        xanchor="left", x=0, font=dict(size=11),
    ),
)


def _apply_base(fig: go.Figure, **overrides) -> go.Figure:
    layout = {**_LAYOUT_BASE, **overrides}
    fig.update_layout(**layout)
    fig.update_xaxes(gridcolor=PALETTE["grid"], zeroline=False)
    fig.update_yaxes(gridcolor=PALETTE["grid"], zeroline=False)
    return fig


# ── Module 1 Dashboard ────────────────────────────────────────────────────

def itc_risk_by_vendor(missing_df: pd.DataFrame) -> go.Figure:
    """Horizontal bar: ITC at risk per vendor (missing in GSTR-2A)."""
    if missing_df.empty:
        return _empty_fig("No ITC at risk. All suppliers have filed.")

    name_col = next(
        (c for c in ["vendor_name_pr", "vendor_name", "vendor"] if c in missing_df.columns),
        None,
    )
    amt_col = next(
        (c for c in ["taxable_amount_pr", "taxable_amount"] if c in missing_df.columns),
        None,
    )
    if not name_col or not amt_col:
        return _empty_fig("Vendor or amount column not found.")

    df = (
        missing_df.groupby(name_col)[amt_col]
        .sum()
        .reset_index()
        .sort_values(amt_col, ascending=True)
        .rename(columns={name_col: "Vendor", amt_col: "ITC at Risk"})
    )

    fig = go.Figure(go.Bar(
        x=df["ITC at Risk"],
        y=df["Vendor"],
        orientation="h",
        marker=dict(color=PALETTE["danger"], line=dict(width=0)),
        text=[f"₹{v:,.0f}" for v in df["ITC at Risk"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>ITC at risk: ₹%{x:,.0f}<extra></extra>",
    ))
    return _apply_base(
        fig,
        title=dict(text="ITC at risk by vendor", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        xaxis_title="Taxable amount (₹)",
        yaxis_title="",
        height=max(280, len(df) * 44),
        margin=dict(l=20, r=80, t=56, b=40),
    )


def reconciliation_summary_donut(summary: dict) -> go.Figure:
    """Donut: matched vs issues."""
    labels = ["Matched", "Amount mismatch", "Missing in GSTR-2A", "Not in books"]
    values = [
        summary.get("matched_clean", 0),
        summary.get("amount_mismatch", 0),
        summary.get("missing_in_gstr2a", 0),
        summary.get("not_in_books", 0),
    ]
    colors = [PALETTE["success"], PALETTE["warning"], PALETTE["danger"], PALETTE["secondary"]]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value} invoices (%{percent})<extra></extra>",
    ))
    total = sum(values)
    return _apply_base(
        fig,
        title=dict(text="Reconciliation breakdown", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        height=340,
        annotations=[dict(
            text=f"<b style='font-size:18px;'>{total}</b><br><span style='color:{PALETTE['muted']};font-size:11px;'>invoices</span>",
            x=0.5, y=0.5, showarrow=False,
        )],
    )


def mismatch_detail_bar(mismatch_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: PR amount vs GSTR-2A amount."""
    if mismatch_df.empty:
        return _empty_fig("No amount mismatches found.")

    inv_col = "invoice_no" if "invoice_no" in mismatch_df.columns else mismatch_df.columns[0]
    pr_col = next((c for c in ["taxable_amount_pr", "taxable_amount"] if c in mismatch_df.columns), None)
    g2a_col = next((c for c in ["taxable_amount_g2a"] if c in mismatch_df.columns), None)

    if not pr_col:
        return _empty_fig("Amount columns not found.")

    df = mismatch_df[[inv_col, pr_col] + ([g2a_col] if g2a_col else [])].head(15)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Your books",
        x=df[inv_col], y=df[pr_col],
        marker=dict(color=PALETTE["primary"]),
        hovertemplate="<b>%{x}</b><br>Books: ₹%{y:,.0f}<extra></extra>",
    ))
    if g2a_col:
        fig.add_trace(go.Bar(
            name="GSTR-2A",
            x=df[inv_col], y=df[g2a_col],
            marker=dict(color=PALETTE["warning"]),
            hovertemplate="<b>%{x}</b><br>GSTR-2A: ₹%{y:,.0f}<extra></extra>",
        ))

    return _apply_base(
        fig,
        title=dict(text="Amount mismatches: books vs GSTR-2A", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        barmode="group",
        xaxis_title="Invoice number",
        yaxis_title="Taxable amount (₹)",
        height=360,
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=56, b=100),
    )


# ── Module 3 Dashboard ────────────────────────────────────────────────────

def payment_status_chart(recon_df: pd.DataFrame) -> go.Figure:
    """Grouped bar: liability vs paid per period+tax_type."""
    if recon_df.empty:
        return _empty_fig("No payment data.")

    recon_df = recon_df.copy()
    recon_df["label"] = recon_df["period"] + " — " + recon_df["tax_type"].astype(str)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Liability", x=recon_df["label"], y=recon_df["liability_amount"],
        marker=dict(color=PALETTE["primary"]),
        hovertemplate="<b>%{x}</b><br>Liability: ₹%{y:,.0f}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="Paid", x=recon_df["label"], y=recon_df["payment_amount"],
        marker=dict(color=PALETTE["success"]),
        hovertemplate="<b>%{x}</b><br>Paid: ₹%{y:,.0f}<extra></extra>",
    ))

    return _apply_base(
        fig,
        title=dict(text="Liability vs payments by period", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        barmode="group",
        xaxis_title="",
        yaxis_title="Amount (₹)",
        height=360,
        xaxis_tickangle=-30,
        margin=dict(l=20, r=20, t=56, b=110),
    )


def payment_status_donut(summary: dict) -> go.Figure:
    """Donut: payment compliance breakdown."""
    labels = ["Matched", "Unpaid", "Underpaid", "Late"]
    values = [
        summary.get("matched", 0),
        summary.get("unpaid", 0),
        summary.get("underpaid", 0),
        summary.get("late_payments", 0),
    ]
    colors = [PALETTE["success"], PALETTE["danger"], PALETTE["warning"], PALETTE["secondary"]]

    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.6,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value} liabilities (%{percent})<extra></extra>",
    ))
    return _apply_base(
        fig,
        title=dict(text="Payment compliance", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        height=340,
    )


# ── Module 2 Dashboard ────────────────────────────────────────────────────

def ocr_confidence_chart(df: pd.DataFrame) -> go.Figure:
    """Bar: invoice confidence level breakdown."""
    if df.empty or "confidence" not in df.columns:
        return _empty_fig("No OCR data.")

    counts = df["confidence"].value_counts().reset_index()
    counts.columns = ["Confidence", "Count"]
    color_map = {
        "high": PALETTE["success"],
        "partial": PALETTE["warning"],
        "low": PALETTE["danger"],
    }
    colors = [color_map.get(c, PALETTE["secondary"]) for c in counts["Confidence"]]

    fig = go.Figure(go.Bar(
        x=counts["Confidence"], y=counts["Count"],
        marker=dict(color=colors),
        text=counts["Count"], textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{y} invoices<extra></extra>",
    ))
    return _apply_base(
        fig,
        title=dict(text="Extraction confidence", font=dict(size=14, color=PALETTE["ink"]), x=0, xanchor="left"),
        xaxis_title="Confidence level",
        yaxis_title="Invoice count",
        height=300,
    )


def ocr_amount_table(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean display DataFrame for OCR results."""
    cols = ["file", "vendor_gstin", "invoice_no", "invoice_date",
            "taxable_amount", "igst", "cgst", "sgst", "total_amount",
            "confidence", "extraction_status"]
    present = [c for c in cols if c in df.columns]
    return df[present].copy()


# ── Helper ────────────────────────────────────────────────────────────────

def _empty_fig(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message, xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=13, color=PALETTE["muted"]),
    )
    return _apply_base(
        fig, height=240,
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        title=dict(text="", font=dict(size=14, color=PALETTE["ink"])),
    )
