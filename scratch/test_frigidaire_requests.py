import urllib.request
import ssl

url = "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "keep-alive",
})

try:
    with urllib.request.urlopen(req, timeout=8.0, context=ctx) as resp:
        print("FRIGIDAIRE STATUS:", resp.getcode())
        print("FRIGIDAIRE FINAL URL:", resp.geturl())
except Exception as e:
        print("FRIGIDAIRE ERROR:", e)
