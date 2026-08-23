import glob
import os

patterns = [
    "c:\\Users\\Sneha\\*\\*.docx",
    "c:\\Users\\Sneha\\*\\*.xlsx",
    "c:\\Users\\Sneha\\*\\*\\*.docx",
    "c:\\Users\\Sneha\\*\\*\\*.xlsx",
    "c:\\Users\\Sneha\\*\\*\\*\\*.docx",
    "c:\\Users\\Sneha\\*\\*\\*\\*.xlsx",
    "c:\\Users\\Sneha\\projects\\*\\*.docx",
    "c:\\Users\\Sneha\\projects\\*\\*.xlsx",
    "c:\\Users\\Sneha\\projects\\*\\*\\*.docx",
    "c:\\Users\\Sneha\\projects\\*\\*\\*.xlsx",
    "c:\\Users\\Sneha\\Downloads\\*.docx",
    "c:\\Users\\Sneha\\Downloads\\*.xlsx",
    "c:\\Users\\Sneha\\Downloads\\*\\*.docx",
    "c:\\Users\\Sneha\\Downloads\\*\\*.xlsx",
    "c:\\Users\\Sneha\\Desktop\\*.docx",
    "c:\\Users\\Sneha\\Desktop\\*.xlsx"
]

found = set()
for p in patterns:
    for f in glob.glob(p):
        found.add(f)

print("Found files:")
for f in sorted(found):
    print("-", f)
