import urllib.request
import ssl

url = "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF"
print("Testing URL:", url)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5.0, context=ctx) as response:
        print("Status:", response.getcode())
        print("Final URL:", response.geturl())
except Exception as e:
    print("Error:", e)
