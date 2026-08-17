import hashlib
from backend.database import get_db_connection
from backend.preprocessing.cleaner import normalize_manufacturer, normalize_brand, clean_text

def compute_fingerprint(manufacturer, brand, mpn, part_desc):
    m = normalize_manufacturer(manufacturer).lower()
    b = normalize_brand(brand).lower()
    p = str(mpn).strip().lower()
    d = clean_text(part_desc).lower()
    
    raw = f"{m}|{b}|{p}|{d}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def find_cached_product(fingerprint, cursor=None):
    own_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        own_conn = True
        
    try:
        # Ensure fingerprint column exists
        try:
            cursor.execute("ALTER TABLE products ADD COLUMN fingerprint TEXT")
            if own_conn:
                cursor.connection.commit()
        except Exception:
            pass
            
        p = cursor.execute("SELECT * FROM products WHERE fingerprint = ? AND status = 'completed' LIMIT 1", (fingerprint,)).fetchone()
        if not p:
            return None
            
        attrs = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (p["id"],)).fetchall()
        return dict(p), [dict(a) for a in attrs]
    finally:
        if own_conn:
            cursor.connection.close()

def save_fingerprint(product_id, fingerprint, cursor=None):
    own_conn = False
    if cursor is None:
        conn = get_db_connection()
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.cursor()
        own_conn = True
        
    try:
        try:
            cursor.execute("ALTER TABLE products ADD COLUMN fingerprint TEXT")
        except Exception:
            pass
            
        cursor.execute("UPDATE products SET fingerprint = ? WHERE id = ?", (fingerprint, product_id))
        if own_conn:
            cursor.connection.commit()
    finally:
        if own_conn:
            cursor.connection.close()
