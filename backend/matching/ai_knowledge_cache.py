import json
import re
import hashlib
from datetime import datetime
from backend.database import get_db_connection, db_writer
from backend.preprocessing.cleaner import normalize_manufacturer, normalize_brand, clean_text

DISTRIBUTOR_PATTERNS = [
    "jam industrial", "industrial supply", "distributors", "supply llc", "vendor",
    "dealers cooperative", "appliance dealers", "cooperative", "supply co", "supply inc"
]

def is_distributor_string(val: str) -> bool:
    if not val:
        return False
    val_lower = str(val).lower()
    return any(pat in val_lower for pat in DISTRIBUTOR_PATTERNS)

def extract_mfg_prefix(mfg_part_num: str) -> str:
    """Extract first alphanumeric block or prefix from MPN (e.g. '5B-332-080' -> '5B', 'MID66302' -> 'MID')."""
    if not mfg_part_num:
        return ""
    clean_mpn = str(mfg_part_num).strip().upper()
    match = re.match(r'^([A-Z0-9]{2,5})', clean_mpn)
    if match:
        return match.group(1)
    return clean_mpn[:4]

def compute_pattern_key(part_manuf: str, mfg_part_num: str) -> str:
    """Compute a reusable pattern key for manufacturer + MPN family prefix. Excludes distributor strings."""
    if is_distributor_string(part_manuf):
        mfr = ""
    else:
        mfr = normalize_manufacturer(part_manuf or "").lower()
    prefix = extract_mfg_prefix(mfg_part_num or "").lower()
    raw = f"pat|{mfr}|{prefix}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def lookup_knowledge_cache(part_manuf: str, mfg_part_num: str, cursor=None) -> dict:
    """Look up cached AI suggestions / web reference knowledge for similar products."""
    pattern_key = compute_pattern_key(part_manuf, mfg_part_num)
    own_conn = False
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        own_conn = True

    try:
        # 1. Exact pattern key match (same manufacturer & MPN prefix) ONLY
        row = cursor.execute(
            "SELECT * FROM ai_knowledge_cache WHERE pattern_key = ? ORDER BY id DESC LIMIT 1",
            (pattern_key,)
        ).fetchone()

        # Fix 2: Distributor fallback lookup ("WHERE part_manuf = ?") REMOVED to prevent cross-brand contamination.

        if not row:
            return None

        result = dict(row)
        if result.get("web_urls"):
            try:
                result["web_urls"] = json.loads(result["web_urls"])
            except Exception:
                result["web_urls"] = []
        else:
            result["web_urls"] = []

        if result.get("attributes_json"):
            try:
                result["attributes"] = json.loads(result["attributes_json"])
            except Exception:
                result["attributes"] = []
        else:
            result["attributes"] = []

        return result
    finally:
        if own_conn:
            cursor.connection.close()

def save_knowledge_cache(
    part_manuf: str,
    mfg_part_num: str,
    resolved_brand: str = "",
    resolved_manufacturer: str = "",
    classpath: str = "",
    web_urls: list = None,
    attributes: list = None,
    source: str = "ai_assist",
    cursor=None
):
    """Save or update learned resolution pattern and web reference URLs to the cache."""
    norm_mfr = normalize_manufacturer(part_manuf or resolved_manufacturer or "")
    mfg_prefix = extract_mfg_prefix(mfg_part_num or "")
    pattern_key = compute_pattern_key(part_manuf, mfg_part_num)
    
    web_urls_str = json.dumps(web_urls if web_urls else [])
    attrs_str = json.dumps(attributes if attributes else [])
    now = datetime.now().isoformat()

    def _do_save(c):
        if source == "url_resolver":
            # Fix 1: URL resolver MUST NEVER write or overwrite resolved_brand / resolved_manufacturer
            c.execute("""
            INSERT INTO ai_knowledge_cache (
                pattern_key, part_manuf, mfg_prefix, resolved_brand,
                resolved_manufacturer, classpath, web_urls, attributes_json, source, created_at
            ) VALUES (?, ?, ?, '', '', ?, ?, ?, ?, ?)
            ON CONFLICT(pattern_key) DO UPDATE SET
                web_urls = excluded.web_urls,
                created_at = excluded.created_at
            """, (
                pattern_key, norm_mfr, mfg_prefix, classpath or "", web_urls_str, attrs_str, source, now
            ))
        else:
            c.execute("""
            INSERT INTO ai_knowledge_cache (
                pattern_key, part_manuf, mfg_prefix, resolved_brand,
                resolved_manufacturer, classpath, web_urls, attributes_json, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pattern_key) DO UPDATE SET
                resolved_brand = CASE WHEN excluded.resolved_brand != '' THEN excluded.resolved_brand ELSE ai_knowledge_cache.resolved_brand END,
                resolved_manufacturer = CASE WHEN excluded.resolved_manufacturer != '' THEN excluded.resolved_manufacturer ELSE ai_knowledge_cache.resolved_manufacturer END,
                classpath = CASE WHEN excluded.classpath != '' THEN excluded.classpath ELSE ai_knowledge_cache.classpath END,
                web_urls = CASE WHEN excluded.web_urls != '[]' THEN excluded.web_urls ELSE ai_knowledge_cache.web_urls END,
                attributes_json = CASE WHEN excluded.attributes_json != '[]' THEN excluded.attributes_json ELSE ai_knowledge_cache.attributes_json END,
                source = excluded.source,
                created_at = excluded.created_at
            """, (
                pattern_key, norm_mfr, mfg_prefix, resolved_brand or "",
                resolved_manufacturer or "", classpath or "", web_urls_str, attrs_str, source, now
            ))

    if cursor is not None:
        _do_save(cursor)
    else:
        db_writer.execute(_do_save, wait=True)
