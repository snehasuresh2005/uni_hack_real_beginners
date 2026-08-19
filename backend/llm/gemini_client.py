import os
import urllib.request
import json

def query_freellmapi(prompt, api_key):
    """Query local freellmapi server using OpenAI-compatible completion format."""
    url = "http://localhost:3001/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "auto",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 2048
    }
    
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers=headers, 
            method="POST"
        )
        # Use a timeout of 60 seconds
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return None
    except Exception as e:
        print(f"freellmapi request failed: {e}")
        return None

def query_gemini(prompt, api_key=None):
    """Run a capped Gemini request; credentials stay in the environment/settings."""
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.environ.get("GEMINI_MODEL", "gemini-1.5-flash"))
        response = model.generate_content(
            prompt,
            generation_config={"max_output_tokens": 1024, "temperature": 0.1},
        )
        return response.text.strip() if response and response.text else None
    except Exception as exc:
        print(f"Gemini query failed: {exc}")
        return None
