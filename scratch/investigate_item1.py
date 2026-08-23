import pandas as pd

expected_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Expected Output - Delivery Format.csv"
input_csv = r"c:\Users\Sneha\projects\unihack_real_beginners\Unihack_ Sample Dataset - Input.csv"

df_exp = pd.read_csv(expected_csv)
print("Expected Output CSV columns:", list(df_exp.columns))
print("Sample rows from Expected Output CSV:")
for idx, row in df_exp.head(10).iterrows():
    print(f"Row {idx+1}: UNILOG_ID={repr(row.get('UNILOG_ID'))}, PART_NUMBER={repr(row.get('PART_NUMBER'))}, MFG_PART_NUMBER={repr(row.get('MFG_PART_NUMBER'))}, BRAND={repr(row.get('UNILOG_BRAND_NAME'))}")

print("\nValue counts / null counts of PART_NUMBER in Expected Output CSV:")
print("Total rows:", len(df_exp))
print("Null count of PART_NUMBER:", df_exp['PART_NUMBER'].isnull().sum())
print("Unique PART_NUMBER count:", df_exp['PART_NUMBER'].nunique())
print("Sample non-null PART_NUMBER values:", df_exp['PART_NUMBER'].dropna().head(10).tolist())

df_in = pd.read_csv(input_csv)
print("\nInput CSV columns:", list(df_in.columns))
print("Sample Mfg_Part_Num from Input CSV:", df_in['Mfg_Part_Num'].head(10).tolist())
