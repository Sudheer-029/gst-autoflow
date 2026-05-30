# GST AutoFlow

> Free, open-source GST reconciliation toolkit for Indian small businesses.

A focused Streamlit app that automates three of the most painful, time-consuming
GST workflows. No signup, no CA fees, no manual spreadsheets. Files are
processed in memory and never stored.

> **Important.** GST AutoFlow is a free utility, not certified accounting
> software. Always verify results with a qualified CA before filing returns.

## Why this exists

Small business owners in India spend hours every month reconciling GSTR-2A,
matching bank entries, and chasing suppliers who haven't filed. Existing
solutions are either expensive enterprise software or generic Excel templates.
This tool sits in the middle: free, focused, and built for the way Indian SMBs
actually work.

## What it does

| Module | Purpose |
| --- | --- |
| **GSTR-2A reconciliation** | Compare a purchase register against GSTR-2A. Identify ITC at risk, amount mismatches, and invoices not filed by suppliers. |
| **Invoice OCR** | Extract GSTIN, invoice number, date, and amounts from vendor PDF invoices. |
| **Payment reconciliation** | Match a bank statement against GSTR-3B liability. Find unpaid, late, and underpaid entries. |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`), click
**Open the toolkit**, and start uploading files. The `sample_data/` folder
has anonymised test files for every module.

## Roadmap

The current release focuses on file-upload workflows. Connectors to existing
SMB tools are next:

- Tally Prime export parser (Day Book / Voucher Register Excel)
- ERPNext / Frappe live connector (REST API + API key)
- Zoho Books connector (OAuth)
- Wider bank statement format coverage (HDFC, ICICI, SBI, Axis, Kotak)
- Hindi UI option
- Mobile-responsive layout
- Saved column mappings (browser local storage)

User accounts, persistence, and a dashboard come later — once we understand
what people actually use.

## Privacy

- Files are processed in memory and discarded when the request finishes
- Nothing is written to a database; there is no database
- No cookies that identify you
- Optional anonymous usage telemetry (disabled by default; see below)

### Optional telemetry

The app can send anonymous usage events (which module ran, how many invoices,
how long it took — never file content) to help understand what's used and
what's broken. Disabled unless explicitly enabled:

```bash
export GST_AUTOFLOW_TELEMETRY=1
export GST_AUTOFLOW_TELEMETRY_URL=https://your-collector.example/events
```

Self-hosted instances default to telemetry off. You stay in control.

## Project layout

```
gst-autoflow/
├── app.py                    # Streamlit entry point and UI
├── gst_autoflow/             # Reusable reconciliation library
│   ├── reconciler.py         # GSTR-2A vs Purchase Register
│   ├── ocr_parser.py         # PDF invoice extraction
│   ├── payment_recon.py      # Bank vs GSTR-3B liability
│   ├── bank_parser.py        # Bank statement parsing
│   ├── column_mapper.py      # Fuzzy column-name mapping
│   ├── dashboard.py          # Plotly chart helpers
│   ├── report.py             # Excel report writers
│   ├── validators.py         # Input validation + size limits
│   ├── telemetry.py          # Anonymous, opt-in usage events
│   └── ocr_patterns.py       # Field-extraction regexes
├── sample_data/              # Anonymised test data + invoice PDFs
├── .streamlit/
│   ├── config.toml           # Theme + server settings
│   └── styles.css            # App stylesheet
├── requirements.txt
├── LICENSE
└── README.md
```

## Tech stack

- **Streamlit** — UI framework
- **pandas** — data processing
- **pdfplumber** + **Pillow** — PDF text extraction
- **plotly** — interactive charts
- **openpyxl** / **xlsxwriter** — Excel I/O

## Contributing

Issues and PRs welcome. If you run a small business in India and have a
reconciliation pain point this app doesn't solve, open an issue with a
description and (if possible) a sanitised sample file. Real-world cases
shape the roadmap.

## License

[MIT](LICENSE) © 2026 Sudheer Bishnoi

## Author

Built by Sudheer Bishnoi.
[LinkedIn](https://www.linkedin.com/in/sudheer-bishnoi) ·
[Portfolio](https://sudheer-029.github.io)
