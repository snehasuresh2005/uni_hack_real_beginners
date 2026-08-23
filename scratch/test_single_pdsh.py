import sys
import os

sys.path.insert(0, r"c:\Users\Sneha\projects\unihack_real_beginners")

from backend.matching.mfr_url_resolver import resolve_product_urls

print("=== TESTING GROUND TRUTH PDSH4816AF ===", flush=True)
res = resolve_product_urls("Frigidaire", "FRIGIDAIRE", "PDSH4816AF", "PDSH4816AF Dishwasher SS")
print("MFR URL:", res["mfr_url"], flush=True)
print("Ref URLs:", res["ref_urls"], flush=True)
