import sqlite3
import sys
import hashlib
import json

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.ai_knowledge_cache import compute_pattern_key, extract_mfg_prefix, lookup_knowledge_cache
from backend.preprocessing.cleaner import normalize_manufacturer

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("==================================================")
print("INVESTIGATION POINT 1: PIPELINE & CACHE TOUCH POINTS")
print("==================================================")

# Check where resolve_brand_and_manufacturer or ai_knowledge_cache is called during pipeline
print("Inspecting products table for PDSH4816AF...")
p_pdsh = cursor.execute("SELECT * FROM products WHERE mfg_part_num = 'PDSH4816AF'").fetchone()
if p_pdsh:
    p_dict = dict(p_pdsh)
    print(f"Product ID {p_dict['id']}: MPN={p_dict['mfg_part_num']}, Brand={p_dict['resolved_brand']}, Mfr={p_dict['resolved_manufacturer']}, E1={p_dict['e1_brand']}, Manuf={p_dict['part_manuf']}")

print("\n==================================================")
print("INVESTIGATION POINT 2: COMPUTE PATTERN KEY COMPARISON & COLLISION")
print("==================================================")
# Check pattern keys for PDSH4816AF under different part_manuf parameters
pm_raw = p_pdsh['part_manuf'] if p_pdsh else "Appliance Dealers Cooperative (APPDE)"
key_raw = compute_pattern_key(pm_raw, "PDSH4816AF")
key_norm = compute_pattern_key(normalize_manufacturer(pm_raw), "PDSH4816AF")
key_mfr_only = compute_pattern_key("General Electric", "PDSH4816AF")
key_empty = compute_pattern_key("", "PDSH4816AF")

print(f"part_manuf='{pm_raw}' -> key={key_raw}")
print(f"part_manuf='{normalize_manufacturer(pm_raw)}' -> key={key_norm}")
print(f"part_manuf='General Electric' -> key={key_mfr_only}")
print(f"part_manuf='' -> key={key_empty}")

print("\n==================================================")
print("INVESTIGATION POINT 3: RAW AI KNOWLEDGE CACHE ROWS FOR PDSH & GE")
print("==================================================")
cache_rows = cursor.execute("SELECT * FROM ai_knowledge_cache WHERE mfg_prefix LIKE 'PDSH%' OR part_manuf LIKE '%Appliance%' OR part_manuf LIKE '%Electric%' OR part_manuf LIKE '%Frigidaire%' OR resolved_brand LIKE '%GE%' OR resolved_brand LIKE '%FRIGIDAIRE%'").fetchall()
for cr in cache_rows:
    print(f"Cache ID {cr['id']}: Key={cr['pattern_key'][:16]}... | Mfr='{cr['part_manuf']}' | Prefix='{cr['mfg_prefix']}' | Brand='{cr['resolved_brand']}' | ResMfr='{cr['resolved_manufacturer']}' | Src='{cr['source']}'")

print("\n==================================================")
print("INVESTIGATION POINT 4: MPN PREFIX HASH COLLISION AUDIT")
print("==================================================")
# Check how many distinct MPNs map to the exact same mfg_prefix & pattern_key
prefixes = cursor.execute("SELECT mfg_prefix, COUNT(*) as cnt FROM ai_knowledge_cache GROUP BY mfg_prefix HAVING cnt > 1").fetchall()
print(f"Prefixes shared across multiple cache entries: {len(prefixes)}")
for pf in prefixes:
    print(f"  Prefix '{pf['mfg_prefix']}': {pf['cnt']} entries")

print("\n==================================================")
print("INVESTIGATION POINT 5: SATCO & PHILIPS BRAND DUPLICATION AUDIT IN PRODUCTS DB")
print("==================================================")
satco_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%SATCO%' GROUP BY resolved_brand").fetchall()
philips_rows = cursor.execute("SELECT resolved_brand, COUNT(*) as cnt FROM products WHERE UPPER(resolved_brand) LIKE '%PHILIPS%' GROUP BY resolved_brand").fetchall()

print("SATCO variations in DB:")
for s in satco_rows:
    print(f"  '{s['resolved_brand']}': {s['cnt']} rows")

print("PHILIPS variations in DB:")
for ph in philips_rows:
    print(f"  '{ph['resolved_brand']}': {ph['cnt']} rows")

print("\nSymbol (®/™) coverage in products DB:")
total_p = cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0]
with_sym = cursor.execute("SELECT COUNT(*) FROM products WHERE resolved_brand LIKE '%®%' OR resolved_brand LIKE '%™%'").fetchone()[0]
print(f"  Total products: {total_p}")
print(f"  Products with ®/™ symbol: {with_sym} ({(with_sym/total_p)*100:.1f}%)")

conn.close()
