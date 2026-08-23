import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

total = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
with_mfr = cursor.execute("SELECT COUNT(*) FROM products WHERE mfr_url IS NOT NULL AND mfr_url != ''").fetchone()[0]
with_ref = cursor.execute("SELECT COUNT(*) FROM products WHERE ref_url_1 IS NOT NULL AND ref_url_1 != ''").fetchone()[0]
flagged = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'flagged_hitl'").fetchone()[0]
flagged_with_mfr = cursor.execute("SELECT COUNT(*) FROM products WHERE status = 'flagged_hitl' AND mfr_url IS NOT NULL AND mfr_url != ''").fetchone()[0]

print("==================================================")
print("DATABASE URL COVERAGE AUDIT")
print("==================================================")
print(f"Total Products in DB         : {total}")
print(f"Products with mfr_url        : {with_mfr}")
print(f"Products with ref_url_1      : {with_ref}")
print(f"Flagged HITL Products        : {flagged}")
print(f"Flagged HITL with mfr_url    : {flagged_with_mfr}")

if total > 0:
    print("\nSAMPLE 10 PRODUCTS & THEIR URL STATUS:")
    rows = cursor.execute("SELECT id, mfg_part_num, part_manuf, resolved_brand, mfr_url, ref_url_1 FROM products LIMIT 10").fetchall()
    for r in rows:
        print(f"ID {r['id']} | MPN: {r['mfg_part_num']} | Brand: {r['resolved_brand']} | Mfr URL: '{r['mfr_url']}'")

conn.close()
