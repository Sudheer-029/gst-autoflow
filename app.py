"""
GST AutoFlow v2.0 — Professional Edition
Login + 3-Module Dashboard: GSTR-2A Recon · Invoice OCR · Payment Recon
"""
import streamlit as st
import tempfile, os, shutil
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

# ── Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GST AutoFlow",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

MAX_EXCEL_MB = 5
MAX_PDF_MB   = 10

# Demo credentials (replace with env vars / secrets in production)
USERS = {
    "demo":  {"password": "Demo@2024",     "name": "Demo User",  "role": "Viewer"},
    "admin": {"password": "GSTAdmin@2024", "name": "Admin",      "role": "Admin"},
}

# ── Global CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Font & Base ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Hide default Streamlit chrome ── */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }

/* ── Top header bar ── */
.app-header {
    background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
    padding: 1rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 15px rgba(26,115,232,0.25);
}
.app-header h1 {
    color: white !important;
    font-size: 1.6rem !important;
    font-weight: 700 !important;
    margin: 0 !important;
    padding: 0 !important;
}
.app-header .tagline {
    color: rgba(255,255,255,0.85);
    font-size: 0.85rem;
    margin-top: 2px;
}
.header-badge {
    background: rgba(255,255,255,0.2);
    color: white;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 500;
}

/* ── Login card ── */
.login-wrapper {
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 70vh;
}
.login-card {
    background: white;
    border-radius: 16px;
    padding: 2.5rem;
    box-shadow: 0 8px 40px rgba(0,0,0,0.12);
    max-width: 420px;
    width: 100%;
    border: 1px solid #e8eaf0;
}
.login-logo {
    text-align: center;
    margin-bottom: 1.5rem;
}
.login-logo h2 {
    font-size: 1.8rem;
    font-weight: 700;
    color: #1a73e8;
    margin: 0;
}
.login-logo p {
    color: #666;
    font-size: 0.875rem;
    margin: 4px 0 0 0;
}
.demo-creds {
    background: #f0f7ff;
    border: 1px solid #c2d9ff;
    border-radius: 8px;
    padding: 0.75rem 1rem;
    margin-bottom: 1.25rem;
    font-size: 0.8rem;
    color: #1a56a0;
}
.demo-creds strong { color: #0d47a1; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: #f8faff;
    border: 1px solid #e3eaff;
    border-radius: 10px;
    padding: 0.75rem 1rem !important;
    box-shadow: 0 2px 8px rgba(26,115,232,0.07);
}
div[data-testid="metric-container"] label {
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #5c6bc0 !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #1a1a2e !important;
}

/* ── Section headers ── */
.section-header {
    border-left: 4px solid #1a73e8;
    padding-left: 0.75rem;
    margin-bottom: 1rem;
}
.section-header h2 {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    color: #1a1a2e !important;
    margin: 0 !important;
}
.section-header p {
    font-size: 0.82rem;
    color: #666;
    margin: 2px 0 0 0;
}

/* ── File uploader ── */
div[data-testid="stFileUploader"] {
    border: 2px dashed #c2d9ff !important;
    border-radius: 10px !important;
    background: #f8faff !important;
    transition: border-color 0.2s;
}
div[data-testid="stFileUploader"]:hover {
    border-color: #1a73e8 !important;
}

/* ── Primary button ── */
div[data-testid="stButton"] > button[kind="primary"] {
    background: linear-gradient(135deg, #1a73e8, #1557b0) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 0.6rem 1.5rem !important;
    box-shadow: 0 3px 10px rgba(26,115,232,0.3) !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 5px 15px rgba(26,115,232,0.4) !important;
}

/* ── Tabs ── */
div[data-testid="stTabs"] button {
    font-weight: 500 !important;
    font-size: 0.9rem !important;
    padding: 0.5rem 1.25rem !important;
}
div[data-testid="stTabs"] button[aria-selected="true"] {
    color: #1a73e8 !important;
    font-weight: 700 !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0d1b2a !important;
}
section[data-testid="stSidebar"] * {
    color: #e8eaf0 !important;
}
.sidebar-logo {
    text-align: center;
    padding: 1rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 1rem;
}
.sidebar-logo h2 {
    color: #4da6ff !important;
    font-size: 1.3rem;
    font-weight: 700;
    margin: 0;
}
.sidebar-logo p {
    color: rgba(255,255,255,0.5) !important;
    font-size: 0.75rem;
    margin: 4px 0 0 0;
}
.user-pill {
    background: rgba(77,166,255,0.15);
    border: 1px solid rgba(77,166,255,0.3);
    border-radius: 8px;
    padding: 0.6rem 0.75rem;
    margin-bottom: 1rem;
    font-size: 0.82rem;
}
.nav-item {
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
    cursor: pointer;
    transition: background 0.15s;
}
.nav-item:hover { background: rgba(255,255,255,0.05); }
.nav-item.active { background: rgba(77,166,255,0.15); color: #4da6ff !important; font-weight: 600; }

/* ── Footer ── */
.app-footer {
    text-align: center;
    color: #aaa;
    font-size: 0.75rem;
    margin-top: 2.5rem;
    padding-top: 1rem;
    border-top: 1px solid #f0f0f0;
}
.app-footer a { color: #1a73e8; text-decoration: none; }

/* ── Expander ── */
div[data-testid="stExpander"] {
    border: 1px solid #e8eaf0 !important;
    border-radius: 8px !important;
}

/* ── Alert boxes ── */
div[data-testid="stAlert"] {
    border-radius: 8px !important;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════
#  AUTH — Session State Login
# ════════════════════════════════════════════════════════════════════════
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.display_name = ""
    st.session_state.role = ""

def do_login(username, password):
    u = username.strip().lower()
    if u in USERS and USERS[u]["password"] == password:
        st.session_state.authenticated = True
        st.session_state.username = u
        st.session_state.display_name = USERS[u]["name"]
        st.session_state.role = USERS[u]["role"]
        return True
    return False

def do_logout():
    for k in ["authenticated", "username", "display_name", "role"]:
        st.session_state[k] = "" if k != "authenticated" else False
    st.rerun()


# ── Login Page ─────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    col_l, col_m, col_r = st.columns([1, 1.2, 1])
    with col_m:
        st.markdown("""
        <div style='text-align:center; margin: 3rem 0 2rem 0;'>
            <div style='font-size:3rem;'>📊</div>
            <h1 style='font-size:1.8rem; font-weight:700; color:#1a73e8; margin:0.5rem 0 0 0;'>GST AutoFlow</h1>
            <p style='color:#666; font-size:0.9rem; margin:0.25rem 0 0 0;'>Know your GST health before your CA does.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="demo-creds">
            <strong>🔑 Demo Access</strong><br>
            Username: <strong>demo</strong> &nbsp;|&nbsp; Password: <strong>Demo@2024</strong>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign In →", type="primary", use_container_width=True)

            if submitted:
                if do_login(username, password):
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        st.markdown("""
        <div style='text-align:center; margin-top:1.5rem; color:#aaa; font-size:0.75rem;'>
            GST AutoFlow v2.0 &nbsp;·&nbsp; Built by 
            <a href='https://sudheer-029.github.io' target='_blank' style='color:#1a73e8;'>Sudheer Bishnoi</a>
        </div>
        """, unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════════════════
#  SIDEBAR — Authenticated
# ════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <h2>📊 GST AutoFlow</h2>
        <p>v2.0 Professional</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="user-pill">
        👤 &nbsp;<strong>{st.session_state.display_name}</strong><br>
        <span style='font-size:0.72rem; opacity:0.7;'>{st.session_state.role} · {st.session_state.username}</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Modules**")
    st.markdown("""
    <div class="nav-item active">🔄 &nbsp;GSTR-2A Reconciliation</div>
    <div class="nav-item">🧾 &nbsp;Invoice OCR Parser</div>
    <div class="nav-item">💳 &nbsp;Payment Reconciliation</div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Sample Files**")
    st.caption("Download to try the app:")

    # Sample data downloads
    sample_dir = os.path.join(os.path.dirname(__file__), "sample_data")
    for fname, label in [
        ("gstr2a.xlsx",           "📥 GSTR-2A Sample"),
        ("purchase_register.xlsx","📥 Purchase Register"),
        ("bank_statement.xlsx",   "📥 Bank Statement"),
        ("gst_liability.xlsx",    "📥 GST Liability"),
    ]:
        fpath = os.path.join(sample_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, "rb") as f:
                st.download_button(label, data=f, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key=f"dl_{fname}")

    st.divider()
    if st.button("🚪 Sign Out", use_container_width=True):
        do_logout()


# ════════════════════════════════════════════════════════════════════════
#  MAIN APP — Header
# ════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <div>
        <h1>📊 GST AutoFlow</h1>
        <div class="tagline">Automated GST reconciliation — GSTR-2A · Invoice OCR · Payment Matching</div>
    </div>
    <div class="header-badge">India GST Suite</div>
</div>
""", unsafe_allow_html=True)


# ── Helper ────────────────────────────────────────────────────────────────
def save_upload(f, suffix, max_mb):
    if f.size / (1024 * 1024) > max_mb:
        raise ValidationError(f"'{f.name}' exceeds {max_mb} MB limit.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(f.read()); tmp.close()
    return tmp.name


# ── Tabs ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔄  GSTR-2A Reconciliation",
    "🧾  Invoice OCR Parser",
    "💳  Payment Reconciliation",
])


# ════════════════════════════════════════════════════════════════════════
#  TAB 1 — GSTR-2A Reconciliation
# ════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("""
    <div class="section-header">
        <h2>GSTR-2A vs Purchase Register</h2>
        <p>Find ITC at risk, amount mismatches, and invoices not in your books — in seconds.</p>
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
                    st.error(f"🔴 **Action Required:** {s['missing_in_gstr2a']} supplier(s) haven't filed — **₹{s['itc_at_risk']:,.0f} ITC at risk.** Chase them before GSTR-3B deadline.")
                elif s["amount_mismatch"] > 0:
                    st.warning(f"⚠️ **Review Needed:** {s['amount_mismatch']} invoice(s) have amount differences.")
                else:
                    st.success("✅ All clean — no ITC at risk, no mismatches.")

                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Invoices",    s["total_pr"])
                m2.metric("✅ Matched Clean",  s["matched_clean"])
                m3.metric("⚠️ Mismatch",       s["amount_mismatch"])
                m4.metric("🔴 Missing",        s["missing_in_gstr2a"])
                m5.metric("ITC at Risk (₹)",   f"₹{s['itc_at_risk']:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1.2, 1])
                with ch1:
                    st.plotly_chart(itc_risk_by_vendor(results["missing_in_gstr2a"]), use_container_width=True)
                with ch2:
                    st.plotly_chart(reconciliation_summary_donut(s), use_container_width=True)
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

            except ValidationError as e:
                st.error(f"⚠️ {e}")
            except Exception:
                st.error("Unexpected error — check your file format and try again.")
            finally:
                for p in [pr_path, g2a_path]:
                    if p and os.path.exists(p): os.unlink(p)
    else:
        st.info("📂 Upload both files above to begin reconciliation.")
        with st.expander("📋 Expected file formats"):
            cc1, cc2 = st.columns(2)
            cc1.markdown("**Purchase Register**\n\nColumns: `supplier_gstin` · `invoice_number` · `invoice_date` · `taxable_amount` · `igst` · `cgst` · `sgst`")
            cc2.markdown("**GSTR-2A**\n\nColumns: `supplier_gstin` · `invoice_number` · `invoice_date` · `taxable_amount` · `igst` · `cgst` · `sgst`")


# ════════════════════════════════════════════════════════════════════════
#  TAB 2 — Invoice OCR Parser
# ════════════════════════════════════════════════════════════════════════
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
                        st.warning(f"⚠️ {len(low_conf)} invoice(s) need manual verification: {', '.join(low_conf['file'].tolist())}")
                    else:
                        st.success(f"✅ All {len(df)} invoices extracted with high confidence.")

                if "confidence" in df.columns:
                    high = (df["confidence"] == "high").sum()
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("📄 Processed",       len(df))
                    m2.metric("✅ High Confidence", int(high))
                    m3.metric("⚠️ Low/Partial",      int(len(df) - high))
                    total_taxable = df["taxable_amount"].sum() if "taxable_amount" in df.columns else 0
                    m4.metric("Total Taxable (₹)",  f"₹{total_taxable:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1, 1.6])
                with ch1:
                    st.plotly_chart(ocr_confidence_chart(df), use_container_width=True)
                with ch2:
                    st.dataframe(ocr_amount_table(df), use_container_width=True, height=280)

                with open(report, "rb") as f:
                    st.download_button("📥 Download Extracted Data (.xlsx)", data=f,
                        file_name=os.path.basename(report),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

            except ValidationError as e:
                st.error(f"⚠️ {e}")
            except Exception:
                st.error("Unexpected error — check your PDF files.")
            finally:
                if tmp_dir and os.path.exists(tmp_dir):
                    shutil.rmtree(tmp_dir, ignore_errors=True)
    else:
        st.info("📎 Upload one or more PDF invoices to begin extraction.")
        st.caption("💡 Text-based PDFs work best. Scanned PDFs need OCR pre-processing.")


# ════════════════════════════════════════════════════════════════════════
#  TAB 3 — Payment Reconciliation
# ════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("""
    <div class="section-header">
        <h2>GST Payment Reconciliation</h2>
        <p>Match bank payments against GSTR-3B liability. Find unpaid, late, and underpaid entries.</p>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    bank_file = c1.file_uploader(f"🏦 Bank Statement (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="bank")
    liab_file = c2.file_uploader(f"📋 GST Liability / GSTR-3B (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="liab")

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
                    st.error(f"🔴 **Immediate Action:** {s['unpaid']} liability(s) unpaid — **₹{s['outstanding']:,.0f} outstanding.** Late filing attracts ₹50/day penalty.")
                elif s["late_payments"] > 0:
                    st.warning(f"⏰ {s['late_payments']} payment(s) after due date. Verify if 18% p.a. interest was paid.")
                else:
                    st.success("✅ All GST payments matched and on time.")

                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total Liabilities", s["total_liabilities"])
                m2.metric("✅ Matched",         s["matched"])
                m3.metric("🔴 Unpaid",          s["unpaid"])
                m4.metric("⚠️ Underpaid",       s["underpaid"])
                m5.metric("⏰ Late",            s["late_payments"])
                m6.metric("Outstanding (₹)",    f"₹{s['outstanding']:,.0f}")

                st.divider()
                ch1, ch2 = st.columns([1.8, 1])
                with ch1:
                    st.plotly_chart(payment_status_chart(results["reconciliation"]), use_container_width=True)
                with ch2:
                    st.plotly_chart(payment_status_donut(s), use_container_width=True)
                st.dataframe(results["reconciliation"], use_container_width=True)

                with open(report, "rb") as f:
                    st.download_button("📥 Download Full Report (.xlsx)", data=f,
                        file_name=os.path.basename(report),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

            except ValidationError as e:
                st.error(f"⚠️ {e}")
            except Exception:
                st.error("Unexpected error — check your file format.")
            finally:
                for p in [bank_path, liab_path]:
                    if p and os.path.exists(p): os.unlink(p)
    else:
        st.info("📂 Upload bank statement and GST liability file to begin matching.")
        with st.expander("📋 Bank Statement format"):
            st.markdown("Columns: `date` · `description` · `debit` · `credit`")
        with st.expander("📋 GST Liability format"):
            st.markdown("Columns: `period` · `tax_type` · `liability_amount` · `due_date`")


# ── Footer ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
    GST AutoFlow v2.0 &nbsp;·&nbsp; Built by 
    <a href="https://sudheer-029.github.io" target="_blank">Sudheer Bishnoi</a>
    &nbsp;·&nbsp; Data is processed in-memory and never stored.
    &nbsp;·&nbsp; <a href="https://github.com/Sudheer-029/gst-autoflow" target="_blank">GitHub</a>
</div>
""", unsafe_allow_html=True)
