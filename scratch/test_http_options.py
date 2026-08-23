import urllib.request
import ssl
import json

urls_to_test = [
    "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF",
    "https://learnwhirlpool.com/smartsearchresults?searchtext=WDTS7024RZ",
    "https://www.milwaukeetool.com/Products/48-22-8424",
    "https://www.3m.com/product/7100075678"
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

for u in urls_to_test:
    req = urllib.request.Request(u, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=5.0, context=ctx) as resp:
            print(f"SUCCESS {resp.getcode()}: {u} -> Final: {resp.geturl()}")
    except Exception as e:
        print(f"FAILED: {u} -> {e}")
