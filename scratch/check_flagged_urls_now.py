import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

prods = cursor.execute("SELECT id, mfg_part_num, resolved_brand, mfr_url, ref_url_1 FROM products WHERE mfr_url IS NOT NULL AND mfr_url != '' LIMIT 10").fetchall()
cnt = cursor.execute("SELECT COUNT(*) FROM products WHERE mfr_url IS NOT NULL AND mfr_url != ''").fetchone()[0]
conn.close()

print(f"Total Database Products with MFR URLs: {cnt}\n")
for p in prods:
    print(f"Product #{p['id']} [{p['resolved_brand']} / MPN: {p['mfg_part_num']}]:")
    print(f"  MFR URL : '{p['mfr_url']}'")
    print(f"  Ref PDF : '{p['ref_url_1']}'\n")
