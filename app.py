"""
GST AutoFlow — GST reconciliation suite for Indian businesses.

A Streamlit application that automates three workflows:
  1. GSTR-2A vs Purchase Register reconciliation
  2. Invoice OCR extraction from PDF
  3. GST liability vs bank payment reconciliation
"""
from __future__ import annotations

import os
import shutil
import tempfile
import traceback
from datetime import datetime

import streamlit as st

from gst_autoflow import (
    ValidationError,
    generate_ocr_report,
    generate_payment_report,
    generate_report,
    parse_invoice_folder,
    reconcile,
    reconcile_payments,
)
from gst_autoflow.dashboard import (
    itc_risk_by_vendor,
    mismatch_detail_bar,
    ocr_amount_table,
    ocr_confidence_chart,
    payment_status_chart,
    payment_status_donut,
    reconciliation_summary_donut,
)
from gst_autoflow.telemetry import track as track_event
from gst_autoflow import session_store

APP_NAME = "GST AutoFlow"
_PERSIST_KEYS = ("history", "_mod1_cache", "_mod2_cache", "_mod3_cache")
APP_VERSION = "3.0"
APP_TAGLINE = "GST reconciliation, automated."
MAX_EXCEL_MB = 5
MAX_PDF_MB = 10


st.set_page_config(
    page_title=f"{APP_NAME} — GST reconciliation",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/Sudheer-029/gst-autoflow",
        "Report a bug": "https://github.com/Sudheer-029/gst-autoflow/issues",
        "About": f"{APP_NAME} v{APP_VERSION} — GST reconciliation toolkit for Indian businesses.",
    },
)

_DEFAULTS = {
    "started": False,           # False -> show landing page; True -> show modules
    "history": [],
    "show_history": False,
    "session_id": "",
    "_session_restored": False,
}
for _k, _v in _DEFAULTS.items():
    st.session_state.setdefault(_k, _v)

# ── Session persistence ────────────────────────────────────────────────────────
def _persist() -> None:
    """Write persistable keys to the session file."""
    sid = st.session_state.get("session_id", "")
    if not sid:
        return
    session_store.save(sid, {k: st.session_state[k]
                              for k in _PERSIST_KEYS
                              if k in st.session_state})

def _init_session() -> None:
    """Assign or restore session from URL query param ?s=..."""
    params = st.query_params
    if "s" not in params:
        # Brand-new visit — generate ID and write to URL
        sid = session_store.new_id()
        st.query_params["s"] = sid
        st.session_state.session_id = sid
        session_store.cleanup()   # housekeeping on new sessions
        return
    sid = params["s"]
    st.session_state.session_id = sid
    # ?home=1 — user clicked the logo; go back to landing page
    if params.get("home") == "1":
        st.session_state.started = False
        _persist()
        del st.query_params["home"]   # strip param so back-button works cleanly
        return
    if st.session_state._session_restored:
        return                    # already restored this Python process run
    st.session_state._session_restored = True
    saved = session_store.load(sid)
    for key in _PERSIST_KEYS:
        if key in saved:
            st.session_state[key] = saved[key]
    if saved.get("history"):
        st.session_state.started = True  # go straight to app if they had work

_init_session()


# Load styles from external file (kept separate for readability)
_STYLE_PATH = os.path.join(os.path.dirname(__file__), ".streamlit", "styles.css")
try:
    with open(_STYLE_PATH, encoding="utf-8") as _f:
        st.markdown(f"<style>{_f.read()}</style>", unsafe_allow_html=True)
except OSError:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def render_topbar() -> None:
    """Persistent top navigation bar."""
    sid = st.session_state.get("session_id", "")
    # When in app mode, wrap brand in a link that triggers home navigation
    if st.session_state.get("started") and sid:
        brand_html = (
            f'<a class="ga-brand ga-brand-link" href="?s={sid}&home=1" target="_self" title="Back to home">'
            f'<span class="ga-monogram"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></span>'
            f'<span>{APP_NAME}</span>'
            f'</a>'
        )
    else:
        brand_html = (
            f'<div class="ga-brand">'
            f'<span class="ga-monogram"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></span>'
            f'<span>{APP_NAME}</span>'
            f'</div>'
        )
    st.markdown(
        f'<div class="ga-topbar">'
        f'{brand_html}'
        f'<div class="ga-topbar-right">'
        f'<a class="ga-topbar-link" href="https://github.com/Sudheer-029/gst-autoflow" target="_blank">GitHub</a>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def banner(kind: str, message: str) -> None:
    """kind: success | warning | danger | info"""
    st.markdown(
        f'<div class="ga-banner ga-banner-{kind}">{message}</div>',
        unsafe_allow_html=True,
    )


def section_header(title: str, description: str, badge: str = "") -> None:
    badge_html = f'<div class="ga-module-badge">{badge}</div>' if badge else ""
    st.markdown(
        f'<div class="ga-section">{badge_html}<h2>{title}</h2><p>{description}</p></div>',
        unsafe_allow_html=True,
    )


def add_history(module: str, summary_text: str) -> None:
    st.session_state.history.insert(0, {
        "time": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "module": module,
        "summary": summary_text,
    })
    if len(st.session_state.history) > 20:
        st.session_state.history = st.session_state.history[:20]
    _persist()


def save_upload(uploaded_file, suffix: str, max_mb: int) -> str:
    if uploaded_file.size / (1024 * 1024) > max_mb:
        raise ValidationError(f"'{uploaded_file.name}' exceeds the {max_mb} MB limit.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read())
    tmp.close()
    return tmp.name


def cleanup_paths(*paths) -> None:
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.unlink(p)
            except OSError:
                pass


def render_error(exc: Exception) -> None:
    """Render a user-friendly error with debug details in an expander."""
    if isinstance(exc, ValidationError):
        banner("warning", f"<b>Input validation:</b> {exc}")
        return
    banner(
        "danger",
        f"<b>Could not complete the operation.</b> {type(exc).__name__}: {exc}",
    )
    with st.expander("Error details (include when reporting a bug):"):
        st.code(traceback.format_exc(), language="text")


def render_workflow_steps(active: int) -> None:
    """Render a 3-step progress indicator. active: 1=Upload, 2=Run, 3=Download."""
    steps = [("1", "Upload"), ("2", "Run"), ("3", "Download")]
    parts = []
    for i, (num, label) in enumerate(steps, start=1):
        if i < active:
            cls = "ga-wf-step ga-wf-done"
            icon = f'<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>'
        elif i == active:
            cls = "ga-wf-step ga-wf-active"
            icon = num
        else:
            cls = "ga-wf-step ga-wf-idle"
            icon = num
        parts.append(
            f'<div class="{cls}"><span class="ga-wf-num">{icon}</span>'
            f'<span class="ga-wf-label">{label}</span></div>'
        )
        if i < len(steps):
            parts.append('<div class="ga-wf-line"></div>')
    st.markdown(
        '<div class="ga-workflow">' + "".join(parts) + '</div>',
        unsafe_allow_html=True,
    )



def fmt_inr(value: float) -> str:
    return f"₹{value:,.0f}"


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f'<div style="padding: 0.25rem 0 1rem;">'
            f'<div style="display:flex; align-items:center; gap:10px;">'
            f'<span class="ga-monogram"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg></span>'
            f'<div><div style="font-weight:600; color:var(--ga-ink); font-size:0.95rem;">{APP_NAME}</div>'
            f'<div style="font-size:0.72rem; color:var(--ga-muted);">v{APP_VERSION}</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        if st.session_state.started:
            st.caption(f"Session runs: {len(st.session_state.history)}")
            if st.button("Back to start", use_container_width=True, key="sb_home"):
                st.session_state.started = False
                _persist()
                st.rerun()
            st.divider()

        st.markdown("**Sample data**")
        st.caption("Test the app with anonymised sample files.")
        sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")
        for fname, label in [
            ("gstr2a.xlsx",            "GSTR-2A sample"),
            ("purchase_register.xlsx", "Purchase register"),
            ("bank_statement.xlsx",    "Bank statement"),
            ("gst_liability.xlsx",     "GST liability"),
        ]:
            fpath = os.path.join(sample_dir, fname)
            if os.path.exists(fpath):
                with open(fpath, "rb") as f:
                    st.download_button(
                        label, data=f.read(), file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True, key=f"sb_{fname}",
                    )

        st.divider()
        st.markdown("**Resources**")
        st.markdown(
            "- [Source on GitHub](https://github.com/Sudheer-029/gst-autoflow)\n"
            "- [Report an issue](https://github.com/Sudheer-029/gst-autoflow/issues)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Landing page
# ─────────────────────────────────────────────────────────────────────────────
def render_landing() -> None:
    render_topbar()

    # Hero
    st.markdown(
        f'<div class="ga-hero">'
        f'<div class="ga-hero-inner">'
        f'<div class="ga-eyebrow">Open source · Free forever · Made in India</div>'
        f'<h1 class="ga-hero-title">{APP_TAGLINE}</h1>'
        f'<p class="ga-hero-sub">'
        f'Match purchase register against GSTR-2A/2B, extract invoice data via OCR, '
        f'and reconcile GST payments — in minutes. No signup. No CA fees. '
        f'Your files never leave your session.'
        f'</p>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # CTA
    _, ctacol, _ = st.columns([1, 1.4, 1])
    with ctacol:
        if st.button(
            "Start reconciling →",
            type="primary",
            use_container_width=True,
            key="cta_start",
        ):
            st.session_state.started = True
            _persist()
            track_event("landing_cta_click", st.session_state.session_id)
            st.rerun()
        st.caption(
            "No account required · No data stored · Open source (MIT) · Free forever"
        )

    # What it does — feature grid
    _ICON_RECON = (
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M9 11l3 3L22 4"/>' +
        '<path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>' +
        '</svg>'
    )
    _ICON_OCR = (
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>' +
        '<polyline points="14 2 14 8 20 8"/>' +
        '<line x1="16" y1="13" x2="8" y2="13"/>' +
        '<line x1="16" y1="17" x2="8" y2="17"/>' +
        '</svg>'
    )
    _ICON_PAY = (
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
        '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/>' +
        '<line x1="1" y1="10" x2="23" y2="10"/>' +
        '</svg>'
    )
    features = [
        (
            _ICON_RECON,
            "GSTR-2A / 2B Reconciliation",
            "Compare your purchase register with GSTR-2A or 2B. See exactly which "
            "suppliers haven't filed, where amounts mismatch, and how much "
            "input tax credit is at risk.",
        ),
        (
            _ICON_OCR,
            "Invoice OCR Parser",
            "Drop in vendor PDF invoices. Extracts GSTIN, invoice number, "
            "date, taxable value, and tax breakup automatically. Flags "
            "low-confidence extractions for manual review.",
        ),
        (
            _ICON_PAY,
            "Payment Reconciliation",
            "Match your bank statement against GSTR-3B liability. Spot "
            "unpaid, late, or short-paid entries before the department does.",
        ),
    ]
    _features_html = '<div class="ga-features">'
    for icon, title, body in features:
        _features_html += (
            f'<div class="ga-feature-card">'
            f'<div class="ga-feature-icon">{icon}</div>'
            f'<div class="ga-feature-title">{title}</div>'
            f'<div class="ga-feature-body">{body}</div>'
            f'</div>'
        )
    _features_html += '</div>'
    st.markdown(_features_html, unsafe_allow_html=True)

    # How it works — three steps
    steps = [
        ("1", "Upload", "Drop in your GSTR-2A, purchase register, bank statement, or PDF invoices."),
        ("2", "Reconcile", "We match, compare, and flag everything that needs your attention."),
        ("3", "Act", "Download a clean Excel report. Send it to your CA or fix it yourself."),
    ]
    _steps_html = '<div class="ga-steps"><div class="ga-steps-title">How it works</div>'
    for num, title, body in steps:
        _steps_html += (
            f'<div class="ga-step">'
            f'<div class="ga-step-num">{num}</div>'
            f'<div class="ga-step-content">'
            f'<div class="ga-step-title">{title}</div>'
            f'<div class="ga-step-body">{body}</div>'
            f'</div></div>'
        )
    _steps_html += '</div>'
    st.markdown(_steps_html, unsafe_allow_html=True)

    # Trust strip
    st.markdown(
        '<div class="ga-trust">'
        '<div class="ga-trust-item"><span class="ga-trust-check">✓</span><b>Open source</b><br>MIT licensed. Audit, fork, or self-host.</div>'
        '<div class="ga-trust-item"><span class="ga-trust-check">✓</span><b>Zero data retention</b><br>Files processed in-session. Nothing stored.</div>'
        '<div class="ga-trust-item"><span class="ga-trust-check">✓</span><b>No account needed</b><br>No email, no password, no tracking pixel.</div>'
        '<div class="ga-trust-item"><span class="ga-trust-check">✓</span><b>GST-compliant logic</b><br>Aligned with CGST Act §16(2)(aa) for ITC claims.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Disclaimer
    st.markdown(
        '<div class="ga-disclaimer" style="margin-top:1.5rem;">'
        'GST AutoFlow is a free utility, not certified accounting software. '
        'Always verify results with a qualified CA before filing returns.'
        '</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Module 1 — GSTR-2A reconciliation
# ─────────────────────────────────────────────────────────────────────────────
def _show_mod1_results(cache: dict) -> None:
    """Render reconciliation results from session_state cache."""
    results = cache["results"]
    s = results["summary"]
    statement_label = cache["statement_label"]

    if s["missing_in_gstr2a"] > 0:
        banner("danger",
            f"<b>Action required.</b> {s['missing_in_gstr2a']} supplier(s) "
            f"haven't filed. {fmt_inr(s['itc_at_risk'])} of input tax credit "
            f"is at risk for this period.")
    elif s["amount_mismatch"] > 0:
        banner("warning",
            f"<b>Review needed.</b> {s['amount_mismatch']} invoice(s) "
            f"have amount differences between books and {statement_label}.")
    else:
        banner("success", f"All invoices match {statement_label}. No ITC at risk.")

    m1, m2, m3, m4 = st.columns(4)
    _total_itc = s.get("claimable_itc", 0) + s["itc_at_risk"]
    _itc_risk_pct = (s["itc_at_risk"] / _total_itc * 100) if _total_itc else 0
    _mismatch_pct = (s["amount_mismatch"] / s["total_pr"] * 100) if s["total_pr"] else 0
    m1.metric("Claimable ITC", fmt_inr(s.get("claimable_itc", 0)),
              help="ITC you can claim — invoices present in both your books and GSTR-2B with matching amounts.")
    m2.metric("ITC at risk", fmt_inr(s["itc_at_risk"]),
              delta=f"{_itc_risk_pct:.1f}% of total ITC" if _itc_risk_pct else None,
              delta_color="inverse",
              help="ITC from suppliers who haven't filed GSTR-1. Blocked under §16(2)(aa) until they file.")
    m3.metric("Mismatches", s["amount_mismatch"],
              delta=f"{_mismatch_pct:.1f}% of invoices" if _mismatch_pct else None,
              delta_color="inverse",
              help="Invoices present in both files but with differing taxable amounts or GST values.")
    m4.metric("Total invoices", s["total_pr"],
              help="Invoice count from your purchase register.")

    st.divider()
    ch1, ch2 = st.columns([1.2, 1])
    with ch1:
        st.plotly_chart(itc_risk_by_vendor(results["missing_in_gstr2a"]), use_container_width=True)
    with ch2:
        st.plotly_chart(reconciliation_summary_donut(s), use_container_width=True)
    st.plotly_chart(mismatch_detail_bar(results["amount_mismatch"]), use_container_width=True)

    dl_col, reset_col = st.columns([3, 1])
    with dl_col:
        st.download_button(
            "Download full report (.xlsx)",
            data=cache["report_bytes"],
            file_name=cache["report_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_mod1",
        )
    with reset_col:
        if st.button("↺ New run", use_container_width=True, key="reset_mod1"):
            del st.session_state["_mod1_cache"]
            _persist()
            st.rerun()

    with st.expander(f"Preview: missing in {statement_label}"):
        st.dataframe(results["missing_in_gstr2a"], use_container_width=True)
    with st.expander("Preview: amount mismatches"):
        st.dataframe(results["amount_mismatch"], use_container_width=True)


def render_gstr2a_module() -> None:
    section_header(
        "GSTR-2B vs Purchase Register",
        "See your claimable ITC, ITC at risk, and amount mismatches in one view. "
        "GSTR-2B is the static monthly statement against which ITC may legally be claimed.",
        badge="Module 1 — ITC Reconciliation",
    )

    # If we have cached results, show them (persists through download button clicks)
    if "_mod1_cache" in st.session_state:
        _show_mod1_results(st.session_state["_mod1_cache"])
        return

    # Mode selector — 2B is recommended; 2A retained for backward compatibility
    with st.container(border=True):
        mc1, mc2 = st.columns([1, 2.5])
        with mc1:
            mode = st.radio(
                "Statement type",
                ["GSTR-2B (recommended)", "GSTR-2A"],
                index=0,
                key="g2_mode",
                help=(
                    "GSTR-2B is the static monthly statement that locks "
                    "your ITC for filing. GSTR-2A is auto-drafted and "
                    "shifts when suppliers file late."
                ),
            )
        with mc2:
            if mode.startswith("GSTR-2B"):
                st.markdown(
                    '<div class="ga-tip">'
                    '<b>Tip:</b> Download GSTR-2B from <code>gst.gov.in → Returns Dashboard → '
                    'GSTR-2B → Download (Excel)</code>. Under Section 16(2)(aa) of '
                    'the CGST Act, ITC is claimable only against the locked 2B statement.'
                    '</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="ga-tip ga-tip-warn">'
                    '<b>Note:</b> GSTR-2A is dynamic and changes when suppliers file late. '
                    'Use it for visibility only. Always reconcile against GSTR-2B before filing.'
                    '</div>',
                    unsafe_allow_html=True,
                )

    mode_short = "2B" if mode.startswith("GSTR-2B") else "2A"
    statement_label = f"GSTR-{mode_short}"

    render_workflow_steps(1)
    c1, c2 = st.columns(2)
    pr_file = c1.file_uploader(
        f"Purchase register (.xlsx, max {MAX_EXCEL_MB} MB)", type=["xlsx"], key="pr",
    )
    g2a_file = c2.file_uploader(
        f"{statement_label} (.xlsx, max {MAX_EXCEL_MB} MB)", type=["xlsx"], key="g2a",
    )

    if not (pr_file and g2a_file):
        banner("info", f"Upload both the purchase register and {statement_label} files to begin.")
        with st.expander("Expected columns"):
            cc1, cc2 = st.columns(2)
            cc1.markdown(
                "**Purchase register**\n\n"
                "`supplier_gstin` · `invoice_number` · `invoice_date` · "
                "`taxable_amount` · `igst` · `cgst` · `sgst`"
            )
            cc2.markdown(
                f"**{statement_label}**\n\n"
                "`supplier_gstin` · `invoice_number` · `invoice_date` · "
                "`taxable_amount` · `igst` · `cgst` · `sgst`"
            )
        return

    if not st.button(
        f"Run {statement_label} reconciliation",
        type="primary",
        use_container_width=True,
        key="btn_recon",
    ):
        return

    pr_path = g2a_path = report = None
    try:
        with st.spinner("Reconciling…"):
            pr_path = save_upload(pr_file, ".xlsx", MAX_EXCEL_MB)
            g2a_path = save_upload(g2a_file, ".xlsx", MAX_EXCEL_MB)
            results = reconcile(pr_path, g2a_path, mode=mode_short)
            report = generate_report(results)
        s = results["summary"]
        # Read bytes immediately so we can delete the temp file
        with open(report, "rb") as rf:
            report_bytes = rf.read()
        st.session_state["_mod1_cache"] = {
            "results": results,
            "report_bytes": report_bytes,
            "report_name": os.path.basename(report),
            "statement_label": statement_label,
        }
        _persist()
        add_history(
            f"{statement_label} reconciliation",
            f"{s['total_pr']} invoices · {s['matched_clean']} matched · "
            f"{s['missing_in_gstr2a']} missing · {fmt_inr(s['itc_at_risk'])} ITC at risk",
        )
        track_event("module_run", st.session_state.session_id, {
            "module": "gstr2_recon",
            "mode": mode_short,
            "total_invoices": int(s["total_pr"]),
            "missing_count": int(s["missing_in_gstr2a"]),
            "mismatch_count": int(s["amount_mismatch"]),
        })
        st.rerun()
    except Exception as exc:
        render_error(exc)
        track_event("module_error", st.session_state.session_id, {
            "module": "gstr2_recon",
            "error_type": type(exc).__name__,
        })
    finally:
        cleanup_paths(pr_path, g2a_path)
        if report and os.path.exists(report):
            try: os.unlink(report)
            except OSError: pass


# ─────────────────────────────────────────────────────────────────────────────
# Module 2 — Invoice OCR
# ─────────────────────────────────────────────────────────────────────────────
def _show_mod2_results(cache: dict) -> None:
    df = cache["df"]
    high = cache["high"]
    total_taxable = cache["total_taxable"]

    if cache.get("low_conf_files"):
        banner("warning", f"<b>{cache['low_conf_count']} invoice(s) need manual review:</b> {cache['low_conf_files']}")
    else:
        banner("success", f"All {len(df)} invoice(s) extracted with high confidence.")

    m1, m2, m3, m4 = st.columns(4)
    _conf_pct = (int(high) / len(df) * 100) if len(df) else 0
    _review_pct = ((len(df) - int(high)) / len(df) * 100) if len(df) else 0
    m1.metric("Processed", len(df),
              help="Total PDF invoices parsed in this run.")
    m2.metric("High confidence", int(high),
              delta=f"{_conf_pct:.0f}% extraction rate",
              delta_color="normal",
              help="Invoices where all key fields (GSTIN, amount, date) were extracted cleanly.")
    m3.metric("Needs review", int(len(df) - high),
              delta=f"{_review_pct:.0f}% of batch" if (len(df) - int(high)) else None,
              delta_color="inverse",
              help="Scanned or low-quality PDFs where fields may be missing or incorrect. Verify manually.")
    m4.metric("Total taxable", fmt_inr(total_taxable),
              help="Sum of taxable_amount across all extracted invoices.")

    st.divider()
    ch1, ch2 = st.columns([1, 1.6])
    with ch1:
        st.plotly_chart(ocr_confidence_chart(df), use_container_width=True)
    with ch2:
        st.dataframe(ocr_amount_table(df), use_container_width=True, height=280)

    dl_col, reset_col = st.columns([3, 1])
    with dl_col:
        st.download_button(
            "Download extracted data (.xlsx)",
            data=cache["report_bytes"],
            file_name=cache["report_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_mod2",
        )
    with reset_col:
        if st.button("↺ New run", use_container_width=True, key="reset_mod2"):
            del st.session_state["_mod2_cache"]
            _persist()
            st.rerun()


def render_ocr_module() -> None:
    section_header(
        "Invoice OCR Parser",
        "Extract GSTIN, invoice number, date, and amounts from vendor PDF invoices.",
        badge="Module 2 — Invoice Extraction",
    )

    if "_mod2_cache" in st.session_state:
        _show_mod2_results(st.session_state["_mod2_cache"])
        return

    render_workflow_steps(1)
    uploaded_pdfs = st.file_uploader(
        f"PDF invoices (multiple, max {MAX_PDF_MB} MB each)",
        type=["pdf"], accept_multiple_files=True, key="pdfs",
    )

    if not uploaded_pdfs:
        banner("info", "Upload one or more PDF invoices to extract structured data.")
        st.caption("Text-based PDFs work best. Scanned image PDFs may yield partial results.")
        return

    if not st.button("Extract invoice data", type="primary", use_container_width=True, key="btn_ocr"):
        return

    tmp_dir = report = None
    try:
        with st.spinner(f"Parsing {len(uploaded_pdfs)} invoice(s)..."):
            tmp_dir = tempfile.mkdtemp()
            for upf in uploaded_pdfs:
                if upf.size / (1024 * 1024) > MAX_PDF_MB:
                    raise ValidationError(f"'{upf.name}' exceeds the {MAX_PDF_MB} MB limit.")
                safe_name = os.path.basename(upf.name).encode("ascii", errors="ignore").decode()
                with open(os.path.join(tmp_dir, safe_name), "wb") as wf:
                    wf.write(upf.read())
            df = parse_invoice_folder(tmp_dir)
            report = generate_ocr_report(df)

        high = (df["confidence"] == "high").sum() if "confidence" in df.columns else len(df)
        total_taxable = df["taxable_amount"].sum() if "taxable_amount" in df.columns else 0
        low_conf = df[df["confidence"].isin(["low", "partial"])] if "confidence" in df.columns else df.iloc[0:0]

        with open(report, "rb") as rf:
            report_bytes = rf.read()
        st.session_state["_mod2_cache"] = {
            "df": df,
            "high": high,
            "total_taxable": total_taxable,
            "low_conf_files": ", ".join(low_conf["file"].tolist()) if not low_conf.empty else "",
            "low_conf_count": len(low_conf),
            "report_bytes": report_bytes,
            "report_name": os.path.basename(report),
        }
        _persist()
        add_history("Invoice OCR", f"{len(df)} invoice(s) parsed · {fmt_inr(total_taxable)} total taxable")
        track_event("module_run", st.session_state.session_id, {
            "module": "invoice_ocr",
            "invoice_count": int(len(df)),
            "high_confidence": int(high),
        })
        st.rerun()
    except Exception as exc:
        render_error(exc)
        track_event("module_error", st.session_state.session_id, {
            "module": "invoice_ocr",
            "error_type": type(exc).__name__,
        })
    finally:
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        if report and os.path.exists(report):
            try: os.unlink(report)
            except OSError: pass


# ─────────────────────────────────────────────────────────────────────────────
# Module 3 — Payment reconciliation
# ─────────────────────────────────────────────────────────────────────────────
def _show_mod3_results(cache: dict) -> None:
    results = cache["results"]
    s = results["summary"]

    if s["unpaid"] > 0:
        banner("danger",
            f"<b>Immediate action.</b> {s['unpaid']} liability(s) unpaid. "
            f"{fmt_inr(s['outstanding'])} outstanding. ₹50/day late fee applies.")
    elif s["late_payments"] > 0:
        banner("warning",
            f"{s['late_payments']} payment(s) made after due date. "
            "Verify 18% p.a. interest has been paid.")
    else:
        banner("success", "All GST payments matched and on time.")

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    _matched_pct = (s["matched"] / s["total_liabilities"] * 100) if s["total_liabilities"] else 0
    m1.metric("Total", s["total_liabilities"],
              help="GST liability entries from your GSTR-3B file.")
    m2.metric("Matched", s["matched"],
              delta=f"{_matched_pct:.0f}% match rate",
              delta_color="normal",
              help="Liabilities with a matching bank payment on or before the due date.")
    m3.metric("Unpaid", s["unpaid"],
              delta_color="inverse",
              help="Liabilities with no matching bank payment. ₹50/day late fee applies.")
    m4.metric("Underpaid", s["underpaid"],
              help="Bank payment found but less than the liability amount.")
    m5.metric("Late", s["late_payments"],
              help="Paid after due date. 18% p.a. interest may apply.")
    m6.metric("Outstanding", fmt_inr(s["outstanding"]),
              help="Total unpaid + underpaid amount still owed.")

    st.divider()
    ch1, ch2 = st.columns([1.8, 1])
    with ch1:
        st.plotly_chart(payment_status_chart(results["reconciliation"]), use_container_width=True)
    with ch2:
        st.plotly_chart(payment_status_donut(s), use_container_width=True)
    st.dataframe(results["reconciliation"], use_container_width=True)

    dl_col, reset_col = st.columns([3, 1])
    with dl_col:
        st.download_button(
            "Download full report (.xlsx)",
            data=cache["report_bytes"],
            file_name=cache["report_name"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="dl_mod3",
        )
    with reset_col:
        if st.button("↺ New run", use_container_width=True, key="reset_mod3"):
            del st.session_state["_mod3_cache"]
            _persist()
            st.rerun()


def render_payment_module() -> None:
    section_header(
        "GST Payment Reconciliation",
        "Match bank payments against GSTR-3B liability. Identify unpaid, late, "
        "and underpaid entries.",
        badge="Module 3 — Payment Matching",
    )

    if "_mod3_cache" in st.session_state:
        _show_mod3_results(st.session_state["_mod3_cache"])
        return

    render_workflow_steps(1)
    c1, c2 = st.columns(2)
    bank_file = c1.file_uploader(
        f"Bank statement (.xlsx, max {MAX_EXCEL_MB} MB)", type=["xlsx"], key="bank",
    )
    liab_file = c2.file_uploader(
        f"GST liability (.xlsx, max {MAX_EXCEL_MB} MB)", type=["xlsx"], key="liab",
    )

    if not (bank_file and liab_file):
        banner("info", "Upload the bank statement and GST liability files to begin.")
        with st.expander("Expected columns"):
            cc1, cc2 = st.columns(2)
            cc1.markdown("**Bank statement**\n\n`date` · `description` · `debit` · `credit`")
            cc2.markdown("**GST liability**\n\n`period` · `tax_type` · `liability_amount` · `due_date`")
        return

    if not st.button(
        "Run payment reconciliation", type="primary",
        use_container_width=True, key="btn_pay",
    ):
        return

    bank_path = liab_path = report = None
    try:
        with st.spinner("Matching payments..."):
            bank_path = save_upload(bank_file, ".xlsx", MAX_EXCEL_MB)
            liab_path = save_upload(liab_file, ".xlsx", MAX_EXCEL_MB)
            results = reconcile_payments(bank_path, liab_path)
            report = generate_payment_report(results)
        s = results["summary"]
        with open(report, "rb") as rf:
            report_bytes = rf.read()
        st.session_state["_mod3_cache"] = {
            "results": results,
            "report_bytes": report_bytes,
            "report_name": os.path.basename(report),
        }
        _persist()
        add_history(
            "Payment reconciliation",
            f"{s['total_liabilities']} liabilities · {s['matched']} matched · "
            f"{s['unpaid']} unpaid · {fmt_inr(s['outstanding'])} outstanding",
        )
        track_event("module_run", st.session_state.session_id, {
            "module": "payment_recon",
            "total_liabilities": int(s["total_liabilities"]),
            "unpaid": int(s["unpaid"]),
            "late": int(s["late_payments"]),
        })
        st.rerun()
    except Exception as exc:
        render_error(exc)
        track_event("module_error", st.session_state.session_id, {
            "module": "payment_recon",
            "error_type": type(exc).__name__,
        })
    finally:
        cleanup_paths(bank_path, liab_path)
        if report and os.path.exists(report):
            try: os.unlink(report)
            except OSError: pass


# ─────────────────────────────────────────────────────────────────────────────
# Module 4 — Sample data
# ─────────────────────────────────────────────────────────────────────────────
def render_samples_module() -> None:
    section_header(
        "Sample data",
        "Download sample files to test all three modules without using real data.",
    )
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    xlsx_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # ── Module 1 & 3 Excel files ──────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Module 1 — GSTR-2A / 2B Reconciliation</div>',
        unsafe_allow_html=True,
    )
    excel_samples = [
        ("gstr2a.xlsx",            "GSTR-2A sample",    "Upload in tab 1 as the GSTR-2A / 2B file."),
        ("purchase_register.xlsx", "Purchase register", "Upload in tab 1 as the purchase register."),
    ]
    c1, c2 = st.columns(2)
    for col, (fname, label, desc) in zip([c1, c2], excel_samples):
        fpath = os.path.join(sample_dir, fname)
        with col:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(desc)
                if os.path.exists(fpath):
                    with open(fpath, "rb") as fh:
                        st.download_button(
                            f"Download {fname}", data=fh, file_name=fname,
                            mime=xlsx_mime, use_container_width=True, key=f"dl_{fname}",
                        )

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # ── Module 2 PDF invoices ─────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Module 2 — Invoice OCR</div>',
        unsafe_allow_html=True,
    )
    invoice_dir = os.path.join(sample_dir, "invoices")
    pdfs = sorted([
        f for f in os.listdir(invoice_dir) if f.endswith(".pdf")
    ]) if os.path.isdir(invoice_dir) else []

    if pdfs:
        pdf_cols = st.columns(3)
        for i, fname in enumerate(pdfs):
            fpath = os.path.join(invoice_dir, fname)
            vendor = fname.replace("invoice_0", "").replace("invoice_", "")
            vendor = "_".join(vendor.split("_")[1:]).replace(".pdf", "").replace("_", " ")
            with pdf_cols[i % 3]:
                with st.container(border=True):
                    st.markdown(f"**{vendor}**")
                    st.caption("Sample vendor invoice (.pdf)")
                    with open(fpath, "rb") as fh:
                        st.download_button(
                            f"Download {fname}", data=fh, file_name=fname,
                            mime="application/pdf",
                            use_container_width=True, key=f"dl_{fname}",
                        )
    else:
        banner("warning", "No sample PDF invoices found in <code>sample_data/invoices/</code>.")

    st.markdown("<div style='height:1.25rem'></div>", unsafe_allow_html=True)

    # ── Module 3 Excel files ──────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Module 3 — Payment Reconciliation</div>',
        unsafe_allow_html=True,
    )
    pay_samples = [
        ("bank_statement.xlsx", "Bank statement", "Upload in tab 3 as the bank statement."),
        ("gst_liability.xlsx",  "GST liability",  "Upload in tab 3 as the GST liability file."),
    ]
    c3, c4 = st.columns(2)
    for col, (fname, label, desc) in zip([c3, c4], pay_samples):
        fpath = os.path.join(sample_dir, fname)
        with col:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(desc)
                if os.path.exists(fpath):
                    with open(fpath, "rb") as fh:
                        st.download_button(
                            f"Download {fname}", data=fh, file_name=fname,
                            mime=xlsx_mime, use_container_width=True, key=f"dl_{fname}",
                        )



# ─────────────────────────────────────────────────────────────────────────────
# Module 5 — Help & Support
# ─────────────────────────────────────────────────────────────────────────────
def render_help_module() -> None:
    section_header(
        "Help & Support",
        "Instructions, frequently asked questions, privacy policy, and how to report issues.",
    )

    # ── Quick Start ──────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Quick Start — How to use each module</div>',
        unsafe_allow_html=True,
    )

    qs_data = [
        (
            "Module 1 — GSTR-2A / 2B Reconciliation",
            [
                ("Download your GSTR-2B", "Go to gst.gov.in → Returns Dashboard → GSTR-2B → Download (Excel). Use GSTR-2B, not 2A — it's the locked monthly statement valid for ITC claims under Section 16(2)(aa)."),
                ("Export your purchase register", "From Tally, Zoho Books, or any accounting software. Must include: supplier GSTIN, invoice number, date, taxable amount, IGST, CGST, SGST."),
                ("Upload both files", "In the GSTR-2A / 2B tab, upload the purchase register and GSTR-2B file. Column names are mapped automatically."),
                ("Run reconciliation", "Click 'Run GSTR-2B reconciliation'. The app matches invoices by GSTIN + invoice number and flags missing suppliers and amount mismatches."),
                ("Act on the results", "Download the Excel report and share with your CA. Follow up with suppliers shown as 'missing in GSTR-2B' — their unfiled GSTR-1 puts your ITC at risk."),
            ],
        ),
        (
            "Module 2 — Invoice OCR Parser",
            [
                ("Collect vendor PDF invoices", "Gather PDF invoices from your vendors. Text-based PDFs (digital) work best. Scanned/image PDFs may yield partial results."),
                ("Upload the PDFs", "In the Invoice OCR tab, upload one or more PDFs at once (max 10 MB each)."),
                ("Review confidence levels", "High = all key fields extracted reliably. Partial/Low = one or more fields uncertain — verify those invoices manually before using the data."),
                ("Download the output", "The Excel report has one row per invoice with GSTIN, invoice number, date, taxable value, IGST, CGST, SGST, and total."),
            ],
        ),
        (
            "Module 3 — Payment Reconciliation",
            [
                ("Export your bank statement", "Download from net banking in Excel format (.xlsx). Must include: date, description, debit, credit columns."),
                ("Get your GST liability", "From gst.gov.in or your CA's records. Must include: period, tax type (CGST/SGST/IGST), liability amount, due date."),
                ("Upload both files", "In the Payment Recon tab, upload both files."),
                ("Review the results", "The app matches bank debits to liability entries by period and tax type. Unpaid entries carry a ₹50/day late fee; underpaid entries trigger 18% p.a. interest."),
            ],
        ),
    ]

    for module_title, steps in qs_data:
        with st.expander(module_title, expanded=False):
            for i, (step_title, step_body) in enumerate(steps, 1):
                st.markdown(
                    f'<div class="ga-step" style="padding:0.5rem 0;">'                    f'<div class="ga-step-num">{i}</div>'                    f'<div class="ga-step-content">'                    f'<div class="ga-step-title">{step_title}</div>'                    f'<div class="ga-step-body">{step_body}</div>'                    f'</div></div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── FAQ ───────────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Frequently Asked Questions</div>',
        unsafe_allow_html=True,
    )

    faqs = [
        (
            "What file formats does the app accept?",
            "Excel (.xlsx) for GSTR-2A/2B, purchase register, bank statement, and GST liability. PDF for invoice OCR. Files must be under 5 MB (Excel) or 10 MB (PDF) each.",
        ),
        (
            "What's the difference between GSTR-2A and GSTR-2B?",
            "GSTR-2A is auto-drafted and changes dynamically as suppliers file late. GSTR-2B is a locked monthly statement — it's the one that matters for ITC claims under Section 16(2)(aa) of the CGST Act. Use 2B for reconciliation before filing.",
        ),
        (
            "Why does my reconciliation show suppliers as 'missing'?",
            "The supplier hasn't filed their GSTR-1 for that period, so the invoice doesn't appear in your GSTR-2B. If they don't file before the cutoff, you cannot claim ITC on that invoice. Follow up with the supplier directly.",
        ),
        (
            "My column names are different from the expected format — will it work?",
            "Yes. The app maps common column name variations automatically (e.g. 'Invoice No.', 'Inv_Number', 'invoice_number' all map correctly). If a column can't be mapped, the error message will tell you exactly which column is missing.",
        ),
        (
            "Invoice OCR shows 'low confidence' — what should I do?",
            "Manually verify those invoices before using the extracted data. Low confidence usually means the PDF is a scanned image, has unusual fonts, or the layout deviates from standard GST invoice formats. The Excel report flags these rows for easy filtering.",
        ),
        (
            "Can I use this tool to file my GST returns?",
            "No. GST AutoFlow is a reconciliation and analysis tool only. Filing returns must be done through the official GST portal (gst.gov.in) or via a certified GST Suvidha Provider (GSP). Always verify results with a qualified CA before filing.",
        ),
        (
            "How many invoices can I process at once?",
            "There's no hard limit on invoice count. Each PDF must be under 10 MB. For Excel files, the limit is 5 MB per file. For very large datasets, split into batches.",
        ),
        (
            "My data is sensitive financial information — is it safe?",
            "Files are processed in your browser session only. Nothing is uploaded to any external server or cloud storage. See the Privacy & Data Policy section below for full details.",
        ),
        (
            "I refreshed the page and my results are gone — how do I get them back?",
            "Results are saved to your session automatically. As long as your URL still contains '?s=...', your last run is restored on refresh. If you opened a completely new tab or cleared the URL, the session is lost and you'll need to re-upload.",
        ),
        (
            "The app is showing an error — what should I do?",
            "Check that your file matches the expected column format (use the 'Expected columns' section in each module as a reference). If the error persists after correcting the file, please report it on GitHub Issues with the error message and a description of your file structure.",
        ),
    ]

    for question, answer in faqs:
        with st.expander(question):
            st.markdown(
                f'<p style="font-size:0.875rem; color:var(--ga-text); line-height:1.6; margin:0;">{answer}</p>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── Privacy & Data Policy ─────────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Privacy & Data Policy</div>',
        unsafe_allow_html=True,
    )

    policy_items = [
        (
            "What data do we collect?",
            "None. We do not collect, transmit, or store any personal data, GSTIN, PAN, bank details, or financial figures. There are no analytics scripts, tracking pixels, or third-party integrations in this application.",
        ),
        (
            "How are uploaded files processed?",
            "Files are loaded into server memory for the duration of your active session only. They are never written to permanent storage, never uploaded to any cloud service, and are deleted from memory as soon as processing is complete.",
        ),
        (
            "What is the session file stored locally?",
            "To allow page-refresh recovery, a small session file is saved on the machine running the app (at <code>~/.gst_autoflow/sessions/</code>). It contains your reconciliation results and history for your session only, identified by a random session ID in your URL. This file is automatically deleted after 48 hours.",
        ),
        (
            "Third-party services",
            "None. GST AutoFlow makes no external API calls. The only external resource loaded is the Inter typeface from Google Fonts (a static CSS file). If you require fully offline operation, you can self-host the font by removing the @import line from styles.css.",
        ),
        (
            "Disclaimer",
            "GST AutoFlow is a free utility tool, not certified accounting software. Results should always be verified with a qualified Chartered Accountant before filing GST returns. The maintainers accept no liability for errors, omissions, or penalties arising from use of this tool.",
        ),
    ]

    for title, body in policy_items:
        with st.expander(title):
            st.markdown(
                f'<p style="font-size:0.875rem; color:var(--ga-text); line-height:1.6; margin:0;">{body}</p>',
                unsafe_allow_html=True,
            )

    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)


    st.markdown("<div style='height:1.5rem'></div>", unsafe_allow_html=True)

    # ── Changelog ─────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Changelog</div>',
        unsafe_allow_html=True,
    )
    changelog_entries = [
        (
            f"v3.0 — Current",
            [
                "Session persistence: results survive page refresh via URL-based session ID",
                "Module 3: GST payment reconciliation against GSTR-3B liability",
                "Telemetry: anonymous event tracking for usage analysis (no personal data)",
                "Dashboard: Plotly charts for ITC risk by vendor, payment status, and confidence",
                "Streamlit 1.x rewrite: tabs, containers, native st.metric with delta support",
            ],
        ),
        (
            "v2.0",
            [
                "Module 2: PDF invoice OCR parser with confidence scoring",
                "Sample data: anonymised GSTR-2A, purchase register, bank statement, and PDF invoices",
                "Column mapper: auto-detects 40+ column name variations across accounting software",
                "Excel reports: multi-sheet output with colour-coded mismatch rows",
            ],
        ),
        (
            "v1.0",
            [
                "Module 1: GSTR-2A vs purchase register reconciliation",
                "GSTR-2B mode added (static monthly statement for ITC claims under §16(2)(aa))",
                "ValidationError handling with user-friendly messages",
                "Streamlit UI with sidebar, section headers, and result cache",
            ],
        ),
    ]
    for version, items in changelog_entries:
        with st.expander(version):
            for item in items:
                st.markdown(
                    f'<div style="font-size:0.875rem; color:var(--ga-text); '
                    f'line-height:1.8; padding:0.1rem 0;">&#x2022; {item}</div>',
                    unsafe_allow_html=True,
                )
    # ── Support ───────────────────────────────────────────────────────────────
    st.markdown(
        '<div class="ga-module-badge">Support & Bug Reports</div>',
        unsafe_allow_html=True,
    )
    _support_html = (
        '<div class="ga-steps" style="margin-top:0.75rem;">'
        '<div class="ga-steps-title">How to report an issue</div>'
        '<div class="ga-step"><div class="ga-step-num">1</div>'
        '<div class="ga-step-content">'
        '<div class="ga-step-title">Check the FAQ above</div>'
        '<div class="ga-step-body">Most column mapping errors and file format issues are covered in the FAQ.</div>'
        '</div></div>'
        '<div class="ga-step"><div class="ga-step-num">2</div>'
        '<div class="ga-step-content">'
        '<div class="ga-step-title">Open a GitHub Issue</div>'
        '<div class="ga-step-body">Go to '
        '<a href="https://github.com/Sudheer-029/gst-autoflow/issues" '
        'target="_blank" style="color:var(--ga-primary);">'
        'github.com/Sudheer-029/gst-autoflow/issues</a> and click <b>New issue</b>.'
        '</div></div>'
        '<div class="ga-step"><div class="ga-step-num">3</div>'
        '<div class="ga-step-content">'
        '<div class="ga-step-title">Include in your report</div>'
        '<div class="ga-step-body">The exact error message · which module · '
        'a description of your file column structure '
        '(do not attach real financial data).</div>'
        '</div></div></div>'
    )
    st.markdown(_support_html, unsafe_allow_html=True)

    st.markdown(
        '<div class="ga-disclaimer" style="margin-top:1.25rem;">'        'Support is provided on a best-effort basis with no guaranteed response time. '        'This is an open-source project — contributions and pull requests are welcome.'        '</div>',
        unsafe_allow_html=True,
    )

def render_history_panel() -> None:
    if not st.session_state.show_history:
        return
    with st.container(border=True):
        st.markdown("**Reconciliation history (this session)**")
        if not st.session_state.history:
            st.caption("No runs yet. Run a reconciliation to see history here.")
        else:
            for i, h in enumerate(st.session_state.history):
                c1, c2, c3 = st.columns([1.5, 3, 0.8])
                c1.markdown(
                    f"<span style='font-size:0.75rem; color:var(--ga-muted);'>{h['time']}</span>",
                    unsafe_allow_html=True,
                )
                c2.markdown(f"**{h['module']}** — {h['summary']}")
                c3.markdown(
                    f"<span style='font-size:0.75rem; color:var(--ga-muted);'>"
                    f"#{len(st.session_state.history) - i}</span>",
                    unsafe_allow_html=True,
                )
            if st.button("Clear history", type="secondary", key="clear_hist"):
                st.session_state.history = []
                _persist()
                st.rerun()
    st.divider()


def render_footer() -> None:
    st.markdown(
        f'<div class="ga-footer">'
        f'<span>{APP_NAME} v{APP_VERSION} · Files processed in memory, never stored.</span>'
        f'<span>'
        f'<a href="https://github.com/Sudheer-029/gst-autoflow" target="_blank">Source</a> · '
        f'<a href="https://github.com/Sudheer-029/gst-autoflow/issues" target="_blank">Report issue</a>'
        f'</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    render_sidebar()

    if not st.session_state.started:
        render_landing()
        return

    render_topbar()

    # History toggle row
    _, _, hcol = st.columns([6, 1, 1])
    with hcol:
        st.session_state.show_history = st.toggle(
            "History",
            value=st.session_state.show_history,
            key="history_toggle",
        )
    render_history_panel()

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "GSTR-2A / 2B",
        "Invoice OCR",
        "Payment Recon",
        "Sample Data",
        "Help & Support",
    ])
    with tab1:
        render_gstr2a_module()
    with tab2:
        render_ocr_module()
    with tab3:
        render_payment_module()
    with tab4:
        render_samples_module()
    with tab5:
        render_help_module()

    render_footer()


main()
