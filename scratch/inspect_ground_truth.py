import pandas as pd

df_exp = pd.read_csv(r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv")

for idx, row in df_exp.iterrows():
    print(f"================ Ground Truth Row #{idx+1} ================")
    print("Part_Desc:", row.get("Part_Desc"))
    print("Mfg_Part_Num:", row.get("Mfg_Part_Num"))
    print("PART_NUMBER:", row.get("PART_NUMBER"))
    print("MANUFACTURER_NAME:", row.get("MANUFACTURER_NAME"))
    print("BRAND_NAME:", row.get("BRAND_NAME"))
    print("Classpath:", row.get("Classpath"))
    print("INVOICE_DESC:", row.get("INVOICE_DESC"))
    print("MOBILE_DESC:", row.get("MOBILE_DESC"))
    print("SHORT_DESC:", row.get("SHORT_DESC"))
    print("LONG_DESC1:", row.get("LONG_DESC1"))
    print("Product Name:", row.get("Product Name"))
    print("With:", row.get("With"))
    print("Standard/Approvals:", row.get("Standard/Approvals"))
    print("Prop 65:", row.get("Prop 65"))
    print("Application:", row.get("Application"))
    print("Includes:", row.get("Includes"))
    print("---------------- Attributes ----------------")
    for i in range(1, 10):
        lbl = row.get(f"ATTRIBUTE_LABEL {i}")
        val = row.get(f"ATTRIBUTE_VALUE {i}")
        uom = row.get(f"ATTRIBUTE_UOM {i}")
        if pd.notna(lbl):
            print(f"  Attr {i}: {lbl} = {val} ({uom})")
