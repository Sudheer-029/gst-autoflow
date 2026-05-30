# GST AutoFlow

**Recover your blocked ITC in minutes, not hours.**

GST AutoFlow automates the three reconciliation tasks Indian SMBs waste the most time on every month: matching GSTR-2A/2B against your purchase register, extracting structured data from vendor PDF invoices, and reconciling bank payments against GSTR-3B liability.

No signup. No CA fees. Your files are processed in memory and never stored.

## What it does

| Module | What you get |
| --- | --- |
| **GSTR-2A / 2B Reconciliation** | See exactly which suppliers haven't filed, how much ITC is at risk, and where amounts mismatch — in one colour-coded Excel report. |
| **Invoice OCR Parser** | Drop in vendor PDFs. Get GSTIN, invoice number, date, and tax amounts extracted automatically, with low-confidence rows flagged for manual review. |
| **Payment Reconciliation** | Match your bank statement against GSTR-3B liability. Spot unpaid, late, and underpaid entries before the department does. |

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`). Sample files for every module are in `sample_data/` — use the **Download template** buttons inside each module to get them directly.

## Privacy

- Files are processed in memory and discarded when processing completes
- Nothing is written to a database; there is no database
- No cookies that identify you
- Optional anonymous usage telemetry (disabled by default; see below)

> **Session note:** Reconciliation results are cached in the current browser session only. If you close the tab or restart the server, results are gone. Download your Excel report immediately — it is your only persistent copy.

### Optional telemetry

The app can send anonymous usage events (which module ran, how many invoices — never file content). Disabled unless explicitly enabled:

```bash
export GST_AUTOFLOW_TELEMETRY=1
export GST_AUTOFLOW_TELEMETRY_URL=https://your-collector.example/events
```

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
- **openpyxl** — Excel I/O

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

The test suite covers reconciler.py: tolerance matching, GSTIN normalisation, ITC-at-risk calculation, and claimable ITC boundary conditions.

## Multi-tester Deployment Note

Session data is stored in `~/.gst_autoflow/sessions/` on the host running Streamlit. If multiple internal testers access the same deployed server, each tester gets a unique session ID (stored in the URL as `?s=<id>`) — sessions do not cross-contaminate unless someone deliberately shares a URL.

If you are running a shared testing instance, set the `GST_SESSION_DIR` environment variable (once added) or deploy separate instances per tester to avoid the shared filesystem.

## Contributing

Issues and PRs welcome. If you run a small business in India and have a reconciliation pain point this app doesn't solve, open an issue with a description and (if possible) a sanitised sample file.

## License

[MIT](LICENSE) © 2026 Sudheer Bishnoi

Built by [Sudheer Bishnoi](https://sudheer-029.github.io) · [LinkedIn](https://www.linkedin.com/in/sudheer-bishnoi)
