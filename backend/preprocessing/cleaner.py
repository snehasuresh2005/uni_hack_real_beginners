import re
import difflib
from backend.ingestion.loader import UOM_ABBREVIATIONS, DECIMAL_FRACTIONS, MANUFACTURER_LIST, BRAND_LIST

def normalize_placeholder(val):
    if not val or str(val).strip().lower() == "nan":
        return ""
    val_s = str(val).strip()
    placeholders = [
        "nan", "none", "unknown", "n/a", "na", "-", "--", "display only",
        "-- unbranded --", "-- no unilog brand --", "-- no dib brand --"
    ]
    if val_s.lower() in placeholders:
        return ""
    return val_s

def clean_text(val):
    if not val:
        return ""
    val_s = str(val).strip()
    val_s = re.sub(r'\s+', ' ', val_s)
    return val_s

def normalize_case(val, mode="upper"):
    if not val:
        return ""
    val_s = str(val).strip()
    if mode == "upper":
        return val_s.upper()
    elif mode == "lower":
        return val_s.lower()
    elif mode == "title":
        return val_s.title()
    return val_s

def normalize_manufacturer(val):
    cleaned = normalize_placeholder(val)
    if not cleaned:
        return "UNKNOWN"
    
    # Remove standard registered symbols
    cleaned_norm = re.sub(r'[®™]', '', cleaned).strip()
    
    # Case-insensitive lookup against canonical list
    for canonical in MANUFACTURER_LIST:
        canon_norm = re.sub(r'[®™]', '', canonical).strip()
        if cleaned_norm.lower() == canon_norm.lower() or cleaned_norm.lower().startswith(canon_norm.lower()) or canon_norm.lower().startswith(cleaned_norm.lower()):
            return canonical
            
    # Fuzzy match lookup
    matches = difflib.get_close_matches(cleaned_norm, MANUFACTURER_LIST, n=1, cutoff=0.7)
    if matches:
        return matches[0]
        
    return cleaned

def normalize_brand(val):
    cleaned = normalize_placeholder(val)
    if not cleaned:
        return "UNKNOWN"
    
    cleaned_norm = re.sub(r'[®™]', '', cleaned).strip()
    c_lower = cleaned_norm.lower()
    
    from backend.ingestion.loader import CANONICAL_BRAND_MAP, BRAND_LIST
    
    # 1. Direct match against CANONICAL_BRAND_MAP
    for k, v in CANONICAL_BRAND_MAP.items():
        if k == c_lower or k in c_lower:
            return v
            
    # 2. Case-insensitive match against BRAND_LIST
    matched_brand = None
    for canonical in BRAND_LIST:
        canon_norm = re.sub(r'[®™]', '', canonical).strip()
        if c_lower == canon_norm.lower() or c_lower.startswith(canon_norm.lower()) or canon_norm.lower().startswith(c_lower):
            matched_brand = canonical
            break
            
    if not matched_brand:
        matches = difflib.get_close_matches(cleaned_norm, BRAND_LIST, n=1, cutoff=0.7)
        if matches:
            matched_brand = matches[0]
            
    if matched_brand:
        mb_lower = matched_brand.lower()
        for k, v in CANONICAL_BRAND_MAP.items():
            if k == mb_lower or k in mb_lower:
                return v
        if not matched_brand.endswith("®") and not matched_brand.endswith("™"):
            return matched_brand.upper() + "®"
        return matched_brand
        
    return cleaned

def normalize_uom(val):
    if not val:
        return ""
    val_s = str(val).strip().lower()
    if val_s in UOM_ABBREVIATIONS:
        return UOM_ABBREVIATIONS[val_s]
    # Check if suffix matches
    for key, abbrev in UOM_ABBREVIATIONS.items():
        if val_s.endswith(key):
            return abbrev
    return val

def normalize_fraction(val):
    if val is None or str(val).strip() == "":
        return ""
    try:
        val_f = float(val)
        if val_f in DECIMAL_FRACTIONS:
            return DECIMAL_FRACTIONS[val_f]
        rounded = round(val_f, 4)
        if rounded in DECIMAL_FRACTIONS:
            return DECIMAL_FRACTIONS[rounded]
    except ValueError:
        pass
    return str(val)

def normalize_attribute_value(val, uom=""):
    cleaned = normalize_placeholder(val)
    if not cleaned:
        return ""
        
    # Check if value already has UOM merged inside
    if uom:
        cleaned = re.sub(rf'\s*{re.escape(uom)}\b', '', cleaned, flags=re.I).strip()
        cleaned = re.sub(rf'\s*{re.escape(normalize_uom(uom))}\b', '', cleaned, flags=re.I).strip()
        
    return cleaned

def normalize_manufacturer_to_brand(val):
    cleaned = normalize_placeholder(val)
    if not cleaned:
        return ""
    
    # 1. Strip trailing parenthetical codes e.g. "Kichler Lighting (KICLI)" -> "Kichler Lighting"
    cleaned = re.sub(r'\s*\([^)]*\)', '', cleaned).strip()
    
    # 2. Strip slashes or sub-brand text generically if present e.g. "Brand A / Brand B"
    if "/" in cleaned:
        parts = [p.strip() for p in cleaned.split("/")]
        cleaned = parts[0]
    
    # 3. Strip common legal, corporate, and business suffixes generically
    legal_patterns = [
        r'\bInc\.?\b', r'\bCo\.?\b', r'\bLtd\.?\b', r'\bCorp\.?\b', r'\bCorporation\b',
        r'\bLLC\b', r'\bUSA\b', r'\bGroup\b', r'\bInternational\b', r'\bIntl\.?\b', r'\bMfg\.?\b',
        r'\bCompany\b', r'\bProd\.?\b', r'\bProducts\b', r'\bSupply\b', r'\bIndustries\b'
    ]
    for pat in legal_patterns:
        cleaned = re.sub(pat, '', cleaned, flags=re.I).strip()
        
    # Clean up punctuation and whitespace
    cleaned = re.sub(r'[\s,-]+$', '', cleaned).strip()
    cleaned = re.sub(r'^\s*[\s,-]+', '', cleaned).strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    return cleaned.strip()



