import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

total_p = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
with_sym = cursor.execute("SELECT COUNT(*) FROM products WHERE resolved_brand LIKE '%®%' OR resolved_brand LIKE '%™%'").fetchone()[0]
pct = (with_sym / total_p) * 100 if total_p else 0

pdsh = cursor.execute("SELECT id, mfg_part_num, part_manuf, resolved_brand, resolved_manufacturer FROM products WHERE mfg_part_num = 'PDSH4816AF'").fetchone()

satco_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%SATCO%' GROUP BY resolved_brand").fetchall()
philips_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%PHILIPS%' GROUP BY resolved_brand").fetchall()

url_brand_written = cursor.execute("SELECT COUNT(*) FROM ai_knowledge_cache WHERE source = 'url_resolver' AND (resolved_brand != '' OR resolved_manufacturer != '')").fetchone()[0]

conn.close()

print(f"Products with Symbol (®/™)   : {with_sym}/{total_p} ({pct:.1f}%)")
if pdsh:
    print(f"PDSH4816AF Brand             : '{pdsh['resolved_brand']}' | Mfr: '{pdsh['resolved_manufacturer']}'")
print(f"SATCO variations             : {[dict(r) for r in satco_rows]}")
print(f"PHILIPS variations           : {[dict(r) for r in philips_rows]}")
print(f"Contaminated Cache Rows      : {url_brand_written}")
