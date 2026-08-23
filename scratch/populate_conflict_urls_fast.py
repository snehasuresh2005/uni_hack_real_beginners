import sqlite3
import sys

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.mfr_url_resolver import resolve_product_urls

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

flagged = cursor.execute("SELECT id, part_manuf, resolved_brand, mfg_part_num, part_desc FROM products WHERE status = 'flagged_hitl' OR id IN (SELECT product_id FROM conflicts)").fetchall()
print(f"Populating URLs for {len(flagged)} flagged conflict products in database...")

updated_count = 0
found_count = 0

for p in flagged:
    res = resolve_product_urls(
        part_manuf=p["part_manuf"],
        resolved_brand=p["resolved_brand"],
        mfg_part_num=p["mfg_part_num"],
        part_desc=p["part_desc"],
        cursor=cursor
    )
    mfr_url = res.get("mfr_url", "")
    ref_urls = res.get("ref_urls", [])
    
    r1 = ref_urls[0] if len(ref_urls) > 0 else ""
    r2 = ref_urls[1] if len(ref_urls) > 1 else ""
    r3 = ref_urls[2] if len(ref_urls) > 2 else ""
    r4 = ref_urls[3] if len(ref_urls) > 3 else ""
    r5 = ref_urls[4] if len(ref_urls) > 4 else ""
    
    cursor.execute("""
        UPDATE products 
        SET mfr_url = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?
        WHERE id = ?
    """, (mfr_url, r1, r2, r3, r4, r5, p["id"]))
    
    updated_count += 1
    if mfr_url:
        found_count += 1
    conn.commit()

# Print sample updated flagged products
samples = cursor.execute("SELECT id, mfg_part_num, resolved_brand, mfr_url, ref_url_1 FROM products WHERE status = 'flagged_hitl' LIMIT 10").fetchall()
conn.close()

print(f"\nSuccessfully populated URLs for {updated_count} flagged conflict items ({found_count} verified URLs found)!\n")
for s in samples:
    print(f"Product #{s['id']} [{s['resolved_brand']} / MPN: {s['mfg_part_num']}]:")
    print(f"  MFR URL : '{s['mfr_url']}'")
    print(f"  Ref PDF : '{s['ref_url_1']}'\n")
