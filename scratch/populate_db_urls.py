import sqlite3
import sys
import os

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.mfr_url_resolver import resolve_product_urls

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

products = cursor.execute("SELECT id, part_manuf, resolved_brand, mfg_part_num, part_desc FROM products").fetchall()
print(f"Populating URLs for {len(products)} products in SQLite database...")

updated_count = 0
found_url_count = 0

for p in products:
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
        found_url_count += 1

conn.commit()
conn.close()

print("==================================================")
print("DATABASE URL POPULATION SUMMARY")
print("==================================================")
print(f"Total Products Updated       : {updated_count}")
print(f"Products with Verified MFR URL: {found_url_count} ({(found_url_count/updated_count)*100:.1f}%)")
print(f"Left Blank (Unmapped/Rejected): {updated_count - found_url_count} ({((updated_count - found_url_count)/updated_count)*100:.1f}%)")
