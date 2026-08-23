import requests

r = requests.get("http://127.0.0.1:8000/api/products/22041")
if r.status_code == 200:
    data = r.json()
    prod = data.get("product", {})
    print("MFR URL   :", prod.get("mfr_url"))
    print("Ref URL 1 :", prod.get("ref_url_1"))
    print("Ref URL 2 :", prod.get("ref_url_2"))
else:
    print("Error:", r.status_code)
