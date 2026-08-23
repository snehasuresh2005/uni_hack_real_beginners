import os
import shutil

project_dir = r"c:\Users\Sneha\projects\unihack_real_beginners"

cleared_count = 0
for root, dirs, files in os.walk(project_dir):
    for d in dirs:
        if d == "__pycache__":
            full_path = os.path.join(root, d)
            try:
                shutil.rmtree(full_path)
                cleared_count += 1
            except Exception as e:
                print(f"Failed to remove {full_path}: {e}")

print(f"Cleared {cleared_count} __pycache__ directories.")
