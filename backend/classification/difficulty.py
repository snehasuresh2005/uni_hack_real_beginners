from backend.preprocessing.cleaner import normalize_placeholder, normalize_manufacturer, normalize_brand

def classify_difficulty(mfg_part_num, part_desc, part_manuf, brand_name):
    score = 0.0
    reasons = []
    
    # 1. Missing manufacturer
    if not normalize_placeholder(part_manuf):
        score += 0.3
        reasons.append("Manufacturer is missing")
        
    # 2. Missing brand
    if not normalize_placeholder(brand_name):
        score += 0.25
        reasons.append("Brand is missing")
        
    # 3. Missing MPN
    if not normalize_placeholder(mfg_part_num) or mfg_part_num.lower() == "nan":
        score += 0.3
        reasons.append("Mfg Part Number (MPN) is missing")
        
    # 4. Short description
    desc = str(part_desc or "").strip()
    if len(desc) < 25:
        score += 0.2
        reasons.append("Product description is extremely short")
        
    # 5. Placeholders present in the text
    if any(p in desc.lower() for p in ["unbranded", "display only", "placeholder"]):
        score += 0.15
        reasons.append("Placeholder text detected in description")
        
    # 6. Ambiguous category
    matching_keywords = []
    desc_lower = desc.lower()
    from backend.pipeline import DOMAINS
    for dom, info in DOMAINS.items():
        if "keywords" in info:
            for keyword in info["keywords"]:
                if keyword in desc_lower:
                    matching_keywords.append(dom)
                    break
    if len(set(matching_keywords)) > 1:
        score += 0.15
        reasons.append("Ambiguous category matches found in description")

    # Routing level
    if score >= 0.5:
        level = "HARD"
    elif score >= 0.2:
        level = "MEDIUM"
    else:
        level = "EASY"
        
    return {
        "level": level,
        "score": round(score, 2),
        "reasons": reasons
    }
