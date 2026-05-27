"""
Generate sample bank statement + GST liability data for Module 3 testing.
"""
import pandas as pd

# GST Liability (GSTR-3B) for Q1 FY2024-25
liability_data = [
    {"period": "Apr-2024", "tax_type": "IGST", "liability_amount": 85420.00, "due_date": "20-05-2024"},
    {"period": "Apr-2024", "tax_type": "CGST", "liability_amount": 32150.00, "due_date": "20-05-2024"},
    {"period": "Apr-2024", "tax_type": "SGST", "liability_amount": 32150.00, "due_date": "20-05-2024"},
    {"period": "May-2024", "tax_type": "IGST", "liability_amount": 91200.00, "due_date": "20-06-2024"},
    {"period": "May-2024", "tax_type": "CGST", "liability_amount": 28600.00, "due_date": "20-06-2024"},
    {"period": "May-2024", "tax_type": "SGST", "liability_amount": 28600.00, "due_date": "20-06-2024"},
    {"period": "Jun-2024", "tax_type": "IGST", "liability_amount": 78900.00, "due_date": "20-07-2024"},
    {"period": "Jun-2024", "tax_type": "CGST", "liability_amount": 25400.00, "due_date": "20-07-2024"},
    {"period": "Jun-2024", "tax_type": "SGST", "liability_amount": 25400.00, "due_date": "20-07-2024"},
]

# Bank Statement (intentional issues for demo)
# Apr IGST paid late | May SGST underpaid | Jun IGST completely missed
bank_data = [
    {"date": "15-04-2024", "description": "NEFT Transfer - Vendor Payment Apex",    "debit": 45000.00,  "credit": 0},
    {"date": "18-04-2024", "description": "GST Challan CGST Apr-2024",               "debit": 32150.00,  "credit": 0},
    {"date": "18-04-2024", "description": "GST Challan SGST Apr-2024",               "debit": 32150.00,  "credit": 0},
    {"date": "25-05-2024", "description": "GST Challan IGST Apr-2024 (LATE)",        "debit": 85420.00,  "credit": 0},  # LATE
    {"date": "19-06-2024", "description": "GST Payment IGST May-2024",               "debit": 91200.00,  "credit": 0},
    {"date": "19-06-2024", "description": "GST Payment CGST May-2024",               "debit": 28600.00,  "credit": 0},
    {"date": "19-06-2024", "description": "GST Payment SGST May-2024",               "debit": 26000.00,  "credit": 0},  # UNDERPAID
    {"date": "22-07-2024", "description": "GST Challan CGST Jun-2024",               "debit": 25400.00,  "credit": 0},
    {"date": "22-07-2024", "description": "GST Challan SGST Jun-2024",               "debit": 25400.00,  "credit": 0},
    # Jun IGST missing entirely
    {"date": "30-07-2024", "description": "NEFT Transfer - Salary July",             "debit": 250000.00, "credit": 0},
    {"date": "01-08-2024", "description": "Customer Payment Received",               "debit": 0,         "credit": 185000.00},
]

pd.DataFrame(liability_data).to_excel("sample_data/gst_liability.xlsx", index=False)
pd.DataFrame(bank_data).to_excel("sample_data/bank_statement.xlsx", index=False)

print("GST liability: 9 entries (3 months x 3 tax types)")
print("Bank statement: 11 entries with deliberate issues:")
print("  - Apr IGST: paid LATE (May 25 vs due May 20)")
print("  - May SGST: UNDERPAID (₹26,000 vs ₹28,600)")
print("  - Jun IGST: NOT PAID at all")
print("\nSample payment data saved to sample_data/")
