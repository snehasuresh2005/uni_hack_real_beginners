import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

prods = cursor.execute("SELECT id, mfg_part_num, invoice_desc, mobile_desc, short_desc, long_desc FROM products WHERE id IN (22041, 22042, 22043)").fetchall()
conn.close()

for p in prods:
    print(f"ID {p['id']} ({p['mfg_part_num']}):")
    print(f"  Invoice Desc: '{p['invoice_desc']}'")
    print(f"  Mobile Desc : '{p['mobile_desc']}' ({len(p['mobile_desc'] or '')} chars)")
    print(f"  Short Desc  : '{p['short_desc']}'")
    print(f"  Long Desc   : '{p['long_desc']}'\n")
