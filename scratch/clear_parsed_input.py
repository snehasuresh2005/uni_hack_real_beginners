import sqlite3
import os

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable WAL & busy timeout
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA busy_timeout = 30000;")
    
    # Get initial counts
    tables = ["products", "attributes", "agent_logs", "conflicts", "product_cache", "ai_knowledge_cache"]
    counts_before = {}
    for t in tables:
        try:
            cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            counts_before[t] = cnt
        except Exception:
            counts_before[t] = 0
            
    print("Counts before clearing:")
    for t, c in counts_before.items():
        print(f"  - {t}: {c} rows")
        
    # Clear all data safely
    for t in tables:
        try:
            cursor.execute(f"DELETE FROM {t}")
        except Exception as e:
            pass

    
    conn.commit()
    
    counts_after = {}
    for t in tables:
        try:
            cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            counts_after[t] = cnt
        except Exception:
            counts_after[t] = 0
            
    conn.close()
    
    print("\nSuccessfully cleared all parsed input and cached product data!")
    print("Counts after clearing:")
    for t, c in counts_after.items():
        print(f"  - {t}: {c} rows")
else:
    print(f"Database file not found at {db_path}")
