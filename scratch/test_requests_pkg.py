import requests

urls = [
    "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF",
    "https://www.whirlpool.com/content/dam/global/documents/202412/owners-manual-w11323304-revj.pdf",
    "https://www.milwaukeetool.com/Products/48-22-8424"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

for u in urls:
    try:
        r = requests.get(u, headers=headers, timeout=5, verify=False)
        print(f"REQUESTS SUCCESS {r.status_code}: {u} -> Final: {r.url}")
    except Exception as e:
        print(f"REQUESTS FAILED: {u} -> {e}")
