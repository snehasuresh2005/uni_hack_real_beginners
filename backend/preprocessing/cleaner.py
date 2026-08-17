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
    for canonical in BRAND_LIST:
        canon_norm = re.sub(r'[®™]', '', canonical).strip()
        if cleaned_norm.lower() == canon_norm.lower() or cleaned_norm.lower().startswith(canon_norm.lower()) or canon_norm.lower().startswith(cleaned_norm.lower()):
            return canonical
            
    matches = difflib.get_close_matches(cleaned_norm, BRAND_LIST, n=1, cutoff=0.7)
    if matches:
        return matches[0]
        
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
