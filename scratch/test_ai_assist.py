import sqlite3
import urllib.request
import json
import os

def run_test():
    db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    rows = cursor.execute("SELECT id, part_desc FROM products WHERE status = 'flagged_hitl' LIMIT 3").fetchall()
    conn.close()
    
    if not rows:
        print("No products with status 'flagged_hitl' found in database.")
        return
    
    for row in rows:
        product_id, part_desc = row["id"], row["part_desc"]
        print(f"\n{'='*60}")
        print(f"Testing AI Assist for Product ID: {product_id} ('{part_desc}')")
        print(f"{'='*60}")
        
        url = f"http://127.0.0.1:8000/api/products/{product_id}/ai-assist"
        req = urllib.request.Request(url, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                status = response.getcode()
                body = response.read().decode("utf-8")
                data = json.loads(body)
                print(f"HTTP Status: {status}")
                print(f"  resolved_brand:        {data.get('resolved_brand', 'MISSING')}")
                print(f"  resolved_manufacturer: {data.get('resolved_manufacturer', 'MISSING')}")
                print(f"  classpath:             {data.get('classpath', 'MISSING')}")
                print(f"  invoice_desc:          {data.get('invoice_desc', 'MISSING')}")
                print(f"  mobile_desc:           {data.get('mobile_desc', 'MISSING')}")
                print(f"  short_desc:            {data.get('short_desc', 'MISSING')}")
                print(f"  long_desc:             {data.get('long_desc', 'MISSING')[:80]}...")
                attrs = data.get('attributes', [])
                print(f"  attributes count:      {len(attrs)}")
                for a in attrs:
                    print(f"    - {a.get('label')}: {a.get('value')} {a.get('uom') or ''}")
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} {e.reason}")
            print(e.read().decode("utf-8"))
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    run_test()
