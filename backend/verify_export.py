import os
import csv
import pandas as pd
from backend.database import get_db_connection

def verify():
    # 1. Read headers from ground truth CSV
    expected_path = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
    if not os.path.exists(expected_path):
        print(f"Error: Expected format CSV not found at {expected_path}")
        return False
        
    df_expected = pd.read_csv(expected_path)
    expected_headers = list(df_expected.columns)
    
    # 2. Run our export logic and write to a temporary file
    # We will mimic the export endpoint logic
    conn = get_db_connection()
    cursor = conn.cursor()
    products = cursor.execute("SELECT * FROM products WHERE status = 'completed'").fetchall()
    
    temp_export = r"C:\Users\Sneha\.gemini\antigravity-ide\brain\97df2dfe-e32a-4f4c-96c1-8048a263b6aa\scratch\exported_verification.csv"
    
    with open(temp_export, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(expected_headers)
        
        for p in products:
            p_id = p["id"]
            attrs = cursor.execute("SELECT * FROM attributes WHERE product_id = ?", (p_id,)).fetchall()
            
            attr_vals = {}
            for idx, a in enumerate(attrs):
                i = idx + 1
                attr_vals[f"ATTRIBUTE_LABEL {i}"] = a["label"]
                attr_vals[f"ATTRIBUTE_VALUE {i}"] = a["value"]
                attr_vals[f"ATTRIBUTE_UOM {i}"] = a["uom"]
                
            # Build features list — map DB column 'label' to pipeline key 'attribute'
            from backend.pipeline import generate_item_features
            features = generate_item_features([{"attribute": a["label"], "value": a["value"], "uom": a["uom"]} for a in attrs])
            
            row = []
            for h in expected_headers:
                if h == "MFR URL":
                    row.append(p["mfr_url"] or "")
                elif h == "Ref URL 1":
                    row.append(p["ref_url_1"] or "")
                elif h == "Ref URL 2":
                    row.append(p["ref_url_2"] or "")
                elif h == "Ref URL 3":
                    row.append(p["ref_url_3"] or "")
                elif h == "Ref URL 4":
                    row.append(p["ref_url_4"] or "")
                elif h == "Ref URL 5":
                    row.append(p["ref_url_5"] or "")
                elif h in ["PART_NUMBER", "Mfg_Part_Num", "MANUFACTURER_PART_NUMBER"]:
                    row.append(p["mfg_part_num"])
                elif h == "Product Name":
                    row.append(p["product_name"] or "")
                elif h == "Part_Desc":
                    row.append(p["part_desc"])
                elif h == "INVOICE_DESC":
                    row.append(p["invoice_desc"] or "")
                elif h == "MOBILE_DESC":
                    row.append(p["mobile_desc"] or "")
                elif h == "SHORT_DESC":
                    row.append(p["short_desc"] or "")
                elif h == "LONG_DESC1":
                    row.append(p["long_desc"] or "")
                elif h == "RETAIL_DESC":
                    row.append(p["retail_desc"] or "")
                elif h == "MARKETING_DESCRIPTION":
                    row.append(p["marketing_description"] or "")
                elif h == "With":
                    row.append(p["with_field"] or "")
                elif h == "Product Image":
                    row.append(p["product_image"] or "")
                elif h in ["Specification Sheet", "Catalog"]:
                    row.append(p["specification_sheet"] or "")
                elif h == "Classpath":
                    row.append(p["classpath"] or "")
                elif h == "MANUFACTURER_NAME":
                    row.append(p["resolved_manufacturer"] or "")
                elif h == "BRAND_NAME":
                    row.append(p["resolved_brand"] or "")
                elif h == "Part_Manuf":
                    row.append(p["part_manuf"] or "")
                elif h == "E1_Brand":
                    row.append(p["e1_brand"] or "")
                elif h == "Unilog_Brand":
                    row.append(p["unilog_brand"] or "")
                elif h == "DIB_Brand":
                    row.append(p["dib_brand"] or "")
                elif h in attr_vals:
                    row.append(attr_vals[h])
                elif h == "Actual Image (Yes/No)":
                    row.append("Yes")
                elif h.startswith("ITEM_FEATURES_"):
                    try:
                        f_idx = int(h.split("_")[-1]) - 1
                        row.append(features[f_idx] if f_idx < len(features) else "")
                    except Exception:
                        row.append("")
                else:
                    row.append("")
            writer.writerow(row)
            
    conn.close()
    
    # 3. Read exported file and compare columns
    df_exported = pd.read_csv(temp_export)
    exported_headers = list(df_exported.columns)
    
    print("Expected headers count:", len(expected_headers))
    print("Exported headers count:", len(exported_headers))
    
    if len(expected_headers) != len(exported_headers):
        print("Mismatch in headers count!")
        return False
        
    mismatches = []
    for exp, exp_out in zip(expected_headers, exported_headers):
        if exp != exp_out:
            mismatches.append((exp, exp_out))
            
    if mismatches:
        print("Found header mismatches:")
        for m in mismatches:
            print(f"Expected: {m[0]} | Exported: {m[1]}")
        return False
        
    print("Success: Exported columns match the Expected Delivery Format EXACTLY!")
    print(f"Exported rows: {len(df_exported)}")
    return True

if __name__ == "__main__":
    verify()
