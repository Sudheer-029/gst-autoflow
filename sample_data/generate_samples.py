"""
Generate realistic sample data for GST reconciliation testing.
Creates purchase_register.xlsx and gstr2a.xlsx with intentional mismatches.
"""
import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

VENDORS = [
    ("Apex Traders", "27AABCT1234A1Z5"),
    ("Blue Star Supplies", "29AABCB5678B1Z3"),
    ("Crown Enterprises", "06AABCC9012C1Z1"),
    ("Delta Industries", "33AABCD3456D1Z9"),
    ("Eagle Exports", "24AABCE7890E1Z7"),
    ("Fortune Goods", "07AABCF1234F1Z4"),
    ("Galaxy Traders", "19AABCG5678G1Z2"),
    ("Horizon Suppliers", "36AABCH9012H1Z0"),
]

def random_date(start="2024-04-01", end="2024-06-30"):
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    delta = end_dt - start_dt
    return (start_dt + timedelta(days=random.randint(0, delta.days))).strftime("%d-%m-%Y")

def gst_split(taxable, rate=18, interstate=False):
    gst = round(taxable * rate / 100, 2)
    if interstate:
        return gst, 0.0, 0.0        # IGST, CGST, SGST
    half = round(gst / 2, 2)
    return 0.0, half, half

def make_invoice_no(vendor_idx, inv_idx):
    return f"INV-{vendor_idx+1:02d}-{inv_idx+1:04d}"

# --- Build base invoice pool ---
invoices = []
for v_idx, (name, gstin) in enumerate(VENDORS):
    n = random.randint(4, 8)
    for i in range(n):
        taxable = round(random.uniform(5000, 80000), 2)
        interstate = gstin[:2] != "27"  # simplified: non-MH = interstate
        igst, cgst, sgst = gst_split(taxable, rate=random.choice([5, 12, 18]), interstate=interstate)
        total = round(taxable + igst + cgst + sgst, 2)
        invoices.append({
            "vendor_name": name,
            "gstin": gstin,
            "invoice_no": make_invoice_no(v_idx, i),
            "invoice_date": random_date(),
            "taxable_amount": taxable,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst,
            "total": total,
        })

# --- Purchase Register: all invoices ---
pr_df = pd.DataFrame(invoices)

# Introduce 3 types of issues for realism:
# 1. Two invoices MISSING from GSTR-2A (supplier didn't file)
missing_in_gstr2a = random.sample(range(len(invoices)), 3)

# 2. Three invoices with AMOUNT MISMATCH in GSTR-2A
mismatch_idxs = random.sample(
    [i for i in range(len(invoices)) if i not in missing_in_gstr2a], 3
)

# 3. Two invoices in GSTR-2A but NOT in purchase register (client missed booking)
extra_gstin = VENDORS[0][1]
extra_invoices = [
    {
        "vendor_name": VENDORS[0][0], "gstin": extra_gstin,
        "invoice_no": "INV-01-9901", "invoice_date": random_date(),
        "taxable_amount": 12000.0, "igst": 2160.0, "cgst": 0.0, "sgst": 0.0,
        "total": 14160.0,
    },
    {
        "vendor_name": VENDORS[1][0], "gstin": VENDORS[1][1],
        "invoice_no": "INV-02-9902", "invoice_date": random_date(),
        "taxable_amount": 9500.0, "igst": 0.0, "cgst": 855.0, "sgst": 855.0,
        "total": 11210.0,
    },
]

# --- GSTR-2A: invoices minus missing, with mismatches, plus extras ---
gstr2a_rows = []
for idx, inv in enumerate(invoices):
    if idx in missing_in_gstr2a:
        continue
    row = inv.copy()
    if idx in mismatch_idxs:
        # Slightly different taxable amount (supplier filed different value)
        row["taxable_amount"] = round(row["taxable_amount"] + random.choice([-500, 500, -1000, 1000]), 2)
        total_gst = row["igst"] + row["cgst"] + row["sgst"]
        row["total"] = round(row["taxable_amount"] + total_gst, 2)
    gstr2a_rows.append(row)

gstr2a_rows.extend(extra_invoices)
gstr2a_df = pd.DataFrame(gstr2a_rows)

# Save both files
pr_df.to_excel("sample_data/purchase_register.xlsx", index=False)
gstr2a_df.to_excel("sample_data/gstr2a.xlsx", index=False)

print(f"Purchase Register: {len(pr_df)} invoices")
print(f"GSTR-2A:           {len(gstr2a_df)} invoices")
print(f"Missing in GSTR-2A (supplier didn't file): {len(missing_in_gstr2a)}")
print(f"Amount mismatches: {len(mismatch_idxs)}")
print(f"Extra in GSTR-2A (not in your books): {len(extra_invoices)}")
print("\nSample data saved to sample_data/")
