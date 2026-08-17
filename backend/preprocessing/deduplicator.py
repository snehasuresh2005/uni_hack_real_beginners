import re
import difflib
from backend.database import get_db_connection
from backend.preprocessing.cleaner import clean_text, normalize_placeholder, normalize_manufacturer, normalize_brand

def normalize_text_for_dup(text):
    if not text:
        return ""
    t = str(text).lower()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', '', t)
    return t

def check_duplicate(product_id, mfg_part_num, part_desc, part_manuf, brand_name, cursor=None):
    """
    Check if a product is a duplicate of any ALREADY APPROVED or COMPLETED product in the database.
    Returns: (duplicate_id, level_reason) or (None, None)
    """
    own_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        own_conn = True
        
    try:
        # Load other completed/flagged products
        others = cursor.execute(
            "SELECT id, mfg_part_num, part_desc, part_manuf, e1_brand, unilog_brand, dib_brand FROM products WHERE id != ? AND status IN ('completed', 'flagged_hitl')",
            (product_id,)
        ).fetchall()
    finally:
        if own_conn:
            cursor.connection.close()
            
    # Clean input
    mpn_in = str(mfg_part_num).strip().lower()
    desc_in = clean_text(part_desc)
    manuf_in = normalize_manufacturer(part_manuf).lower()
    brand_in = normalize_brand(brand_name).lower()
    
    desc_norm_in = normalize_text_for_dup(desc_in)
    
    for row in others:
        other_id = row["id"]
        other_mpn = str(row["mfg_part_num"]).strip().lower()
        other_desc = clean_text(row["part_desc"])
        other_manuf = normalize_manufacturer(row["part_manuf"]).lower()
        other_brand = normalize_brand(row["e1_brand"] or row["unilog_brand"] or row["dib_brand"] or "").lower()
        
        other_desc_norm = normalize_text_for_dup(other_desc)
        
        # If both products have valid, non-empty MPNs and they are different, they are not duplicates.
        if mpn_in and other_mpn and mpn_in != "nan" and other_mpn != "nan" and mpn_in != other_mpn:
            continue
        
        # Level 1: Exact row/field duplicate
        if mpn_in == other_mpn and desc_in.lower() == other_desc.lower() and manuf_in == other_manuf:
            return other_id, "Level 1: Exact Duplicate"
            
        # Level 2: Product Identity duplicate (manufacturer + brand + MPN, or brand + MPN)
        if mpn_in == other_mpn and mpn_in != "" and mpn_in != "nan":
            if manuf_in == other_manuf and brand_in == other_brand:
                return other_id, "Level 2: Product Identity Duplicate (Mfg + Brand + MPN)"
            elif brand_in == other_brand and brand_in != "unbranded":
                return other_id, "Level 2: Product Identity Duplicate (Brand + MPN)"
                
        # Level 3: Normalized textual duplicate
        if desc_norm_in == other_desc_norm and desc_norm_in != "":
            return other_id, "Level 3: Normalized Textual Duplicate"
            
        # Level 4: Fuzzy duplicate (Description similarity >= 92% and same brand/manufacturer)
        if (brand_in == other_brand or manuf_in == other_manuf) and brand_in != "unbranded":
            ratio = difflib.SequenceMatcher(None, desc_in.lower(), other_desc.lower()).ratio()
            if ratio >= 0.92:
                return other_id, f"Level 4: Fuzzy Duplicate ({int(ratio*100)}% match)"
                
    return None, None
