import re

MFR_DOMAIN_MAP = {
    "frigidaire": "frigidaire.com",
    "whirlpool": "whirlpool.com",
    "milwaukee": "milwaukeetool.com",
    "diablo": "freudtools.com",
    "freud": "freudtools.com",
    "3m": "3m.com",
    "bosch": "boschtools.com",
    "mirka": "mirka.com",
    "dewalt": "dewalt.com",
}

def get_manufacturer_domain(part_manuf: str, resolved_brand: str) -> str:
    mfr_s = (part_manuf or "").lower().strip()
    brand_s = (resolved_brand or "").lower().strip()
    
    # Strip special characters and parentheticals
    mfr_s = re.sub(r'[\ufffd\u00ae\u2122\u00a9\ufffd]', '', mfr_s)
    mfr_s = re.sub(r'\s*\([a-zA-Z0-9\s]+\)\s*$', '', mfr_s).strip()
    
    brand_s = re.sub(r'[\ufffd\u00ae\u2122\u00a9\ufffd]', '', brand_s).strip()
    
    for key, dom in MFR_DOMAIN_MAP.items():
        if key in mfr_s or key in brand_s:
            return dom
    return ""

test_cases = [
    ("Freud Inc (2435)", "FREUD"),
    ("Jam Industrial Supply LLC (JAMIN)", "3M"),
    ("Mirka Abrasives Inc (MIRUS)", "MIRKA"),
    ("DeWalt Tool Co", "DeWalt")
]

for mfr, brd in test_cases:
    dom = get_manufacturer_domain(mfr, brd)
    print(f"Mfr: '{mfr}', Brd: '{brd}' -> Domain: '{dom}'")
