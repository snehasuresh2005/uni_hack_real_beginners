import os
import json
import urllib.request
from datetime import datetime
from backend.database import get_db_connection

def get_ollama_url():
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

def is_ollama_available():
    url = get_ollama_url()
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            return response.status == 200
    except Exception:
        return False

def detect_available_models():
    url = get_ollama_url()
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []

def log_llm_call(product_id, reason_for_llm_call, model, input_size, output, confidence=1.0):
    now = datetime.now().isoformat()
    def do_write(c):
        c.execute(
            """INSERT INTO llm_calls 
            (product_id, reason_for_llm_call, model, timestamp, input_size, output, confidence) 
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (product_id, reason_for_llm_call, model, now, input_size, str(output)[:1000], confidence)
        )
    try:
        from backend.database import db_writer
        db_writer.execute(do_write, wait=False)
    except Exception as e:
        print("Failed to log LLM call to DB:", e)

def should_use_llm(context):
    """
    Returns False for deterministic tasks, True only for genuine semantic ambiguity.
    """
    # Deterministic operations are handled by standard Python regex/lookups.
    task_type = context.get("task_type", "").lower()
    
    # 1. Rules/Lookups for deterministic conversions
    if task_type in ["uom_normalization", "fraction_conversion", "exact_lookup", "regex_attribute"]:
        return False
        
    # 2. Ambiguity resolution (Hard product category prediction or ambiguous brand name)
    if task_type in ["ambiguous_taxonomy", "ambiguous_manufacturer", "semantic_spec_extraction"]:
        return True
        
    return False

def query_ollama(prompt, model_name="llama3"):
    url = get_ollama_url()
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"num_predict": int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "256"))}
    }
    try:
        req = urllib.request.Request(
            f"{url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=60) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("response", "").strip()
    except Exception as e:
        print(f"Ollama query failed: {e}")
        return None
