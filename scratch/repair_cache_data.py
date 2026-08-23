import sqlite3
import sys

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("FIX 5: REPAIRING CONTAMINATED AI KNOWLEDGE CACHE DATA")
print("==================================================")

# Count contaminated rows
contaminated = cursor.execute("""
    SELECT COUNT(*) FROM ai_knowledge_cache 
    WHERE source = 'url_resolver' AND (resolved_brand != '' OR resolved_manufacturer != '')
""").fetchone()[0]

print(f"Contaminated cache rows identified (source = 'url_resolver' with brand/mfr data): {contaminated}")

# Clear contaminated brand/manufacturer fields on url_resolver rows
cursor.execute("""
    UPDATE ai_knowledge_cache
    SET resolved_brand = '', resolved_manufacturer = ''
    WHERE source = 'url_resolver'
""")

conn.commit()
print("Successfully purged contaminated brand/manufacturer fields from url_resolver rows in ai_knowledge_cache!")

# Check total rows remaining in cache
total_cache = cursor.execute("SELECT COUNT(*) FROM ai_knowledge_cache").fetchone()[0]
print(f"Total rows remaining in ai_knowledge_cache: {total_cache}")

conn.close()
