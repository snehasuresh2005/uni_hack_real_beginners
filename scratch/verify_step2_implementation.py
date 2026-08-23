import sys
import sqlite3
import pandas as pd

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.mfr_url_resolver import resolve_product_urls

print("==================================================")
print("VERIFYING GROUND TRUTH PRODUCT: PDSH4816AF")
print("==================================================")

res_gt = resolve_product_urls("Frigidaire", "FRIGIDAIRE", "PDSH4816AF", "PDSH4816AF Dishwasher SS")
print(f"Ground Truth MPN: PDSH4816AF")
print(f"  MFR URL: {repr(res_gt['mfr_url'])}")
print(f"  Ref URLs ({len(res_gt['ref_urls'])} PDFs): {res_gt['ref_urls']}")

print("\n==================================================")
print("RUNNING VERIFICATION ACROSS 40 CATALOG PRODUCTS")
print("==================================================")

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Query 40 products from diverse manufacturers
prods = cursor.execute("""
    SELECT id, mfg_part_num, part_desc, part_manuf, e1_brand, resolved_brand, resolved_manufacturer
    FROM products
    WHERE mfg_part_num IS NOT NULL AND mfg_part_num != ''
    ORDER BY id ASC
    LIMIT 40
""").fetchall()
conn.close()

found_mfr_count = 0
blank_count = 0
found_examples = []

for i, p in enumerate(prods, 1):
    mfr = p['resolved_manufacturer'] or p['part_manuf'] or ""
    brand = p['resolved_brand'] or p['e1_brand'] or ""
    mpn = p['mfg_part_num'] or ""
    desc = p['part_desc'] or ""
    
    res = resolve_product_urls(mfr, brand, mpn, desc)
    mfr_url = res['mfr_url']
    ref_urls = res['ref_urls']
    
    if mfr_url:
        found_mfr_count += 1
        found_examples.append((p['id'], mfr, brand, mpn, mfr_url, ref_urls))
        print(f"Row {i:02d} [ID {p['id']} | MPN: {mpn:18s} | MFR: {mfr:15s}] -> VERIFIED MFR URL: {mfr_url}")
        if ref_urls:
            print(f"       -> Ref PDFs ({len(ref_urls)}): {ref_urls}")
    else:
        blank_count += 1
        print(f"Row {i:02d} [ID {p['id']} | MPN: {mpn:18s} | MFR: {mfr:15s}] -> LEFT BLANK")

total = len(prods)
print("\n==================================================")
print("STEP 2 IMPLEMENTATION VERIFICATION METRICS")
print("==================================================")
print(f"Total Products Tested             : {total}")
print(f"Manufacturer URL Found (200 OK)   : {found_mfr_count} ({found_mfr_count/total*100:.1f}%)")
print(f"Left Blank (Unmapped / Rejected) : {blank_count} ({blank_count/total*100:.1f}%)")

print("\n10 VERIFIED EXAMPLE URLS (HIGH CONFIDENCE):")
for idx, (pid, mfr, brand, mpn, url, pdfs) in enumerate(found_examples[:10], 1):
    print(f"\nExample #{idx}: Product ID {pid} ({mfr} / {brand} MPN: {mpn})")
    print(f"  MFR URL  : {url}")
    print(f"  Ref PDFs : {pdfs if pdfs else 'None (0 PDFs on page)'}")
