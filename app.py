"""
GST AutoFlow — Unified 3-Module App with Dashboard
Security: file size limits, ValidationError handling, finally cleanup.
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

MAX_EXCEL_MB = 5
MAX_PDF_MB   = 10

st.set_page_config(page_title="GST AutoFlow", page_icon="📊", layout="wide")

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 GST AutoFlow")
    st.caption("Know your GST health before your CA does.")
    st.divider()
    st.markdown("""
**Modules**
- 🔄 GSTR-2A Reconciliation
- 🧾 Invoice OCR Parser
- 💳 Payment Reconciliation
    """)
    st.divider()
    st.caption(f"Excel ≤ {MAX_EXCEL_MB} MB · PDF ≤ {MAX_PDF_MB} MB")
    st.caption("v1.2 · by Sudheer Bishnoi")


# ── Helper ────────────────────────────────────────────────────────────────
def save_upload(f, suffix, max_mb):
    if f.size / (1024 * 1024) > max_mb:
        raise ValidationError(f"'{f.name}' exceeds {max_mb} MB limit.")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(f.read()); tmp.close()
    return tmp.name


# ── Tabs ──────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔄 GSTR-2A Reconciliation",
    "🧾 Invoice OCR Parser",
    "💳 Payment Reconciliation",
])


# ════════════════════════════════════════════════════════════════════════
#  TAB 1 — GSTR-2A Reconciliation + Dashboard
# ════════════════════════════════════════════════════════════════════════
with tab1:
    st.header("GSTR-2A vs Purchase Register")
    st.caption("Find ITC at risk, amount mismatches, and invoices not in your books — in seconds.")
    st.divider()

    c1, c2 = st.columns(2)
    pr_file  = c1.file_uploader(f"📁 Purchase Register (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="pr")
    g2a_file = c2.file_uploader(f"📁 GSTR-2A (.xlsx ≤{MAX_EXCEL_MB}MB)",           type=["xlsx"], key="g2a")

    if pr_file and g2a_file:
        if st.button("🔄 Run Reconciliation", type="primary", use_container_width=True):
            pr_path = g2a_path = None
            try:
                with st.spinner("Reconciling..."):
                    pr_path  = save_upload(pr_file,  ".xlsx", MAX_EXCEL_MB)
                    g2a_path = save_upload(g2a_file, ".xlsx", MAX_EXCEL_MB)
                    results  = reconcile(pr_path, g2a_path)
                    report   = generate_report(results)

                s = results["summary"]

                # ── Action Alert ──────────────────────────────────────
                if s["missing_in_gstr2a"] > 0:
                    st.error(
                        f"🔴 **Action Required:** {s['missing_in_gstr2a']} supplier(s) "
                        f"haven't filed — **₹{s['itc_at_risk']:,.0f} ITC at risk.** "
                        f"Chase them before GSTR-3B deadline."
                    )
                elif s["amount_mismatch"] > 0:
                    st.warning(
                        f"⚠️ **Review Needed:** {s['amount_mismatch']} invoice(s) "
                        f"have amount differences between your books and GSTR-2A."
                    )
                else:
                    st.success("✅ All clean — no ITC at risk, no mismatches.")

                # ── Metrics row ───────────────────────────────────────
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Total Invoices (PR)",   s["total_pr"])
                m2.metric("✅ Matched Clean",       s["matched_clean"])
                m3.metric("⚠️ Amount Mismatch",     s["amount_mismatch"])
                m4.metric("🔴 Missing in GSTR-2A",  s["missing_in_gstr2a"])
                m5.metric("🔴 ITC at Risk (₹)",     f"₹{s['itc_at_risk']:,.0f}")

                st.divider()

                # ── Charts ────────────────────────────────────────────
                ch1, ch2 = st.columns([1.2, 1])
                with ch1:
                    st.plotly_chart(
                        itc_risk_by_vendor(results["missing_in_gstr2a"]),
                        use_container_width=True
                    )
                with ch2:
                    st.plotly_chart(
                        reconciliation_summary_donut(s),
                        use_container_width=True
                    )

                st.plotly_chart(
                    mismatch_detail_bar(results["amount_mismatch"]),
                    use_container_width=True
                )

                # ── Download + Preview ────────────────────────────────
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
        st.info("Upload both files to begin.")


# ════════════════════════════════════════════════════════════════════════
#  TAB 2 — Invoice OCR Parser + Dashboard
# ════════════════════════════════════════════════════════════════════════
with tab2:
    st.header("Invoice OCR Parser")
    st.caption("Upload vendor invoices (PDF). Extract GSTIN, invoice number, dates, and amounts automatically.")
    st.divider()

    uploaded_pdfs = st.file_uploader(
        f"📎 Upload PDF Invoices (multiple, ≤{MAX_PDF_MB} MB each)",
        type=["pdf"], accept_multiple_files=True, key="pdfs"
    )

    if uploaded_pdfs:
        if st.button("🧾 Extract Invoice Data", type="primary", use_container_width=True):
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

                # ── Action Alert ──────────────────────────────────────
                if "confidence" in df.columns:
                    low_conf = df[df["confidence"].isin(["low", "partial"])]
                    if not low_conf.empty:
                        st.warning(
                            f"⚠️ {len(low_conf)} invoice(s) extracted with low/partial confidence. "
                            f"Verify these manually: {', '.join(low_conf['file'].tolist())}"
                        )
                    else:
                        st.success(f"✅ All {len(df)} invoices extracted with high confidence.")

                # ── Metrics ───────────────────────────────────────────
                if "confidence" in df.columns:
                    high = (df["confidence"] == "high").sum()
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("📄 Invoices Processed", len(df))
                    m2.metric("✅ High Confidence",    int(high))
                    m3.metric("⚠️ Low/Partial",         int(len(df) - high))
                    total_taxable = df["taxable_amount"].sum() if "taxable_amount" in df.columns else 0
                    m4.metric("Total Taxable Value (₹)", f"₹{total_taxable:,.0f}")

                st.divider()

                # ── Charts ────────────────────────────────────────────
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
        st.info("Upload one or more PDF invoices to begin.")
        st.caption("💡 Text-based PDFs work best. Scanned PDFs need Tesseract installed.")


# ════════════════════════════════════════════════════════════════════════
#  TAB 3 — Payment Reconciliation + Dashboard
# ════════════════════════════════════════════════════════════════════════
with tab3:
    st.header("GST Payment Reconciliation")
    st.caption("Match bank payments against GSTR-3B liability. Find unpaid, late, and underpaid entries.")
    st.divider()

    c1, c2 = st.columns(2)
    bank_file = c1.file_uploader(f"🏦 Bank Statement (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="bank")
    liab_file = c2.file_uploader(f"📋 GST Liability / GSTR-3B (.xlsx ≤{MAX_EXCEL_MB}MB)", type=["xlsx"], key="liab")

    if bank_file and liab_file:
        if st.button("💳 Run Payment Reconciliation", type="primary", use_container_width=True):
            bank_path = liab_path = None
            try:
                with st.spinner("Matching payments..."):
                    bank_path = save_upload(bank_file, ".xlsx", MAX_EXCEL_MB)
                    liab_path = save_upload(liab_file, ".xlsx", MAX_EXCEL_MB)
                    results   = reconcile_payments(bank_path, liab_path)
                    report    = generate_payment_report(results)

                s = results["summary"]

                # ── Action Alert ──────────────────────────────────────
                if s["unpaid"] > 0:
                    st.error(
                        f"🔴 **Immediate Action:** {s['unpaid']} GST liability(s) unpaid — "
                        f"**₹{s['outstanding']:,.0f} outstanding.** Late filing attracts ₹50/day penalty."
                    )
                elif s["late_payments"] > 0:
                    st.warning(
                        f"⏰ {s['late_payments']} payment(s) were made after the due date. "
                        f"Verify if interest (18% p.a.) was paid."
                    )
                else:
                    st.success("✅ All GST payments matched and on time.")

                # ── Metrics ───────────────────────────────────────────
                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Total Liabilities",   s["total_liabilities"])
                m2.metric("✅ Matched",           s["matched"])
                m3.metric("🔴 Unpaid",            s["unpaid"])
                m4.metric("⚠️ Underpaid",         s["underpaid"])
                m5.metric("⏰ Late",              s["late_payments"])
                m6.metric("Outstanding (₹)",      f"₹{s['outstanding']:,.0f}")

                st.divider()

                # ── Charts ────────────────────────────────────────────
                ch1, ch2 = st.columns([1.8, 1])
                with ch1:
                    st.plotly_chart(
                        payment_status_chart(results["reconciliation"]),
                        use_container_width=True
                    )
                with ch2:
                    st.plotly_chart(
                        payment_status_donut(s),
                        use_container_width=True
                    )

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
        st.info("Upload bank statement and GST liability file to begin.")
        with st.expander("📋 Bank Statement format"):
            st.markdown("Columns: `date` · `description` · `debit` · `credit`")
        with st.expander("📋 GST Liability format"):
            st.markdown("Columns: `period` · `tax_type` · `liability_amount` · `due_date`")
