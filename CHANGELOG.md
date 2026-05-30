# Changelog

All notable changes to GST AutoFlow are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- `GST_SESSION_DIR` env var for configurable session persistence path
- `extraction_status: ok | partial` field in OCR parser output
- Unit tests: `test_reconciler.py` (7), `test_payment_recon.py` (6), `test_ocr_parser.py` (5)

### Changed
- Download filenames now include date and mode: `GST_ITC_Recon_{mode}_{YYYYMMDD}.xlsx`, `Invoice_OCR_{YYYYMMDD}.xlsx`, `Payment_Recon_{YYYYMMDD}.xlsx`
- All six `st.metric()` cards now show contextual delta (% of total / rate)
- Error banner no longer exposes raw exception type to users; technical details in collapsible expander
- Workflow progress bar uses `st.status()` — step 2 now visible during processing

---

## [0.3.0] — 2026-05-28

### Added
- Column preview widget: shows matched/missing columns before running reconciliation (#5)
- Illustrated empty states with SVG icons in all three modules (#8)
- "Next steps" card after each successful reconciliation (#20)
- Recent activity strip on landing page when session history exists (#9)
- Social proof strip (open source · zero data retention · no account needed) (#7)
- `render_error()` helper with pre-filled GitHub issue link on uncaught exceptions (#2)

### Changed
- Plotly charts: `displayModeBar: false` on all six charts — cleaner UI (#6)
- Topbar monogram replaced with ₹ symbol — finance-domain signal (#1)
- `sample_data/README.md` notes dev-only status to avoid confusing end users

### Fixed
- Payment recon: `⚠️ Underpaid` / `⚠️ Overpaid` statuses were unreachable dead code
  — now picks closest-amount candidate via `idxmin()` among description-matched rows
- `RE_INV_NO` regex: `(?:no|number)` made required for `tax invoice` / `challan` branches
  — prevented header words from being captured as invoice numbers
- Cached `_show_column_preview` by MD5 to avoid redundant re-computation on re-renders

---

## [0.2.0] — 2026-05-15

### Added
- Module 3: Payment Reconciliation (GSTR-3B liability vs. bank statement)
- Session persistence via URL query param `?s=<id>`
- Sidebar sample file downloads in all three modules
- Disclaimer banner on landing page

### Changed
- GSTIN validation runs on uploaded purchase register and flags malformed entries
- `TOLERANCE = 10.0` paise for reconciler; `TOLERANCE = 1.0` for payment recon

---

## [0.1.0] — 2026-05-01

### Added
- Module 1: GSTR-2A / 2B Reconciliation
- Module 2: Invoice OCR Parser (text-based PDFs via pdfplumber)
- Streamlit multi-tab UI with sticky topbar and custom CSS design system
- Plotly charts: donut summary, horizontal bar by vendor, stacked bar by month, scatter
- Excel report generation with colour-coded sheets
- Column auto-mapping for common Tally / Zoho Books / SAP export formats
