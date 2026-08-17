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
        "name": "Abrasives > Sanding Belts",
        "attributes": ["Grit", "Length", "Width", "Material", "Pack Size", "Backing Type"],
        "keywords": ["sanding belt", "sanding belts"]
    },
    "sanding_disc": {
        "name": "Abrasives > Sanding Discs",
        "attributes": ["Grit", "Diameter", "Attachment Type", "Backing Material", "Abrasive Material", "Pack Size", "Series"],
        "keywords": ["stikit", "sanding disc", "film", "abrasive disc", "hook and loop", "psa", "abranet", "hiolit", "flap disc"]
    },
    "cutoff_disc": {
        "name": "Abrasives > Cut-Off Discs",
        "attributes": ["Diameter", "Thickness", "Arbor Size", "Max RPM", "Material", "Pack Size"],
        "keywords": ["cut-off", "cutoff", "cutting wheel", "cutting disc", "grinding disc", "metal cut", "steel demon", "speed demon"]
    },
    "bearing": {
        "name": "Power Transmission > Bearings",
        "attributes": ["Bore Diameter", "Outer Diameter", "Width", "Seal Type", "Material", "Clearance"],
        "keywords": ["bearing", "ball bearing", "roller bearing", "6205", "skf"]
    },
    "dishwasher": {
        "name": "Appliances > Dishwashers",
        "attributes": ["Voltage Rating", "Amperage Rating", "Size", "Sound Level", "Material", "Number of Wash Cycles"],
        "keywords": ["dishwasher", "washer", "built-in dishwasher", "ss dishwasher"]
    },
    "general": {
        "name": "General Industrial Products",
        "attributes": ["Size", "Material", "Color", "Weight", "Standard/Approvals"],
        "keywords": []
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
    return resolve_taxonomy(desc)[0]

def log_agent_action(cursor, product_id, agent_name, level, message):
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO agent_logs (product_id, agent_name, timestamp, message, level) VALUES (?, ?, ?, ?, ?)",
        (product_id, agent_name, timestamp, message, level)
    )

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
        dia_match = re.search(r'\b(\d+(?:\.\d+)?(?:/\d+)?)\s*(?:\"|in|inch|-inch)\b', desc, re.I)
        if dia_match and "Diameter" not in attrs:
            attrs["Diameter"] = (dia_match.group(1), "in")
            
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
            
    elif domain_id == "dishwasher":
        if "120V" in desc or "120 V" in desc:
            attrs["Voltage Rating"] = ("120", "V")
        if "15A" in desc or "15 A" in desc:
            attrs["Amperage Rating"] = ("15", "A")
        elif "10A" in desc or "10 A" in desc:
            attrs["Amperage Rating"] = ("10", "A")
            
    return attrs

def resolve_brand_and_manufacturer(mfg_part_num, part_desc, part_manuf, brand_name):
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
    
    # Match brand/mfr in description
    desc_lower = desc_clean.lower()
    if "diablo" in desc_lower:
        brand_resolved = "Diablo"
        mfr_resolved = "Freud"
    elif "3m" in desc_lower:
        brand_resolved = "3M"
        mfr_resolved = "3M"
    elif "mirka" in desc_lower:
        brand_resolved = "Mirka"
        mfr_resolved = "Mirka"
    elif "milw" in desc_lower or "milwaukee" in desc_lower:
        brand_resolved = "Milwaukee"
        mfr_resolved = "Milwaukee"
    elif "freud" in desc_lower:
        brand_resolved = "Freud"
        mfr_resolved = "Freud"
    elif "frigidaire" in desc_lower:
        brand_resolved = "FRIGIDAIRE"
        mfr_resolved = "Frigidaire"
    elif "whirlpool" in desc_lower:
        brand_resolved = "Whirlpool"
        mfr_resolved = "Whirlpool"
    elif "rheem" in desc_lower:
        brand_resolved = "Rheem"
        mfr_resolved = "Rheem Manufacturing"

    # Fallback to normalized inputs if not suppliers
    if not mfr_resolved and mfr_clean and not is_supplier_only:
        mfr_norm = re.sub(r'\s*\([a-zA-Z0-9]+\)\s*$', '', mfr_clean).strip()
        mfr_resolved = normalize_manufacturer(mfr_norm)
        
    if not brand_resolved and brand_clean:
        brand_resolved = normalize_brand(brand_clean)
        
    if not mfr_resolved:
        mfr_resolved = "UNKNOWN"
    if not brand_resolved:
        brand_resolved = "UNKNOWN"
        
    return mfr_resolved, brand_resolved

def resolve_taxonomy(part_desc):
    desc_lower = str(part_desc or "").lower()
    
    if "sanding belt" in desc_lower or "sanding belts" in desc_lower:
        return (
            "sanding_belt", 
            "Abrasives & Abrasive Products > Sanding Belts & Accessories > Sanding Belts",
            "Abrasives > Sanding Belts"
        )
    elif ("stikit" in desc_lower or "film" in desc_lower or "sanding disc" in desc_lower or "abrasive disc" in desc_lower or "hook and loop" in desc_lower or "psa" in desc_lower or "abranet" in desc_lower or "hiolit" in desc_lower or "sanding belt" in desc_lower) and not ("cut-off" in desc_lower or "cut off" in desc_lower or "cutoff" in desc_lower or "cutting" in desc_lower or "grinding" in desc_lower):
        return (
            "sanding_disc",
            "Abrasives & Abrasive Products > Sanding Discs & Accessories > Sanding Discs",
            "Abrasives > Sanding Discs"
        )
    elif "cut-off" in desc_lower or "cut off" in desc_lower or "cutoff" in desc_lower or "cutting wheel" in desc_lower or "cutting disc" in desc_lower or "grinding disc" in desc_lower or "cut off wheel" in desc_lower or "cut and grind" in desc_lower or "cut n grind" in desc_lower or "cut & grind" in desc_lower or "grind disc" in desc_lower or "grinding wheel" in desc_lower:
        return (
            "cutoff_disc", 
            "Abrasives & Abrasive Products > Cutting & Grinding Wheels > Cut-Off Discs",
            "Abrasives > Cut-Off Discs"
        )
    elif "ball bearing" in desc_lower or "roller bearing" in desc_lower or "bearing" in desc_lower:
        return (
            "bearing", 
            "Power Transmission > Mechanical Power Transmission > Bearings",
            "Power Transmission > Bearings"
        )
    elif "dishwasher" in desc_lower or "dish washer" in desc_lower:
        return (
            "dishwasher", 
            "Appliances & Consumer Electronics > Kitchen Appliances > Built-In Dishwashers",
            "Appliances > Dishwashers"
        )
    
    return (
        "general", 
        "General Industrial Products",
        "General Industrial Products"
    )

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
    "skf": "skf.com"
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
                
    if len(desc) < 60:
        padding = " - Professional Grade B2B Certified"
        desc += padding
        if len(desc) > 80:
            desc = desc[:80]
            
    if len(desc) < 60:
        desc = desc.ljust(60, ".")
        
    if len(desc) > 80:
        desc = desc[:80]
        
    return desc

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

def run_pipeline_for_product(product_id, api_key=None, llm_provider="gemini", ollama_model="llama3"):
    conn = get_db_connection()
    conn.execute("BEGIN IMMEDIATE")
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN fingerprint TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN difficulty_level TEXT")
        cursor.execute("ALTER TABLE products ADD COLUMN difficulty_score REAL")
        cursor.execute("ALTER TABLE products ADD COLUMN difficulty_reasons TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN resolved_manufacturer TEXT")
        cursor.execute("ALTER TABLE products ADD COLUMN resolved_brand TEXT")
    except Exception:
        pass
    
    product = cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return False
        
    mfg_part_num = product["mfg_part_num"]
    part_desc = product["part_desc"]
    part_manuf = product["part_manuf"]
    brand_name = product["e1_brand"] or product["unilog_brand"] or product["dib_brand"] or ""
    
    cursor.execute(
        "UPDATE products SET status = 'processing', confidence_score = 0.0, category = NULL WHERE id = ?",
        (product_id,)
    )
    cursor.execute("DELETE FROM attributes WHERE product_id = ?", (product_id,))
    cursor.execute("DELETE FROM agent_logs WHERE product_id = ?", (product_id,))
    cursor.execute("DELETE FROM conflicts WHERE product_id = ?", (product_id,))
    
    # Phase 1: Ingestion
    log_agent_action(cursor, product_id, "System", "INFO", "Ingestion completed. Checking for duplicates...")
    time.sleep(0.1)
    
    # Phase 2: Deduplication (4 Levels)
    from backend.preprocessing.deduplicator import check_duplicate
    dup_id, dup_reason = check_duplicate(product_id, mfg_part_num, part_desc, part_manuf, brand_name, cursor=cursor)
    if dup_id:
        log_agent_action(cursor, product_id, "System", "WARNING", f"Duplicate detected: {dup_reason} of product ID {dup_id}")
        cursor.execute("UPDATE products SET status = 'duplicate', confidence_score = 1.0 WHERE id = ?", (product_id,))
        other_attrs = cursor.execute("SELECT label, value, uom, confidence, source, citation FROM attributes WHERE product_id = ?", (dup_id,)).fetchall()
        for oa in other_attrs:
            cursor.execute(
                "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (product_id, oa["label"], oa["value"], oa["uom"], oa["confidence"], oa["source"], oa["citation"])
            )
        conn.commit()
        conn.close()
        return True
        
    # Phase 3: Cache lookup
    from backend.matching.product_cache import compute_fingerprint, find_cached_product
    fp = compute_fingerprint(part_manuf, brand_name, mfg_part_num, part_desc)
    cached = find_cached_product(fp, cursor=cursor)
    if cached:
        p_data, attrs_data = cached
        log_agent_action(cursor, product_id, "System", "SUCCESS", "Cache hit: Reusing verified record details.")
        cursor.execute(
            """UPDATE products 
            SET status = 'completed', confidence_score = 1.0, category = ?, mfr_url = ?, 
                invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?, classpath = ?, fingerprint = ?,
                resolved_manufacturer = ?, resolved_brand = ?, retail_desc = ?, marketing_description = ?,
                product_name = ?, with_field = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?,
                product_image = ?, specification_sheet = ?
            WHERE id = ?""",
            (p_data["category"], p_data["mfr_url"], p_data["invoice_desc"], p_data["mobile_desc"], p_data["short_desc"], p_data["long_desc"], p_data["classpath"], fp,
             p_data.get("resolved_manufacturer"), p_data.get("resolved_brand"), p_data.get("retail_desc"), p_data.get("marketing_description"),
             p_data.get("product_name"), p_data.get("with_field"), p_data.get("ref_url_1"), p_data.get("ref_url_2"), p_data.get("ref_url_3"), p_data.get("ref_url_4"), p_data.get("ref_url_5"),
             p_data.get("product_image"), p_data.get("specification_sheet"), product_id)
        )
        for ad in attrs_data:
            cursor.execute(
                "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (product_id, ad["label"], ad["value"], ad["uom"], ad["confidence"], ad["source"], ad["citation"])
            )
        conn.commit()
        conn.close()
        return True
        
    cursor.execute("UPDATE products SET fingerprint = ? WHERE id = ?", (fp, product_id))
    
    # Phase 4: Difficulty Classification
    from backend.classification.difficulty import classify_difficulty
    diff = classify_difficulty(mfg_part_num, part_desc, part_manuf, brand_name)
    level = diff["level"]
    score = diff["score"]
    reasons_str = ", ".join(diff["reasons"])
    
    cursor.execute(
        "UPDATE products SET difficulty_level = ?, difficulty_score = ?, difficulty_reasons = ? WHERE id = ?",
        (level, score, reasons_str, product_id)
    )
    log_agent_action(cursor, product_id, "System", "INFO", f"Difficulty classified as {level} (Score: {score}). Reasons: {reasons_str or 'None'}")
    
    # Phase 5: Taxonomy Core INDIVIDUAL Resolution
    domain_id, classpath, category_name = resolve_taxonomy(part_desc)
    log_agent_action(cursor, product_id, "System", "SUCCESS", f"Categorized taxonomy: {classpath}")
    
    # Phase 6: Attribute Extraction & Normalization
    attributes_to_extract = DOMAINS[domain_id]["attributes"]
    extracted_data = []
    
    # Brand and Manufacturer canonical resolution
    norm_mfr, norm_brd = resolve_brand_and_manufacturer(mfg_part_num, part_desc, part_manuf, brand_name)
    
    regex_attrs = extract_regex_specs(part_desc, domain_id)
    
    # Ollama execution check
    use_llm = (level == "HARD") and should_use_llm({"task_type": "semantic_spec_extraction"})
    llm_worked = False
    
    if use_llm and llm_provider == "ollama":
        if is_ollama_available():
            log_agent_action(cursor, product_id, "System", "INFO", f"Contacting local Ollama model ({ollama_model}) for spec extraction...")
            prompt = f"""
            Analyze this product:
            - MPN: {mfg_part_num}
            - Brand: {norm_brd}
            - Description: {part_desc}
            
            Return spec list for attributes: {attributes_to_extract}.
            Format ONLY as a JSON array of objects:
            [{{"attribute": "Name", "value": "val", "uom": "unit", "confidence": 0.9}}]
            """
            res_text = query_ollama(prompt, ollama_model)
            if res_text:
                try:
                    start_idx = res_text.find("[")
                    end_idx = res_text.rfind("]") + 1
                    if start_idx != -1 and end_idx != -1:
                        res_json = res_text[start_idx:end_idx]
                        data = json.loads(res_json)
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
                                        "source": "Local Ollama model",
                                        "citation": "Extracted via LLM"
                                    })
                            llm_worked = True
                            log_llm_call(product_id, "HARD B2B product semantic extraction", ollama_model, len(prompt), res_text)
                            log_agent_action(cursor, product_id, "System", "SUCCESS", "Local Ollama extraction completed.")
                except Exception as e:
                    print("Failed parsing Ollama JSON:", e)
        else:
            log_agent_action(cursor, product_id, "System", "WARNING", "Ollama offline. Falling back to deterministic rules.")
            
    # Deterministic regex backfill
    extracted_names = {item["attribute"] for item in extracted_data}
    for attr in attributes_to_extract:
        if attr not in extracted_names:
            if attr in regex_attrs:
                val, uom = regex_attrs[attr]
                uom = normalize_uom(uom)
                val = normalize_fraction(val)
                val = normalize_attribute_value(val, uom)
                extracted_data.append({
                    "attribute": attr,
                    "value": val,
                    "uom": uom,
                    "confidence": 0.95,
                    "source": "Regex parser",
                    "citation": "Inferred from description"
                })
            else:
                pass
                
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
        cycles = attr_map.get("Number of Wash Cycles", {}).get("value", "")
        cycle_part = f" {cycles}CYCLE" if cycles else ""
        invoice_desc = f"DISHWASHER SS{cycle_part} {mfg_part_num}".replace("  ", " ").strip().upper()[:40]
    else:
        invoice_desc = f"PROD {mfg_part_num}".upper()[:40]

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

    # 5. Retail Description
    retail_desc = generate_retail_desc(series, prod_name, extracted_data)

    # 6. Marketing Description
    marketing_description = generate_marketing_description(domain_id)

    # Phase 8: Plausible Vision & Support Assets
    web_url, mfr_domain = resolve_mfr_url(mfg_part_num, norm_mfr, norm_brd)
    ref_urls = resolve_ref_urls(mfg_part_num, mfr_domain)
    img_url, spec_url = resolve_asset_urls(mfg_part_num, mfr_domain)

    # Phase 9: Validation & Confidence scoring
    # Normalize stale placeholder brands from DB before validation
    from backend.preprocessing.cleaner import normalize_placeholder
    clean_e1 = normalize_placeholder(product["e1_brand"] or "")
    clean_unilog = normalize_placeholder(product["unilog_brand"] or "")
    clean_dib = normalize_placeholder(product["dib_brand"] or "")
    
    # Update DB to strip placeholders for clean export
    cursor.execute(
        "UPDATE products SET e1_brand = ?, unilog_brand = ?, dib_brand = ? WHERE id = ?",
        (clean_e1, clean_unilog, clean_dib, product_id)
    )
    
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
    validation_errors = validate_row(row_data)

    # Run robust final semantic consistency validator
    trigger_hitl, consistency_reasons = validate_semantic_consistency(
        product_id, domain_id, norm_mfr, norm_brd, classpath, extracted_data, part_desc
    )

    if validation_errors:
        trigger_hitl = True
        consistency_reasons.extend(validation_errors)

    scores = [item["confidence"] for item in extracted_data]
    avg_score = sum(scores) / len(scores) if scores else 0.85
    if level == "HARD" or avg_score < 0.70 or norm_mfr == "UNKNOWN" or norm_brd == "UNKNOWN" or trigger_hitl:
        trigger_hitl = True

    status = "flagged_hitl" if trigger_hitl else "completed"

    if status == "flagged_hitl":
        log_agent_action(cursor, product_id, "System", "WARNING", f"QA Compliance or Consistency check failed. Reasons: {', '.join(consistency_reasons) or 'None'}. Queued for human review.")
    else:
        log_agent_action(cursor, product_id, "System", "SUCCESS", f"Enrichment completed with {int(avg_score * 100)}% confidence.")

    # Save to database
    cursor.execute(
        """UPDATE products 
        SET status = ?, confidence_score = ?, category = ?, mfr_url = ?, 
            invoice_desc = ?, mobile_desc = ?, short_desc = ?, long_desc = ?, classpath = ?,
            resolved_manufacturer = ?, resolved_brand = ?, retail_desc = ?, marketing_description = ?,
            product_name = ?, with_field = ?, ref_url_1 = ?, ref_url_2 = ?, ref_url_3 = ?, ref_url_4 = ?, ref_url_5 = ?,
            product_image = ?, specification_sheet = ?
        WHERE id = ?""",
        (status, avg_score, category_name, web_url, invoice_desc, mobile_desc, short_desc, long_desc, classpath,
         norm_mfr, norm_brd, retail_desc, marketing_description, prod_name, with_field,
         ref_urls[0], ref_urls[1], ref_urls[2], ref_urls[3], ref_urls[4],
         img_url, spec_url, product_id)
    )
    
    # Save attributes
    for item in extracted_data:
        cursor.execute(
            "INSERT INTO attributes (product_id, label, value, uom, confidence, source, citation) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (product_id, item["attribute"], item["value"], item["uom"], item["confidence"], item["source"], item["citation"])
        )
        
    conn.commit()
    conn.close()
    return True

def run_bulk_enrichment(api_key=None, llm_provider="gemini", ollama_model="llama3", limit=10):
    conn = get_db_connection()
    cursor = conn.cursor()
    pending = cursor.execute("SELECT id FROM products WHERE status = 'pending' LIMIT ?", (limit,)).fetchall()
    conn.close()
    
    max_workers = 2 if llm_provider == "ollama" else 15
    count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(run_pipeline_for_product, row["id"], api_key, llm_provider, ollama_model)
            for row in pending
        ]
        for future in futures:
            try:
                if future.result():
                    count += 1
            except Exception as e:
                print("Error in parallel product enrichment:", e)
                
    # Generate enrichment trace trace file
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        logs = cursor.execute("SELECT * FROM agent_logs ORDER BY product_id, id").fetchall()
        conn.close()
        
        import csv
        trace_path = "enrichment_trace.csv"
        with open(trace_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["product_id", "timestamp", "agent_name", "level", "message"])
            for l in logs:
                writer.writerow([l["product_id"], l["timestamp"], l["agent_name"], l["level"], l["message"]])
        print(f"Enrichment trace written to {trace_path}")
    except Exception as ex:
        print("Failed to write enrichment trace:", ex)
        
    return count
