import requests
import urllib3
urllib3.disable_warnings()

url = "https://www.frigidaire.com/en/p/owner-center/product-support/PDSH4816AF"
s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "max-age=0",
    "Upgrade-Insecure-Requests": "1"
})

try:
    r = s.get(url, timeout=3.0, verify=False)
    print("STATUS:", r.status_code)
    print("URL:", r.url)
    print("HTML length:", len(r.text))
except Exception as e:
    print("ERR:", e)
