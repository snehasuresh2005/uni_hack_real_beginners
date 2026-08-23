import pandas as pd
import sqlite3
import json

db_path = r"c:\Users\Sneha\projects\unihack_real_beginners\backend\database.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get all 999 products from database
prods = cursor.execute("SELECT id, mfg_part_num, part_desc, part_manuf, e1_brand, unilog_brand, dib_brand, resolved_brand, resolved_manufacturer FROM products").fetchall()
conn.close()

# Load brand dictionary
with open(r"c:\Users\Sneha\projects\unihack_real_beginners\backend\brand_dictionary.json", "r") as f:
    brand_dict = json.load(f)

# Master Manufacturer Domain Map (40+ top B2B manufacturers)
MFR_DOMAIN_MAP = {
    "frigidaire": "frigidaire.com",
    "whirlpool": "whirlpool.com",
    "milwaukee": "milwaukeetool.com",
    "diablo": "freudtools.com",
    "freud": "freudtools.com",
    "3m": "3m.com",
    "bosch": "boschtools.com",
    "lg": "lg.com",
    "kitchenaid": "kitchenaid.com",
    "dewalt": "dewalt.com",
    "black & decker": "blackanddecker.com",
    "makita": "makitatools.com",
    "mirka": "mirka.com",
    "speed queen": "speedqueen.com",
    "ge": "geappliances.com",
    "rheem": "rheem.com",
    "trex": "trex.com",
    "timbertech": "timbertech.com",
    "emseal": "emseal.com",
    "kichler": "kichler.com",
    "hunter": "hunterfan.com",
    "festool": "festoolusa.com",
    "kreg": "kregtool.com",
    "edge eyewear": "edgeeyewear.com",
    "paslode": "paslode.com",
    "stabila": "stabila.com",
    "lenox": "lenoxtools.com",
    "irwin": "irwin.com",
    "satco": "satco.com",
    "schumacher": "schumacherelectric.com",
    "andersen": "andersencorp.com",
    "nicholson": "apextoolgroup.com",
    "mafell": "mafell.de",
    "fisch": "fisch-tools.com",
    "barrette": "barretteoutdoorliving.com",
    "vessel": "vessel.co.jp",
    "skf": "skf.com",
    "senco": "senco.com",
    "leviton": "leviton.com",
    "southwire": "southwire.com",
    "square d": "se.com",
    "lithonia": "acuitybrands.com",
    "philips": "signify.com",
    "certainteed": "certainteed.com",
    "velux": "veluxusa.com",
    "huber": "huberwood.com",
    "thomas & betts": "tnb.abb.com",
}

covered_count = 0
uncovered_count = 0

covered_by_mfr = {}
uncovered_mfrs = {}

for p in prods:
    mfr_raw = (p['resolved_manufacturer'] or p['part_manuf'] or "").strip().lower()
    brand_raw = (p['resolved_brand'] or p['e1_brand'] or p['unilog_brand'] or "").strip().lower()
    
    # Check match against domain map
    matched_domain = None
    for key, dom in MFR_DOMAIN_MAP.items():
        if key in mfr_raw or key in brand_raw:
            matched_domain = dom
            break
            
    if matched_domain:
        covered_count += 1
        covered_by_mfr[matched_domain] = covered_by_mfr.get(matched_domain, 0) + 1
    else:
        uncovered_count += 1
        uncovered_mfrs[mfr_raw] = uncovered_mfrs.get(mfr_raw, 0) + 1

total = len(prods)
print(f"==================================================")
print(f"MANUFACTURER DOMAIN COVERAGE AUDIT ({total} PRODUCTS)")
print(f"==================================================")
print(f"Covered Products   : {covered_count} ({covered_count/total*100:.1f}%)")
print(f"Uncovered Products : {uncovered_count} ({uncovered_count/total*100:.1f}%)")

print(f"\nTop Covered Manufacturer Domains:")
for dom, cnt in sorted(covered_by_mfr.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"  - {dom}: {cnt} products ({cnt/total*100:.1f}%)")

print(f"\nTop Uncovered Raw Manufacturers:")
for mfr, cnt in sorted(uncovered_mfrs.items(), key=lambda x: x[1], reverse=True)[:15]:
    print(f"  - '{mfr}': {cnt} products ({cnt/total*100:.1f}%)")
