import os
import pandas as pd

# Global caches
TAXONOMY_MAP = {}
MANUFACTURER_LIST = []
BRAND_LIST = []
UOM_ABBREVIATIONS = {}
DECIMAL_FRACTIONS = {}

def find_file(filename):
    """
    Search for a file in common locations.
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", filename),
        os.path.join(os.path.dirname(__file__), "..", filename),
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join("c:\\Users\\Sneha\\projects\\unihack_real_beginners", filename),
        os.path.join("c:\\Users\\Sneha\\Downloads", filename),
        os.path.join("c:\\Users\\Sneha\\OneDrive\\Desktop", filename),
        os.path.join("c:\\Users\\Sneha\\OneDrive\\Documents", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def load_all_references():
    global MANUFACTURER_LIST, BRAND_LIST, UOM_ABBREVIATIONS, DECIMAL_FRACTIONS
    
    # 1. Load UOM standard abbreviations
    uom_path = find_file("Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx")
    if uom_path:
        try:
            df = pd.read_excel(uom_path)
            for _, row in df.iterrows():
                term = str(row.iloc[0]).strip().lower() if len(row) > 0 else ""
                abbrev = str(row.iloc[1]).strip() if len(row) > 1 else ""
                if term and abbrev and term != "nan" and abbrev != "nan":
                    UOM_ABBREVIATIONS[term] = abbrev
        except Exception as e:
            print("Failed to load UOM standards:", e)
            
    # 2. Load Decimal Fraction mapping
    frac_path = find_file("Decimal_Fraction.xlsx")
    if frac_path:
        try:
            df = pd.read_excel(frac_path)
            for _, row in df.iterrows():
                dec = row.iloc[0] if len(row) > 0 else None
                frac = row.iloc[1] if len(row) > 1 else None
                if dec is not None and frac is not None and str(dec) != "nan" and str(frac) != "nan":
                    DECIMAL_FRACTIONS[float(dec)] = str(frac)
        except Exception as e:
            print("Failed to load Decimal Fraction mappings:", e)
            
    # 3. Load Manufacturer and Brand list
    mfr_path = find_file("UniCat_Manufacturer_and_Brand_List.xlsx")
    if mfr_path:
        try:
            df = pd.read_excel(mfr_path)
            MANUFACTURER_LIST = list(set(str(m).strip() for m in df.iloc[:, 0].dropna() if str(m).strip() != "nan"))
            if df.shape[1] > 1:
                BRAND_LIST = list(set(str(b).strip() for b in df.iloc[:, 1].dropna() if str(b).strip() != "nan"))
        except Exception as e:
            print("Failed to load Manufacturer and Brand list:", e)

    # Initialize standard B2B fallbacks if files are missing
    if not UOM_ABBREVIATIONS:
        UOM_ABBREVIATIONS = {
            "volt": "V", "volts": "V", "voltage": "V",
            "amp": "A", "amps": "A", "amperage": "A",
            "inch": "in", "inches": "in", "in.": "in",
            "millimeter": "mm", "millimeters": "mm",
            "decibel": "dBA", "decibels": "dBA", "rpm": "RPM"
        }

    if not DECIMAL_FRACTIONS:
        DECIMAL_FRACTIONS = {
            0.5: "1/2", 0.25: "1/4", 0.75: "3/4",
            0.125: "1/8", 0.375: "3/8", 0.625: "5/8",
            0.875: "7/8", 0.0625: "1/16", 0.045: ".045"
        }

    seed_brands = [
        "3M", "GE", "GE Appliances", "Speed Queen", "SQ", "Whirlpool", "Frigidaire", "Rheem", "SKF",
        "Milwaukee", "Milw", "DeWalt", "Dewlt", "Bosch", "Makita", "Paslode", "Stabila", "Lenox",
        "Irwin", "Satco", "Schumacher", "Andersen", "Nicholson", "Mafell", "Fisch", "Barrette",
        "Vessel", "Tech Gear", "Kichler", "Hunter", "Festool", "Kreg", "Edge Eyewear", "Diablo",
        "Mirka", "Freud", "AJM", "BRK", "CENTURY COMPONENTS", "Carlon", "DSI Westbury", "Dremel",
        "Feit Electric", "First Alert", "GT-Lite", "HAGER", "JAMESHARDIE", "LP SMARTSIDE", "Leviton",
        "PROVIA", "Philips", "Police Security", "Prime", "Southwire", "Square D", "StealthMounts",
        "TIMBERTECH", "TREX", "United Window & Door", "Wiz"
    ]
    for b in seed_brands:
        if b not in BRAND_LIST:
            BRAND_LIST.append(b)

    seed_mfrs = [
        "3M Company", "GE Appliances", "Alliance Laundry Systems", "Whirlpool Corporation", "Frigidaire",
        "Rheem Manufacturing", "SKF", "Milwaukee Tool", "DeWalt Industrial Tool Co.", "Robert Bosch GmbH",
        "Makita Corporation", "Kichler Lighting", "Hunter Fan Company", "Festool", "Satco Products",
        "Andersen Corporation", "Southwire Company", "First Alert - BRK Brands", "Schumacher Electric"
    ]
    for m in seed_mfrs:
        if m not in MANUFACTURER_LIST:
            MANUFACTURER_LIST.append(m)

CANONICAL_BRAND_MAP = {
    "frigidaire": "FRIGIDAIRE®",
    "frigidaire gallery": "FRIGIDAIRE®",
    "frigidaire professional": "FRIGIDAIRE®",
    "pdsh": "FRIGIDAIRE®",
    "3m": "3M®",
    "ge": "GE®",
    "ge appliances": "GE®",
    "cafe": "CAFÉ®",
    "café": "CAFÉ®",
    "speed queen": "SPEED QUEEN®",
    "sq": "SPEED QUEEN®",
    "whirlpool": "WHIRLPOOL®",
    "dewalt": "DEWALT®",
    "dewlt": "DEWALT®",
    "milwaukee": "MILWAUKEE®",
    "milw": "MILWAUKEE®",
    "bosch": "BOSCH®",
    "makita": "MAKITA®",
    "rheem": "RHEEM®",
    "skf": "SKF®",
    "mirka": "MIRKA®",
    "freud": "FREUD®",
    "diablo": "DIABLO®",
    "lenox": "LENOX®",
    "irwin": "IRWIN®",
    "festool": "FESTOOL®",
    "southwire": "SOUTHWIRE®",
    "square d": "SQUARE D®",
    "leviton": "LEVITON®",
    "first alert": "FIRST ALERT®",
    "brk": "BRK®",
    "dremel": "DREMEL®",
    "philips": "PHILIPS®",
    "phillips": "PHILIPS®",
    "kichler": "KICHLER®",
    "trex": "TREX®",
    "timbertech": "TIMBERTECH®",
    "u s tape": "U S TAPE®",
    "u s lumber": "U S LUMBER®",
    "satco": "SATCO®",
    "kreg": "KREG®",
    "edge eyewear": "EDGE EYEWEAR®",
    "hunter": "HUNTER®",
    "vessel": "VESSEL®",
    "sawstop": "SAWSTOP®",
    "bow": "BOW®"
}

CANONICAL_MFR_MAP = {
    "frigidaire": "Rheem Manufacturing",
    "pdsh": "Rheem Manufacturing",
    "rheem": "Rheem Manufacturing",
    "ge": "GE Appliances",
    "ge appliances": "GE Appliances",
    "3m": "3M Company",
    "alliance": "Alliance Laundry Systems",
    "speed queen": "Alliance Laundry Systems",
    "whirlpool": "Whirlpool Corporation",
    "dewalt": "DeWalt Industrial Tool Co.",
    "black & decker": "DeWalt Industrial Tool Co.",
    "bosch": "Robert Bosch GmbH",
    "makita": "Makita Corporation",
    "milwaukee": "Milwaukee Tool",
    "skf": "SKF Group",
    "mirka": "Mirka Ltd.",
    "freud": "Freud Tools",
    "southwire": "Southwire Company",
    "schumacher": "Schumacher Electric Corporation",
    "first alert": "First Alert - BRK Brands",
    "andersen": "Andersen Corporation",
    "phillips": "Signify Netherlands N.V.",
    "philips": "Signify Netherlands N.V.",
    "boise cascade": "Boise Cascade Company",
    "appliance dealers": "Appliance Dealers Cooperative",
    "kichler": "Kichler Lighting LLC",
    "parksite": "Parksite Inc.",
    "timbertech": "The AZEK Company Inc.",
    "u s lumber": "U.S. LUMBER Group",
    "satco": "Satco Products Inc.",
    "leviton": "Leviton Manufacturing Co.",
    "festool": "Festool USA",
    "tech gear": "Custom LeatherCraft / CLC",
    "kreg": "Kreg Tool Company",
    "edge eyewear": "Wolf Peak International Inc.",
    "u s tape": "U.S. Tape Company",
    "hunter": "Hunter Fan Company",
    "palmer donavin": "Palmer-Donavin Co.",
    "premier metals": "Premier Metals Inc.",
    "jam industrial": "Jam Industrial Supply LLC",
    "vessel": "Vessel Tools USA Inc.",
    "oliver": "Oliver Machinery Company",
    "prime wire": "Prime Wire & Cable Inc.",
    "bow": "Bow Products LLC",
    "saw stop": "SawStop LLC",
    "rees cast": "Rees Cast Stone Company"
}

def resolve_canonical_brand_and_mfr(raw_brand, raw_mfr, mpn="", desc=""):
    b_norm = (raw_brand or "").strip().lower()
    m_norm = (raw_mfr or "").strip().lower()
    mpn_norm = (mpn or "").strip().lower()
    desc_norm = (desc or "").strip().lower()

    resolved_b = None
    for k, v in CANONICAL_BRAND_MAP.items():
        if k == b_norm or k in b_norm or k in mpn_norm or k in desc_norm:
            resolved_b = v
            break

    if not resolved_b:
        if raw_brand and raw_brand != "UNKNOWN" and ("®" in raw_brand or "™" in raw_brand):
            resolved_b = raw_brand.strip()
        elif raw_brand and raw_brand != "UNKNOWN" and raw_brand.strip():
            resolved_b = raw_brand.strip().upper() + "®"
        else:
            resolved_b = "GENERAL®"

    resolved_m = None
    for k, v in CANONICAL_MFR_MAP.items():
        if k == m_norm or k in m_norm or k in b_norm or k in mpn_norm:
            resolved_m = v
            break

    if not resolved_m or resolved_m.strip().upper() in ["UNKNOWN", "NO PART MANUF", "NO MANUFACTURER", "-- NO PART MANUF --"]:
        if raw_mfr and raw_mfr.strip() and raw_mfr.strip().upper() not in ["UNKNOWN", "NO PART MANUF", "NO MANUFACTURER", "-- NO PART MANUF --"]:
            resolved_m = raw_mfr.strip()
        elif resolved_b and resolved_b.strip().upper() not in ["UNKNOWN", "GENERAL®"]:
            import re
            b_clean = re.sub(r'[®™]', '', resolved_b).strip()
            resolved_m = f"{b_clean} Inc."
        else:
            resolved_m = "General Industrial Products"

    return resolved_b, resolved_m

# Automatically trigger load on import
load_all_references()
