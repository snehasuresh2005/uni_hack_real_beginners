import os

root_dir = "c:\\Users\\Sneha\\projects\\unihack_real_beginners"

keywords = ["UNILOG", "GUIDELINE", "UNICAT", "LOV", "PART_NUMBER", "INVOICE_DESC", "MOBILE_DESC", "SHORT_DESC", "LONG_DESC"]

for dirpath, dirnames, filenames in os.walk(root_dir):
    if ".git" in dirpath or "node_modules" in dirpath or "__pycache__" in dirpath:
        continue
    for f in filenames:
        filepath = os.path.join(dirpath, f)
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                found_kw = [kw for kw in keywords if kw.lower() in content.lower()]
                if found_kw:
                    print(f"{f} ({os.path.relpath(filepath, root_dir)}) -> matched: {found_kw}")
        except Exception as e:
            pass
