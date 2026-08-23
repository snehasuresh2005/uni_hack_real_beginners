import os

search_names = ["unilog", "guideline", "unicat", "lov", "200"]

found = []
for root, dirs, files in os.walk("c:\\Users\\Sneha"):
    if "AppData" in root or ".git" in root or "node_modules" in root:
        continue
    for f in files:
        f_lower = f.lower()
        if any(k in f_lower for k in search_names):
            full_path = os.path.join(root, f)
            found.append((f, full_path, os.path.getsize(full_path)))

print(f"Found {len(found)} matching files:")
for f, path, sz in found:
    print(f"- {f} ({sz} bytes) -> {path}")
