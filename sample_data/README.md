# sample_data — READ BEFORE RUNNING ANYTHING

This directory contains **pre-generated test fixtures** for testers.

## Safe to use (just open or upload)
- `purchase_register.xlsx` — sample purchase register for Module 1
- `gstr2a.xlsx` — sample GSTR-2B/2A file for Module 1
- `bank_statement.xlsx` — sample bank statement for Module 3
- `gst_liability.xlsx` — sample GST liability file for Module 3
- `invoices/` — sample PDF invoices for Module 2

## DO NOT RUN — development scripts only
The following scripts regenerate the test fixtures from scratch.
Running them **will overwrite the canonical sample data** that testers depend on.

- `generate_samples.py` — generates all Excel fixtures
- `generate_invoices.py` — generates PDF invoice samples
- `generate_payment_data.py` — generates payment/bank data

These are dev tooling. If you accidentally ran one, restore from git:

```
git checkout -- sample_data/
```
