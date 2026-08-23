import sqlite3
import pandas as pd
import os
import json
import re

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
input_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Sample Dataset - Input.csv"
expected_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
enriched_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\enriched_products_fixed.csv"

print("==================================================")
print("ITEM 1: INPUT FILES & GROUND TRUTH PART_NUMBER ANALYSIS")
print("==================================================")

files_to_check = {
    "Input CSV": input_csv,
    "Expected Output CSV": expected_csv,
    "Enriched Products Fixed CSV": enriched_csv
}

for name, path in files_to_check.items():
    if os.path.exists(path):
        df = pd.read_csv(path)
        print(f"\n--- {name} ({len(df)} rows) ---")
        print("Columns:", list(df.columns))
        pn_cols = [c for c in df.columns if "part" in c.lower() or "mpn" in c.lower() or "num" in c.lower()]
        print("Part number related columns:", pn_cols)
        for col in pn_cols:
            sample_vals = df[col].dropna().head(5).tolist()
            null_count = df[col].isnull().sum()
            blank_count = (df[col].astype(str).str.strip() == "").sum()
            print(f"  Column '{col}': Nulls={null_count}, Blanks={blank_count}, Samples={sample_vals}")

print("\n==================================================")
print("ITEM 2: SAMPLE 10 PRODUCTS GENERATED DESCRIPTIONS")
print("==================================================")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

sample_prods = cursor.execute("SELECT id, mfg_part_num, part_desc, e1_brand, resolved_brand, part_manuf, resolved_manufacturer, invoice_desc, mobile_desc, short_desc, long_desc, classpath FROM products LIMIT 10").fetchall()

for i, p in enumerate(sample_prods, 1):
    print(f"\nProduct #{i} (ID: {p['id']}, MPN: {p['mfg_part_num']})")
    print(f"  Raw Part_Desc: {repr(p['part_desc'])}")
    print(f"  Brand/Mfr: {repr(p['resolved_brand'])} / {repr(p['resolved_manufacturer'])}")
    print(f"  Classpath: {repr(p['classpath'])}")
    print(f"  INVOICE_DESC ({len(str(p['invoice_desc']))} chars): {repr(p['invoice_desc'])}")
    print(f"  MOBILE_DESC ({len(str(p['mobile_desc']))} chars): {repr(p['mobile_desc'])}")
    print(f"  SHORT_DESC ({len(str(p['short_desc']))} chars): {repr(p['short_desc'])}")
    print(f"  LONG_DESC ({len(str(p['long_desc']))} chars): {repr(p['long_desc'])}")

print("\n==================================================")
print("ITEM 3: CLASSPATH TRAILING SPACE INCONSISTENCY ANALYSIS")
print("==================================================")

all_classpaths = cursor.execute("SELECT classpath, COUNT(*) as cnt FROM products GROUP BY classpath").fetchall()

trailing_space_cp = []
for row in all_classpaths:
    cp = row['classpath'] or ""
    cnt = row['cnt']
    has_trailing = cp != cp.strip()
    parts = cp.split(">")
    has_part_trailing = any(p != p.strip() for p in parts)
    if has_trailing or has_part_trailing:
        trailing_space_cp.append((cp, cnt, has_trailing, has_part_trailing))

print(f"Total distinct Classpaths in output: {len(all_classpaths)}")
print(f"Distinct Classpaths with leading/trailing whitespace: {len(trailing_space_cp)}")
for cp, cnt, ht, hpt in trailing_space_cp[:15]:
    print(f"  - Repr: {repr(cp)} | Count: {cnt} | Outer Space: {ht} | Node Space: {hpt}")

print("\n==================================================")
print("ITEM 4: ATTRIBUTE COVERAGE GAP ANALYSIS")
print("==================================================")

total_prods = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]

attr_counts = cursor.execute("""
    SELECT p.id, p.classpath, COUNT(a.id) as attr_cnt 
    FROM products p 
    LEFT JOIN attributes a ON p.id = a.product_id 
    GROUP BY p.id
""").fetchall()

with_attrs = [r for r in attr_counts if r['attr_cnt'] > 0]
zero_attrs = [r for r in attr_counts if r['attr_cnt'] == 0]

print(f"Total Products: {total_prods}")
print(f"Products with >=1 Attribute: {len(with_attrs)} ({len(with_attrs)/total_prods*100:.1f}%)")
print(f"Products with 0 Attributes: {len(zero_attrs)} ({len(zero_attrs)/total_prods*100:.1f}%)")

# Group zero-attribute products by full classpath
zero_df = pd.DataFrame([{"id": r["id"], "classpath": r["classpath"] or "UNKNOWN"} for r in zero_attrs])
cp_counts = zero_df['classpath'].value_counts().head(10)

print("\nTop 10 Classpaths in Zero-Attribute Group:")
for cp, count in cp_counts.items():
    top_level = cp.split(">")[0] if ">" in cp else cp
    print(f"  - [{count} rows] Classpath: {repr(cp)} (Top Level: {repr(top_level)})")

conn.close()
