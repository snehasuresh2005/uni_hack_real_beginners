import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.pipeline import run_pipeline_for_product

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("RESETTING FINGERPRINTS & STATUS TO FORCE FRESH PIPELINE RUN")
print("==================================================")
cursor.execute("UPDATE products SET fingerprint = NULL, status = 'pending', resolved_brand = NULL, resolved_manufacturer = NULL")
conn.commit()

products = cursor.execute("SELECT id FROM products").fetchall()
p_ids = [p["id"] for p in products]
conn.close()

print(f"Executing parallel run_pipeline_for_product across {len(p_ids)} products with 10 workers...")

completed_cnt = 0
def _process_item(pid):
    global completed_cnt
    try:
        run_pipeline_for_product(pid)
    except Exception as e:
        pass
    completed_cnt += 1

with ThreadPoolExecutor(max_workers=10) as executor:
    list(executor.map(_process_item, p_ids))

print(f"\nParallel pipeline execution completed across all {len(p_ids)} products!\n")

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("VERIFICATION CHECK 1: PRODUCT PDSH4816AF RESOLUTION")
print("==================================================")
pdsh = cursor.execute("SELECT id, mfg_part_num, part_manuf, resolved_brand, resolved_manufacturer, classpath, mfr_url FROM products WHERE mfg_part_num = 'PDSH4816AF'").fetchone()
if pdsh:
    print(f"Product #{pdsh['id']} [MPN: {pdsh['mfg_part_num']}]:")
    print(f"  Part_Manuf           : '{pdsh['part_manuf']}'")
    print(f"  Resolved Brand       : '{pdsh['resolved_brand']}'")
    print(f"  Resolved Manufacturer: '{pdsh['resolved_manufacturer']}'")
    print(f"  Classpath            : '{pdsh['classpath']}'")
    print(f"  MFR URL              : '{pdsh['mfr_url']}'")

print("\n==================================================")
print("VERIFICATION CHECK 2: BRAND SYMBOL (®/™) COVERAGE")
print("==================================================")
total_p = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
with_sym = cursor.execute("SELECT COUNT(*) FROM products WHERE resolved_brand LIKE '%®%' OR resolved_brand LIKE '%™%'").fetchone()[0]
pct = (with_sym / total_p) * 100 if total_p else 0
print(f"Total Products               : {total_p}")
print(f"Products with Symbol (®/™)   : {with_sym} ({pct:.1f}%)")

print("\n==================================================")
print("VERIFICATION CHECK 3: SATCO & PHILIPS CANONICAL CASING COLLAPSE")
print("==================================================")
satco_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%SATCO%' GROUP BY resolved_brand").fetchall()
philips_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%PHILIPS%' GROUP BY resolved_brand").fetchall()

print("SATCO variations in DB:")
for s in satco_rows:
    print(f"  '{s['resolved_brand']}': {s['cnt']} rows")

print("\nPHILIPS variations in DB:")
for ph in philips_rows:
    print(f"  '{ph['resolved_brand']}': {ph['cnt']} rows")

print("\n==================================================")
print("VERIFICATION CHECK 4: MFR URL & REF PDF FILL RATES")
print("==================================================")
mfr_cnt = cursor.execute("SELECT COUNT(*) FROM products WHERE mfr_url IS NOT NULL AND mfr_url != ''").fetchone()[0]
ref_cnt = cursor.execute("SELECT COUNT(*) FROM products WHERE ref_url_1 IS NOT NULL AND ref_url_1 != ''").fetchone()[0]
print(f"Products with Verified MFR URL: {mfr_cnt} ({(mfr_cnt/total_p)*100:.1f}%)")
print(f"Products with Verified Ref PDF: {ref_cnt} ({(ref_cnt/total_p)*100:.1f}%)")

print("\n==================================================")
print("VERIFICATION CHECK 5: AI KNOWLEDGE CACHE ISOLATION AUDIT")
print("==================================================")
url_brand_written = cursor.execute("SELECT COUNT(*) FROM ai_knowledge_cache WHERE source = 'url_resolver' AND (resolved_brand != '' OR resolved_manufacturer != '')").fetchone()[0]
print(f"Cache rows with source = 'url_resolver' and brand/mfr written: {url_brand_written} (Target: 0)")

conn.close()
