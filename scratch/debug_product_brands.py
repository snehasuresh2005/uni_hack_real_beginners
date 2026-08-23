import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

prods = cursor.execute("SELECT id, mfg_part_num, part_manuf, resolved_brand, e1_brand, unilog_brand, dib_brand FROM products LIMIT 15").fetchall()
conn.close()

for p in prods:
    print(f"ID {p['id']} | MPN: '{p['mfg_part_num']}' | Manuf: '{p['part_manuf']}' | ResBrd: '{p['resolved_brand']}' | E1: '{p['e1_brand']}'")
