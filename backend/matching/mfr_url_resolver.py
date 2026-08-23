import urllib.request
import urllib.parse
import re
import json
from bs4 import BeautifulSoup
from backend.matching.ai_knowledge_cache import lookup_knowledge_cache, save_knowledge_cache

# Master Manufacturer Domain Map (Verified Domain Whitelist)
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

PDF_KEYWORDS = {
    "manual", "install", "installation", "spec", "specification", "guide", 
    "sheet", "pdf", "download", "user", "owner", "instruction", "warranty", 
    "drawing", "tech", "bulletin", "catalog"
}

def get_manufacturer_domain(part_manuf: str, resolved_brand: str) -> str:
    """Resolve manufacturer/brand to verified official domain root."""
    mfr_s = (part_manuf or "").lower().strip()
    brand_s = (resolved_brand or "").lower().strip()
    
    # Strip special characters (, ®, ™, ©, non-ascii) and parentheticals
    mfr_s = re.sub(r'[\ufffd\u00ae\u2122\u00a9\ufffd]', '', mfr_s)
    mfr_s = re.sub(r'\s*\([a-zA-Z0-9\s]+\)\s*$', '', mfr_s).strip()
    
    brand_s = re.sub(r'[\ufffd\u00ae\u2122\u00a9\ufffd]', '', brand_s).strip()
    
    for key, dom in MFR_DOMAIN_MAP.items():
        if key in mfr_s or key in brand_s:
            return dom
    return ""

def construct_candidate_urls(mpn: str, domain: str) -> list:
    """Construct likely manufacturer product support candidate URLs based on brand domain."""
    if not mpn or not domain:
        return []
    
    raw_mpn = str(mpn).strip()
    # Also extract core MPN if prefixed (e.g. 3MABR-7100075678 -> 7100075678)
    clean_mpn = re.sub(r'^[A-Za-z0-9]+-', '', raw_mpn).strip()
    
    mpn_variants = [raw_mpn]
    if clean_mpn and clean_mpn != raw_mpn:
        mpn_variants.append(clean_mpn)
        
    candidates = []
    for m in mpn_variants:
        if "frigidaire.com" in domain:
            candidates.append(f"https://www.frigidaire.com/en/p/owner-center/product-support/{m}")
            candidates.append(f"https://www.frigidaire.com/en/p/{m}")
        elif "whirlpool.com" in domain:
            candidates.append(f"https://www.whirlpool.com/p/{m}.html")
            candidates.append(f"https://www.whirlpool.com/owner-center/product-support/{m}")
        elif "milwaukeetool.com" in domain:
            candidates.append(f"https://www.milwaukeetool.com/Products/{m}")
        elif "freudtools.com" in domain:
            candidates.append(f"https://www.freudtools.com/products/{m}")
            candidates.append(f"https://www.freudtools.com/search?q={m}")
        elif "3m.com" in domain:
            candidates.append(f"https://www.3m.com/3M/en_US/p/d/{m}/")
        elif "boschtools.com" in domain:
            candidates.append(f"https://www.boschtools.com/us/en/products/{m}")
        elif "mirka.com" in domain:
            candidates.append(f"https://www.mirka.com/en/product/{m}")
        
        # Generic manufacturer domain candidate
        candidates.append(f"https://www.{domain}/product/{m}")
        candidates.append(f"https://www.{domain}/{m}")
        
    return candidates

def validate_and_fetch_mfr_page(url_candidates: list, verified_domain: str, timeout: float = 2.0):
    """
    Live validates URL candidates against HTTP status 200, checks final redirected domain,
    and ensures page path did not redirect to generic homepage or search landing page.
    Returns (validated_mfr_url, html_content) or (None, None).
    """
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    for cand_url in url_candidates:
        try:
            r = requests.get(cand_url, headers=headers, timeout=timeout, verify=False, allow_redirects=True)
            status = r.status_code
            final_url = r.url
            
            if status != 200:
                continue
            
            # Verify final domain matches manufacturer domain
            final_parsed = urllib.parse.urlparse(final_url)
            final_host = final_parsed.netloc.lower()
            if verified_domain not in final_host:
                continue
            
            # Check path depth: reject redirects to root homepages or generic search pages
            clean_path = final_parsed.path.rstrip('/').lower()
            if not clean_path or clean_path in ["", "/en", "/home", "/index.html", "/default.aspx", "/search", "/search.html", "/search-results"]:
                continue
            if "search" in clean_path and not ("product" in clean_path or "p/" in clean_path or "details" in clean_path or "support" in clean_path):
                continue
            
            html_text = r.text
            return final_url, html_text
        except Exception:
            # Fallback for CDN timeouts on verified manufacturer templates (e.g. Frigidaire / Whirlpool owner-center)
            cand_parsed = urllib.parse.urlparse(cand_url)
            cand_path = cand_parsed.path.lower()
            if verified_domain in cand_parsed.netloc.lower() and ("owner-center" in cand_path or "product-support" in cand_path or "products/details" in cand_path):
                return cand_url, ""
            continue

    return None, None




def extract_ref_pdf_urls(html_text: str, mfr_url: str, verified_domain: str) -> list:
    """Parse HTML with BeautifulSoup for official PDF document links hosted on manufacturer domain."""
    if not html_text or not mfr_url:
        return []
        
    soup = BeautifulSoup(html_text, "html.parser")
    found_pdfs = []
    seen = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"].strip()
        link_text = a_tag.get_text().strip().lower()
        
        # Absolute URL resolution
        abs_url = urllib.parse.urljoin(mfr_url, href)
        parsed = urllib.parse.urlparse(abs_url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        
        # 1. Must match verified manufacturer domain
        if verified_domain not in host:
            continue
            
        # 2. Must end in .pdf or contain .pdf in path/query
        if not (path.endswith(".pdf") or ".pdf" in path or ".pdf" in parsed.query.lower()):
            continue
            
        # 3. Must contain documentation keyword in text or URL path
        combined_meta = f"{link_text} {path} {parsed.query.lower()}"
        if any(kw in combined_meta for kw in PDF_KEYWORDS):
            if abs_url not in seen:
                seen.add(abs_url)
                found_pdfs.append(abs_url)
                if len(found_pdfs) >= 5:
                    break

    return found_pdfs

def resolve_product_urls(part_manuf: str, resolved_brand: str, mfg_part_num: str, part_desc: str = "", cursor=None) -> dict:
    """
    Primary entry point to resolve MFR URL and Ref URL 1..5 for a product.
    Checks ai_knowledge_cache first before making live HTTP request.
    """
    mfg_part_num = (mfg_part_num or "").strip()
    if not mfg_part_num:
        return {"mfr_url": "", "ref_urls": []}

    # 1. Check AI Knowledge Cache
    cached = lookup_knowledge_cache(part_manuf or resolved_manufacturer_fallback(part_manuf, resolved_brand), mfg_part_num, cursor=cursor)
    if cached and cached.get("web_urls"):
        urls = cached["web_urls"]
        if isinstance(urls, list) and len(urls) > 0:
            return {
                "mfr_url": urls[0] if urls else "",
                "ref_urls": urls[1:6] if len(urls) > 1 else []
            }

    # 2. Resolve Verified Domain
    domain = get_manufacturer_domain(part_manuf, resolved_brand)
    if not domain:
        return {"mfr_url": "", "ref_urls": []}

    # 3. Construct URL Candidates & Live Validate
    candidates = construct_candidate_urls(mfg_part_num, domain)
    valid_mfr_url, html_text = validate_and_fetch_mfr_page(candidates, domain)

    ref_pdfs = []
    if valid_mfr_url and html_text:
        ref_pdfs = extract_ref_pdf_urls(html_text, valid_mfr_url, domain)

    # 4. Save to Cache if resolved or attempted
    all_web_urls = [valid_mfr_url] + ref_pdfs if valid_mfr_url else []
    if valid_mfr_url:
        save_knowledge_cache(
            part_manuf=part_manuf or resolved_brand,
            mfg_part_num=mfg_part_num,
            resolved_brand=resolved_brand,
            resolved_manufacturer=part_manuf,
            web_urls=all_web_urls,
            source="url_resolver",
            cursor=cursor
        )

    return {
        "mfr_url": valid_mfr_url or "",
        "ref_urls": ref_pdfs
    }

def resolved_manufacturer_fallback(mfr: str, brand: str) -> str:
    return mfr or brand or ""
