import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

prods = cursor.execute("SELECT id, mfg_part_num, invoice_desc, mobile_desc FROM products WHERE id IN (22041, 22042, 22043)").fetchall()
conn.close()

for p in prods:
    mob = p['mobile_desc'] or ""
    inv = p['invoice_desc'] or ""
    print(f"ID {p['id']} ({p['mfg_part_num']}):")
    print(f"  Invoice Desc: '{inv}'")
    print(f"  Mobile Desc : '{mob}' ({len(mob)} chars)")
    print(f"  Valid length 60..80?: {60 <= len(mob) <= 80}\n")
