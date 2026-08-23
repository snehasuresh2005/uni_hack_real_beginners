import os

root_dir = "c:\\Users\\Sneha\\projects\\unihack_real_beginners"

for dirpath, dirnames, filenames in os.walk(root_dir):
    if ".git" in dirpath or "node_modules" in dirpath or "__pycache__" in dirpath:
        continue
    for f in filenames:
        if f.endswith(".docx") or f.endswith(".xlsx") or f.endswith(".csv") or "guidelines" in f.lower() or "lov" in f.lower() or "ground" in f.lower():
            full_path = os.path.join(dirpath, f)
            print(f"{f} -> {full_path} ({os.path.getsize(full_path)} bytes)")
