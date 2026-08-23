import os

api_key = os.environ.get("OPENROUTER_API_KEY", "")
url = "https://openrouter.ai/api/v1/chat/completions"

prompt = """You are a B2B product intelligence assistant. Return ONLY a valid JSON array for the following item:
- MPN: 73019647
- Brand: Whirlpool
- Description: Finyline Wh 8' Str Rail Kit Rd

Output JSON array format:
[{"id": 1, "resolved_brand": "Whirlpool", "resolved_manufacturer": "Whirlpool", "classpath": "Industrial Hardware"}]
"""

candidate_models = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "openrouter/free"
]

for model in candidate_models:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 300,
        "reasoning": {"enabled": False}
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/unihack-real-beginners",
        "X-Title": "B2B Product Intelligence"
    }
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            msg = res_data.get("choices", [{}])[0].get("message", {})
            content = msg.get("content")
            print(f"=== MODEL: {model} ===")
            print("Content:", repr(content))
    except Exception as e:
        print(f"=== MODEL: {model} === FAILED: {e}")
