import sys
import re

def format_enriched_descriptions(resolved_brand, resolved_manufacturer, mpn, part_desc, short_desc, long_desc, attributes):
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
        lng = f"{lng.rstrip('.')} Additional Information: {add_info_str}."

    return sh, lng

# Test case from user screenshot: DeWalt DW7029
sh, lng = format_enriched_descriptions(
    resolved_brand="DeWalt",
    resolved_manufacturer="DeWalt Industrial Tool Co.",
    mpn="DW7029",
    part_desc="Miter Saw Stand Support",
    short_desc="Miter Saw Stand Support",
    long_desc="DeWalt Miter Saw Stand Support for stable and accurate cuts",
    attributes=[
        {"label": "Type", "value": "Miter Saw Stand"},
        {"label": "Compatibility", "value": "DeWalt Miter Saws"},
        {"label": "Material", "value": "Steel"}
    ]
)

print("ENRICHED SHORT DESC:")
print(sh)
print("\nENRICHED LONG DESC:")
print(lng)
