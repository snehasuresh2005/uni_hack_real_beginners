import sys
import sqlite3
import pandas as pd

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.mfr_url_resolver import resolve_product_urls

print("==================================================")
print("TESTING MFR URL RESOLVER ON GROUND TRUTH: PDSH4816AF")
print("==================================================")

res_gt = resolve_product_urls("Frigidaire", "FRIGIDAIRE", "PDSH4816AF", "PDSH4816AF Dishwasher SS")
print(f"Result for PDSH4816AF:")
print(f"  MFR URL: {repr(res_gt['mfr_url'])}")
print(f"  Ref URLs ({len(res_gt['ref_urls'])} found): {res_gt['ref_urls']}")

print("\n==================================================")
print("TESTING MFR URL RESOLVER ON BATCH OF 40 PRODUCTS")
print("==================================================")

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

sample_prods = cursor.execute("""
    SELECT id, mfg_part_num, part_desc, part_manuf, e1_brand, resolved_brand, resolved_manufacturer
    FROM products
    ORDER BY id ASC
    LIMIT 40
""").fetchall()
conn.close()

found_count = 0
blank_count = 0
sample_found = []

for i, p in enumerate(sample_prods, 1):
    mfr = p['resolved_manufacturer'] or p['part_manuf'] or ""
    brand = p['resolved_brand'] or p['e1_brand'] or ""
    mpn = p['mfg_part_num'] or ""
    desc = p['part_desc'] or ""
    
    res = resolve_product_urls(mfr, brand, mpn, desc)
    mfr_url = res['mfr_url']
    ref_urls = res['ref_urls']
    
    if mfr_url:
        found_count += 1
        sample_found.append((p['id'], mfr, brand, mpn, mfr_url, ref_urls))
        print(f"Product #{i} [ID {p['id']}, MPN: {mpn}] -> FOUND MFR URL: {mfr_url}")
        if ref_urls:
            print(f"   PDF Ref URLs ({len(ref_urls)}): {ref_urls}")
    else:
        blank_count += 1
        print(f"Product #{i} [ID {p['id']}, MPN: {mpn}] -> LEFT BLANK")

total = len(sample_prods)
print(f"\n==================================================")
print(f"VERIFICATION SUMMARY ({total} PRODUCTS TESTED)")
print(f"==================================================")
print(f"MFR URLs Found (High Confidence) : {found_count} ({found_count/total*100:.1f}%)")
print(f"Left Blank (Unverified/Unmapped) : {blank_count} ({blank_count/total*100:.1f}%)")

print(f"\n10 EXAMPLES OF FOUND MFR & REF URLS:")
for idx, (pid, mfr, brand, mpn, url, pdfs) in enumerate(sample_found[:10], 1):
    print(f"{idx}. Product ID {pid} ({mfr} / {brand} MPN: {mpn})")
    print(f"   MFR URL: {url}")
    if pdfs:
        print(f"   Ref PDFs: {pdfs}")
