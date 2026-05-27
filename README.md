# GST AutoFlow 📊

> Know your GST health before your CA does.

A free, open-source Streamlit app for Indian businesses to automate GST reconciliation — no CA fees, no manual spreadsheets.

## Features

| Module | What it does |
|---|---|
| 🔄 **GSTR-2A Reconciliation** | Upload Purchase Register + GSTR-2A → instantly find ITC at risk, amount mismatches, and unfiled suppliers |
| 🧾 **Invoice OCR Parser** | Upload vendor PDF invoices → extract GSTIN, invoice numbers, dates, amounts automatically |
| 💳 **Payment Reconciliation** | Match bank payments against GSTR-3B liability → find unpaid, late, and underpaid entries |

## Live Demo

👉 **[Launch App](https://gst-autoflow.streamlit.app)**

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Sample Data

`sample_data/` contains ready-to-use test files:
- `gstr2a.xlsx` — sample GSTR-2A download
- `purchase_register.xlsx` — sample purchase register
- `bank_statement.xlsx` — sample bank transactions
- `gst_liability.xlsx` — sample GSTR-3B liability

## Tech Stack

- **Streamlit** — UI
- **pdfplumber** — PDF text extraction
- **pandas** — data processing
- **plotly** — interactive charts
- **openpyxl / xlsxwriter** — Excel I/O

## Built by

Sudheer Bishnoi — [LinkedIn](https://www.linkedin.com/in/sudheer-bishnoi) · [Portfolio](https://sudheer-029.github.io)
