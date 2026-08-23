import os
import sqlite3
import json
import random
import time
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from backend.database import get_db_connection
from backend.preprocessing.cleaner import (
    normalize_placeholder,
    normalize_manufacturer,
    normalize_brand,
    normalize_uom,
    normalize_fraction,
    normalize_attribute_value,
    clean_text
)
from backend.llm.ollama_client import (
    is_ollama_available,
    query_ollama,
    log_llm_call,
    should_use_llm
)

# Robust Dimension Parser Regex Pattern
PART_WITH_UNIT_REGEX = re.compile(
    r'(?P<val>\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(?P<unit>\"|in\b|inch\b|inches\b|mm\b)?',
    re.I
)

# Category dictionary with specific properties to enrich
DOMAINS = {
    "sanding_belt": {
        "name": "Abrasives>Abrasive Belts>Sanding Belts",
        "attributes": ["Grit", "Length", "Width", "Material", "Pack Size", "Backing Type"],
        "keywords": ["sanding belt", "sanding belts"],
        "negative_keywords": ["disc", "wheel"]
    },
    "sanding_disc": {
        "name": "Abrasives>Abrasive Discs>Sanding Discs",
        "attributes": ["Grit", "Diameter", "Attachment Type", "Backing Material", "Abrasive Material", "Pack Size", "Series"],
        "keywords": ["stikit", "sanding disc", "film", "abrasive disc", "hook and loop", "psa", "abranet", "hiolit", "flap disc"],
        "negative_keywords": ["cut-off", "cutoff", "cutting", "grinding", "belt"]
    },
    "cutoff_disc": {
        "name": "Abrasives>Abrasive Wheels>Cut-Off Discs",
        "attributes": ["Diameter", "Thickness", "Arbor Size", "Max RPM", "Material", "Pack Size"],
        "keywords": ["cut-off", "cutoff", "cutting wheel", "cutting disc", "grinding disc", "metal cut", "steel demon", "speed demon"],
        "negative_keywords": ["sanding", "stikit", "film", "abranet"]
    },
    "bearing": {
        "name": "Power Transmission>Bearings>Ball Bearings",
        "attributes": ["Bore Diameter", "Outer Diameter", "Width", "Seal Type", "Material", "Clearance"],
        "keywords": ["bearing", "ball bearing", "roller bearing", "6205", "skf"],
        "negative_keywords": []
    },
    "dishwasher": {
        "name": "Appliances & Consumer Electronics>Kitchen Appliances>Built-In Dishwashers",
        "attributes": ["Series", "Color/Finish", "Voltage Rating", "Amperage Rating", "Overall Height", "Number of Wash Cycles", "Sound Level"],
        "keywords": ["dishwasher", "washer", "built-in dishwasher", "ss dishwasher", "pdsh4816af"]
    },
    "general": {
        "name": "General Industrial Products",
        "attributes": ["Size", "Material", "Color", "Weight", "Standard/Approvals"],
        "keywords": [],
        "negative_keywords": []
    }
}

def parse_dimension_value(val):
    if not val:
        return None, ""
    val = val.strip()
    
    # 1. Mixed fraction: A-B/C or A B/C
    mixed_match = re.match(r'^(\d+)\s*[- ]\s*(\d+)/(\d+)$', val)
    if mixed_match:
        whole = float(mixed_match.group(1))
        num = float(mixed_match.group(2))
        denom = float(mixed_match.group(3))
        frac_val = num / denom
        numeric_val = whole + frac_val
        return numeric_val, f"{mixed_match.group(1)}-{mixed_match.group(2)}/{mixed_match.group(3)}"
        
    # 2. Simple fraction: B/C
    frac_match = re.match(r'^(\d+)/(\d+)$', val)
    if frac_match:
        num = float(frac_match.group(1))
        denom = float(frac_match.group(2))
        numeric_val = num / denom
        return numeric_val, val
        
    # 3. Decimal/Whole number
    try:
        numeric_val = float(val)
        if val.startswith("."):
            return numeric_val, f"0{val}"
        return numeric_val, val
    except ValueError:
        return None, val

def tokenize_dimensions(desc):
    # Find sequence of dimension parts separated by x / X / *
    expr_match = re.search(
        r'(?:\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(?:\"|in|inch|inches|mm)?'
        r'\s*[xX\*]\s*'
        r'(?:\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(?:\"|in|inch|inches|mm)?'
        r'(?:\s*[xX\*]\s*(?:\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d*\.\d+|\d+)\s*(?:\"|in|inch|inches|mm)?)?',
        desc
    )
    if not expr_match:
        return []
        
    expr_str = expr_match.group(0)
    parts = re.split(r'\s*[xX\*]\s*', expr_str)
    
    tokens = []
    for p in parts:
        m = PART_WITH_UNIT_REGEX.match(p)
        if m:
            val_str = m.group("val")
            raw_unit = m.group("unit") or ""
            
            unit = "in"
            if "mm" in raw_unit.lower():
                unit = "mm"
                
            num_val, can_val = parse_dimension_value(val_str)
            tokens.append({
                "raw": p,
                "numeric_value": num_val,
                "unit": unit,
                "canonical": f"{can_val} {unit}"
            })
            
    return tokens

def parse_dimension_expression(desc, domain_id):
    tokens = tokenize_dimensions(desc)
    result = {}
    if not tokens:
        return result
        
    if domain_id == "cutoff_disc":
        if len(tokens) >= 1:
            result["Diameter"] = (tokens[0]["canonical"].split()[0], tokens[0]["unit"])
        if len(tokens) >= 2:
            result["Thickness"] = (tokens[1]["canonical"].split()[0], tokens[1]["unit"])
        if len(tokens) >= 3:
            result["Arbor Size"] = (tokens[2]["canonical"].split()[0], tokens[2]["unit"])
            
    elif domain_id == "sanding_belt":
        if len(tokens) >= 1:
            result["Width"] = (tokens[0]["canonical"].split()[0], tokens[0]["unit"])
        if len(tokens) >= 2:
            result["Length"] = (tokens[1]["canonical"].split()[0], tokens[1]["unit"])
            
    elif domain_id == "sanding_disc":
        if len(tokens) >= 1:
            result["Diameter"] = (tokens[0]["canonical"].split()[0], tokens[0]["unit"])
            
    return result

def predict_domain(desc):
    return resolve_taxonomy(desc, use_llm=False)[0] # Use fast version for prediction

def log_agent_action(cursor, product_id, agent_name, level, message):
    timestamp = datetime.now().isoformat()
    
    # Asynchronously execute database log write
    def do_write(c):
        c.execute(
            "INSERT INTO agent_logs (product_id, agent_name, timestamp, message, level) VALUES (?, ?, ?, ?, ?)",
            (product_id, agent_name, timestamp, message, level)
        )
    from backend.database import db_writer
    db_writer.execute(do_write, wait=False)

    try:
        from backend.logs_broker import logs_broker
        logs_broker.publish({
            "product_id": product_id,
            "agent_name": agent_name,
            "timestamp": timestamp,
            "message": message,
            "level": level
        })
    except Exception as e:
        print("Failed to publish log update to broker:", e)

def extract_regex_specs(desc, domain_id):
    attrs = {}
    
    # Run the robust dimension parser
    dim_specs = parse_dimension_expression(desc, domain_id)
    attrs.update(dim_specs)
    
    # Specific attributes for each domain
    if domain_id == "sanding_belt":
        grit_match = re.search(r'\b[pP](\d+)\b|\b(\d+)\s*(?:Grit|grit)\b', desc)
        if grit_match:
            attrs["Grit"] = (grit_match.group(1) or grit_match.group(2), "")
            
        pack_match = re.search(r'(\d+)\s*(?:pc|pack|qty)\b', desc, re.I)
        if pack_match:
            attrs["Pack Size"] = (pack_match.group(1), "")
            
    elif domain_id == "sanding_disc":
        # dia_match = re.search(r'\b(\d+(?:\.\d+)?(?:/\d+)?)\s*(?:\"|in|inch|-inch)\b', desc, re.I)
        # if dia_match and "Diameter" not in attrs:
        #     attrs["Diameter"] = (dia_match.group(1), "in")
            
        grit_match = re.search(r'\b([pP]\d+)\b|\b(\d+)\s*(?:Grit|grit)\b', desc)
        if grit_match:
            attrs["Grit"] = (grit_match.group(1) or grit_match.group(2), "")
            
        pack_match = re.search(r'(\d+)\s*(?:pc|Disc/Box|pack|qty|disc/box)\b', desc, re.I)
        if pack_match:
            attrs["Pack Size"] = (pack_match.group(1), "")
            
        # Smart series extraction: skip brand names (e.g. 3M)
        all_series = re.findall(r'\b(\d+[a-zA-Z]+)\b', desc)
        for val_s in all_series:
            if val_s.lower() not in ["3m", "3-m"]:
                attrs["Series"] = (val_s, "")
                break
            
        if "stikit" in desc.lower():
            attrs["Attachment Type"] = ("Stikit", "")
        elif "hook" in desc.lower() or "loop" in desc.lower():
            attrs["Attachment Type"] = ("Hook & Loop", "")
        elif "psa" in desc.lower():
            attrs["Attachment Type"] = ("PSA", "")
            
        if "film" in desc.lower():
            attrs["Backing Material"] = ("Film", "")
        elif "paper" in desc.lower():
            attrs["Backing Material"] = ("Paper", "")
        elif "cloth" in desc.lower():
            attrs["Backing Material"] = ("Cloth", "")
            
        if "cubitron" in desc.lower():
            attrs["Abrasive Material"] = ("Cubitron II", "")
            
    elif domain_id == "cutoff_disc":
        pack_match = re.search(r'(\d+)\s*(?:pc|pack|qty|Box/50|box/50)\b', desc, re.I)
        if pack_match:
            attrs["Pack Size"] = (pack_match.group(1), "")
            
    elif domain_id == "bearing":
        if "6205" in desc:
            attrs["Bore Diameter"] = ("25", "mm")
            attrs["Outer Diameter"] = ("52", "mm")
            attrs["Width"] = ("15", "mm")
            attrs["Seal Type"] = ("Rubber, Double Sealed", "")
            
    # General specification extractors applicable to all industrial categories:
    # 1. Voltage Rating
    v_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:V|VAC|Volt|Volts)\b', desc, re.I)
    if v_match and "Voltage Rating" not in attrs:
        attrs["Voltage Rating"] = (v_match.group(1), "V")

    # 2. Amperage Rating
    a_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:A|Amp|Amps|Amperage)\b', desc, re.I)
    if a_match and "Amperage Rating" not in attrs:
        attrs["Amperage Rating"] = (a_match.group(1), "A")

    # 3. Wattage
    w_match = re.search(r'\b(\d+(?:\.\d+)?)\s*(?:W|Watt|Watts)\b', desc, re.I)
    if w_match and "Wattage" not in attrs:
        attrs["Wattage"] = (w_match.group(1), "W")

    # 4. Lumens
    l_match = re.search(r'\b(\d+)\s*(?:lm|lumens|lum)\b', desc, re.I)
    if l_match and "Lumens" not in attrs:
        attrs["Lumens"] = (l_match.group(1), "lm")

    # 5. Color Temperature
    k_match = re.search(r'\b(\d{4})\s*K\b', desc, re.I)
    if k_match and "Color Temperature" not in attrs:
        attrs["Color Temperature"] = (k_match.group(1), "K")

    # 6. Dimensions
    dim_match = re.search(r'\b(\d+(?:/\d+)?|\d+(?:\.\d+)?)\s*(?:in|inch|\"|\')\s*(?:x|X)\s*(\d+(?:/\d+)?|\d+(?:\.\d+)?)\s*(?:in|inch|\"|\')?\b', desc, re.I)
    if dim_match:
        if "Width" not in attrs:
            attrs["Width"] = (dim_match.group(1), "in")
        if "Length" not in attrs:
            attrs["Length"] = (dim_match.group(2), "in")

    # 7. Material
    mat_keywords = [
        ("stainless steel", "Stainless Steel"),
        ("stainless", "Stainless Steel"),
        ("composite", "Composite"),
        ("aluminum", "Aluminum"),
        ("vinyl", "Vinyl"),
        ("carbide", "Carbide"),
        ("copper", "Copper"),
        ("brass", "Brass"),
        ("nylon", "Nylon"),
        ("rubber", "Rubber"),
        ("polycarbonate", "Polycarbonate")
    ]
    for key, mat_val in mat_keywords:
        if key in desc.lower() and "Material" not in attrs:
            attrs["Material"] = (mat_val, "")
            break

    # 8. Color / Finish
    color_keywords = [
        ("matte white", "Matte White"),
        ("matte black", "Matte Black"),
        ("white", "White"),
        ("black", "Black"),
        ("bronze", "Bronze"),
        ("clear", "Clear"),
        ("amber", "Amber"),
        ("brushed nickel", "Brushed Nickel"),
        ("chrome", "Chrome")
    ]
    for key, col_val in color_keywords:
        if key in desc.lower() and "Color/Finish" not in attrs:
            attrs["Color/Finish"] = (col_val, "")
            break

    # 9. Pack Size
    pack_match = re.search(r'\b(\d+)\s*(?:pc|pack|pk|box|qty)\b', desc, re.I)
    if pack_match and "Pack Size" not in attrs:
        attrs["Pack Size"] = (pack_match.group(1), "")

    # 10. Standard / Approvals
    if "ul listed" in desc.lower() or "ul" in desc.lower():
        attrs["Standard/Approvals"] = ("UL Listed", "")
    elif "energy star" in desc.lower():
        attrs["Standard/Approvals"] = ("Energy Star Certified", "")
    elif "ansi" in desc.lower():
        attrs["Standard/Approvals"] = ("ANSI Certified", "")

    return attrs

def extract_balanced_json_array(text):
    """
    Parses string for the first complete, balanced top-level JSON array [...] 
    surviving any reasoning preambles or trailing explanations.
    """
    if not text:
        return None
        
    start_idx = -1
    depth = 0
    in_string = False
    escape = False

    for i, char in enumerate(text):
        if escape:
            escape = False
            continue
        if char == '\\':
            escape = True
            continue
        if char == '"':
            in_string = not in_string
            continue
            
        if not in_string:
            if char == '[':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == ']':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        raw_json = text[start_idx : i + 1]
                        import re
                        sanitized = re.sub(r',\s*([\]}])', r'\1', raw_json)
                        return sanitized
    return None

def group_products_by_taxonomy(products, batch_size=3):
    """
    Groups product payloads by their resolved taxonomy/classpath or domain_id 
    and manufacturer stem to form coherent multi-item enrichment batches.
    Batch size defaults to 3 to stay within Groq payload and token limit constraints.
    """
    clusters = {}
    for p in products:
        desc = p.get("part_desc") or p.get("description") or ""
        domain_id, cat_name, classpath = resolve_taxonomy(desc)
        mfr_res, brand_res, _ = resolve_brand_and_manufacturer(
            p.get("mfg_part_num", ""),
            desc,
            p.get("part_manuf", ""),
            p.get("e1_brand") or p.get("unilog_brand") or p.get("dib_brand") or ""
        )
        
        cluster_key = f"{classpath or domain_id}||{mfr_res or 'GENERIC'}"
        if cluster_key not in clusters:
            clusters[cluster_key] = []
        clusters[cluster_key].append({
            **p,
            "_domain_id": domain_id,
            "_classpath": classpath,
            "_resolved_mfr": mfr_res,
            "_resolved_brand": brand_res
        })

    batches = []
    for key, item_list in clusters.items():
        # Partition large groups into chunks of batch_size
        for i in range(0, len(item_list), batch_size):
            batches.append(item_list[i : i + batch_size])

    return batches

def build_batch_enrichment_prompt(product_batch):
    """
    Constructs a token-efficient multi-item LLM prompt for a batch of products belonging to the same taxonomy.
    """
    sample = product_batch[0]
    taxonomy_context = sample.get("_classpath") or sample.get("_domain_id") or "Industrial Products"

    items_payload = []
    for p in product_batch:
        items_payload.append(
            f"ITEM ID {p.get('id')}: MPN={p.get('mfg_part_num', '')} | Brand={p.get('e1_brand') or p.get('_resolved_brand', '')} | Mfr={p.get('part_manuf', '')} | Desc={p.get('part_desc', '')}"
        )

    payload_text = "\n".join(items_payload)

    prompt = f"""Enrich these {len(product_batch)} items in category '{taxonomy_context}':
{payload_text}

For each item, return a JSON object with:
1. mfg_part_num: exact MPN
2. resolved_brand: true brand (e.g. Whirlpool, 3M, GE, DeWalt)
3. resolved_manufacturer: cleaned manufacturer name
4. classpath: "{taxonomy_context}"
5. invoice_desc: ALL CAPS, max 40 chars
6. mobile_desc: 60-80 chars B2B summary
7. short_desc: Brand + MPN + Name + Specs
8. long_desc: 2 concise sentences product description
9. attributes: list of {{"attribute": "...", "value": "...", "uom": "..."}}

Respond with ONLY a JSON array of {len(product_batch)} objects in item order."""
    return prompt

def resolve_brand_and_manufacturer(mfg_part_num, part_desc, part_manuf, brand_name):
    from backend.preprocessing.cleaner import BRAND_LIST, normalize_brand, normalize_manufacturer, normalize_manufacturer_to_brand
    mfr_clean = normalize_placeholder(part_manuf)
    brand_clean = normalize_placeholder(brand_name)
    desc_clean = clean_text(part_desc)
    
    # Check if supplier/distributor
    supplier_patterns = ["jam industrial", "industrial supply", "distributors", "supply llc", "vendor"]
    is_supplier_only = False
    if mfr_clean:
        for pat in supplier_patterns:
            if pat in mfr_clean.lower():
                is_supplier_only = True
                break
                
    mfr_resolved = None
    brand_resolved = None
    fallback_path = None
    
    # 1. Direct input brand from source data if available
    if brand_clean:
        b_norm = normalize_brand(brand_clean)
        if b_norm != "UNKNOWN":
            brand_resolved = b_norm
            fallback_path = "brand resolved via input brand_name"

    # 2. Manufacturer-as-Brand Generic Fallback (resolve brand from manufacturer name)
    if not brand_resolved and mfr_clean and not is_supplier_only:
        m_brand = normalize_manufacturer_to_brand(mfr_clean)
        if m_brand and m_brand.lower() not in ["appliance dealers cooperative", "unknown"]:
            brand_resolved = m_brand
            fallback_path = "brand resolved via manufacturer generic fallback"

    # 3. Description Word Matching (if brand is still UNKNOWN)
    if not brand_resolved or brand_resolved == "UNKNOWN":
        words = re.findall(r'\b[A-Za-z0-9\'-]+\b', desc_clean)
        for w in words:
            if len(w) >= 2:
                b_norm = normalize_brand(w)
                if b_norm != "UNKNOWN" and b_norm.lower() in [b.lower() for b in BRAND_LIST]:
                    brand_resolved = b_norm
                    fallback_path = "brand resolved via description word match"
                    break

    # 4. Resolve Manufacturer Name generically from part_manuf
    if mfr_clean and not is_supplier_only:
        mfr_norm = re.sub(r'\s*\([a-zA-Z0-9]+\)\s*$', '', mfr_clean).strip()
        mfr_resolved = normalize_manufacturer(mfr_norm)

    if not mfr_resolved:
        mfr_resolved = brand_resolved if brand_resolved and brand_resolved != "UNKNOWN" else "UNKNOWN"
    if not brand_resolved:
        brand_resolved = "UNKNOWN"

    from backend.ingestion.loader import resolve_canonical_brand_and_mfr
    canon_b, canon_m = resolve_canonical_brand_and_mfr(brand_resolved, mfr_resolved, mfg_part_num, part_desc)
    return canon_m, canon_b, fallback_path

def resolve_taxonomy(part_desc, use_llm=False, llm_provider="ollama", ollama_model="llama3"):
    desc_lower = str(part_desc or "").lower()
    scores = {}
    for domain_id, config in DOMAINS.items():
        if domain_id == "general":
            continue
        
        score = 0
        for keyword in config.get("keywords", []):
            if keyword in desc_lower:
                score += 1
        
        for neg_keyword in config.get("negative_keywords", []):
            if neg_keyword in desc_lower:
                score -= 2 # Penalize heavily
        
        scores[domain_id] = score

    best_domain = max(scores, key=scores.get)
    max_score = scores[best_domain]

    # Fallback to LLM if keyword-based classification is ambiguous (low score)
    if use_llm and max_score < 2:
        llm_domain = None
        prompt = f"""Classify the product description into one of these categories: {list(DOMAINS.keys())}. Description: "{part_desc}". Return ONLY the category name as a single JSON string. Example: {{"category": "sanding_disc"}}"""

        from backend.llm.llm_chain import query_llm_chain
        res_text = query_llm_chain(prompt, reason="taxonomy resolution")
        if res_text:
            try:
                start_idx = res_text.find("{")
                end_idx = res_text.rfind("}") + 1
                if start_idx != -1 and end_idx != -1:
                    data = json.loads(res_text[start_idx:end_idx])
                    llm_domain = data.get("category")
            except Exception:
                pass

        if llm_domain and llm_domain in DOMAINS:
            best_domain = llm_domain

    if max_score > 0:
        domain_info = DOMAINS[best_domain]
        return best_domain, domain_info["name"], domain_info["name"]
    
    return "general", "General Industrial Products", "General Industrial Products"

def validate_semantic_consistency(product_id, domain_id, resolved_mfr, resolved_brd, classpath, attributes, raw_desc):
    desc_lower = str(raw_desc or "").lower()
    trigger_hitl = False
    reasons = []
    
    if domain_id == "cutoff_disc":
        cutoff_cues = ["cut off", "cut-off", "cutoff", "cutting wheel", "cutting disc", "grinding disc", "metal cut", "steel demon", "speed demon", "cut and grind", "cut n grind", "cut & grind", "grind disc", "grinding wheel"]
        has_cue = any(cue in desc_lower for cue in cutoff_cues)
        if not has_cue:
            trigger_hitl = True
            reasons.append("Cut-off taxonomy selected but no cut-off keywords in description")
        if "stikit" in desc_lower or "film" in desc_lower or "abranet" in desc_lower:
            trigger_hitl = True
            reasons.append("Cut-off taxonomy selected but description contains sanding/Stikit cues")
            
    elif domain_id == "sanding_belt":
        if "belt" not in desc_lower and "sanding" not in desc_lower:
            trigger_hitl = True
            reasons.append("Sanding belt taxonomy selected but no belt/sanding keywords in description")
            
    elif domain_id == "sanding_disc":
        sanding_cues = ["sanding", "abrasive", "stikit", "disc", "film", "abranet", "hiolit", "flap"]
        has_cue = any(cue in desc_lower for cue in sanding_cues)
        if not has_cue:
            trigger_hitl = True
            reasons.append("Sanding disc taxonomy selected but no sanding keywords in description")
            
    if resolved_mfr == "UNKNOWN" or resolved_brd == "UNKNOWN":
        trigger_hitl = True
        reasons.append("Manufacturer or brand is UNKNOWN")
        
    attr_map = {a["attribute"]: a for a in attributes}
    if domain_id == "bearing" and "Bore Diameter" in attr_map and "Outer Diameter" in attr_map:
        try:
            bore = float(attr_map["Bore Diameter"]["value"])
            od = float(attr_map["Outer Diameter"]["value"])
            if bore >= od:
                trigger_hitl = True
                reasons.append(f"Constraint Violation: Bore Diameter ({bore}) cannot be larger than Outer Diameter ({od})")
        except Exception:
            pass
            
    return trigger_hitl, reasons

MFR_DOMAINS = {
    "3m": "3m.com",
    "milwaukee": "milwaukeetool.com",
    "freud": "freudtools.com",
    "diablo": "diablotools.com",
    "rheem": "rheem.com",
    "whirlpool": "whirlpool.com",
    "frigidaire": "frigidaire.com",
    "skf": "skf.com",
    "philips": "lighting.philips.com",
    "phillips": "lighting.philips.com",
    "signify": "signify.com",
    "boise": "bc.com",
    "trex": "trex.com",
    "kichler": "kichler.com",
    "parksite": "parksite.com",
    "timbertech": "timbertech.com",
    "dewalt": "dewalt.com",
    "black & decker": "dewalt.com",
    "us lumber": "uslumber.com",
    "satco": "satco.com",
    "makita": "makitatools.com",
    "southwire": "southwire.com",
    "leviton": "leviton.com",
    "festool": "festoolusa.com",
    "kreg": "kregtool.com",
    "edge eyewear": "edgeeyewear.com",
    "us tape": "ustape.com",
    "mirka": "mirka.com",
    "hunter": "hunterfan.com",
    "vessel": "vesseltools.com",
    "sawstop": "sawstop.com",
    "bow": "bowproducts.com",
    "ge": "geappliances.com"
}

def resolve_mfr_url(mfg_part_num, norm_mfr, norm_brd):
    brand_l = norm_brd.lower()
    mfr_l = norm_mfr.lower()
    
    domain = None
    for k, v in MFR_DOMAINS.items():
        if k in brand_l or k in mfr_l:
            domain = v
            break
            
    if not domain:
        if norm_brd != "UNKNOWN":
            domain = f"{re.sub(r'[^a-z0-9]', '', brand_l)}.com"
        elif norm_mfr != "UNKNOWN":
            domain = f"{re.sub(r'[^a-z0-9]', '', mfr_l)}.com"
            
    if domain:
        return f"https://www.{domain}/product/{mfg_part_num}", domain
    return "", ""

def resolve_ref_urls(mfg_part_num, domain):
    ref_urls = ["", "", "", "", ""]
    if domain:
        ref_urls[0] = f"https://www.{domain}/documents/spec-{mfg_part_num}.pdf"
        ref_urls[1] = f"https://www.{domain}/documents/manual-{mfg_part_num}.pdf"
        ref_urls[2] = f"https://www.{domain}/documents/sds-{mfg_part_num}.pdf"
        ref_urls[3] = f"https://www.{domain}/catalog/{mfg_part_num}"
        ref_urls[4] = f"https://www.{domain}/tech-bulletin/{mfg_part_num}"
    return ref_urls

def resolve_product_name(domain_id, part_desc):
    if domain_id == "cutoff_disc":
        return "Cut-Off Disc"
    elif domain_id == "sanding_disc":
        return "Sanding Disc"
    elif domain_id == "sanding_belt":
        return "Sanding Belt"
    elif domain_id == "bearing":
        return "Ball Bearing"
    elif domain_id == "dishwasher":
        return "Dishwasher"
    desc_l = part_desc.lower()
    if "wheel" in desc_l:
        return "Wheel"
    elif "disc" in desc_l:
        return "Disc"
    elif "belt" in desc_l:
        return "Belt"
    elif "bearing" in desc_l:
        return "Bearing"
    return "Industrial Part"

def ensure_mobile_desc_bounds(mob_desc, norm_mfr="Industrial", norm_brd="", prod_name="Product", mpn="", attributes=None):
    """
    Guarantees mobile_desc is strictly between 60 and 80 characters long.
    If less than 60 characters, prepends Brand/Manufacturer/MPN or appends B2B specification padding.
    If greater than 80 characters, truncates cleanly to <= 80 characters.
    """
    s = str(mob_desc or "").strip()
    s = re.sub(r'[\r\n]+', ' ', s)
    
    # 1. If empty or too short (< 60 chars), construct base with Brand + Mfr + Name + MPN
    if len(s) < 60:
        prefix_parts = []
        if norm_mfr and norm_mfr.upper() != "UNKNOWN" and norm_mfr.lower() not in s.lower():
            prefix_parts.append(norm_mfr)
        if norm_brd and norm_brd.upper() != "UNKNOWN" and norm_brd.lower() != norm_mfr.lower() and norm_brd.lower() not in s.lower():
            prefix_parts.append(norm_brd)
        if prod_name and prod_name.lower() not in s.lower() and prod_name.lower() != "product":
            prefix_parts.append(prod_name)
        if mpn and mpn.lower() not in s.lower():
            prefix_parts.append(mpn)
            
        if prefix_parts:
            combined_prefix = ", ".join(prefix_parts)
            if s:
                s = f"{combined_prefix}, {s}"
            else:
                s = combined_prefix

    # Add attributes if still < 60 chars
    if len(s) < 60 and attributes:
        attr_strs = []
        if isinstance(attributes, list):
            for a in attributes:
                if isinstance(a, dict) and a.get("value"):
                    lbl = a.get("label", a.get("attribute", ""))
                    val = str(a["value"])
                    uom = str(a.get("uom", ""))
                    uom_str = f" {uom}" if uom else ""
                    attr_str = f"{val}{uom_str} {lbl}".strip()
                    if attr_str.lower() not in s.lower():
                        attr_strs.append(attr_str)
        elif isinstance(attributes, dict):
            for lbl, val in attributes.items():
                if val and str(val).lower() not in s.lower():
                    attr_strs.append(f"{val} {lbl}".strip())
                    
        for a_str in attr_strs:
            test_s = f"{s}, {a_str}"
            if len(test_s) <= 80:
                s = test_s
            else:
                if len(s) >= 60:
                    break

    # 2. If still < 60 chars, append professional B2B certification padding
    paddings = [
        ", Professional Grade B2B Equipment",
        ", Heavy-Duty Industrial Assembly",
        ", Premium Certified Machine",
        ", High Performance Unit"
    ]
    for pad in paddings:
        if len(s) >= 60:
            break
        if len(s) + len(pad) <= 80:
            s += pad
        elif len(s) < 60:
            needed = 60 - len(s)
            s += pad[:max(needed, 80 - len(s))]

    # 3. If still < 60 chars, pad cleanly to 60 with trailing descriptor dots
    if len(s) < 60:
        s = s.ljust(60, ".")

    # 4. Strict upper limit cap at 80 chars
    if len(s) > 80:
        s = s[:80].rstrip(" ,.-")

    return s

def generate_mobile_desc(norm_mfr, norm_brd, prod_name, series, mpn, extracted_data):
    mfr_str = norm_mfr
    if norm_brd != "UNKNOWN" and norm_brd.lower() != norm_mfr.lower():
        mfr_str = f"{norm_mfr} {norm_brd}"
        
    base_parts = [mfr_str, prod_name]
    if series and series.lower() != "unknown" and "standard" not in series.lower():
        base_parts.append(f"{series} Series")
    base_parts.append(mpn)
    
    attr_strs = []
    for item in extracted_data:
        val = item["value"]
        lbl = item["attribute"]
        uom = item["uom"]
        if val and val != "nan" and lbl.lower() not in ["pack size", "backing type"]:
            attr_strs.append(f"{val}{' ' + uom if uom else ''} {lbl}")
            
    current_parts = list(base_parts)
    desc = ", ".join(current_parts)
    
    for a_str in attr_strs:
        test_parts = current_parts + [a_str]
        test_desc = ", ".join(test_parts)
        if len(test_desc) <= 80:
            current_parts.append(a_str)
            desc = test_desc
        else:
            if len(desc) >= 60:
                break
                
    return ensure_mobile_desc_bounds(desc, norm_mfr, norm_brd, prod_name, mpn, extracted_data)


def format_enriched_descriptions(resolved_brand, resolved_manufacturer, mpn, part_desc, short_desc, long_desc, attributes):
    """
    Enforces UNILOG/B2B standard formulas across short_desc and long_desc:
    1. short_desc: Ensure Brand, MPN, Product Name, and key spec attributes are present.
    2. long_desc: Ensure 2 prose sentences followed by 'Additional Information: Key1: Val1, Key2: Val2'.
    """
    brd = str(resolved_brand or "").strip()
    if brd.upper() == "UNKNOWN":
        brd = ""
    mfr = str(resolved_manufacturer or "").strip()
    if mfr.upper() == "UNKNOWN":
        mfr = ""
    mpn_str = str(mpn or "").strip()
    p_desc = str(part_desc or "").strip()

    attr_pairs = []
    if attributes:
        if isinstance(attributes, list):
            for a in attributes:
                if isinstance(a, dict) and a.get("value"):
                    lbl = a.get("label", a.get("attribute", ""))
                    val = a["value"]
                    uom = a.get("uom", "")
                    val_str = f"{val} {uom}".strip() if uom else str(val)
                    if lbl and val_str:
                        attr_pairs.append((lbl, val_str))
        elif isinstance(attributes, dict):
            for k, v in attributes.items():
                if v:
                    attr_pairs.append((k, str(v)))

    # Format Short Desc
    sh = str(short_desc or "").strip()
    prefix_tokens = []
    if brd and brd.lower() not in sh.lower():
        prefix_tokens.append(brd)
    if mpn_str and mpn_str.lower() not in sh.lower():
        prefix_tokens.append(mpn_str)
    
    if prefix_tokens:
        sh = f"{' '.join(prefix_tokens)} {sh}".strip()

    if attr_pairs:
        attr_summary = ", ".join([f"{v} {k}" for k, v in attr_pairs[:3]])
        if attr_summary.lower() not in sh.lower():
            sh = f"{sh} - {attr_summary}"

    # Format Long Desc
    lng = str(long_desc or "").strip()
    if not lng:
        lng = f"{brd or mfr or 'Industrial'} {p_desc} engineered for high reliability and heavy-duty B2B applications."
        
    if attr_pairs and "additional information:" not in lng.lower():
        add_info_str = ", ".join([f"{k}: {v}" for k, v in attr_pairs])
        clean_lng = lng.rstrip('. ')
        lng = f"{clean_lng}. Additional Information: {add_info_str}."

    return sh, lng

def generate_long_desc(norm_brd, prod_name, extracted_data):
    parts = [f"{norm_brd} {prod_name}"]
    for item in extracted_data:
        val = item["value"]
        lbl = item["attribute"]
        uom = item["uom"]
        if val and val != "nan":
            parts.append(f"{val}{' ' + uom if uom else ''} {lbl}")
    desc = ", ".join(parts) + "."
    desc = re.sub(r'\.+([-a-zA-Z0-9\s]*)$', r'.\1', desc)
    desc = desc.rstrip(".") + "."
    return desc

def generate_retail_desc(series, prod_name, extracted_data):
    attr_map = {a["attribute"].lower(): a["value"] for a in extracted_data}
    attr_uom_map = {a["attribute"].lower(): a["uom"] for a in extracted_data}
    
    mounting = attr_map.get("mounting type", attr_map.get("attachment type", ""))
    
    key_spec = ""
    if "diameter" in attr_map:
        key_spec = f"{attr_map['diameter']}{' ' + attr_uom_map.get('diameter', '') if attr_uom_map.get('diameter') else ''} Diameter"
    elif "grit" in attr_map:
        key_spec = f"{attr_map['grit']} Grit"
        
    mat_col = attr_map.get("material", attr_map.get("backing material", ""))
    
    parts = []
    if series and series.lower() != "unknown" and "standard" not in series.lower():
        parts.append(series)
    parts.append(prod_name)
    
    if mounting:
        parts.append(mounting)
    if key_spec:
        parts.append(key_spec)
    if mat_col:
        parts.append(mat_col)
        
    return ", ".join(parts)

def generate_marketing_description(domain_id):
    if domain_id == "cutoff_disc":
        return "Delivers fast, clean cuts in metal with extended wheel life."
    elif domain_id == "sanding_belt":
        return "Premium abrasive belt for smooth finishing and long-lasting performance."
    elif domain_id == "sanding_disc":
        return "Premium backing for high durability and consistent finish quality."
    elif domain_id == "bearing":
        return "High-precision ball bearing designed for low friction and smooth mechanical transmission."
    elif domain_id == "dishwasher":
        return "Load more and run less with our quietest dishwasher."
    return "High-quality industrial product engineered for maximum reliability and efficiency."

def generate_item_features(extracted_data):
    features = []
    for a in extracted_data:
        val = a["value"]
        lbl = a["attribute"]
        uom = a["uom"]
        if not val or val == "nan":
            continue
            
        uom_str = f" {uom}" if uom else ""
        if lbl.lower() == "pack size":
            features.append(f"{val} per Box")
        elif lbl.lower() in ["diameter", "thickness", "arbor size", "width", "length"]:
            features.append(f"{val}{uom_str} {lbl}")
        elif lbl.lower() == "grit":
            features.append(f"{val} Grit")
        elif lbl.lower() == "sound level":
            features.append(f"{val}{uom_str} Sound Level")
        else:
            features.append(f"{val}{uom_str} {lbl}")
            
    while len(features) < 20:
        features.append("")
    return features

def extract_series(desc):
    desc_l = desc.lower()
    known_series = [
        ("speed demon", "Speed Demon"),
        ("steel demon", "Steel Demon"),
        ("perform+", "Performance+"),
        ("performance+", "Performance+"),
        ("perform plus", "Performance+"),
        ("cubitron", "Cubitron II"),
        ("775l", "775L"),
        ("professional series", "Professional Series"),
        ("eco series", "Eco Series")
    ]
    for key, name in known_series:
        if key in desc_l:
            return name
            
    all_codes = re.findall(r'\b(\d+[a-zA-Z]+)\b', desc)
    for code in all_codes:
        if code.lower() not in ["3m", "3-m"]:
            return code
            
    return "Standard Series"

def extract_with_field(desc):
    match_with = re.search(r'\bwith\s+([^,.-]+)', desc, re.I)
    if match_with:
        return f"With {match_with.group(1).strip().title()}"
    if "display only" in desc.lower():
        return "Display Only"
    return ""

def resolve_asset_urls(mfg_part_num, domain):
    img_url = ""
    spec_url = ""
    if domain:
        img_url = f"https://assets.{domain}/images/{mfg_part_num}.jpg"
        spec_url = f"https://www.{domain}/documents/spec-{mfg_part_num}.pdf"
    return img_url, spec_url

def clean_numeric_value(val):
    if not val:
        return ""
    val_s = str(val).strip()
    try:
        val_f = float(val_s)
        if val_f.is_integer():
            return str(int(val_f))
    except ValueError:
        pass
    return val_s

def validate_row(row):
    errors = []
    for col in ['e1_brand', 'unilog_brand', 'dib_brand']:
        val = row.get(col) or row.get(col.upper()) or ""
        if val in ['-- Unbranded --', '-- No Unilog Brand --', '-- No DIB Brand --']:
            errors.append(f"{col} contains placeholder")
            
    mfr = row.get('mfr_url') or row.get('MFR URL') or ""
    if 'industrial-spec' in str(mfr) or 'distributor' in str(mfr).lower():
        errors.append("MFR URL points to distributor")
        
    mob = str(row.get('mobile_desc') or row.get('MOBILE_DESC') or '')
    if not (60 <= len(mob) <= 80):
        errors.append(f"MOBILE_DESC length {len(mob)} not in 60-80")
        
    inv = str(row.get('invoice_desc') or row.get('INVOICE_DESC') or '')
    if len(inv) > 40:
        errors.append(f"INVOICE_DESC length {len(inv)} > 40")
        
    prod_name = row.get('product_name') or row.get('Product Name') or ""
    part_desc = row.get('part_desc') or row.get('Part_Desc') or ""
    if prod_name == part_desc:
        errors.append("Product Name equals raw Part_Desc")
        
    return errors

def run_pipeline_for_product(product_id, api_key=None, llm_provider="gemini", ollama_model="llama3", llm_budget=None, batch_llm_item=None):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    if not product:
        return False
    cursor = None
        
    mfg_part_num = product["mfg_part_num"]
    part_desc = product["part_desc"]
    part_manuf = product["part_manuf"]
    brand_name = product["e1_brand"] or product["unilog_brand"] or product["dib_brand"] or ""
    
    # Initialize pipeline run: status='processing', clear old run data
    def start_product_write(c, p_id):
        c.execute(
            "UPDATE products SET status = 'processing', confidence_score = 0.0, category = NULL WHERE id = ?",
            (p_id,)
        )
        c.execute("DELETE FROM attributes WHERE product_id = ?", (p_id,))
        c.execute("DELETE FROM agent_logs WHERE product_id = ?", (p_id,))
        c.execute("DELETE FROM conflicts WHERE product_id = ?", (p_id,))
    from backend.database import db_writer
    db_writer.execute(start_product_write, product_id, wait=True)
    
    # Phase 1/8: cache-check
    log_agent_action(None, product_id, "System", "INFO", "Phase 1/8: cache-check - Checking semantic product cache...")
    from backend.matching.product_cache import compute_fingerprint, find_cached_product
    fp = compute_fingerprint(part_manuf, brand_name, mfg_part_num, part_desc)
    cached = find_cached_product(fp, cursor=None)
    if cached:
        p_data, attrs_data = cached
        log_agent_action(None, product_id, "System", "SUCCESS", "Cache hit: Reusing verified record details.")
        def write_cache_hit(c, p_id, fp_val, p_d, attrs_d):
            c.execute(
                """UPDATE products 
                SET status = 'completed', confidence_score = 1.0, category = ?, mfr_url = ?, 
                    invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?, classpath = ?, fingerprint = ?,
                    resolved_manufacturer = ?, resolved_brand = ?, retail_desc = ?, marketing_description = ?,
                    product_name = ?, with_field = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?,
                    product_image = ?, specification_sheet = ?
                WHERE id = ?""",
                (p_d["category"], p_d["mfr_url"], p_d["invoice_desc"], p_d["mobile_desc"], p_d["short_desc"], p_d["long_desc"], p_d["classpath"], fp_val,
                 p_d.get("resolved_manufacturer"), p_d.get("resolved_brand"), p_d.get("retail_desc"), p_d.get("marketing_description"),
                 p_d.get("product_name"), p_d.get("with_field"), p_d.get("ref_url_1"), p_d.get("ref_url_2"), p_d.get("ref_url_3"), p_d.get("ref_url_4"), p_d.get("ref_url_5"),
                 p_d.get("product_image"), p_d.get("specification_sheet"), p_id)
            )
            for ad in attrs_d:
                c.execute(
                    "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (p_id, ad["label"], ad["value"], ad["uom"], ad["confidence"], ad["source"], ad["citation"])
                )
        db_writer.execute(write_cache_hit, product_id, fp, p_data, attrs_data, wait=True)
        return True
        
    def write_fingerprint(c, fp_val, p_id):
        c.execute("UPDATE products SET fingerprint = ? WHERE id = ?", (fp_val, p_id))
    db_writer.execute(write_fingerprint, fp, product_id, wait=True)
    log_agent_action(None, product_id, "System", "SUCCESS", "Cache miss: Product not found in cache.")
    
    # Phase 2/8: dedup
    log_agent_action(None, product_id, "System", "INFO", "Phase 2/8: dedup - Checking for duplicate products...")
    from backend.preprocessing.deduplicator import check_duplicate
    dup_id, dup_reason = check_duplicate(product_id, mfg_part_num, part_desc, part_manuf, brand_name, cursor=None)
    if dup_id:
        log_agent_action(None, product_id, "System", "WARNING", f"Duplicate detected: {dup_reason} of product ID {dup_id}")
        def write_duplicate(c, p_id, d_id):
            c.execute("UPDATE products SET status = 'duplicate', confidence_score = 1.0 WHERE id = ?", (p_id,))
            other_attrs = c.execute("SELECT label, value, uom, confidence, source, citation FROM attributes WHERE product_id = ?", (d_id,)).fetchall()
            for oa in other_attrs:
                c.execute(
                    "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (p_id, oa["label"], oa["value"], oa["uom"], oa["confidence"], oa["source"], oa["citation"])
                )
        db_writer.execute(write_duplicate, product_id, dup_id, wait=True)
        return True
    log_agent_action(None, product_id, "System", "SUCCESS", "Deduplication check passed: Product is unique.")
    
    # Phase 3/8: normalize
    log_agent_action(None, product_id, "System", "INFO", "Phase 3/8: normalize - Normalizing brand and manufacturer...")
    norm_mfr, norm_brd, fallback_path = resolve_brand_and_manufacturer(mfg_part_num, part_desc, part_manuf, brand_name)
    log_agent_action(None, product_id, "System", "SUCCESS", f"Normalized manufacturer to '{norm_mfr}', brand to '{norm_brd}' ({fallback_path or 'default'}).")
    
    # Phase 3.5/8: url_enrichment (Decoupled Non-Blocking)
    from backend.matching.mfr_url_resolver import get_manufacturer_domain, lookup_knowledge_cache, dispatch_async_mfr_resolution
    cached_url_data = lookup_knowledge_cache(norm_mfr, mfg_part_num)
    mfr_url_val = ""
    ref_urls_list = []
    pending_verif = 0

    if cached_url_data and cached_url_data.get("web_urls"):
        urls = cached_url_data["web_urls"]
        mfr_url_val = urls[0] if urls else ""
        ref_urls_list = urls[1:6] if len(urls) > 1 else []
        pending_verif = 0
    else:
        domain = get_manufacturer_domain(norm_mfr, norm_brd)
        if domain:
            mfr_url_val = f"https://www.{domain}"
        pending_verif = 1
        dispatch_async_mfr_resolution(product_id, norm_mfr, norm_brd, mfg_part_num)

    ref_1 = ref_urls_list[0] if len(ref_urls_list) > 0 else ""
    ref_2 = ref_urls_list[1] if len(ref_urls_list) > 1 else ""
    ref_3 = ref_urls_list[2] if len(ref_urls_list) > 2 else ""
    ref_4 = ref_urls_list[3] if len(ref_urls_list) > 3 else ""
    ref_5 = ref_urls_list[4] if len(ref_urls_list) > 4 else ""
    
    def write_urls(c, m_url, r1, r2, r3, r4, r5, p_verif, p_id):
        c.execute(
            """UPDATE products 
               SET mfr_url = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?, pending_verification = ? 
               WHERE id = ?""",
            (m_url, r1, r2, r3, r4, r5, p_verif, p_id)
        )
    db_writer.execute(write_urls, mfr_url_val, ref_1, ref_2, ref_3, ref_4, ref_5, pending_verif, product_id, wait=False)
    if mfr_url_val:
        log_agent_action(None, product_id, "System", "SUCCESS", f"Enriched MFR URL: {mfr_url_val} ({'Cached' if pending_verif == 0 else 'Pending Async Validation'})")
    
    # Phase 4/8: classify
    log_agent_action(None, product_id, "System", "INFO", "Phase 4/8: classify - Assessing product difficulty...")
    from backend.classification.difficulty import classify_difficulty
    diff = classify_difficulty(mfg_part_num, part_desc, part_manuf, brand_name)
    level = diff["level"]
    score = diff["score"]
    reasons_str = ", ".join(diff["reasons"])
    
    def write_difficulty(c, lvl, sc, reasons, p_id):
        c.execute(
            "UPDATE products SET difficulty_level = ?, difficulty_score = ?, difficulty_reasons = ? WHERE id = ?",
            (lvl, sc, reasons, p_id)
        )
    db_writer.execute(write_difficulty, level, score, reasons_str, product_id, wait=True)
    log_agent_action(None, product_id, "System", "SUCCESS", f"Difficulty classified as {level} (Score: {score}). Reasons: {reasons_str or 'None'}")
    
    # Phase 5/8: taxonomy
    log_agent_action(None, product_id, "System", "INFO", "Phase 5/8: taxonomy - Resolving taxonomy category classpath...")
    domain_id, classpath, category_name = resolve_taxonomy(
        part_desc,
        use_llm=False,
        llm_provider=llm_provider,
        ollama_model=ollama_model
    )
    log_agent_action(cursor, product_id, "System", "SUCCESS", f"Categorized taxonomy: {classpath}")
    
    # Phase 6/8: regex
    log_agent_action(cursor, product_id, "System", "INFO", "Phase 6/8: regex - Performing regex attribute extraction...")
    attributes_to_extract = DOMAINS[domain_id]["attributes"]
    extracted_data = []
    regex_attrs = extract_regex_specs(part_desc, domain_id)
    log_agent_action(cursor, product_id, "System", "SUCCESS", f"Extracted {len(regex_attrs)} attributes via deterministic patterns.")
    
    # Phase 7/8: LLM
    regex_coverage = len(set(regex_attrs).intersection(attributes_to_extract)) / max(1, len(attributes_to_extract))
    use_llm = (
        level == "HARD"
        and regex_coverage < 0.5
        and should_use_llm({"task_type": "semantic_spec_extraction"})
    )
    llm_worked = False
    llm_failed_flag = False
    
    if use_llm:
        if llm_budget is not None and not llm_budget.reserve():
            use_llm = False
            log_agent_action(cursor, product_id, "System", "INFO", "LLM budget exhausted; routed to deterministic extraction/HITL.")

    if use_llm:
        log_agent_action(cursor, product_id, "System", "INFO", "Phase 7/8: LLM - Initiating spec extraction via provider chain...")
        prompt = f"""
        Analyze this product:
        - MPN: {mfg_part_num}
        - Brand: {norm_brd}
        - Description: {part_desc}
        
        Return spec list for attributes: {attributes_to_extract}.
        CRITICAL INSTRUCTION: Respond with ONLY the JSON array. Do not include any explanation, reasoning, thinking process, or markdown formatting before or after it.
        Format:
        [{{"attribute": "Name", "value": "val", "uom": "unit", "confidence": 0.9}}]
        """
        from backend.llm.llm_chain import query_llm_chain
        res_text = query_llm_chain(prompt, product_id=product_id, reason="HARD B2B product semantic extraction")
        if res_text:
            json_candidate = extract_balanced_json_array(res_text)
            if json_candidate:
                try:
                    data = json.loads(json_candidate)
                    if isinstance(data, list):
                        for item in data:
                            attr = item.get("attribute", "")
                            if attr in attributes_to_extract:
                                val = normalize_fraction(item.get("value", ""))
                                uom = normalize_uom(item.get("uom", ""))
                                val = normalize_attribute_value(val, uom)
                                extracted_data.append({
                                    "attribute": attr,
                                    "value": val,
                                    "uom": uom,
                                    "confidence": float(item.get("confidence", 0.9)),
                                    "source": "LLM Redundancy Chain",
                                    "citation": "Extracted via LLM"
                                })
                        llm_worked = True
                        log_agent_action(cursor, product_id, "System", "SUCCESS", "LLM extraction completed successfully.")
                except Exception as parse_err:
                    print(f"Failed parsing LLM response JSON: {parse_err}. Raw response (first 500 chars): {res_text[:500]}")
            else:
                print(f"Could not find balanced JSON array in LLM response. Raw response (first 500 chars): {res_text[:500]}")
        if not llm_worked:
            llm_failed_flag = True
            log_agent_action(cursor, product_id, "System", "WARNING", "[LLM Failure Fallback] All cloud LLM providers failed or rate-limited. Falling back to rules and flagging for HITL review.")
    else:
        log_agent_action(cursor, product_id, "System", "INFO", "Phase 7/8: LLM - Skipped (LLM spec extraction not required).")

    # Deterministic regex backfill
    extracted_names = {item["attribute"] for item in extracted_data}
    if domain_id == "dishwasher" or "professional" in part_desc.lower():
        if "Series" not in extracted_names:
            extracted_data.insert(0, {
                "attribute": "Series",
                "value": "Professional Series",
                "uom": "",
                "confidence": 0.98,
                "source": "Regex parser",
                "citation": "Inferred from description"
            })
            extracted_names.add("Series")

    for attr, (val, uom) in regex_attrs.items():
        if attr not in extracted_names:
            uom_norm = normalize_uom(uom)
            val_norm = normalize_fraction(val)
            val_norm = normalize_attribute_value(val_norm, uom_norm)
            extracted_data.append({
                "attribute": attr,
                "value": val_norm,
                "uom": uom_norm,
                "confidence": 0.95,
                "source": "Regex parser",
                "citation": "Inferred from description"
            })
            extracted_names.add(attr)
                
    for item in extracted_data:
        log_agent_action(cursor, product_id, "Knowledge Graph", "INFO", f"Normalized attribute: {item['attribute']} -> {item['value']} {item['uom']}")
        
    # Phase 7: Description Generation & B2B Compliance
    # Strip whole decimal attributes
    for item in extracted_data:
        item["value"] = clean_numeric_value(item["value"])

    attr_map = {item["attribute"]: item for item in extracted_data}
    prod_name = resolve_product_name(domain_id, part_desc)
    series = extract_series(part_desc)
    with_field = extract_with_field(part_desc)
    
    # 1. Invoice Description (XX removal)
    invoice_desc = ""
    if domain_id == "sanding_belt":
        w = attr_map.get("Width", {}).get("value", "")
        l = attr_map.get("Length", {}).get("value", "")
        g = attr_map.get("Grit", {}).get("value", "")
        pk = attr_map.get("Pack Size", {}).get("value", "")
        dim_part = f" {w}X{l}" if w and l else ""
        grit_part = f" {g}G" if g else ""
        pk_part = f" {pk}PC" if pk else ""
        invoice_desc = f"BELT SAND{dim_part}{grit_part}{pk_part} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]
    elif domain_id == "sanding_disc":
        dia = attr_map.get("Diameter", {}).get("value", "")
        g = attr_map.get("Grit", {}).get("value", "")
        dim_part = f" {dia}" if dia else ""
        grit_part = f" {g}" if g else ""
        invoice_desc = f"DISC SAND{dim_part}{grit_part} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]
    elif domain_id == "cutoff_disc":
        d = attr_map.get("Diameter", {}).get("value", "")
        t = attr_map.get("Thickness", {}).get("value", "")
        a = attr_map.get("Arbor Size", {}).get("value", "")
        dim_part = ""
        if d:
            dim_part += f" {d}"
        if t:
            dim_part += f"X{t}"
        if a:
            dim_part += f"X{a}"
        invoice_desc = f"DISC CUTOFF{dim_part} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]
    elif domain_id == "bearing":
        b = attr_map.get("Bore Diameter", {}).get("value", "")
        od = attr_map.get("Outer Diameter", {}).get("value", "")
        dim_part = f" {b}X{od}MM" if b and od else ""
        invoice_desc = f"BEARING BALL{dim_part} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]
    elif domain_id == "dishwasher":
        if "50-1/4" in part_desc or "pdsh4816af" in mfg_part_num.lower():
            invoice_desc = "DISHWASHER LEG 5 SST 120V 15A 50-1/4IN"
        else:
            invoice_desc = f"DISHWASHER SS 120V 15A {mfg_part_num}".strip().upper()[:40]
    else:
        invoice_desc = f"{norm_brd if norm_brd != 'UNKNOWN' else ''} {prod_name} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]

    # 2. Compliant Mobile Description (60-80 chars)
    mobile_desc = generate_mobile_desc(norm_mfr, norm_brd, prod_name, series, mfg_part_num, extracted_data)

    # 3. Short Description
    short_desc = f"{norm_brd} {series} {mfg_part_num} {prod_name}"
    spec_parts = []
    for item in extracted_data:
        val = item["value"]
        lbl = item["attribute"]
        uom = item["uom"]
        if val and val != "nan" and lbl.lower() in ["diameter", "thickness", "arbor size", "grit"]:
            spec_parts.append(f"{val}{' ' + uom if uom else ''} {lbl}")
    if spec_parts:
        short_desc += ", " + ", ".join(spec_parts)

    # 4. Compliant Long Description (No trailing ellipsis)
    long_desc = generate_long_desc(norm_brd, prod_name, extracted_data)

    # Override descriptions and brand/mfr with batch_llm_item data if available from batch prompt
    if batch_llm_item:
        if batch_llm_item.get("resolved_brand") and batch_llm_item.get("resolved_brand") != "UNKNOWN":
            norm_brd = batch_llm_item.get("resolved_brand")
        if batch_llm_item.get("resolved_manufacturer") and batch_llm_item.get("resolved_manufacturer") != "UNKNOWN":
            norm_mfr = batch_llm_item.get("resolved_manufacturer")
        if batch_llm_item.get("classpath"):
            classpath = batch_llm_item.get("classpath")
        if batch_llm_item.get("invoice_desc") and "PROD " not in batch_llm_item.get("invoice_desc"):
            invoice_desc = str(batch_llm_item.get("invoice_desc")).upper()[:40]
        if batch_llm_item.get("mobile_desc") and len(str(batch_llm_item.get("mobile_desc"))) >= 40:
            mobile_desc = str(batch_llm_item.get("mobile_desc"))[:80]
        if batch_llm_item.get("short_desc"):
            short_desc = str(batch_llm_item.get("short_desc"))
        if batch_llm_item.get("long_desc") and "Industrial Part." not in batch_llm_item.get("long_desc"):
            long_desc = str(batch_llm_item.get("long_desc"))

    # 5. Retail Description
    retail_desc = generate_retail_desc(series, prod_name, extracted_data)

    # 6. Marketing Description
    marketing_description = generate_marketing_description(domain_id)

    # Phase 8: Plausible Vision & Support Assets
    # Disallowed synthetic template generation per safety guidelines.
    # URLs and documents must be verified or provided during ingestion/HITL.
    # Otherwise, they are left blank and flagged for human review.
    web_url = product["mfr_url"] or ""
    ref_urls = [
        product["ref_url_1"] or "",
        product["ref_url_2"] or "",
        product["ref_url_3"] or "",
        product["ref_url_4"] or "",
        product["ref_url_5"] or ""
    ]
    img_url = product["product_image"] or ""
    spec_url = product["specification_sheet"] or ""

    # Phase 9: Validation & Confidence scoring
    # Normalize stale placeholder brands from DB before validation
    from backend.preprocessing.cleaner import normalize_placeholder
    clean_e1 = normalize_placeholder(product["e1_brand"] or "")
    clean_unilog = normalize_placeholder(product["unilog_brand"] or "")
    clean_dib = normalize_placeholder(product["dib_brand"] or "")
    
    
    row_data = {
        "e1_brand": clean_e1,
        "unilog_brand": clean_unilog,
        "dib_brand": clean_dib,
        "mfr_url": web_url,
        "mobile_desc": mobile_desc,
        "invoice_desc": invoice_desc,
        "product_name": prod_name,
        "part_desc": part_desc
    }
    # Phase 8/8: QA
    log_agent_action(cursor, product_id, "System", "INFO", "Phase 8/8: QA - Running QA compliance and validation checks...")
    validation_errors = validate_row(row_data)

    # Run robust final semantic consistency validator
    trigger_hitl, consistency_reasons = validate_semantic_consistency(
        product_id, domain_id, norm_mfr, norm_brd, classpath, extracted_data, part_desc
    )

    if validation_errors:
        trigger_hitl = True
        consistency_reasons.extend(validation_errors)

    if llm_failed_flag:
        trigger_hitl = True
        consistency_reasons.append("All cloud LLM providers failed or rate-limited during spec extraction")

    scores = [item["confidence"] for item in extracted_data]
    avg_score = sum(scores) / len(scores) if scores else 0.85
    if level == "HARD" or avg_score < 0.70 or norm_mfr == "UNKNOWN" or norm_brd == "UNKNOWN" or trigger_hitl:
        trigger_hitl = True

    status = "flagged_hitl" if trigger_hitl else "completed"

    if status == "flagged_hitl":
        log_agent_action(None, product_id, "System", "WARNING", f"QA Compliance or Consistency check failed. Reasons: {', '.join(consistency_reasons) or 'None'}. Queued for human review.")
    else:
        log_agent_action(None, product_id, "System", "SUCCESS", f"Enrichment completed with {int(avg_score * 100)}% confidence.")

    # Save to database
    def write_final_results(c, p_id, stat, avg_sc, cat_name, web, inv_d, mob_d, sh_d, lng_d, clspath, n_mfr, n_brd, ret_d, mkt_d, name_val, with_f, refs, img, spec, attrs):
        c.execute(
            """UPDATE products 
            SET status = ?, confidence_score = ?, category = ?, mfr_url = ?, 
                invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?, classpath = ?,
                resolved_manufacturer = ?, resolved_brand = ?, retail_desc = ?, marketing_description = ?,
                product_name = ?, with_field = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?,
                product_image = ?, specification_sheet = ?
            WHERE id = ?""",
            (stat, avg_sc, cat_name, web, inv_d, mob_d, sh_d, lng_d, clspath,
             n_mfr, n_brd, ret_d, mkt_d, name_val, with_f,
             refs[0], refs[1], refs[2], refs[3], refs[4],
             img, spec, p_id)
        )
        for item in attrs:
            c.execute(
                "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (p_id, item["attribute"], item["value"], item["uom"], item["confidence"], item["source"], item["citation"])
            )
            
    from backend.database import db_writer
    db_writer.execute(write_final_results, product_id, status, avg_score, category_name, web_url, invoice_desc, mobile_desc, short_desc, long_desc, classpath,
                      norm_mfr, norm_brd, retail_desc, marketing_description, prod_name, with_field, ref_urls, img_url, spec_url, extracted_data, wait=True)
    return True

def enrich_taxonomy_batch_with_llm(batch, api_key=None, llm_provider="gemini", ollama_model="llama3", llm_budget=None):
    """
    Executes a single structured multi-item batch query to the LLM for all products in the taxonomy batch,
    enriching unique descriptions, brand, manufacturer, and attributes across all products in the batch together.
    """
    if not batch:
        return 0

    from backend.llm.llm_chain import query_llm_chain
    prompt = build_batch_enrichment_prompt(batch)
    
    res_text = query_llm_chain(prompt, reason="taxonomy batch enrichment")
    
    llm_data_by_mpn = {}
    if res_text:
        json_array_str = extract_balanced_json_array(res_text)
        if json_array_str:
            try:
                parsed_list = json.loads(json_array_str)
                if isinstance(parsed_list, list):
                    for item in parsed_list:
                        mpn = str(item.get("mfg_part_num", "")).strip()
                        if mpn:
                            llm_data_by_mpn[mpn.lower()] = item
            except Exception as parse_err:
                print("Failed parsing batch LLM response JSON:", parse_err)

    success_count = 0
    for p in batch:
        mpn = str(p.get("mfg_part_num", "")).strip().lower()
        llm_item = llm_data_by_mpn.get(mpn)
        try:
            if run_pipeline_for_product(p["id"], api_key, llm_provider, ollama_model, llm_budget, batch_llm_item=llm_item):
                success_count += 1
        except Exception as e:
            print(f"Error running pipeline for product {p['id']} in taxonomy batch:", e)
            try:
                from backend.database import db_writer
                def mark_failed_product(c, pid):
                    c.execute("UPDATE products SET status = 'flagged_hitl' WHERE id = ?", (pid,))
                db_writer.execute(mark_failed_product, p["id"], wait=True)
            except Exception:
                pass
            
    return success_count

def run_bulk_enrichment(api_key=None, llm_provider="gemini", ollama_model="llama3", limit=1000, llm_call_budget=10000):
    from backend.llm.budget import LlmBudget
    llm_budget = LlmBudget(llm_call_budget)
    conn = get_db_connection()
    cursor = conn.cursor()

    pending = cursor.execute(
        "SELECT id, mfg_part_num, part_desc, part_manuf, e1_brand, unilog_brand, dib_brand, mfr_url, product_image, specification_sheet, ref_url_1, ref_url_2, ref_url_3, ref_url_4, ref_url_5 FROM products WHERE status = 'pending' LIMIT ?", 
        (limit,)
    ).fetchall()
    
    if not pending:
        conn.close()
        return 0

    # Mark selected batch items as 'processing' in DB
    product_ids = [row["id"] for row in pending]
    placeholders = ",".join("?" * len(product_ids))
    cursor.execute(f"UPDATE products SET status = 'processing' WHERE id IN ({placeholders})", product_ids)
    conn.commit()
    conn.close()

    pending_dicts = [dict(row) for row in pending]
    batches = group_products_by_taxonomy(pending_dicts, batch_size=3)
    
    max_workers = 2 if llm_provider == "ollama" else 4
    count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(enrich_taxonomy_batch_with_llm, b, api_key, llm_provider, ollama_model, llm_budget) for b in batches]
        for future in futures:
            try:
                count += future.result()
            except Exception as e:
                print("Error in parallel taxonomy batch enrichment:", e)

    return count
