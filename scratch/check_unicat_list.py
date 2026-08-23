import os

search_dir = "c:\\Users\\Sneha\\projects\\unihack_real_beginners"
found = []

for root, dirs, files in os.walk(search_dir):
    for f in files:
        if "unicat" in f.lower() or "brand" in f.lower() or "manuf" in f.lower() or f.endswith(".xlsx"):
            path = os.path.join(root, f)
            found.append((f, path, os.path.getsize(path)))

print(f"Found {len(found)} matching files in project:")
for f, path, sz in found:
    print(f"- {f} ({sz} bytes) -> {path}")
