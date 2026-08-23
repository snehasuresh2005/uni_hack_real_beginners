import os

roots = ["c:\\Users\\Sneha\\projects", "c:\\Users\\Sneha\\Downloads", "c:\\Users\\Sneha\\Desktop"]

for root in roots:
    if os.path.exists(root):
        for dirpath, dirnames, filenames in os.walk(root):
            if ".git" in dirpath or "AppData" in dirpath:
                continue
            for f in filenames:
                if f.endswith(".docx") or f.endswith(".xlsx") or "guidelines" in f.lower() or "unicat" in f.lower() or "lov" in f.lower():
                    full_path = os.path.join(dirpath, f)
                    print(f"{f} -> {full_path}")
