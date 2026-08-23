import sqlite3
import requests

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

prods = cursor.execute("SELECT id FROM products LIMIT 3").fetchall()
conn.close()

if prods:
    ids = [p['id'] for p in prods]
    print(f"Testing /api/batches/brand-ai-assist for IDs {ids}...")
    try:
        r = requests.post("http://127.0.0.1:8000/api/batches/brand-ai-assist", json={"product_ids": ids}, timeout=15.0)
        print("Status code:", r.status_code)
        print("Response body:", r.json())
    except Exception as e:
        print("Exception:", e)
else:
    print("No products in database to test.")
