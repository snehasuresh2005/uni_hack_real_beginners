import sqlite3
import sys

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.pipeline import ensure_mobile_desc_bounds, generate_mobile_desc

test_cases = [
    {
        "mfr": "Oliver Machinery Company",
        "brd": "Oliver",
        "desc": '13" Planer, 2HP, 115V, 1Ph',
        "mpn": "4430.001",
        "attrs": [{"label": "Motor", "value": "2", "uom": "HP"}, {"label": "Voltage", "value": "115", "uom": "V"}]
    },
    {
        "mfr": "3M Company",
        "brd": "3M",
        "desc": '3M 775L Stikit Film P180 - Cubitron II',
        "mpn": "7100075690",
        "attrs": [{"label": "Grit", "value": "P180", "uom": ""}]
    },
    {
        "mfr": "Rheem Manufacturing",
        "brd": "FRIGIDAIRE",
        "desc": 'PDSH4816AF Dishwasher SS',
        "mpn": "PDSH4816AF",
        "attrs": [{"label": "Voltage Rating", "value": "120", "uom": "V"}, {"label": "Amperage Rating", "value": "15", "uom": "A"}]
    }
]

print("==================================================")
print("VERIFYING MOBILE_DESC 60-80 CHARACTER BOUNDS ENFORCEMENT")
print("==================================================")

for idx, tc in enumerate(test_cases, 1):
    raw_mob = tc["desc"]
    bounded = ensure_mobile_desc_bounds(raw_mob, tc["mfr"], tc["brd"], "Planer", tc["mpn"], tc["attrs"])
    print(f"\nTest #{idx}: {tc['brd']} / {tc['mfr']} (MPN: {tc['mpn']})")
    print(f"  Raw Mobile Desc     : '{raw_mob}' ({len(raw_mob)} chars)")
    print(f"  Enforced Mobile Desc: '{bounded}' ({len(bounded)} chars)")
    print(f"  Length in 60..80 range?: {60 <= len(bounded) <= 80}")
