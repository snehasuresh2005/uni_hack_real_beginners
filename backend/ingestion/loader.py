import os
import pandas as pd

# Global caches
TAXONOMY_MAP = {}
MANUFACTURER_LIST = []
BRAND_LIST = []
UOM_ABBREVIATIONS = {}
DECIMAL_FRACTIONS = {}

def find_file(filename):
    """
    Search for a file in common locations.
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "..", "..", filename),
        os.path.join(os.path.dirname(__file__), "..", filename),
        os.path.join(os.path.dirname(__file__), filename),
        os.path.join("c:\\Users\\Sneha\\projects\\unihack_real_beginners", filename),
        os.path.join("c:\\Users\\Sneha\\Downloads", filename),
        os.path.join("c:\\Users\\Sneha\\OneDrive\\Desktop", filename),
        os.path.join("c:\\Users\\Sneha\\OneDrive\\Documents", filename)
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def load_all_references():
    global MANUFACTURER_LIST, BRAND_LIST, UOM_ABBREVIATIONS, DECIMAL_FRACTIONS
    
    # 1. Load UOM standard abbreviations
    uom_path = find_file("Unilog_Master_UOM_Standards_Abbreviations_and_Terms.xlsx")
    if uom_path:
        try:
            df = pd.read_excel(uom_path)
            for _, row in df.iterrows():
                term = str(row.iloc[0]).strip().lower() if len(row) > 0 else ""
                abbrev = str(row.iloc[1]).strip() if len(row) > 1 else ""
                if term and abbrev and term != "nan" and abbrev != "nan":
                    UOM_ABBREVIATIONS[term] = abbrev
        except Exception as e:
            print("Failed to load UOM standards:", e)
            
    # 2. Load Decimal Fraction mapping
    frac_path = find_file("Decimal_Fraction.xlsx")
    if frac_path:
        try:
            df = pd.read_excel(frac_path)
            for _, row in df.iterrows():
                dec = row.iloc[0] if len(row) > 0 else None
                frac = row.iloc[1] if len(row) > 1 else None
                if dec is not None and frac is not None and str(dec) != "nan" and str(frac) != "nan":
                    DECIMAL_FRACTIONS[float(dec)] = str(frac)
        except Exception as e:
            print("Failed to load Decimal Fraction mappings:", e)
            
    # 3. Load Manufacturer and Brand list
    mfr_path = find_file("UniCat_Manufacturer_and_Brand_List.xlsx")
    if mfr_path:
        try:
            df = pd.read_excel(mfr_path)
            MANUFACTURER_LIST = list(set(str(m).strip() for m in df.iloc[:, 0].dropna() if str(m).strip() != "nan"))
            if df.shape[1] > 1:
                BRAND_LIST = list(set(str(b).strip() for b in df.iloc[:, 1].dropna() if str(b).strip() != "nan"))
        except Exception as e:
            print("Failed to load Manufacturer and Brand list:", e)

    # Initialize standard B2B fallbacks if files are missing
    if not UOM_ABBREVIATIONS:
        UOM_ABBREVIATIONS = {
            "volt": "V", "volts": "V", "voltage": "V",
            "amp": "A", "amps": "A", "amperage": "A",
            "inch": "in", "inches": "in", "in.": "in",
            "millimeter": "mm", "millimeters": "mm",
            "decibel": "dBA", "decibels": "dBA", "rpm": "RPM"
        }

    if not DECIMAL_FRACTIONS:
        DECIMAL_FRACTIONS = {
            0.5: "1/2", 0.25: "1/4", 0.75: "3/4",
            0.125: "1/8", 0.375: "3/8", 0.625: "5/8",
            0.875: "7/8", 0.0625: "1/16", 0.045: ".045"
        }

    if not MANUFACTURER_LIST:
        MANUFACTURER_LIST = ["Rheem Manufacturing", "Whirlpool Corporation", "Appliance Dealers Cooperative (APPDE)", "3M", "SKF", "Frigidaire"]

    if not BRAND_LIST:
        BRAND_LIST = ["FRIGIDAIRE", "Whirlpool", "Rheem", "3M", "SKF", "Eco Series", "Professional Series"]

# Automatically trigger load on import
load_all_references()
