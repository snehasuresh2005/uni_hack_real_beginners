import os
import json
import time
import re
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from backend.llm.ollama_client import is_ollama_available, query_ollama, log_llm_call

# ──────────────────────────────────────────────
# GLOBAL PROVIDER COOLDOWN & QUOTA TRACKER
# ──────────────────────────────────────────────
PROVIDER_STATUS = {
    "gemini": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""},
    "groq": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""},
    "openrouter": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""},
    "ollama": {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}
}

LAST_GROQ_CALL_TIME = 0.0
GROQ_MIN_SPACING_SEC = 1.5

def mark_provider_daily_exhausted(provider, reason, duration_hours=24):
    """Marks a provider as daily quota exhausted for duration_hours (default 24h)."""
    reset_timestamp = time.time() + (duration_hours * 3600)
    reset_iso = datetime.fromtimestamp(reset_timestamp).isoformat()
    PROVIDER_STATUS[provider] = {
        "is_disabled": True,
        "cooldown_until": reset_timestamp,
        "disabled_reason": f"{reason} (Cooldown active until {reset_iso})"
    }
    print(f"[LLM Quota Tracker] Provider '{provider}' marked DAILY EXHAUSTED until {reset_iso}. Reason: {reason}")

def mark_provider_short_cooldown(provider, reason, duration_seconds=45):
    """Marks a provider as short-term rate limited for duration_seconds (default 45s)."""
    reset_timestamp = time.time() + duration_seconds
    reset_iso = datetime.fromtimestamp(reset_timestamp).strftime("%H:%M:%S")
    PROVIDER_STATUS[provider] = {
        "is_disabled": True,
        "cooldown_until": reset_timestamp,
        "disabled_reason": f"{reason} (Rate limited until {reset_iso})"
    }
    print(f"[LLM Quota Tracker] Provider '{provider}' marked RATE LIMITED until {reset_iso} ({duration_seconds:.1f}s cooldown). Reason: {reason}")

def reset_provider_cooldown(provider=None):
    """Resets provider cooldown state (used on settings update or manual key refresh)."""
    if provider and provider in PROVIDER_STATUS:
        PROVIDER_STATUS[provider] = {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}
    else:
        for p in PROVIDER_STATUS:
            PROVIDER_STATUS[p] = {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}

GROQ_MAX_SAFE_PROMPT_CHARS = 3500

def query_openai_compatible_endpoint(url, payload, api_key, extra_headers=None, timeout=5):
    """
    Generic query helper for OpenAI-compatible REST endpoints (Groq, OpenRouter, etc.).
    Returns (status_code, response_text_or_error_msg).
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BProductIntelligence/1.0"
    }
    if extra_headers:
        headers.update(extra_headers)

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            choices = res_data.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                content = msg.get("content")
                if not content and msg.get("reasoning"):
                    content = msg.get("reasoning")
                if content:
                    return (200, str(content).strip())
            return (200, None)
    except urllib.error.HTTPError as http_err:
        try:
            err_body = http_err.read().decode("utf-8")
        except Exception:
            err_body = str(http_err)
        return (http_err.code, f"HTTP Error {http_err.code}: {err_body}")
    except Exception as e:
        return (500, f"Request error: {str(e)}")

def query_gemini_provider(prompt, api_key=None, model_name=None, timeout=8):
    """Query Google Gemini API directly via REST endpoint with retry and model fallback."""
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return (401, "No Gemini API key provided")
        
    requested_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    if requested_model.startswith("models/"):
        requested_model = requested_model[7:]
    if requested_model in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]:
        requested_model = "gemini-1.5-flash"

    candidate_models = [requested_model]
    for alt in ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    last_status = 500
    last_err = "Unknown Gemini error"

    for m_name in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 4096
            }
        }

        for attempt in range(4):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    candidates = res_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return (200, parts[0].get("text", "").strip())
                    return (200, None)
            except urllib.error.HTTPError as http_err:
                last_status = http_err.code
                try:
                    err_body = http_err.read().decode("utf-8")
                except Exception:
                    err_body = str(http_err)
                last_err = f"HTTP Error {http_err.code}: {err_body}"
                if http_err.code in [429, 401, 403]:
                    return (http_err.code, last_err)
                elif http_err.code == 503:
                    time.sleep(1.0)
                    continue
                elif http_err.code == 404:
                    break
            except Exception as exc:
                last_status = 500
                last_err = f"Gemini REST error: {str(exc)}"
                time.sleep(1)
                continue

    return (last_status, last_err)

def query_groq_provider(prompt, api_key=None, model_name=None):
    """Query Groq API endpoint with request spacing and model fallbacks."""
    global LAST_GROQ_CALL_TIME
    if not api_key:
        api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        return (401, "No Groq API key provided")

    # Request spacing throttling: Enforce minimum 1.5s delay between Groq calls
    now = time.time()
    elapsed = now - LAST_GROQ_CALL_TIME
    if elapsed < GROQ_MIN_SPACING_SEC:
        time.sleep(GROQ_MIN_SPACING_SEC - elapsed)
    LAST_GROQ_CALL_TIME = time.time()

    # Prompt Size Guard Check
    if len(prompt) > GROQ_MAX_SAFE_PROMPT_CHARS:
        print(f"[LLM Prompt Guard Warning] Prompt size ({len(prompt)} chars) exceeds Groq safe threshold ({GROQ_MAX_SAFE_PROMPT_CHARS} chars). Truncating payload...")
        prompt = prompt[:GROQ_MAX_SAFE_PROMPT_CHARS] + "\n[Truncated for Groq payload limits]"

    requested_model = model_name or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    candidate_models = [requested_model]
    for alt in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "llama3-70b-8192", "llama3-8b-8192"]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    url = "https://api.groq.com/openai/v1/chat/completions"
    last_status = 500
    last_err = "Unknown Groq error"

    for m_name in candidate_models:
        payload = {
            "model": m_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 512
        }
        status_code, result = query_openai_compatible_endpoint(url, payload, api_key)
        if status_code == 200 and result:
            return (200, result)
        last_status = status_code
        last_err = result

    return (last_status, last_err)

def query_openrouter_provider(prompt, api_key=None, model_name=None):
    """Query OpenRouter API endpoint with automatic free model fallbacks."""
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return (401, "No OpenRouter API key provided")

    requested_model = model_name or os.environ.get("OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
    candidate_models = [requested_model]
    for alt in [
        "google/gemma-2-9b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen-2.5-72b-instruct:free",
        "deepseek/deepseek-r1:free"
    ]:
        if alt not in candidate_models:
            candidate_models.append(alt)

    url = "https://openrouter.ai/api/v1/chat/completions"
    extra_headers = {
        "HTTP-Referer": "https://github.com/unihack-real-beginners",
        "X-Title": "B2B Product Intelligence"
    }

    last_status = 500
    last_err = "Unknown OpenRouter error"

    for m_name in candidate_models:
        payload = {
            "model": m_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 512,
            "reasoning": {"enabled": False}
        }
        status_code, result = query_openai_compatible_endpoint(url, payload, api_key, extra_headers=extra_headers)
        if status_code == 200 and result:
            return (200, result)
        last_status = status_code
        last_err = result

    return (last_status, last_err)

def query_ollama_provider(prompt, model_name=None):
    """Query local Ollama instance if available."""
    model_name = model_name or os.environ.get("OLLAMA_MODEL", "llama3")
    if not is_ollama_available():
        return (503, "Local Ollama server is offline")
    try:
        res = query_ollama(prompt, model_name)
        if res:
            return (200, res)
        return (500, "Ollama returned empty response")
    except Exception as e:
        return (500, f"Ollama error: {str(e)}")

def query_llm_chain(prompt, product_id=None, reason="semantic extraction", settings=None):
    """
    Executes the LLM failover chain: Gemini -> Groq -> OpenRouter -> (Ollama optional).
    Handles rate-limit (429), auth (401/403), and 404 errors, smoothly trying the next provider.
    Returns response_text or None.
    """
    if settings is None:
        try:
            from backend.app import load_settings
            settings = load_settings()
        except Exception:
            settings = {}

    provider_choice = (settings.get("llm_provider") or os.environ.get("LLM_PROVIDER") or "auto").lower()

    chain = []
    if provider_choice == "gemini":
        chain = ["gemini", "groq", "openrouter"]
    elif provider_choice == "groq":
        chain = ["groq", "openrouter", "gemini"]
    elif provider_choice == "openrouter":
        chain = ["openrouter", "gemini", "groq"]
    elif provider_choice == "ollama":
        chain = ["ollama", "gemini", "groq", "openrouter"]
    else: # "auto" or default
        chain = ["gemini", "groq", "openrouter"]

    if settings.get("enable_ollama_fallback", False) or os.environ.get("ENABLE_OLLAMA_FALLBACK", "false").lower() == "true":
        if "ollama" not in chain and is_ollama_available():
            chain.append("ollama")

    # If Ollama is not available in the current environment, filter it out from the failover chain
    if not is_ollama_available():
        chain = [p for p in chain if p != "ollama"]

    gemini_key = settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY", "")
    gemini_model = settings.get("gemini_model") or os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")
    if gemini_model in ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]:
        gemini_model = "gemini-1.5-flash"
    
    groq_model = settings.get("groq_model") or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    if groq_model in ["gemma2-9b-it", "groq/compound"]:
        groq_model = "llama-3.3-70b-versatile"
    
    openrouter_key = settings.get("openrouter_api_key") or os.environ.get("OPENROUTER_API_KEY", "")
    openrouter_model = settings.get("openrouter_model") or os.environ.get("OPENROUTER_MODEL", "google/gemma-2-9b-it:free")
    if "llama-3.1-8b-instruct" in openrouter_model or "gemma2-9b-it" in openrouter_model or "gemma-4" in openrouter_model:
        openrouter_model = "google/gemma-2-9b-it:free"
    
    ollama_model = settings.get("ollama_model") or os.environ.get("OLLAMA_MODEL", "llama3")

    prompt_len = len(prompt)
    approx_prompt_tokens = prompt_len // 4

    for provider in chain:
        if provider == "gemini":
            if not gemini_key:
                print("[LLM Failover] Skipping Gemini: No API key configured.")
                continue

            gem_status = PROVIDER_STATUS.get("gemini", {})
            if gem_status.get("is_disabled"):
                if time.time() < gem_status.get("cooldown_until", 0.0):
                    reset_time_iso = datetime.fromtimestamp(gem_status["cooldown_until"]).isoformat()
                    print(f"[LLM Chain] Skipping Gemini (Daily Quota Exhausted until {reset_time_iso}). Moving straight to Groq...")
                    continue
                else:
                    PROVIDER_STATUS["gemini"] = {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}

            print(f"[LLM Chain] Attempting Gemini ({gemini_model}) [Prompt: {prompt_len} chars / ~{approx_prompt_tokens} tokens]...")
            status_code, result = query_gemini_provider(prompt, gemini_key, gemini_model)
            
            if status_code == 200 and result:
                approx_out_tokens = len(result) // 4
                print(f"[LLM Chain] Gemini Succeeded! Response: {len(result)} chars (~{approx_out_tokens} tokens).")
                if product_id:
                    log_llm_call(product_id, reason, f"gemini:{gemini_model}", prompt_len, result)
                return result

            if status_code in [403, 429] and ("PerDay" in str(result) or "quotaId" in str(result) or "free_tier_requests" in str(result) or "RESOURCE_EXHAUSTED" in str(result) or "suspended" in str(result).lower() or "PERMISSION_DENIED" in str(result)):
                mark_provider_daily_exhausted("gemini", f"Google Gemini Key Suspended / Quota Exhausted (Status {status_code})")

            print(f"[LLM Failover] Gemini failed (Status {status_code}): {str(result)[:180]}... Moving to next provider...")

        elif provider == "groq":
            if not groq_key:
                print("[LLM Failover] Skipping Groq: No API key configured.")
                continue

            # Check Short Rate Limit Cooldown Tracker for Groq
            groq_status = PROVIDER_STATUS.get("groq", {})
            if groq_status.get("is_disabled"):
                if time.time() < groq_status.get("cooldown_until", 0.0):
                    reset_time_iso = datetime.fromtimestamp(groq_status["cooldown_until"]).strftime("%H:%M:%S")
                    print(f"[LLM Chain] Skipping Groq (Rate Limited until {reset_time_iso}). Moving straight to OpenRouter...")
                    continue
                else:
                    # Short cooldown expired, re-enable Groq
                    PROVIDER_STATUS["groq"] = {"is_disabled": False, "cooldown_until": 0.0, "disabled_reason": ""}

            print(f"[LLM Chain] Attempting Groq ({groq_model}) [Prompt: {prompt_len} chars / ~{approx_prompt_tokens} tokens]...")
            status_code, result = query_groq_provider(prompt, groq_key, groq_model)
            
            if status_code == 200 and result:
                approx_out_tokens = len(result) // 4
                print(f"[LLM Chain] Groq Succeeded! Response: {len(result)} chars (~{approx_out_tokens} tokens).")
                if product_id:
                    log_llm_call(product_id, reason, f"groq:{groq_model}", prompt_len, result)
                return result

            # Detect Groq Rate Limit (429) & Apply Short Cooldown
            if status_code in [429, 413]:
                # Try parsing retry delay from API error body
                retry_match = re.search(r"retry in (\d+(?:\.\d+)?)s", str(result), re.IGNORECASE)
                cooldown_secs = float(retry_match.group(1)) if retry_match else 45.0
                cooldown_secs = max(15.0, min(cooldown_secs, 120.0))
                mark_provider_short_cooldown("groq", f"Groq Rate Limit Reached (Status {status_code})", duration_seconds=cooldown_secs)

            print(f"[LLM Failover] Groq failed (Status {status_code}): {str(result)[:180]}... Moving to next provider...")

        elif provider == "openrouter":
            if not openrouter_key:
                print("[LLM Failover] Skipping OpenRouter: No API key configured.")
                continue

            print(f"[LLM Chain] Attempting OpenRouter ({openrouter_model}) [Prompt: {prompt_len} chars / ~{approx_prompt_tokens} tokens]...")
            status_code, result = query_openrouter_provider(prompt, openrouter_key, openrouter_model)
            
            if status_code == 200 and result:
                approx_out_tokens = len(result) // 4
                print(f"[LLM Chain] OpenRouter Succeeded! Response: {len(result)} chars (~{approx_out_tokens} tokens).")
                if product_id:
                    log_llm_call(product_id, reason, f"openrouter:{openrouter_model}", prompt_len, result)
                return result

            print(f"[LLM Failover] OpenRouter failed (Status {status_code}): {str(result)[:180]}... Moving to next provider...")

        elif provider == "ollama":
            print(f"[LLM Chain] Attempting Ollama ({ollama_model}) [Prompt: {prompt_len} chars / ~{approx_prompt_tokens} tokens]...")
            status_code, result = query_ollama_provider(prompt, ollama_model)
            if status_code == 200 and result:
                approx_out_tokens = len(result) // 4
                print(f"[LLM Chain] Ollama Succeeded! Response: {len(result)} chars (~{approx_out_tokens} tokens).")
                if product_id:
                    log_llm_call(product_id, reason, f"ollama:{ollama_model}", prompt_len, result)
                return result
            print(f"[LLM Failover] Ollama failed (Status {status_code}): {str(result)[:180]}.")

    print("[LLM Failover Error] All providers in the failover chain failed.")
    return None
