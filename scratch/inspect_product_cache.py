import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

pc_cnt = cursor.execute("SELECT COUNT(*) FROM product_cache").fetchone()[0]
print(f"Total rows in product_cache table: {pc_cnt}")

# Clear product_cache so pipeline re-evaluates all products cleanly with the new fixes!
cursor.execute("DELETE FROM product_cache")
conn.commit()
print("Cleared product_cache table so pipeline re-evaluates cleanly!")

conn.close()
