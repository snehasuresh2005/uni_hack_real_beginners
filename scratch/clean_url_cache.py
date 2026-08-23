import sqlite3

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clear cache entries with search in URL or created by url_resolver
cursor.execute("DELETE FROM ai_knowledge_cache WHERE source = 'url_resolver' OR web_urls LIKE '%search%'")
conn.commit()
print("Cleared stale search URLs from ai_knowledge_cache. Rows deleted:", cursor.rowcount)
conn.close()
