import sqlite3
import pandas as pd
import json
import re
import sys

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("ITEM 1: PART_NUMBER DATASET AUDIT")
print("==================================================")

input_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Sample Dataset - Input.csv"
df_in = pd.read_csv(input_csv)
print(f"Input CSV File: Unihack_ Sample Dataset - Input.csv ({len(df_in)} rows)")
print("Input Columns:", list(df_in.columns))

gt_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
df_gt = pd.read_csv(gt_csv)
print(f"\nGround Truth CSV: Unihack_ Expected Output - Delivery Format.csv ({len(df_gt)} rows)")
for idx, r in df_gt.iterrows():
    print(f"  Ground Truth Row {idx+1}: PART_NUMBER={r.get('PART_NUMBER')}, Mfg_Part_Num={r.get('Mfg_Part_Num')}, Brand={r.get('BRAND_NAME')}")

# Check if PART_NUMBER exists in SQLite products table
db_cols = [row['name'] for row in cursor.execute("PRAGMA table_info(products)").fetchall()]
print(f"\nSQLite Products Table Columns ({len(db_cols)}):", db_cols)
has_part_num_col = "part_number" in [c.lower() for c in db_cols]
print("Is 'part_number' column present in SQLite schema?:", has_part_num_col)

print("\n==================================================")
print("ITEM 2: DESCRIPTION FIELD COMPLIANCE (10 SAMPLE PRODUCTS)")
print("==================================================")

prods_10 = cursor.execute("""
    SELECT id, mfg_part_num, part_desc, e1_brand, resolved_brand, part_manuf, resolved_manufacturer,
           invoice_desc, mobile_desc, short_desc, long_desc, classpath
    FROM products
    ORDER BY id ASC
    LIMIT 10
""").fetchall()

for i, p in enumerate(prods_10, 1):
    print(f"\nProduct #{i} [ID: {p['id']}, MPN: {p['mfg_part_num']}]")
    print(f"  Raw Part_Desc : {repr(p['part_desc'])}")
    print(f"  Brand / Mfr   : {repr(p['resolved_brand'])} / {repr(p['resolved_manufacturer'])}")
    print(f"  INVOICE_DESC  ({len(str(p['invoice_desc']))} chars): {repr(p['invoice_desc'])}")
    print(f"  MOBILE_DESC   ({len(str(p['mobile_desc']))} chars): {repr(p['mobile_desc'])}")
    print(f"  SHORT_DESC    ({len(str(p['short_desc']))} chars): {repr(p['short_desc'])}")
    print(f"  LONG_DESC     ({len(str(p['long_desc']))} chars): {repr(p['long_desc'])}")

print("\n==================================================")
print("ITEM 3: CLASSPATH TRAILING-SPACE AUDIT")
print("==================================================")

all_cp_rows = cursor.execute("SELECT id, classpath FROM products").fetchall()
trailing_space_records = []
clean_cp_map = {}

for r in all_cp_rows:
    p_id = r['id']
    cp = r['classpath'] or ""
    has_outer_space = cp != cp.strip()
    nodes = cp.split(">")
    has_node_space = any(n != n.strip() for n in nodes)
    if has_outer_space or has_node_space:
        trailing_space_records.append((p_id, cp, has_outer_space, has_node_space))

print(f"Total Products in DB: {len(all_cp_rows)}")
print(f"Total Rows with Classpath Whitespace Anomalies: {len(trailing_space_records)}")

cp_summary = cursor.execute("SELECT classpath, COUNT(*) as cnt FROM products GROUP BY classpath").fetchall()
anomalous_classpaths = []
for row in cp_summary:
    cp = row['classpath'] or ""
    cnt = row['cnt']
    nodes = cp.split(">")
    if cp != cp.strip() or any(n != n.strip() for n in nodes):
        anomalous_classpaths.append((cp, cnt))

print(f"Distinct Classpaths in Output: {len(cp_summary)}")
print(f"Distinct Classpaths with Whitespace Anomalies: {len(anomalous_classpaths)}")
for cp, cnt in anomalous_classpaths:
    clean_cp = ">".join(n.strip() for n in cp.strip().split(">"))
    print(f"  - Raw: {repr(cp)} (Count: {cnt}) -> Clean Equivalent: {repr(clean_cp)}")

print("\n==================================================")
print("ITEM 4: ZERO-ATTRIBUTE BREAKDOWN & LOV COVERAGE AUDIT")
print("==================================================")

# Query zero attribute rows
zero_attr_rows = cursor.execute("""
    SELECT p.id, p.mfg_part_num, p.part_desc, p.classpath
    FROM products p
    LEFT JOIN attributes a ON p.id = a.product_id
    WHERE a.id IS NULL
""").fetchall()

print(f"Total Zero-Attribute Rows: {len(zero_attr_rows)}")

df_zero = pd.DataFrame([{"id": r["id"], "classpath": r["classpath"] or "UNKNOWN"} for r in zero_attr_rows])

# Group by full raw classpath
top10_raw = df_zero['classpath'].value_counts().head(10)
print("\nTop 10 Classpaths in Zero-Attribute Group (Raw):")
for cp, cnt in top10_raw.items():
    clean_cp = ">".join(n.strip() for n in cp.strip().split(">"))
    print(f"  - [{cnt} rows] Raw: {repr(cp)} | Clean: {repr(clean_cp)}")

# Test LOV / Pipeline domain matching for these top 10 zero-attribute classpaths
from backend.pipeline import resolve_taxonomy, DOMAINS

print("\nAuditing LOV / Domain Attribute Coverage for Zero-Attribute Classpaths:")
gen_ind_mismatch_count = 0
unmapped_category_count = 0

for r in zero_attr_rows:
    cp = r['classpath'] or ""
    desc = r['part_desc'] or ""
    dom_id, cat_name, res_cp = resolve_taxonomy(desc)
    
    # Check if domain has attributes defined
    dom_info = DOMAINS.get(dom_id, {})
    has_dom_attrs = len(dom_info.get("attributes", [])) > 0
    
    if dom_id == "other" or not has_dom_attrs:
        unmapped_category_count += 1
    else:
        gen_ind_mismatch_count += 1

print(f"\nZero-Attribute Breakdown ({len(zero_attr_rows)} total rows):")
print(f"  1. Rows belonging to unmapped categories with NO LOV attribute specs ('other' / generic): {unmapped_category_count} rows ({unmapped_category_count/len(zero_attr_rows)*100:.1f}%)")
print(f"  2. Rows belonging to mapped categories with valid LOV specs BUT missed due to fallback/matching/whitespace bugs: {gen_ind_mismatch_count} rows ({gen_ind_mismatch_count/len(zero_attr_rows)*100:.1f}%)")

conn.close()
