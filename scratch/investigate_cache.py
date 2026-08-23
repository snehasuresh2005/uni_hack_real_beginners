import sqlite3
import hashlib
import re
import sys

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.ai_knowledge_cache import compute_pattern_key, extract_mfg_prefix

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("1. AI KNOWLEDGE CACHE CONTENTS (ALL ROWS)")
print("==================================================")
rows = cursor.execute("SELECT id, pattern_key, part_manuf, mfg_prefix, resolved_brand, resolved_manufacturer, classpath, source, created_at FROM ai_knowledge_cache").fetchall()
for r in rows:
    print(f"ID {r['id']} | Key: {r['pattern_key'][:10]}... | Mfr: '{r['part_manuf']}' | Prefix: '{r['mfg_prefix']}' | ResBrd: '{r['resolved_brand']}' | ResMfr: '{r['resolved_manufacturer']}' | Src: {r['source']}")

print("\n==================================================")
print("2. PDSH4816AF INVESTIGATION")
print("==================================================")
# Check product row for PDSH4816AF
p_row = cursor.execute("SELECT * FROM products WHERE mfg_part_num = 'PDSH4816AF'").fetchone()
if p_row:
    p_dict = dict(p_row)
    print(f"Product PDSH4816AF DB Row:")
    print(f"  Part_Manuf: '{p_dict.get('part_manuf')}'")
    print(f"  Resolved Brand: '{p_dict.get('resolved_brand')}'")
    print(f"  Resolved Manufacturer: '{p_dict.get('resolved_manufacturer')}'")
    print(f"  Classpath: '{p_dict.get('classpath')}'")
    
    # Compute keys
    pm = p_dict.get('part_manuf', '')
    mpn = p_dict.get('mfg_part_num', '')
    prefix = extract_mfg_prefix(mpn)
    key = compute_pattern_key(pm, mpn)
    print(f"\n  Prefix extracted: '{prefix}'")
    print(f"  Pattern Key computed: {key}")
    
    # Look up in cache using exact key
    cache_exact = cursor.execute("SELECT * FROM ai_knowledge_cache WHERE pattern_key = ?", (key,)).fetchone()
    print(f"  Cache Exact Key Match: {dict(cache_exact) if cache_exact else 'NONE'}")
    
    # Look up in cache using part_manuf fallback
    from backend.preprocessing.cleaner import normalize_manufacturer
    norm_mfr = normalize_manufacturer(pm)
    cache_mfr = cursor.execute("SELECT * FROM ai_knowledge_cache WHERE part_manuf = ? ORDER BY id DESC", (norm_mfr,)).fetchall()
    print(f"  Cache Manufacturer Fallback Hits for '{norm_mfr}': {len(cache_mfr)} rows")
    for cm in cache_mfr:
        print(f"    - ID {cm['id']} | Prefix: '{cm['mfg_prefix']}' | ResBrd: '{cm['resolved_brand']}' | ResMfr: '{cm['resolved_manufacturer']}' | Src: {cm['source']}")

conn.close()
