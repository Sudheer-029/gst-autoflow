"""
GST AutoFlow v2.1 — Persistent header · Session history · Login always accessible
"""
import streamlit as st
import tempfile, os, shutil
from datetime import datetime
import pandas as pd
from gst_autoflow import (
    reconcile, generate_report,
    parse_invoice_folder, generate_ocr_report,
    reconcile_payments, generate_payment_report,
    ValidationError,
)
from gst_autoflow.dashboard import (
    itc_risk_by_vendor, reconciliation_summary_donut, mismatch_detail_bar,
    payment_status_chart, payment_status_donut,
    ocr_confidence_chart, ocr_amount_table,
)

st.set_page_config(
    page_title="GST AutoFlow",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

MAX_EXCEL_MB = 5
MAX_PDF_MB   = 10

USERS = {
    "demo":  {"password": "Demo@2024",     "name": "Demo User",  "role": "Viewer"},
    "admin": {"password": "GSTAdmin@2024", "name": "Admin",      "role": "Admin"},
}

# ── Session state defaults ─────────────────────────────────────────────
for k, v in {
    "authenticated": False,
    "username": "",
    "display_name": "",
    "role": "",
    "history": [],          # list of dicts: {time, module, summary}
    "active_tab": 0,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Global CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { display: none !important; }
.block-container { padding-top: 0 !important; padding-bottom: 2rem !important; max-width: 1200px !important; }

/* ── TOP NAVBAR — always visible ── */
.topbar {
    background: #0d1b2a;
    padding: 0 1.5rem;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 999;
    margin: -1rem -4rem 0 -4rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.topbar-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    color: white;
    font-weight: 700;
    font-size: 1.1rem;
}
.topbar-brand span { color: #4da6ff; font-size: 1.3rem; }
.topbar-right {
    display: flex;
    align-items: center;
    gap: 12px;
}
.user-badge {
    background: rgba(77,166,255,0.15);
    border: 1px solid rgba(77,166,255,0.35);
    color: #a8c8ff !important;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
}
.role-badge {
    background: rgba(255,255,255,0.06);
    color: rgba(255,255,255,0.5) !important;
    padding: 3px 8px;
    border-radius: 10px;
    font-size: 0.7rem;
}

/* ── Module nav bar ── */
.module-nav {
    background: white;
    border-bottom: 2px solid #e8eaf0;
    padding: 0 1.5rem;
    display: flex;
    align-items: center;
    gap: 4px;
    margin: 0 -4rem 1.5rem -4rem;
    position: sticky;
    top: 56px;
    z-index: 998;
}
.nav-tab {
    padding: 14px 18px;
    font-size: 0.875rem;
    font-weight: 500;
    color: #666;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
    white-space: nowrap;
}
.nav-tab.active {
    color: #1a73e8;
    border-bottom-color: #1a73e8;
    font-weight: 600;
}
.nav-right {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
}
.history-btn {
    background: #f0f7ff;
    border: 1px solid #c2d9ff;
    color: #1a73e8 !important;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 500;
    cursor: pointer;
}

/* ── Login page ── */
.login-page {
    min-height: 90vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%);
    margin: 0 -4rem;
    padding: 2rem;
}
.login-card {
    background: white;
    border-radius: 16px;
    padding: 2.5rem 2.5rem;
    box-shadow: 0 8px 40px rgba(0,0,0,0.1);
    width: 100%;
    max-width: 420px;
    border: 1px solid #e0eaff;
}
.login-header { text-align: center; margin-bottom: 1.75rem; }
.login-header h1 { font-size: 1.75rem; font-weight: 700; color: #1a73e8; margin: 0.5rem 0 0; }
.login-header p  { color: #888; font-size: 0.875rem; margin: 0.25rem 0 0; }
.demo-box {
    background: #f0f7ff;
    border: 1px solid #c2d9ff;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 1.25rem;
    font-size: 0.8rem;
    color: #1a56a0;
    line-height: 1.6;
}

/* ── Section header ── */
.section-header { border-left: 4px solid #1a73e8; padding-left: 0.75rem; margin-bottom: 1.25rem; }
.section-header h2 { font-size: 1.15rem; font-weight: 600; color: #1a1a2e; margin: 0; }
.section-header p  { font-size: 0.82rem; color: #666; margin: 3px 0 0; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #f8faff; border: 1px solid #e3eaff;
    border-radius: 10px; padding: 0.75rem 1rem !important;
    box-shadow: 0 2px 8px rgba(26,115,232,0.07);
}
div[data-testid="metric-container"] label {
    font-size: 0.72rem !important; font-weight: 600 !important;
    color: #5c6bc0 !important; text-transform: uppercase; letter-spacing: 0.5px;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 1.45rem !important; font-weight: 700 !important; color: #1a1a2e !important;
}

/* ── File uploader ── */
div[data-testid="stFileUploader"] {
    border: 2px dashed #c2d9ff !important;
    border-radius: 10px !important; background: #f8faff !important;
}

/* ── Buttons ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a73e8, #1557b0) !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 600 !important; font-size: 0.9rem !important;
    box-shadow: 0 3px 10px rgba(26,115,232,0.3) !important;
}
div[data-testid="stButton"] > button[kind="secondary"] {
    border-radius: 8px !important; font-size: 0.85rem !important;
}

/* ── History panel ── */
.history-card {
    background: #fafbff;
    border: 1px solid #e3eaff;
    border-radius: 10px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.82rem;
}
.history-card .time { color: #999; font-size: 0.72rem; }
.history-card .module { font-weight: 600; color: #1a73e8; }
.history-empty { text-align: center; color: #aaa; padding: 2rem; font-size: 0.85rem; }

/* ── Tabs ── */
div[data-testid="stTabs"] button { font-weight: 500 !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #1a73e8 !important; font-weight: 700 !important; }

/* ── Footer ── */
.app-footer {
    text-align: center; color: #bbb; font-size: 0.75rem;
    margin-top: 3rem; padding-top: 1rem; border-top: 1px solid #f0f0f0;
}
.app-footer a { color: #1a73e8; text-decoration: none; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════
#  SIDEBAR — always present, never critical
# ════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding:1rem 0 0.5rem;">
        <div style="font-size:2rem;">📊</div>
        <div style="font-weight:700; font-size:1.1rem; color:#1a73e8;">GST AutoFlow</div>
        <div style="font-size:0.72rem; color:#aaa; margin-top:2px;">v2.1 · India GST Suite</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    if st.session_state.get("authenticated"):
        st.markdown(f"""
        <div style="background:#f0f7ff; border:1px solid #c2d9ff; border-radius:8px;
                    padding:0.6rem 0.75rem; margin-bottom:0.75rem; font-size:0.82rem;">
            👤 <strong>{st.session_state.display_name}</strong><br>
            <span style="color:#888; font-size:0.72rem;">{st.session_state.role} · {st.session_state.username}</span>
        </div>
        """, unsafe_allow_html=True)
        st.caption(f"🕐 {len(st.session_state.history)} run(s) this session")
        st.divider()

    st.markdown("**📥 Sample Files**")
    st.caption("Download to try the app:")
    sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")
    for fname, label in [
        ("gstr2a.xlsx",            "GSTR-2A Sample"),
        ("purchase_register.xlsx", "Purchase Register"),
        ("bank_statement.xlsx",    "Bank Statement"),
        ("gst_liability.xlsx",     "GST Liability"),
    ]:
        fpath = os.path.join(sample_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                st.download_button(f"⬇ {label}", data=f.read(), file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"sb_{fname}")

    st.divider()
    st.markdown("**ℹ️ About**")
    st.caption("GST AutoFlow automates GST reconciliation for Indian businesses. No CA fees. No manual spreadsheets.")
    st.markdown("[GitHub ↗](https://github.com/Sudheer-029/gst-autoflow)  ·  [Portfolio ↗](https://sudheer-029.github.io)")


# ════════════════════════════════════════════════════════════════════════
#  AUTH HELPERS
# ════════════════════════════════════════════════════════════════════════
def do_login(username, password):
    u = username.strip().lower()
    if u in USERS and USERS[u]["password"] == password:
        st.session_state.authenticated = True
        st.session_state.username      = u
        st.session_state.display_name  = USERS[u]["name"]
        st.session_state.role          = USERS[u]["role"]
        return True
    return False

def do_logout():
    for k in ["authenticated", "username", "display_name", "role", "history"]:
        st.session_state[k] = False if k == "authenticated" else ([] if k == "history" else "")
    st.rerun()

def add_history(module, summary_text):
    st.session_state.history.insert(0, {
        "time":    datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "module":  module,
        "summary": summary_text,
    })
    if len(st.session_state.history) > 20:
        st.session_state.history = st.session_state.history[:20]

def save_upload(f, suffix, max_mb):
    if f.size / (1024 * 1024) > max_mb:
        raise ValidationError(f"'{f.name}' exceeds {max_mb} MB limit.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(f.read()); tmp.close()
    return tmp.name


# ════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ════════════════════════════════════════════════════════════════════════
if not st.session_state.authenticated:
    # Minimal topbar even on login
    st.markdown("""
    <div class="topbar">
        <div class="topbar-brand"><span>📊</span> GST AutoFlow</div>
        <div class="topbar-right">
            <span class="role-badge">India GST Suite · v2.1</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.1, 1])
    with col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="login-header">
            <div style="font-size:3rem;">📊</div>
            <h1>GST AutoFlow</h1>
            <p>Know your GST health before your CA does.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="demo-box">
            <strong>🔑 Try the demo</strong><br>
            Username: <code>demo</code> &nbsp;·&nbsp; Password: <code>Demo@2024</code>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            cols = st.columns([1, 1])
            submitted = cols[0].form_submit_button("Sign In →", type="primary", use_container_width=True)
            cols[1].form_submit_button("Try Demo", use_container_width=True)

            if submitted:
                if do_login(username, password):
                    st.rerun()
                else:
                    st.error("Incorrect username or password.")

        # Auto-fill demo on "Try Demo" click (workaround via session state flag)
        st.markdown("""
        <div style="text-align:center; margin-top:1.25rem; color:#bbb; font-size:0.75rem;">
            GST AutoFlow v2.1 &nbsp;·&nbsp; 
            Built by <a href="https://sudheer-029.github.io" target="_blank" style="color:#1a73e8;">Sudheer Bishnoi</a>
        </div>
        """, unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════════════════
#  AUTHENTICATED — PERSISTENT TOPBAR (always visible)
# ════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="topbar">
    <div class="topbar-brand"><span>📊</span> GST AutoFlow</div>
    <div class="topbar-right">
        <span class="role-badge">{st.session_state.role}</span>
        <span class="user-badge">👤 {st.session_state.display_name}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Sign out + history in a slim row just below topbar
tb1, tb2, tb3, tb4 = st.columns([3, 1, 1, 1])
with tb4:
    if st.button("🚪 Sign Out", use_container_width=True):
        do_logout()
with tb3:
    show_history = st.toggle("🕐 History", value=False)
with tb2:
    st.markdown(f"<span style='font-size:0.78rem; color:#888;'>Session: {len(st.session_state.history)} run(s)</span>", unsafe_allow_html=True)

st.divider()


# ════════════════════════════════════════════════════════════════════════
#  HISTORY PANEL (collapsible)
# ════════════════════════════════════════════════════════════════════════
if show_history:
    with st.container(border=True):
        st.markdown("#### 🕐 Reconciliation History (this session)")
        if not st.session_state.history:
            st.markdown('<div class="history-empty">No runs yet. Run a reconciliation to see history here.</div>', unsafe_allow_html=True)
        else:
            for i, h in enumerate(st.session_state.history):
                c1, c2, c3 = st.columns([1.5, 3, 1])
                c1.markdown(f"<span style='font-size:0.72rem;color:#999;'>{h['time']}</span>", unsafe_allow_html=True)
                c2.markdown(f"**{h['module']}** — {h['summary']}")
                c3.markdown(f"<span style='font-size:0.75rem;color:#1a73e8;'>Run #{len(st.session_state.history)-i}</span>", unsafe_allow_html=True)
        if st.session_state.history:
            if st.button("Clear History", type="secondary"):
                st.session_state.history = []
                st.rerun()
    st.divider()


# ════════════════════════════════════════════════════════════════════════
#  MAIN TABS
# ════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "🔄  GSTR-2A Reconciliation",
    "🧾  Invoice OCR Parser",
    "💳  Payment Reconciliation",
    "📥  Sample Files",
])


# ── TAB 1 — GSTR-2A ───────────────────────────────────────────────────
with tab1:
    st.markdown("""
    <div class="section-header">
        <h2>GSTR-2A vs Purchase Register</h2>
        <p>Find ITC at risk, amount mismatches, and invoices not filed by suppliers — in seconds.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    pr_file  = c1.file_uploader(f"📁 Purchase Register (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="pr")
    g2a_file = c2.file_uploader(f"📁 GSTR-2A (.xlsx ≤{MAX_EXCEL_MB}MB)",           type=["xlsx"], key="g2a")

    if pr_file and g2a_file:
        if st.button("🔄 Run Reconciliation", type="primary", use_container_width=True, key="btn_recon"):
            pr_path = g2a_path = None
            try:
                with st.spinner("Reconciling..."):
                    pr_path  = save_upload(pr_file,  ".xlsx", MAX_EXCEL_MB)
                    g2a_path = save_upload(g2a_file, ".xlsx", MAX_EXCEL_MB)
                    results  = reconcile(pr_path, g2a_path)
                    report   = generate_report(results)
                s = results["summary"]

                if s["missing_in_gstr2a"] > 0:
                    st.error(f"🔴 **Action Required:** {s['missing_in_gstr2a']} supplier(s) haven't filed — **₹{s['itc_at_risk']:,.0f} ITC at risk.**")
                elif s["amount_mismatch"] > 0:
                    st.warning(f"⚠️ **Review Needed:** {s['amount_mismatch']} invoice(s) have amount differences.")
                else:
                    st.success("✅ All clean — no ITC at risk, no mismatches.")

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Invoices",   s["total_pr"])
                m2.metric("✅ Matched",       s["matched_clean"])
                m3.metric("⚠️ Mismatch",      s["amount_mismatch"])
                m4.metric("🔴 Missing",       s["missing_in_gstr2a"])
                m5.metric("ITC at Risk (₹)",  f"₹{s['itc_at_risk']:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1.2, 1])
                with ch1: st.plotly_chart(itc_risk_by_vendor(results["missing_in_gstr2a"]), use_container_width=True)
                with ch2: st.plotly_chart(reconciliation_summary_donut(s), use_container_width=True)
                st.plotly_chart(mismatch_detail_bar(results["amount_mismatch"]), use_container_width=True)

                with open(report, "rb") as f:
                    st.download_button("📥 Download Full Report (.xlsx)", data=f,
                        file_name=os.path.basename(report),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                with st.expander("Preview — Missing in GSTR-2A"):
                    st.dataframe(results["missing_in_gstr2a"], use_container_width=True)
                with st.expander("Preview — Amount Mismatches"):
                    st.dataframe(results["amount_mismatch"], use_container_width=True)

                add_history("GSTR-2A Reconciliation",
                    f"{s['total_pr']} invoices · {s['matched_clean']} matched · {s['missing_in_gstr2a']} missing · ₹{s['itc_at_risk']:,.0f} ITC at risk")

            except ValidationError as e: st.error(f"⚠️ {e}")
            except Exception: st.error("Unexpected error — check your file format.")
            finally:
                for p in [pr_path, g2a_path]:
                    if p and os.path.exists(p): os.unlink(p)
    else:
        st.info("📂 Upload both files above to begin reconciliation.")
        with st.expander("📋 Expected column names"):
            cc1, cc2 = st.columns(2)
            cc1.markdown("**Purchase Register**\n\n`supplier_gstin` · `invoice_number` · `invoice_date` · `taxable_amount` · `igst` · `cgst` · `sgst`")
            cc2.markdown("**GSTR-2A**\n\n`supplier_gstin` · `invoice_number` · `invoice_date` · `taxable_amount` · `igst` · `cgst` · `sgst`")


# ── TAB 2 — Invoice OCR ───────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="section-header">
        <h2>Invoice OCR Parser</h2>
        <p>Upload vendor PDF invoices — extract GSTIN, invoice numbers, dates, and amounts automatically.</p>
    </div>
    """, unsafe_allow_html=True)

    uploaded_pdfs = st.file_uploader(
        f"📎 Upload PDF Invoices (multiple, ≤{MAX_PDF_MB} MB each)",
        type=["pdf"], accept_multiple_files=True, key="pdfs"
    )
    if uploaded_pdfs:
        if st.button("🧾 Extract Invoice Data", type="primary", use_container_width=True, key="btn_ocr"):
            tmp_dir = None
            try:
                with st.spinner(f"Parsing {len(uploaded_pdfs)} invoice(s)..."):
                    tmp_dir = tempfile.mkdtemp()
                    for upf in uploaded_pdfs:
                        if upf.size / (1024*1024) > MAX_PDF_MB:
                            raise ValidationError(f"'{upf.name}' exceeds {MAX_PDF_MB} MB.")
                        safe_name = os.path.basename(upf.name).encode("ascii", errors="ignore").decode()
                        with open(os.path.join(tmp_dir, safe_name), "wb") as f:
                            f.write(upf.read())
                    df     = parse_invoice_folder(tmp_dir)
                    report = generate_ocr_report(df)

                if "confidence" in df.columns:
                    low_conf = df[df["confidence"].isin(["low", "partial"])]
                    if not low_conf.empty:
                        st.warning(f"⚠️ {len(low_conf)} invoice(s) need manual check: {', '.join(low_conf['file'].tolist())}")
                    else:
                        st.success(f"✅ All {len(df)} invoices extracted with high confidence.")

                    high = (df["confidence"] == "high").sum()
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("📄 Processed",       len(df))
                    m2.metric("✅ High Confidence", int(high))
                    m3.metric("⚠️ Low/Partial",      int(len(df) - high))
                    total_taxable = df["taxable_amount"].sum() if "taxable_amount" in df.columns else 0
                    m4.metric("Total Taxable (₹)",  f"₹{total_taxable:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1, 1.6])
                with ch1: st.plotly_chart(ocr_confidence_chart(df), use_container_width=True)
                with ch2: st.dataframe(ocr_amount_table(df), use_container_width=True, height=280)

                with open(report, "rb") as f:
                    st.download_button("📥 Download Extracted Data (.xlsx)", data=f,
                        file_name=os.path.basename(report),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                add_history("Invoice OCR Parser", f"{len(df)} invoice(s) parsed · ₹{total_taxable:,.0f} total taxable")

            except ValidationError as e: st.error(f"⚠️ {e}")
            except Exception: st.error("Unexpected error — check your PDF files.")
            finally:
                if tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        st.info("📎 Upload one or more PDF invoices to begin extraction.")
        st.caption("💡 Text-based PDFs work best.")


# ── TAB 3 — Payment Recon ─────────────────────────────────────────────
with tab3:
    st.markdown("""
    <div class="section-header">
        <h2>GST Payment Reconciliation</h2>
        <p>Match bank payments against GSTR-3B liability. Find unpaid, late, and underpaid entries.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    bank_file = c1.file_uploader(f"🏦 Bank Statement (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="bank")
    liab_file = c2.file_uploader(f"📋 GST Liability (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="liab")

    if bank_file and liab_file:
        if st.button("💳 Run Payment Reconciliation", type="primary", use_container_width=True, key="btn_pay"):
            bank_path = liab_path = None
            try:
                with st.spinner("Matching payments..."):
                    bank_path = save_upload(bank_file, ".xlsx", MAX_EXCEL_MB)
                    liab_path = save_upload(liab_file, ".xlsx", MAX_EXCEL_MB)
                    results   = reconcile_payments(bank_path, liab_path)
                    report    = generate_payment_report(results)
                s = results["summary"]

                if s["unpaid"] > 0:
                    st.error(f"🔴 **Immediate Action:** {s['unpaid']} liability(s) unpaid — **₹{s['outstanding']:,.0f} outstanding.** ₹50/day penalty applies.")
                elif s["late_payments"] > 0:
                    st.warning(f"⏰ {s['late_payments']} payment(s) after due date. Verify 18% p.a. interest.")
                else:
                    st.success("✅ All GST payments matched and on time.")

                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total",          s["total_liabilities"])
                m2.metric("✅ Matched",     s["matched"])
                m3.metric("🔴 Unpaid",      s["unpaid"])
                m4.metric("⚠️ Underpaid",   s["underpaid"])
                m5.metric("⏰ Late",        s["late_payments"])
                m6.metric("Outstanding ₹", f"₹{s['outstanding']:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1.8, 1])
                with ch1: st.plotly_chart(payment_status_chart(results["reconciliation"]), use_container_width=True)
                with ch2: st.plotly_chart(payment_status_donut(s), use_container_width=True)
                st.dataframe(results["reconciliation"], use_container_width=True)

                with open(report, "rb") as f:
                    st.download_button("📥 Download Full Report (.xlsx)", data=f,
                        file_name=os.path.basename(report),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                add_history("Payment Reconciliation",
                    f"{s['total_liabilities']} liabilities · {s['matched']} matched · {s['unpaid']} unpaid · ₹{s['outstanding']:,.0f} outstanding")

            except ValidationError as e: st.error(f"⚠️ {e}")
            except Exception: st.error("Unexpected error — check your file format.")
            finally:
                for p in [bank_path, liab_path]:
                    if p and os.path.exists(p): os.unlink(p)
    else:
        st.info("📂 Upload bank statement and GST liability file to begin.")
        with st.expander("📋 Bank Statement format"):
            st.markdown("`date` · `description` · `debit` · `credit`")
        with st.expander("📋 GST Liability format"):
            st.markdown("`period` · `tax_type` · `liability_amount` · `due_date`")


# ── TAB 4 — Sample Files ──────────────────────────────────────────────
with tab4:
    st.markdown("""
    <div class="section-header">
        <h2>Sample Files</h2>
        <p>Download these to test all three modules immediately — no real data needed.</p>
    </div>
    """, unsafe_allow_html=True)

    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    samples = [
        ("gstr2a.xlsx",            "📊 GSTR-2A Sample",         "Use in Tab 1 alongside Purchase Register"),
        ("purchase_register.xlsx", "📋 Purchase Register",      "Use in Tab 1 alongside GSTR-2A"),
        ("bank_statement.xlsx",    "🏦 Bank Statement",         "Use in Tab 3 alongside GST Liability"),
        ("gst_liability.xlsx",     "📄 GST Liability / GSTR-3B","Use in Tab 3 alongside Bank Statement"),
    ]
    cols = st.columns(2)
    for i, (fname, label, desc) in enumerate(samples):
        fpath = os.path.join(sample_dir, fname)
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(desc)
                if os.path.exists(fpath):
                    with open(fpath, "rb") as f:
                        st.download_button(f"⬇ Download {fname}", data=f, file_name=fname,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True, key=f"dl_{fname}")

    st.info("💡 For Invoice OCR: sample PDFs are in the `sample_data/invoices/` folder in the GitHub repo.")


# ── Footer ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
    GST AutoFlow v2.1 &nbsp;·&nbsp;
    Built by <a href="https://sudheer-029.github.io" target="_blank">Sudheer Bishnoi</a>
    &nbsp;·&nbsp; Data processed in-memory, never stored.
    &nbsp;·&nbsp; <a href="https://github.com/Sudheer-029/gst-autoflow" target="_blank">GitHub ↗</a>
</div>
""", unsafe_allow_html=True)
