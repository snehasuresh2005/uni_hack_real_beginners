import sqlite3
import requests

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Find any product or insert sample product to test API endpoint
p = cursor.execute("SELECT id, mfg_part_num, part_desc FROM products LIMIT 1").fetchone()
conn.close()

if p:
    print(f"Testing API for product ID {p['id']} ({p['mfg_part_num']})...")
    try:
        r = requests.post(f"http://127.0.0.1:8000/api/products/{p['id']}/ai-assist", timeout=10.0)
        if r.status_code == 200:
            data = r.json()
            mob = data.get("mobile_desc", "")
            print(f"API Returned Mobile Desc ({len(mob)} chars): '{mob}'")
            print("Length within 60..80 chars?:", 60 <= len(mob) <= 80)
        else:
            print("API returned error:", r.status_code, r.text)
    except Exception as e:
        print("API test exception:", e)
else:
    print("No products currently in DB. Database is empty.")
