import sqlite3
import pandas as pd
import sys
sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.pipeline import DOMAINS, resolve_taxonomy

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get zero attribute rows
zero_rows = cursor.execute("""
    SELECT p.id, p.mfg_part_num, p.part_desc, p.classpath, p.status
    FROM products p
    LEFT JOIN attributes a ON p.id = a.product_id
    WHERE a.id IS NULL
""").fetchall()

print(f"Total Zero-Attribute Rows: {len(zero_rows)}")

status_counts = pd.Series([r['status'] for r in zero_rows]).value_counts()
print("\nStatus distribution of Zero-Attribute Rows:")
print(status_counts)

# Audit top 10 classpaths in zero attribute group
cp_counts = pd.Series([r['classpath'] for r in zero_rows]).value_counts().head(10)
print("\nTop 10 Classpaths in Zero-Attribute Group:")
for cp, cnt in cp_counts.items():
    print(f"\n--- Classpath: {repr(cp)} ({cnt} rows) ---")
    sample = [r for r in zero_rows if r['classpath'] == cp][:3]
    for s in sample:
        domain_id, cat_name, res_cp = resolve_taxonomy(s['part_desc'])
        dom_attrs = DOMAINS.get(domain_id, {}).get("attributes", [])
        print(f"  ID: {s['id']} | MPN: {s['mfg_part_num']} | Status: {s['status']}")
        print(f"    Desc: {repr(s['part_desc'])}")
        print(f"    Resolved Domain: {domain_id} ({cat_name})")
        print(f"    Target LOV Attributes for Domain: {dom_attrs}")

conn.close()
