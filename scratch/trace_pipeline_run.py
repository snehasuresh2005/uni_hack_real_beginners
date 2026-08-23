import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("PRODUCT 22102 (PDSH4816AF) AGENT LOGS TRACE")
print("==================================================")
logs = cursor.execute("SELECT * FROM agent_logs WHERE product_id = 22102 OR message LIKE '%PDSH4816AF%'").fetchall()
for l in logs:
    d = dict(l)
    t = d.get('timestamp') or d.get('created_at') or ''
    a = d.get('agent_name') or ''
    lvl = d.get('level') or ''
    msg = d.get('message') or ''
    print(f"[{t}] [{a}] ({lvl}): {msg}")

print("\n==================================================")
print("PRODUCT 22102 CONFLICT RECORD")
print("==================================================")
conflicts = cursor.execute("SELECT * FROM conflicts WHERE product_id = 22102").fetchall()
for c in conflicts:
    print(f"Conflict ID {c['id']}: Type={c['conflict_type']} | SourceA={c['source_a']}:{c['val_a']} | SourceB={c['source_b']}:{c['val_b']} | Status={c['status']}")

print("\n==================================================")
print("CHECK BRAND DISTRIBUTION ACROSS 999 PRODUCTS")
print("==================================================")
products = cursor.execute("SELECT id, mfg_part_num, resolved_brand, resolved_manufacturer, status, ai_drafted FROM products").fetchall()
status_counts = {}
brand_counts = {}
for p in products:
    brd = p["resolved_brand"]
    brand_counts[brd] = brand_counts.get(brd, 0) + 1
    st = p["status"]
    status_counts[st] = status_counts.get(st, 0) + 1

print(f"Status distribution across 999 products: {status_counts}")
print("\nTop 30 Brand Values in DB:")
sorted_brands = sorted(brand_counts.items(), key=lambda x: x[1], reverse=True)[:30]
for b, cnt in sorted_brands:
    print(f"  '{b}': {cnt} products")

conn.close()
