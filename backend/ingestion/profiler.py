import pandas as pd
import numpy as np
import io

def profile_dataset(file_path_or_bytes, filename="uploaded_file.csv"):
    try:
        if isinstance(file_path_or_bytes, str):
            if file_path_or_bytes.endswith('.xlsx') or file_path_or_bytes.endswith('.xls'):
                df = pd.read_excel(file_path_or_bytes)
            else:
                df = pd.read_csv(file_path_or_bytes)
        else:
            # Bytes
            try:
                df = pd.read_csv(file_path_or_bytes)
            except Exception:
                if hasattr(file_path_or_bytes, 'seek'):
                    file_path_or_bytes.seek(0)
                df = pd.read_excel(file_path_or_bytes)
                
        rows, cols = df.shape
        total_cells = rows * cols
        missing_count = df.isna().sum().sum()
        missing_pct = round((missing_count / total_cells) * 100, 2) if total_cells > 0 else 0.0
        
        # Check duplicate rows
        duplicates = df.duplicated().sum()
        
        # Unique products based on MPN or similar field if exists
        mpn_col = None
        for col in df.columns:
            if "mpn" in col.lower() or "part" in col.lower() or "sku" in col.lower() or "number" in col.lower():
                mpn_col = col
                break
                
        unique_products = df[mpn_col].nunique() if mpn_col else rows
        
        # Missing values breakdown by interesting columns
        missing_manuf = 0
        missing_brand = 0
        missing_desc = 0
        
        for col in df.columns:
            col_l = col.lower()
            if "manuf" in col_l or "mfr" in col_l:
                missing_manuf = int(df[col].isna().sum())
            if "brand" in col_l:
                missing_brand = int(df[col].isna().sum())
            if "desc" in col_l:
                missing_desc = int(df[col].isna().sum())
                
        # Detect fields and potential product identifiers
        detected_fields = list(df.columns)
        potential_identifiers = [col for col in df.columns if any(x in col.lower() for x in ["mpn", "part_num", "sku", "id", "part_desc"])]
        
        return {
            "filename": filename,
            "rows": rows,
            "columns": cols,
            "missing_pct": missing_pct,
            "duplicates": int(duplicates),
            "unique_products": int(unique_products),
            "detected_fields": detected_fields,
            "potential_identifiers": potential_identifiers,
            "missing_manuf": missing_manuf,
            "missing_brand": missing_brand,
            "missing_desc": missing_desc
        }
    except Exception as e:
        return {"error": str(e)}
