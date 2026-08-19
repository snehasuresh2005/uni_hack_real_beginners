import hashlib
from backend.database import get_db_connection
from backend.preprocessing.cleaner import normalize_manufacturer, normalize_brand, clean_text

def compute_fingerprint(manufacturer, brand, mpn, part_desc):
    """Return a reusable semantic cache key.

    MPN is intentionally excluded: it is a catalog identifier, while this cache is
    for identical normalized product content across supplier feeds.  The exact
    description remains part of the key, so variants with different dimensions do
    not share extracted attributes.
    """
    m = normalize_manufacturer(manufacturer).lower()
    b = normalize_brand(brand).lower()
    d = clean_text(part_desc).lower()

    raw = f"v2|{m}|{b}|{d}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def find_cached_product(fingerprint, cursor=None):
    own_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        own_conn = True
        
    try:
        p = cursor.execute("SELECT * FROM products WHERE fingerprint = ? AND status = 'completed' LIMIT 1", (fingerprint,)).fetchone()
        if not p:
            return None
            
        attrs = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (p["id"],)).fetchall()
        return dict(p), [dict(a) for a in attrs]
    finally:
        if own_conn:
            cursor.connection.close()

def save_fingerprint(product_id, fingerprint, cursor=None):
    if cursor is not None:
        cursor.execute("UPDATE products SET fingerprint = ? WHERE id = ?", (fingerprint, product_id))
        return
        
    def do_write(c):
        c.execute("UPDATE products SET fingerprint = ? WHERE id = ?", (fingerprint, product_id))
    from backend.database import db_writer
    db_writer.execute(do_write, wait=True)
